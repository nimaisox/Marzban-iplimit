"""
This module contains functions to get logs from the panel and nodes.
"""
import asyncio
import random
import ssl
import sys
import traceback

from asyncio import Task

from utils.parse_logs import INVALID_IPS, parse_logs
from utils.panel_api import get_nodes, get_token
from utils.types import NodeType, PanelType
from utils.logs import logger
from utils.read_config import ConfigManager

try:
    import websockets.client
    import websockets.exceptions
    from websockets.exceptions import ConnectionClosedError
except ImportError:
    logger.warning(
        "Module 'websockets' is not installed use: 'pip install websockets' to install it"
    )
    sys.exit()

from telegram_bot.send_message import send_logs

TASKS = []

task_node_mapping = {}
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

PROTOCOL_CACHE = {}

async def retrieve_token(panel_data: PanelType) -> str:
    """
    Retrieves the panel token.

    Args:
        panel_data (PanelType): The panel data containing credentials.

    Returns:
        str: The retrieved panel token.

    Raises:
        ValueError: If token retrieval fails.
    """
    try:
        get_panel_token = await get_token(panel_data)
        return get_panel_token.panel_token
    except ValueError as error:
        logger.error("Failed to retrieve token: %s", error)
        raise error


async def get_panel_logs(panel_data: PanelType) -> None:
    """
    Establishes a websocket connection to retrieve logs from a panel server.
    """
    interval = random.uniform(0.9, 1.7)
    try:
        get_panel_token = await get_token(panel_data)
        token = get_panel_token.panel_token
    except ValueError as error:
        logger.error("Failed to retrieve token: %s", error)
        raise error

    panel_domain = panel_data.panel_domain.replace("https://", "").replace("http://", "")

    if panel_data.panel_domain.startswith("https"):
        schemes = ["wss"]
    elif panel_data.panel_domain.startswith("http"):
        schemes = ["ws"]
    else:
        message = "Unsupported protocol in panel domain. Ensure it starts with http or https."
        logger.error(message)
        await send_logs(message)
        raise ValueError(message)

    ssl_ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ssl_ctx.check_hostname = True
    ssl_ctx.verify_mode = ssl.CERT_REQUIRED

    retry_delay = 1

    for scheme in schemes:
        url = (
            f"{scheme}://{panel_domain}/api/core/logs"
            f"?interval={interval}&token={token}"
        )
        current_ssl_ctx = ssl_ctx if scheme == "wss" else None

        while True:
            try:
                async with websockets.connect(url, ssl=current_ssl_ctx,
                                               ping_interval=60, ping_timeout=50) as ws:
                    log_message = f"Connected to panel logs via {scheme} protocol."
                    await send_logs(log_message)
                    logger.info(log_message)

                    config_manager = ConfigManager(config_file="config.json")

                    while True:
                        new_log = await ws.recv()
                        await parse_logs(str(new_log), config_manager)
            except ConnectionClosedError as error:
                logger.error("Connection closed unexpectedly for %s: %s", scheme, error)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)
                continue
            except Exception as error:  # pylint: disable=broad-except
                logger.error("Unexpected error with %s: %s\n%s", scheme, error,
                              traceback.format_exc())
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)
                continue

async def get_nodes_logs(panel_data: PanelType, node: NodeType) -> None:
    """
    Establish a WebSocket connection to a specific node and retrieve logs.
    """
    interval = random.uniform(0.9, 1.7)
    try:
        get_panel_token = await get_token(panel_data)
        token = get_panel_token.panel_token
    except ValueError as error:
        logger.error("Failed to retrieve token: %s", error)
        raise error

    panel_domain = panel_data.panel_domain.replace("https://", "").replace("http://", "")

    if panel_data.panel_domain.startswith("https"):
        schemes = ["wss"]
    elif panel_data.panel_domain.startswith("http"):
        schemes = ["ws"]
    else:
        message = "Unsupported protocol in panel domain. Ensure it starts with http or https."
        logger.error(message)
        await send_logs(message)
        raise ValueError(message)

    secure_ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    secure_ssl_context.check_hostname = True
    secure_ssl_context.verify_mode = ssl.CERT_REQUIRED

    retry_delay = 1

    for scheme in schemes:
        url = (
            f"{scheme}://{panel_domain}/api/node/{node.node_id}/logs"
            f"?interval={interval}&token={token}"
        )
        ssl_ctx = secure_ssl_context if scheme == "wss" else None

        while True:
            try:
                async with websockets.connect(url, ssl=ssl_ctx,
                                               ping_interval=60, ping_timeout=50) as ws:
                    log_message = f"Connected to node {node.node_id} logs via {scheme} protocol."
                    await send_logs(log_message)
                    logger.info(log_message)

                    config_manager = ConfigManager(config_file="config.json")

                    while True:
                        new_log = await ws.recv()
                        await parse_logs(str(new_log), config_manager)
            except ConnectionClosedError as error:
                logger.error(
                    "Connection closed for node [ID: %s, Name: %s] using %s: %s",
                    node.node_id,
                    node.node_name,
                    scheme,
                    error,
                )
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)
                continue
            except ssl.SSLError as error:
                logger.error(
                    "SSL error for node [ID: %s, Name: %s] using %s: %s",
                    node.node_id,
                    node.node_name,
                    scheme,
                    error,
                )
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)
                continue
            except Exception as error:  # pylint: disable=broad-except
                logger.error(
                    "Unexpected error for node [ID: %s, Name: %s] using %s: %s",
                    node.node_id,
                    node.node_name,
                    scheme,
                    error,
                )
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)
                continue

