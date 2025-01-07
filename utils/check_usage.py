"""
This module checks if a user (name and IP address)
appears more than two times in the ACTIVE_USERS  list.
"""

import asyncio
from collections import Counter

from telegram_bot.send_message import send_logs
from utils.logs import logger
from utils.panel_api import disable_user
from utils.read_config import ConfigManager
from utils.types import PanelType, UserType

ACTIVE_USERS: dict[str, UserType] | dict = {}


async def check_ip_used() -> dict:
    """
    This function checks if a user (name and IP address)
    appears more than two times in the ACTIVE_USERS list.
    """
    all_users_log = {}
    for email in list(ACTIVE_USERS.keys()):
        data = ACTIVE_USERS[email]
        ip_counts = Counter(data.ip)
        data.ip = list({ip for ip in data.ip if ip_counts[ip] > 2})
        all_users_log[email] = data.ip
        logger.info(data)
    total_ips = sum(len(ips) for ips in all_users_log.values())
    all_users_log = dict(
        sorted(
            all_users_log.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        )
    )
    messages = [
        f"<code>{email}</code> with <code>{len(ips)}</code> active ip  \n- "
        + "\n- ".join(ips)
        for email, ips in all_users_log.items()
        if ips
    ]
    logger.info("Number of all active ips: %s", str(total_ips))
    messages.append(f"---------\nCount Of All Active IPs: <b>{total_ips}</b>")

    max_message_length = 4096
    shorter_messages = []
    current_chunk = ""

    for message in messages:
        if len(current_chunk) + len(message) + 1 > max_message_length:
            shorter_messages.append(current_chunk)
            current_chunk = message
        else:
            current_chunk += "\n" + message

    if current_chunk:
        shorter_messages.append(current_chunk)

    for message in shorter_messages:
        await send_logs(message)

    return all_users_log


async def check_users_usage(panel_data: PanelType, config_manager: ConfigManager):
    """
    Checks the usage of active users.

    Args:
        panel_data (PanelType): Panel data for user operations.
        config_manager (ConfigManager): Instance of the ConfigManager to fetch config data.
    """
    try:
        config_data = await config_manager.read_config()
        all_users_log = await check_ip_used()
        except_users = config_data.get("EXCEPT_USERS", [])
        special_limit = config_data.get("SPECIAL_LIMIT", {})
        limit_number = int(config_data.get("GENERAL_LIMIT", 0))

        for user_name, user_ip in all_users_log.items():
            if user_name not in except_users:
                user_limit_number = int(special_limit.get(user_name, limit_number))
                if len(set(user_ip)) > user_limit_number:
                    message = (
                        f"User {user_name} has {len(set(user_ip))} active IPs: {set(user_ip)}"
                    )
                    logger.warning("Exceeded IP limit: %s", message)
                    await send_logs(f"<b>Warning: </b>{message}")
                    try:
                        await disable_user(panel_data, UserType(name=user_name, ip=[]))
                    except ValueError as error:
                        logger.error("Error disabling user %s: %s", user_name, error)
    except KeyError as error:
        logger.error("Missing required key in configuration: %s", error)
    except ValueError as error:
        logger.error("Configuration value error: %s", error)
    except Exception as error:  # pylint: disable=broad-except
        logger.error("Unexpected error in check_users_usage: %s", error)


async def run_check_users_usage(panel_data: PanelType, config_manager: ConfigManager) -> None:
    """
    Run the check_users_usage function periodically.

    Args:
        panel_data (PanelType): Panel data for user operations.
        config_manager (ConfigManager): Instance of the ConfigManager to fetch config data.
    """
    while True:
        try:
            await check_users_usage(panel_data, config_manager)
            config_data = await config_manager.read_config()
            check_interval = int(config_data.get("CHECK_INTERVAL", 60))
            await asyncio.sleep(check_interval)
        except KeyError as error:
            logger.error("Missing required key in configuration during interval fetch: %s", error)
        except ValueError as error:
            logger.error("Invalid CHECK_INTERVAL value: %s", error)
        except Exception as error:  # pylint: disable=broad-except
            logger.error("Unexpected error in run_check_users_usage: %s", error)
            await asyncio.sleep(60)
