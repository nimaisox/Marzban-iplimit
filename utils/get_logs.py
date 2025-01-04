"""
This module contains functions to get logs from the panel and nodes.
"""

# 1. ماژول‌های استاندارد پایتون
import asyncio
import random
import ssl
import sys

# 2. ماژول‌های داخلی پایتون (مانند asyncio import Task)
from asyncio import Task

# 3. ماژول‌های داخلی پروژه
from utils.parse_logs import INVALID_IPS, parse_logs
from utils.panel_api import get_nodes, get_token
from utils.types import NodeType, PanelType
from utils.logs import logger

try:
    import websockets.client
    import websockets.exceptions
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

async def is_protocol_supported(url: str, context=None) -> bool:
    """
    Check if the protocol (WS/WSS) is supported by attempting a simple handshake.

    Args:
        url (str): The WebSocket URL to test.
        ssl_context: SSL context for WSS connections.

    Returns:
        bool: True if the protocol is supported, False otherwise.
    """
    try:
        async with websockets.connect(url, ssl=context) as ws:
            await ws.send("ping")
            await ws.recv()
            return True
    except websockets.exceptions.InvalidHandshake as handshake_error:
        logger.error("Invalid handshake error for URL %s: %s", url, handshake_error)
        return False
    except websockets.exceptions.ConnectionClosedError as connection_error:
        logger.error("Connection closed unexpectedly for URL %s: %s", url, connection_error)
        return False
    except asyncio.TimeoutError as timeout_error:
        logger.error("Timeout error for URL %s: %s", url, timeout_error)
        return False
    except ssl.SSLError as ssl_error:
        logger.error("SSL error for URL %s: %s", url, ssl_error)
        return False


async def get_panel_logs(panel_data: PanelType) -> None:
    """
    This function establishes a websocket connection to the main server and retrieves logs.
    """
    interval = random.choice(("0.9", "1.3", "1.5", "1.7"))
    get_panel_token = await get_token(panel_data)
    if isinstance(get_panel_token, ValueError):
        raise get_panel_token
    token = get_panel_token.panel_token

    last_successful_protocol = None

    if last_successful_protocol:
        schemes = [last_successful_protocol] + ["wss", "ws"]
    else:
        schemes = ["wss", "ws"]

    for scheme in schemes:
        url = (
            f"{scheme}://{panel_data.panel_domain}/api/core/logs"
            f"?interval={interval}&token={token}"
        )
        ssl_ctx = ssl_context if scheme == "wss" else None

        if not await is_protocol_supported(url, ssl_ctx):
            continue

        while True:
            try:
                async with websockets.connect(url, ssl=ssl_ctx) as ws:
                    last_successful_protocol = scheme
                    log_message = f"Connected to panel logs via {scheme} protocol."
                    await send_logs(log_message)
                    logger.info(log_message)

                    while True:
                        new_log = await ws.recv()
                        await parse_logs(str(new_log))
            except websockets.exceptions.ConnectionClosedError as error:
                logger.error("Connection closed unexpectedly for %s: %s", scheme, error)
                break


async def get_nodes_logs(panel_data: PanelType, node: NodeType) -> None:
    """
    Establish a WebSocket connection to a specific node and retrieve logs.
    """
    interval = random.choice(("0.9", "1.3", "1.5", "1.7"))
    get_panel_token = await get_token(panel_data)
    if isinstance(get_panel_token, ValueError):
        raise get_panel_token
    token = get_panel_token.panel_token

    last_successful_protocol = None

    if last_successful_protocol:
        schemes = [last_successful_protocol] + ["wss", "ws"]
    else:
        schemes = ["wss", "ws"]

    for scheme in schemes:
        url = (
            f"{scheme}://{panel_data.panel_domain}/api/node/{node.node_id}/logs"
            f"?interval={interval}&token={token}"
        )
        ssl_ctx = ssl_context if scheme == "wss" else None

        if not await is_protocol_supported(url, ssl_ctx):
            continue

        while True:
            try:
                async with websockets.connect(url, ssl=ssl_ctx) as ws:
                    last_successful_protocol = scheme
                    log_message = f"Connected to node {node.node_id} logs via {scheme} protocol."
                    await send_logs(log_message)
                    logger.info(log_message)

                    while True:
                        new_log = await ws.recv()
                        await parse_logs(str(new_log))
            except websockets.exceptions.ConnectionClosedError as error:
                logger.error(
                    "Connection closed for node [ID: %s, Name: %s] using %s: %s",
                    node.node_id,
                    node.node_name,
                    scheme,
                    error,
                )
                break


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


async def handle_cancel_one(tasks: list[Task]) -> None:
    """
    *This is used for tests*
    An asynchronous coroutine that cancels just one tasks in the given list.

    Args:
        tasks (list[Task]): The list of tasks to be cancelled.
    """
    for task in tasks:
        if task.get_name() == "Task-panel":
            logger.warning("Cancelling %s...", task.get_name())
            task.cancel()
            tasks.remove(task)


async def handle_cancel_all(tasks: list[Task], panel_data: PanelType) -> None:
    """
    An asynchronous coroutine that cancels All tasks in the given list.
    To fix these issues: #67, #65, #62 And many more

    Args:
        tasks (list[Task]): The list of tasks to be cancelled.
    """
    # pylint: disable=duplicate-code
    async with asyncio.TaskGroup() as tg:
        while True:
            await asyncio.sleep(8192)  # =~ 2 hours and 27 minutes
            for task in tasks:
                logger.warning("Cancelling %s...", task.get_name())
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


async def create_panel_task(panel_data: PanelType, tg: asyncio.TaskGroup) -> None:
    """
    An asynchronous coroutine that creates a new task for a node and adds it to the TASKS list.

    Args:
        panel_data (PanelType): The credentials for the panel.
        tg (asyncio.TaskGroup): The TaskGroup to which the new task will be added.
    """
    TASKS.append(
        tg.create_task(get_panel_logs(panel_data), name="Task-panel"),
    )


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
