"""
Optimized module for fetching logs from panel and nodes.
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
    logger.warning("Module 'websockets' is not installed. Use: 'pip install websockets'")
    sys.exit()

from telegram_bot.send_message import send_logs

TASKS = []
TASKS_LOCK = asyncio.Lock()
task_node_mapping = {}

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

MAX_RETRIES = 5  # تعداد تلاش‌های مجدد در صورت خطا
RETRY_DELAY_BASE = 1  # مقدار تأخیر اولیه هنگام بروز خطا

async def retrieve_token(panel_data: PanelType) -> str:
    """Retrieve panel authentication token."""
    try:
        panel_token = await get_token(panel_data)
        return panel_token.panel_token
    except ValueError as error:
        logger.error("Failed to retrieve token: %s", error)
        raise error

async def get_panel_logs(panel_data: PanelType) -> None:
    """Fetch logs from panel using WebSocket."""
    interval = random.uniform(0.9, 1.7)
    token = await retrieve_token(panel_data)

    panel_domain = panel_data.panel_domain.replace("https://", "").replace("http://", "")
    scheme = "wss" if panel_data.panel_domain.startswith("https") else "ws"
    url = f"{scheme}://{panel_domain}/api/core/logs?interval={interval}&token={token}"

    ssl_ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH) if scheme == "wss" else None
    retry_attempts = 0

    while retry_attempts < MAX_RETRIES:
        try:
            async with websockets.connect(url, ssl=ssl_ctx, ping_interval=20, ping_timeout=15) as ws:
                log_message = "Connected to panel logs successfully."
                await send_logs(log_message)
                logger.info(log_message)

                config_manager = ConfigManager(config_file="config.json")

                async for new_log in ws:
                    await parse_logs(str(new_log), config_manager)

        except (ConnectionClosedError, ssl.SSLError) as error:
            logger.error("Connection error: %s", error)
        except Exception as error:
            logger.error("Unexpected error: %s\n%s", error, traceback.format_exc())

        retry_attempts += 1
        await asyncio.sleep(min(RETRY_DELAY_BASE * (2 ** retry_attempts), 60))

    logger.error("Max retries reached for panel logs. Stopping.")
    return

async def get_nodes_logs(panel_data: PanelType, node: NodeType) -> None:
    """Fetch logs from a specific node using WebSocket."""
    interval = random.uniform(0.9, 1.7)
    token = await retrieve_token(panel_data)

    panel_domain = panel_data.panel_domain.replace("https://", "").replace("http://", "")
    scheme = "wss" if panel_data.panel_domain.startswith("https") else "ws"
    url = f"{scheme}://{panel_domain}/api/node/{node.node_id}/logs?interval={interval}&token={token}"

    ssl_ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH) if scheme == "wss" else None
    retry_attempts = 0

    while retry_attempts < MAX_RETRIES:
        try:
            async with websockets.connect(url, ssl=ssl_ctx, ping_interval=20, ping_timeout=15) as ws:
                log_message = f"Connected to node {node.node_id} logs."
                await send_logs(log_message)
                logger.info(log_message)

                config_manager = ConfigManager(config_file="config.json")

                async for new_log in ws:
                    await parse_logs(str(new_log), config_manager)

        except (ConnectionClosedError, ssl.SSLError) as error:
            logger.error("Connection error: %s", error)
        except Exception as error:
            logger.error("Unexpected error: %s\n%s", error, traceback.format_exc())

        retry_attempts += 1
        await asyncio.sleep(min(RETRY_DELAY_BASE * (2 ** retry_attempts), 60))

    logger.error(f"Max retries reached for node {node.node_id}. Stopping.")
    return

async def create_panel_task(panel_data: PanelType, tg: asyncio.TaskGroup) -> None:
    """Create a task to fetch panel logs if not already running."""
    async with TASKS_LOCK:
        if any(task.get_name() == "Task-panel" for task in TASKS):
            logger.info("Task-panel already exists. Skipping creation.")
            return

    logger.info("Creating Task-panel...")
    new_task = tg.create_task(get_panel_logs(panel_data), name="Task-panel")
    await safe_append_task(new_task)

async def create_node_task(panel_data: PanelType, tg: asyncio.TaskGroup, node: NodeType) -> None:
    """Create a task to fetch node logs if not already running."""
    task_name = f"Task-{node.node_id}-{node.node_name}"
    async with TASKS_LOCK:
        if any(task.get_name() == task_name for task in TASKS):
            logger.info(f"Task for node {node.node_id} already exists. Skipping.")
            return

    logger.info(f"Creating task for node: {node.node_id}")
    task = tg.create_task(get_nodes_logs(panel_data, node), name=task_name)
    await safe_append_task(task)

async def handle_cancel_all(tasks: list[Task], panel_data: PanelType) -> None:
    """Cancels all tasks and recreates only necessary ones every 3 hours."""
    async with asyncio.TaskGroup() as tg:
        while True:
            await asyncio.sleep(10800)  # Every 3 hours

            async with TASKS_LOCK:
                for task in tasks[:]:  # Copy the list to prevent modification errors
                    if task.done():
                        logger.warning("Removing completed task: %s...", task.get_name())
                        tasks.remove(task)

            logger.info("Recreating necessary tasks.")
            await create_panel_task(panel_data, tg)

            nodes_list = await get_nodes(panel_data)
            if nodes_list:
                for node in nodes_list:
                    await create_node_task(panel_data, tg, node)

async def safe_append_task(task):
    """Safely append a task to TASKS with thread-safe locking."""
    async with TASKS_LOCK:
        TASKS.append(task)

async def safe_remove_task(task):
    """Safely remove a task from TASKS with thread-safe locking."""
    async with TASKS_LOCK:
        if task in TASKS:
            TASKS.remove(task)
