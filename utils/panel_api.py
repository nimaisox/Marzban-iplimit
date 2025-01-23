"""
This module contains functions to interact with the panel API.
"""

import asyncio
import random
import sys
import traceback
from datetime import datetime

from telegram_bot.send_message import send_logs
from utils.handel_users import DisabledUsers
from utils.logs import logger
from utils.read_config import ConfigManager
from utils.types import NodeType, PanelType, UserType

try:
    import httpx
except ImportError:
    logger.warning("Module 'httpx' is not installed. Use: 'pip install httpx' to install it.")
    sys.exit()

TOKEN_CACHE = {}  # Cache for storing tokens and expiry

async def get_token(panel_data: PanelType, max_retries=10,
                    retry_delay_min=2, retry_delay_max=5) -> PanelType | ValueError:
    """
    Get access token from the panel API.

    Args:
        panel_data (PanelType): A PanelType object containing username, password, and domain.
        max_retries (int): Maximum number of attempts to get the token.
        retry_delay_min (int): Minimum delay between retries.
        retry_delay_max (int): Maximum delay between retries.

    Returns:
        PanelType: The updated PanelType object with the access token.

    Raises:
        ValueError: If it fails to get a token after max_retries attempts.
    """
    payload = {
        "username": panel_data.panel_username,
        "password": panel_data.panel_password,
    }
    url = f"{panel_data.panel_domain}/api/admin/token"

    if not url.startswith(("http://", "https://")):
        raise ValueError(f"Invalid URL: {url}. It must start with http:// or https://")

    # Check if we have a valid cached token
    if panel_data.panel_domain in TOKEN_CACHE:
        cached_token, expiry_time = TOKEN_CACHE[panel_data.panel_domain]
        if datetime.now() < expiry_time:
            panel_data.panel_token = cached_token
            return panel_data

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(http2=True, timeout=httpx.Timeout(10.0)) as client:
                response = await client.post(url, data=payload)
                response.raise_for_status()

            json_obj = response.json()
            panel_data.panel_token = json_obj["access_token"]
            TOKEN_CACHE[panel_data.panel_domain] = (panel_data.panel_token, datetime.now())

            logger.info("Token retrieved successfully on attempt %d.", attempt + 1)
            return panel_data

        except httpx.HTTPStatusError as http_error:
            logger.error("Token request failed [%d]: %s", http_error.response.status_code, http_error.response.text)

        except Exception as error:
            logger.error("Unexpected error during token request: %s", traceback.format_exc())

        delay = random.randint(retry_delay_min, retry_delay_max) * (2 ** attempt)
        logger.warning("Retrying in %d seconds... (Attempt %d/%d)", delay, attempt + 1, max_retries)
        await asyncio.sleep(delay)

    message = "Failed to get token after multiple attempts. Ensure the panel is running."
    logger.error(message)
    raise ValueError(message)

async def enable_selected_users(panel_data: PanelType, inactive_users: set[str]) -> None:
    """Enable selected users on the panel."""
    try:
        panel_data = await get_token(panel_data)
    except ValueError as error:
        logger.error("Failed to retrieve token: %s", error)
        return

    headers = {"Authorization": f"Bearer {panel_data.panel_token}"}
    url_template = f"{panel_data.panel_domain}/api/user/{{username}}"

    for username in inactive_users:
        url = url_template.format(username=username)
        status_payload = {"status": "active"}

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(http2=True) as client:
                    response = await client.put(url, json=status_payload, headers=headers)
                    response.raise_for_status()

                logger.info("User %s enabled successfully.", username)
                break
            except Exception as error:
                logger.error("Error enabling user %s: %s", username, error)
                await asyncio.sleep(2 ** attempt)

async def disable_user(panel_data: PanelType, username: UserType) -> None:
    """Disable a user on the panel."""
    try:
        panel_data = await get_token(panel_data)
    except ValueError as error:
        logger.error("Failed to retrieve token: %s", error)
        return

    headers = {"Authorization": f"Bearer {panel_data.panel_token}"}
    url = f"{panel_data.panel_domain}/api/user/{username.name}"
    status_payload = {"status": "disabled"}

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(http2=True) as client:
                response = await client.put(url, json=status_payload, headers=headers)
                response.raise_for_status()

            logger.info("User %s disabled successfully.", username.name)
            dis_obj = DisabledUsers()
            await dis_obj.add_user(username.name)
            break
        except Exception as error:
            logger.error("Error disabling user %s: %s", username.name, error)
            await asyncio.sleep(2 ** attempt)

async def get_nodes(panel_data: PanelType) -> list[NodeType] | ValueError:
    """Retrieve list of nodes from the panel API."""
    try:
        panel_data = await get_token(panel_data)
    except ValueError as error:
        logger.error("Failed to retrieve token: %s", error)
        return []

    headers = {"Authorization": f"Bearer {panel_data.panel_token}"}
    url = f"{panel_data.panel_domain}/api/nodes"

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(http2=True) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

            nodes = [
                NodeType(
                    node_id=node["id"],
                    node_name=node["name"],
                    node_ip=node["address"],
                    status=node["status"],
                    message=node.get("message", "")
                )
                for node in response.json()
            ]
            return nodes
        except Exception as error:
            logger.error("Error retrieving nodes: %s", error)
            await asyncio.sleep(2 ** attempt)

    logger.error("Failed to get nodes after multiple attempts.")
    return []

async def enable_dis_user(panel_data: PanelType, config_manager: ConfigManager):
    """Periodically enable disabled users based on configuration."""
    dis_obj = DisabledUsers()

    while True:
        try:
            config_data = await config_manager.read_config()
            time_to_active_users = int(config_data.get("TIME_TO_ACTIVE_USERS", 3600))
            check_interval = int(config_data.get("CHECK_INTERVAL", 300))

            dis_obj.disabled_users = dis_obj.load_disabled_users()
            if dis_obj.disabled_users:
                for username, disabled_time in list(dis_obj.disabled_users.items()):
                    if (datetime.now() - disabled_time).total_seconds() >= time_to_active_users:
                        await enable_selected_users(panel_data, {username})
                        await dis_obj.remove_user(username)

            await asyncio.sleep(check_interval)

        except Exception as error:
            logger.error("Unexpected error in enable_dis_user: %s", error)
            await asyncio.sleep(60)
