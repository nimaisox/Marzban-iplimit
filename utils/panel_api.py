"""
This module contains functions to interact with the panel API.
"""

import asyncio
import random
import sys
import traceback

from telegram_bot.send_message import send_logs

from utils.handel_dis_users import DISABLED_USERS, DisabledUsers
from utils.logs import logger
from utils.read_config import ConfigManager
from utils.types import NodeType, PanelType, UserType

try:
    import httpx
except ImportError:
    logger.warning("Module 'httpx' is not installed use: 'pip install httpx' to install it")
    sys.exit()


async def get_token(panel_data: PanelType) -> PanelType | ValueError:
    """
    Get access token from the panel API.

    Args:
        panel_data (PanelType): A PanelType object containing
        the username, password, and domain for the panel API.

    Returns:
        PanelType: The updated PanelType object with the access token.

    Raises:
        ValueError: If the function fails to get a token after multiple attempts.
    """
    payload = {
        "username": panel_data.panel_username,
        "password": panel_data.panel_password,
    }
    url = f"{panel_data.panel_domain}/api/admin/token"

    for attempt in range(20):
        try:
            timeout = httpx.Timeout(connect=10.0, read=30.0, write=15.0, pool=10.0)
            async with httpx.AsyncClient(http2=True, timeout=timeout) as client:
                response = await client.post(url, data=payload, timeout=5)
                response.raise_for_status()
            json_obj = response.json()
            panel_data.panel_token = json_obj["access_token"]
            return panel_data
        except httpx.HTTPStatusError:
            message = f"[{response.status_code}] {response.text}"
            await send_logs(message)
            logger.error(message)
        except Exception as error:  # pylint: disable=broad-except
            message = f"Unexpected error during token request: {error}\n{traceback.format_exc()}"
            await send_logs(message)
            logger.error(message)
        await asyncio.sleep(random.randint(2, 5) * (attempt + 1))

    message = (
        "Failed to get token after 20 attempts. Make sure the panel is running "
        "and the username and password are correct."
    )
    await send_logs(message)
    logger.error(message)
    raise ValueError(message)


async def all_user(panel_data: PanelType) -> list[UserType] | ValueError:
    """
    Get the list of all users from the panel API.

    Args:
        panel_data (PanelType): A PanelType object containing
        the username, password, and domain for the panel API.

    Returns:
        list[UserType]: The list of user objects.

    Raises:
        ValueError: If the function fails to get the users after multiple attempts.
    """
    try:
        get_panel_token = await get_token(panel_data)
        token = get_panel_token.panel_token
    except ValueError as error:
        logger.error("Failed to retrieve token: %s", error)
        raise error

    headers = {
        "Authorization": f"Bearer {token}",
    }
    url = f"{panel_data.panel_domain}/api/users"

    for attempt in range(20):
        try:
            timeout = httpx.Timeout(connect=10.0, read=30.0, write=15.0, pool=10.0)
            async with httpx.AsyncClient(http2=True, timeout=timeout) as client:
                response = await client.get(url, headers=headers, timeout=10)
                response.raise_for_status()

            user_inform = response.json()
            logger.info("Successfully fetched users.")
            return [
                UserType(name=user["username"]) for user in user_inform["users"]
            ]
        except httpx.HTTPStatusError:
            message = f"[{response.status_code}] {response.text}"
            await send_logs(message)
            logger.error(message)
        except Exception as error:  # pylint: disable=broad-except
            message = f"An unexpected error occurred: {error}"
            await send_logs(message)
            logger.error(message)

        await asyncio.sleep(random.randint(2, 5) * (attempt + 1))

    message = (
        "Failed to get users after 20 attempts. Make sure the panel is running "
        "and the username and password are correct."
    )
    await send_logs(message)
    logger.error(message)
    raise ValueError(message)