async def handle_cancel(panel_data: PanelType, tasks: list[Task]) -> None:
    """
    An asynchronous coroutine that cancels all tasks in the given list.

    Args:
        panel_data (PanelType): The credentials for the panel.
        tasks (list[Task]): The list of tasks to be cancelled.
    """
    deactivate_nodes = set()
    while True:
        nodes_list = await get_nodes(panel_data)
        for node in nodes_list:
            if node.status != "connected":
                deactivate_nodes.add(f"Task-{node.node_id}-{node.node_name}")

        for task in tasks:
            if task.get_name() in deactivate_nodes:
                log_message = f"Cancelling {task.get_name()}"
                await send_logs(log_message)
                logger.info(log_message)
                deactivate_nodes.remove(task.get_name())
                task.cancel()
                tasks.remove(task)
                if task in task_node_mapping:
                    task_node_mapping.pop(task)
        await asyncio.sleep(20)

async def handle_cancel_all(tasks: list[Task], panel_data: PanelType) -> None:
    """
    An asynchronous coroutine that cancels All tasks in the given list.

    Args:
        tasks (list[Task]): The list of tasks to be cancelled.
    """
    async with asyncio.TaskGroup() as tg:
        while True:
            await asyncio.sleep(8192)  # =~ 2 hours and 27 minutes
            for task in tasks:
                logger.warning(" %s...", task.get_name())
                task.cancel()
                tasks.remove(task)
            logger.info("Start Create Panel Task Test: ")
            await create_panel_task(panel_data, tg)
            await asyncio.sleep(5)
            nodes_list = await get_nodes(panel_data)
            if nodes_list and not isinstance(nodes_list, ValueError):
                logger.info("Start Create Nodes Task Test: ")
                for node in nodes_list:
                    if node.status == "connected":
                        await create_node_task(panel_data, tg, node)
                        await asyncio.sleep(3)

async def check_and_add_new_nodes(panel_data: PanelType, tg: asyncio.TaskGroup) -> None:
    """
    An asynchronous coroutine that checks for new nodes and creates tasks for them.

    Args:
        panel_data (PanelType): The credentials for the panel.
        tg (asyncio.TaskGroup): The TaskGroup to which the new task will be added.
    """
    while True:
        all_nodes = await get_nodes(panel_data)
        if all_nodes and not isinstance(all_nodes, ValueError):
            for node in all_nodes:
                if (
                    node not in task_node_mapping.values()
                    and node.status == "connected"
                ):
                    log_message = (
                        f"Add a new node. id: {node.node_id}"
                        + f" name: {node.node_name} ip: {node.node_ip}"
                    )
                    await send_logs(log_message)
                    logger.info(log_message)
                    await create_node_task(panel_data, tg, node)
        await asyncio.sleep(25)


TASKS_LOCK = asyncio.Lock()

async def safe_append_task(task):
    """
    Safely appends a task to the TASKS list with a lock to ensure thread-safe operations.

    Args:
        task (asyncio.Task): The task to be appended to the TASKS list.
    """
    async with TASKS_LOCK:
        TASKS.append(task)

async def safe_remove_task(task):
    """
    Safely removes a task from the TASKS list with a lock to ensure thread-safe operations.
    If the task is not found in the list, no action is taken.

    Args:
        task (asyncio.Task): The task to be removed from the TASKS list.
    """
    async with TASKS_LOCK:
        if task in TASKS:
            TASKS.remove(task)


async def create_panel_task(panel_data: PanelType, tg: asyncio.TaskGroup) -> None:
    """
    An asynchronous coroutine that creates a new task for a node and adds it to the TASKS list.

    Args:
        panel_data (PanelType): The credentials for the panel.
        tg (asyncio.TaskGroup): The TaskGroup to which the new task will be added.
    """
    try:
        async with TASKS_LOCK:
            if any(task.get_name() == "Task-panel" for task in TASKS):
                logger.info("Task-panel already exists. Skipping creation.")
                return

        logger.info("Creating Task-panel...")
        new_task = tg.create_task(get_panel_logs(panel_data), name="Task-panel")
        await safe_append_task(new_task)

        new_task.add_done_callback(lambda t: asyncio.create_task(safe_remove_task(new_task)))
        logger.info("Task-panel successfully created and added to TASKS.")
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Failed to create Task-panel: %s", e)


async def create_node_task(
    panel_data: PanelType, tg: asyncio.TaskGroup, node: NodeType
) -> None:
    """
    An asynchronous coroutine that creates a new task for a node and adds it to the TASKS list.

    Args:
        panel_data (PanelType): The credentials for the panel.
        tg (asyncio.TaskGroup): The TaskGroup to which the new task will be added.
        node (NodeType): The node for which the new task will be created.
    """
    INVALID_IPS.add(node.node_ip)
    task = tg.create_task(
        get_nodes_logs(panel_data, node), name=f"Task-{node.node_id}-{node.node_name}"
    )
    TASKS.append(task)
    task_node_mapping[task] = node
