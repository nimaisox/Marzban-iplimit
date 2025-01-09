"""
main.py is the
main file that run other files and functions to run the program.
"""
import argparse
import asyncio
import atexit
import sys
import traceback

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

async def initialize_config(config_manager):
    """Load and validate configuration."""
    while True:
        try:
            config_file = await config_manager.read_config(check_required_elements=True)
            logger.info("Configuration loaded successfully.")
            return config_file
        except ValueError as error:
            logger.error("Configuration error: %s", error)
            await send_logs(f"<code>{error}</code>")
            await send_logs(
                "Please fill the <b>required</b> elements (details with /start):\n"
                "/create_config: <code>Config panel information (username, password,...)</code>\n"
                "/country_code: <code>Set your country code</code>\n"
                "/set_general_limit_number: <code>Set the general limit number</code>\n"
                "/set_check_interval: <code>Set the check interval time</code>\n"
                "/set_time_to_active_users: <code>Set the time to active users</code>\n"
                "\nRetrying in <b>60 seconds</b>."
            )
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
            except Exception as e:  # pylint: disable=broad-except
                logger.error("Failed to enable user %s during cleanup: %s", username, e)

        logger.info("All disabled users have been handled successfully.")
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Error while handling disabled users during exit: %s", e)

def register_exit_handler(panel_data):
    """Register atexit handler for cleanup."""
    def exit_handler():
        logger.info("Executing registered atexit handler...")
        asyncio.run(handle_disabled_users_on_exit(panel_data))

    # Register the exit handler
    atexit.register(exit_handler)

async def main():
    """Main program entry point."""
    logger.info("Starting Telegram Bot...")
    asyncio.create_task(run_telegram_bot())
    await asyncio.sleep(2)

    config_manager = ConfigManager(config_file="config.json")
    config_file = await initialize_config(config_manager)

    panel_data = PanelType(
        config_file["PANEL_USERNAME"],
        config_file["PANEL_PASSWORD"],
        config_file["PANEL_DOMAIN"],
    )

    try:
        while True:
            await run_tasks(panel_data, config_manager)
            await asyncio.sleep(60)
    except asyncio.CancelledError:
        logger.info("Tasks cancelled. Exiting...")
        sys.exit(1)
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Error during task execution: %s", e)
        await send_logs(f"Unexpected error: <code>{e}</code>")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program interrupted by user. Exiting gracefully.")
        sys.exit(1)
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Unhandled exception: %s", e)
        logger.error(traceback.format_exc())
        sys.exit(1)