async def enable_all_user(panel_data: PanelType) -> None | ValueError:
    """
    Enable all users on the panel.

    Args:
        panel_data (PanelType): A PanelType object containing
        the username, password, and domain for the panel API.

    Returns:
        None

    Raises:
        ValueError: If the function fails to enable the users after multiple attempts.
    """
    try:
        get_panel_token = await get_token(panel_data)
        token = get_panel_token.panel_token
    except ValueError as error:
        logger.error("Failed to retrieve token: %s", error)
        raise error

    headers = {
        "Authorization": f"Bearer {token}",
    }

    try:
        users = await all_user(panel_data)
    except ValueError as error:
        logger.error("Failed to retrieve all users: %s", error)
        raise error

    url_template = f"{panel_data.panel_domain}/api/user/{{username}}"

    for username in users:
        url = url_template.format(username=username.name)
        status = {"status": "active"}
        try:
            timeout = httpx.Timeout(connect=10.0, read=30.0, write=15.0, pool=10.0)
            async with httpx.AsyncClient(http2=True, timeout=timeout) as client:
                response = await client.put(
                    url, json=status, headers=headers, timeout=5
                )
                response.raise_for_status()

            message = f"Enabled user: {username.name}"
            await send_logs(message)
            logger.info(message)
        except httpx.HTTPStatusError:
            message = f"[{response.status_code}] {response.text}"
            await send_logs(message)
            logger.error(message)
        except Exception as error:  # pylint: disable=broad-except
            message = f"An unexpected error occurred: {error}"
            await send_logs(message)
            logger.error(message)
    logger.info("Enabled all users")



async def enable_selected_users(
    panel_data: PanelType, inactive_users: set[str]
) -> None | ValueError:
    """
    Enable selected users on the panel.

    Args:
        panel_data (PanelType): A PanelType object containing
        the username, password, and domain for the panel API.
        inactive_users (set[str]): A set of usernames that are currently inactive.

    Returns:
        None

    Raises:
        ValueError: If the function fails to enable the users after multiple attempts.
    """
    try:
        get_panel_token = await get_token(panel_data)
        token = get_panel_token.panel_token
    except ValueError as error:
        logger.error("Failed to retrieve token: %s", error)
        raise error

    headers = {
        "Authorization": f"Bearer {token}",
    }

    url_template = f"{panel_data.panel_domain}/api/user/{{username}}"

    for username in inactive_users:
        url = url_template.format(username=username)
        status = {"status": "active"}
        success = False
        for attempt in range(5):
            try:
                timeout = httpx.Timeout(connect=10.0, read=30.0, write=15.0, pool=10.0)
                async with httpx.AsyncClient(http2=True, timeout=timeout) as client:
                    response = await client.put(
                        url, json=status, headers=headers, timeout=5
                    )
                    response.raise_for_status()

                message = f"Enabled user: {username}"
                await send_logs(message)
                logger.info(message)
                success = True
                break
            except httpx.HTTPStatusError as http_error:
                message = (
                    f"HTTP error while enabling user {username}: "
                    f"[{http_error.response.status_code}] {http_error.response.text}"
                )
                await send_logs(message)
                logger.error(message)
            except Exception as error:  # pylint: disable=broad-except
                message = f"An unexpected error occurred while enabling user {username}: {error}"
                await send_logs(message)
                logger.error(message)

            await asyncio.sleep(random.randint(2, 5) * (attempt + 1))

        if not success:
            message = (
                f"Failed to enable user: {username} after 5 attempts. Ensure the panel is running "
                "and the username and password are correct."
            )
            await send_logs(message)
            logger.error(message)
            raise ValueError(message)

    logger.info("Enabled selected users")



