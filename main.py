"""
main.py is the
main file that runs other files and functions to run the program.
"""

# pylint: disable=broad-except

import argparse
import asyncio
import sys
import traceback
import signal

from run_telegram import run_telegram_bot
from telegram_bot.send_message import send_logs
from utils.check_usage import run_check_users_usage
from utils.get_logs import (
    TASKS,
    check_and_add_new_nodes,
    create_node_task,
    create_panel_task,
    handle_cancel,
    handle_cancel_all,
)
from utils.handel_users import DisabledUsers
from utils.logs import logger
from utils.panel_api import (
    enable_dis_user,
    enable_selected_users,
    get_nodes,
)
from utils.read_config import ConfigManager
from utils.types import PanelType

VERSION = "1.0.1"
parser = argparse.ArgumentParser(description="Run the program with various options.")
parser.add_argument("--version", action="version", version=VERSION)
args = parser.parse_args()


async def initialize_config(config_manager, max_retries=5):
    """Load and validate configuration with retry limit."""
    retries = 0
    while retries < max_retries:
        try:
            config_file = await config_manager.read_config(check_required_elements=True)
            logger.info("Configuration loaded successfully.")
            return config_file
        except ValueError as error:
            logger.error("Configuration error: %s", error)
            await send_logs(f"<code>{error}</code>")
            retries += 1
            if retries >= max_retries:
                logger.error("Max retries reached. Exiting...")
                sys.exit(1)
            await asyncio.sleep(60)


async def run_tasks(panel_data, config_manager):
    """Run all the tasks required for the program."""
    await get_nodes(panel_data)

    async with asyncio.TaskGroup() as tg:
        logger.info("Starting Panel Task...")
        await create_panel_task(panel_data, tg)
        await asyncio.sleep(5)

        nodes_list = await get_nodes(panel_data)
        if nodes_list and not isinstance(nodes_list, ValueError):
            logger.info("Starting Node Tasks...")
            for node in nodes_list:
                if node.status == "connected":
                    await create_node_task(panel_data, tg, node)
                    await asyncio.sleep(4)

        logger.info("Starting additional background tasks...")
        if len(asyncio.all_tasks()) < 50:
            tg.create_task(check_and_add_new_nodes(panel_data, tg), name="add_new_nodes")
            tg.create_task(handle_cancel(panel_data, TASKS), name="cancel_disable_nodes")
            tg.create_task(handle_cancel_all(TASKS, panel_data), name="cancel_all")
            tg.create_task(enable_dis_user(panel_data, config_manager), name="enable_dis_user")

        await run_check_users_usage(panel_data, config_manager)


async def handle_disabled_users_on_exit(panel_data):
    """Handle disabled users during program exit."""
    try:
        logger.info("Handling disabled users during program exit...")
        disabled_users_manager = DisabledUsers()
        disabled_users = await disabled_users_manager.get_all_users()

        if not disabled_users:
            logger.info("No disabled users to handle during exit.")
            return

        logger.info("Enabling disabled users during cleanup...")
        for username in list(disabled_users.keys()):
            try:
                logger.debug("Processing user: %s", username)
                await enable_selected_users(panel_data, {username})
                await disabled_users_manager.remove_user(username)
                logger.info("Enabled user during cleanup: %s", username)
            except Exception as e:
                logger.error("Failed to enable user %s during cleanup: %s", username, e)

        logger.info("All disabled users have been handled successfully.")
    except Exception as e:
        logger.error("Error while handling disabled users during exit: %s", e)


async def graceful_shutdown(signal_name, panel_data):
    """Handle graceful shutdown before forcibly exiting."""
    logger.info("Received signal %s. Shutting down gracefully...", signal_name)
    try:
        if panel_data:
            cleanup_task = asyncio.create_task(handle_disabled_users_on_exit(panel_data))
            await cleanup_task
    except Exception as e:
        logger.error("Error during shutdown: %s", e)
    finally:
        logger.info("Shutdown complete. Exiting forcefully.")
        loop = asyncio.get_running_loop()
        loop.stop()


def setup_signal_handlers(panel_data):
    """Set up signal handlers for cleanup and exit."""
    def signal_handler(signal_name):
        print(f"Signal {signal_name} received. Triggering shutdown...")
        asyncio.create_task(graceful_shutdown(signal_name, panel_data))

    if sys.platform != "win32":
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda s=sig: signal_handler(s.name))
    else:
        print("Signal handling is limited on Windows. Using KeyboardInterrupt for shutdown.")


async def monitor_tasks():
    """Monitor the number of running asyncio tasks."""
    max_tasks = 50  # مقدار مناسب برای جلوگیری از مصرف بی‌رویه CPU
    while True:
        tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
        logger.info(f"Running tasks: {len(tasks)}")

        if len(tasks) > max_tasks:
            logger.warning(f"Too many tasks running ({len(tasks)}). Consider optimizing the task execution.")
            break  # خروج از حلقه در صورت نیاز

        await asyncio.sleep(10)


async def main():
    """Main program entry point."""
    logger.info("Starting Telegram Bot...")
    asyncio.create_task(run_telegram_bot())
    asyncio.create_task(monitor_tasks())
    await asyncio.sleep(2)

    config_manager = ConfigManager(config_file="config.json")
    config_file = await initialize_config(config_manager)

    panel_data = PanelType(
        config_file["PANEL_USERNAME"],
        config_file["PANEL_PASSWORD"],
        config_file["PANEL_DOMAIN"],
    )

    try:
        logger.info("Running main tasks. Waiting for shutdown signal...")
        while True:
            await asyncio.gather(
                run_tasks(panel_data, config_manager),
                asyncio.sleep(60),
            )
    except asyncio.CancelledError:
        logger.info("Tasks cancelled. Exiting...")
    except Exception as e:
        logger.error("Error during task execution: %s", e)
        await send_logs(f"Unexpected error: <code>{e}</code>")
    finally:
        logger.info("Main loop stopped.")


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    PANEL_DATA_INSTANCE = None

    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Program interrupted by user. Exiting gracefully.")
        try:
            loop.run_until_complete(handle_disabled_users_on_exit(PANEL_DATA_INSTANCE))
        except Exception as e:
            logger.error("Error during shutdown: %s", e)
        finally:
            logger.info("Shutdown tasks complete.")
    except Exception as e:
        logger.error("Unhandled exception: %s", e)
        logger.error(traceback.format_exc())
    finally:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()
        logger.info("Event loop closed. Exiting program.")
        sys.exit(0)