async def disable_user(panel_data: PanelType, username: UserType) -> None | ValueError:
    """
    Disable a user on the panel.

    Args:
        panel_data (PanelType): A PanelType object containing
        the username, password, and domain for the panel API.
        username (UserType): The username of the user to disable.

    Returns:
        None

    Raises:
        ValueError: If the function fails to disable the user after multiple attempts.
    """
    try:
        get_panel_token = await get_token(panel_data)
        token = get_panel_token.panel_token
    except ValueError as error:
        logger.error("Failed to retrieve token: %s", error)
        raise error

    headers = {
        "Authorization": f"Bearer {token}",
    }

    url = f"{panel_data.panel_domain}/api/user/{username.name}"
    status = {"status": "disabled"}
    success = False

    for attempt in range(5):
        try:
            timeout = httpx.Timeout(connect=10.0, read=30.0, write=15.0, pool=10.0)
            async with httpx.AsyncClient(http2=True, timeout=timeout) as client:
                response = await client.put(url, json=status, headers=headers, timeout=5)
                response.raise_for_status()

            message = f"Disabled user: {username.name}"
            await send_logs(message)
            logger.info(message)

            dis_obj = DisabledUsers()
            await dis_obj.add_user(username.name)

            success = True
            break
        except httpx.HTTPStatusError as http_error:
            message = (
                f"HTTP error while disabling user {username.name}: "
                f"[{http_error.response.status_code}] {http_error.response.text}"
            )
            await send_logs(message)
            logger.error(message)
        except Exception as error:  # pylint: disable=broad-except
            message = f"An unexpected error occurred while disabling user {username.name}: {error}"
            await send_logs(message)
            logger.error(message)

        await asyncio.sleep(random.randint(2, 5) * (attempt + 1))

    if not success:
        message = (
            f"Failed to disable user: {username.name} after 5 attempts. Ensure the panel is running"
            "and the username and password are correct."
        )
        await send_logs(message)
        logger.error(message)
        raise ValueError(message)

    logger.info("Disabled user successfully")


async def get_nodes(panel_data: PanelType) -> list[NodeType] | ValueError:
    """
    Get the IDs of all nodes from the panel API.

    Args:
        panel_data (PanelType): A PanelType object containing
        the username, password, and domain for the panel API.

    Returns:
        list[NodeType]: The list of IDs and other information of all nodes.

    Raises:
        ValueError: If the function fails to get the nodes after multiple attempts.
    """

    def parse_nodes(response_json):
        return [
            NodeType(
                node_id=node["id"],
                node_name=node["name"],
                node_ip=node["address"],
                status=node["status"],
                message=node.get("message", "")
            )
            for node in response_json
        ]

    try:
        get_panel_token = await get_token(panel_data)
        token = get_panel_token.panel_token
    except ValueError as error:
        logger.error("Failed to retrieve token: %s", error)
        raise error

    headers = {
        "Authorization": f"Bearer {token}",
    }

    url = f"{panel_data.panel_domain}/api/nodes"

    for attempt in range(5):
        try:
            timeout = httpx.Timeout(connect=10.0, read=30.0, write=15.0, pool=10.0)
            async with httpx.AsyncClient(http2=True, timeout=timeout) as client:
                response = await client.get(url, headers=headers, timeout=10)
                response.raise_for_status()

            nodes = parse_nodes(response.json())
            logger.info("Successfully retrieved nodes.")
            return nodes
        except httpx.HTTPStatusError as http_error:
            message = (
                f"HTTP error while retrieving nodes: "
                f"[{http_error.response.status_code}] {http_error.response.text}"
            )
            await send_logs(message)
            logger.error(message)
        except Exception as error:  # pylint: disable=broad-except
            message = f"An unexpected error occurred while retrieving nodes: {error}"
            await send_logs(message)
            logger.error(message)

        await asyncio.sleep(random.randint(2, 5) * (attempt + 1))

    message = (
        "Failed to get nodes after 5 attempts. Ensure the panel is running "
        "and the username and password are correct."
    )
    await send_logs(message)
    logger.error(message)
    raise ValueError(message)


async def enable_dis_user(panel_data: PanelType, config_manager: ConfigManager):
    """
    Periodically enable disabled users based on the 'TIME_TO_ACTIVE_USERS' configuration.

    Args:
        panel_data (PanelType): Panel data for user operations.
        config_manager (ConfigManager): Instance of the ConfigManager to fetch configuration data.
    """
    dis_obj = DisabledUsers()
    while True:
        try:
            config_data = await config_manager.read_config()
            time_to_active_users = int(config_data.get("TIME_TO_ACTIVE_USERS", 60))

            await asyncio.sleep(time_to_active_users)

            if DISABLED_USERS:
                logger.info("Enabling disabled users: %s", DISABLED_USERS)
                await enable_selected_users(panel_data, DISABLED_USERS)
                await dis_obj.read_and_clear_users()

        except KeyError as error:
            logger.error("Missing key in configuration: %s", error)
        except ValueError as error:
            logger.error("Invalid value in configuration: %s", error)
        except Exception as error: # pylint: disable=broad-except
            logger.error("Unexpected error in enable_dis_user: %s", error)
            await asyncio.sleep(60)
