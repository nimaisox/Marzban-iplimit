"""
This module contains functions to interact with the panel API.
"""

import asyncio
import random
import sys
from ssl import SSLError

from telegram_bot.send_message import send_logs

from utils.handel_dis_users import DISABLED_USERS, DisabledUsers
from utils.logs import logger
from utils.read_config import read_config
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
        str: The access token from the panel API.

    Raises:
        ValueError: If the function fails to get a token from both the HTTP
        and HTTPS endpoints.
    """
    payload = {
        "username": f"{panel_data.panel_username}",
        "password": f"{panel_data.panel_password}",
    }
    successful_scheme = None
    for attempt in range(20):
        schemes = ["https", "http"] if not successful_scheme else [successful_scheme]
        for scheme in schemes:
            url = f"{scheme}://{panel_data.panel_domain}/api/admin/token"
            try:
                timeout = httpx.Timeout(connect=10.0, read=30.0, write=15.0, pool=10.0)
                async with httpx.AsyncClient(http2=True, timeout=timeout) as client:
                    response = await client.post(url, data=payload, timeout=5)
                    response.raise_for_status()
                json_obj = response.json()
                panel_data.panel_token = json_obj["access_token"]
                successful_scheme = scheme
                return panel_data
            except SSLError:
                logger.warning("SSL error with %s, trying another scheme.", scheme.upper())
                continue
            except httpx.HTTPStatusError:
                message = f"[{response.status_code}] {response.text}"
                await send_logs(message)
                logger.error(message)
                continue
            except Exception as error:  # pylint: disable=broad-except
                message = f"Unexpected error with {scheme.upper()} endpoint: {error}"
                await send_logs(message)
                logger.error(message)
                continue
        await asyncio.sleep(random.randint(2, 5) * (attempt + 1))
    message = (
        "Failed to get token after 20 attempts. Make sure the panel is running "
        + "and the username and password are correct."
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
        list[user]: The list of usernames of all users.

    Raises:
        ValueError: If the function fails to get the users from both the HTTP
        and HTTPS endpoints.
    """
    successful_scheme = None
    for attempt in range(20):
        try:
            get_panel_token = await get_token(panel_data)
            token = get_panel_token.panel_token
        except ValueError as error:
            logger.error("Failed to retrieve token: %s", error)
            raise error

        headers = {
            "Authorization": f"Bearer {token}",
        }

        schemes = ["https", "http"] if not successful_scheme else [successful_scheme]

        for scheme in schemes:
            url = f"{scheme}://{panel_data.panel_domain}/api/users"
            try:
                timeout = httpx.Timeout(connect=10.0, read=30.0, write=15.0, pool=10.0)
                async with httpx.AsyncClient(http2=True, timeout=timeout) as client:
                    response = await client.get(url, headers=headers, timeout=10)
                    response.raise_for_status()

                user_inform = response.json()
                successful_scheme = scheme
                logger.info("Successfully fetched users using %s.", scheme.upper())
                return [
                    UserType(name=user["username"]) for user in user_inform["users"]
                ]
            except SSLError:
                logger.warning("SSL error with %s, trying another scheme.", scheme.upper())
                continue
            except httpx.HTTPStatusError:
                message = f"[{response.status_code}] {response.text}"
                await send_logs(message)
                logger.error(message)
                continue
            except Exception as error:  # pylint: disable=broad-except
                message = f"An unexpected error occurred: {error}"
                await send_logs(message)
                logger.error(message)
                continue

        await asyncio.sleep(random.randint(2, 5) * (attempt + 1))

    message = (
        "Failed to get users after 20 attempts. make sure the panel is running "
        + "and the username and password are correct."
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
        ValueError: If the function fails to enable the users on both the HTTP
        and HTTPS endpoints.
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

    successful_scheme = None

    for username in users:
        schemes = ["https", "http"] if not successful_scheme else [successful_scheme]
        for scheme in schemes:
            url = f"{scheme}://{panel_data.panel_domain}/api/user/{username.name}"
            status = {"status": "active"}
            try:
                timeout = httpx.Timeout(connect=10.0, read=30.0, write=15.0, pool=10.0)
                async with httpx.AsyncClient(http2=True, timeout=timeout) as client:
                    response = await client.put(
                        url, json=status, headers=headers, timeout=5
                    )
                    response.raise_for_status()

                successful_scheme = scheme

                message = f"Enabled user: {username.name}"
                await send_logs(message)
                logger.info(message)
                break
            except SSLError:
                logger.warning(
                    "SSL error with %s while enabling user %s. Trying another scheme.",
                    scheme.upper(),
                    username.name,
                )
                continue
            except httpx.HTTPStatusError:
                message = f"[{response.status_code}] {response.text}"
                await send_logs(message)
                logger.error(message)
                continue
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
        inactive_users (set[str]): A list of user str that are currently inactive.

    Returns:
        None

    Raises:
        ValueError: If the function fails to enable the users on both the HTTP
        and HTTPS endpoints.
    """
    async def enable_user_request(url: str, headers: dict, status: dict) -> None:
        timeout = httpx.Timeout(connect=10.0, read=30.0, write=15.0, pool=10.0)
        async with httpx.AsyncClient(http2=True, timeout=timeout) as client:
            response = await client.put(url, json=status, headers=headers, timeout=5)
            response.raise_for_status()

    async def get_request_data(panel_data: PanelType) -> dict:
        """Retrieve panel token and create request data."""
        get_panel_token = await get_token(panel_data)
        token = get_panel_token.panel_token
        return {
            "headers": {"Authorization": f"Bearer {token}"},
            "status": {"status": "active"},
        }

    async def handle_scheme(
        username: str, schemes: list[str], request_data: dict
    ) -> tuple[bool, str | None]:
        """Attempt to enable a user using the provided schemes."""
        for scheme in schemes:
            url = f"{scheme}://{panel_data.panel_domain}/api/user/{username}"
            try:
                await enable_user_request(url, request_data["headers"], request_data["status"])
                return True, scheme
            except SSLError:
                logger.warning(
                    "SSL error with %s while enabling user %s. Trying another scheme.",
                    scheme.upper(),
                    username,
                )
            except httpx.HTTPStatusError as http_error:
                message = (
                    f"HTTP error while enabling user {username} using {scheme.upper()}: "
                    f"[{http_error.response.status_code}] {http_error.response.text}"
                )
                await send_logs(message)
                logger.error(message)
            except Exception as error:  # pylint: disable=broad-except
                message = f"An unexpected error occurred: {error}"
                await send_logs(message)
                logger.error(message)
                continue
        return False, None

    successful_scheme = None

    for username in inactive_users:
        success = False
        for attempt in range(5):
            try:
                request_data = await get_request_data(panel_data)
            except ValueError as error:
                logger.error("Failed to retrieve token: %s", error)
                raise error

            schemes = ["https", "http"] if not successful_scheme else [successful_scheme]
            success, successful_scheme = await handle_scheme(username, schemes, request_data)
            if success:
                message = f"Enabled user: {username}"
                await send_logs(message)
                logger.info(message)
                break

            await asyncio.sleep(random.randint(2, 5) * (attempt + 1))

        if not success:
            message = (
                f"Failed to enable user: {username} after 20 attempts. Ensure the panel is running "
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
        username (user): The username of the user to disable.

    Returns:
        None

    Raises:
        ValueError: If the function fails to disable the user on both the HTTP
        and HTTPS endpoints.
    """
    async def disable_request(url: str, headers: dict, status: dict) -> None:
        """
        Helper function to send a disable request.
        """
        timeout = httpx.Timeout(connect=10.0, read=30.0, write=15.0, pool=10.0)
        async with httpx.AsyncClient(http2=True, timeout=timeout) as client:
            response = await client.put(url, json=status, headers=headers, timeout=5)
            response.raise_for_status()

    successful_scheme = None

    for attempt in range(20):
        try:
            get_panel_token = await get_token(panel_data)
            token = get_panel_token.panel_token
        except ValueError as error:
            logger.error("Failed to retrieve token: %s", error)
            raise error

        request_data = {
            "headers": {"Authorization": f"Bearer {token}"},
            "status": {"status": "disabled"},
        }

        schemes = ["https", "http"] if not successful_scheme else [successful_scheme]

        for scheme in schemes:
            url = f"{scheme}://{panel_data.panel_domain}/api/user/{username.name}"
            try:
                await disable_request(url, request_data["headers"], request_data["status"])

                successful_scheme = scheme
                message = f"Disabled user: {username.name}"
                await send_logs(message)
                logger.info(message)

                dis_obj = DisabledUsers()
                await dis_obj.add_user(username.name)

                return None
            except SSLError:
                logger.warning(
                    "SSL error with %s while disabling user %s. Trying another scheme.",
                    scheme.upper(),
                    username.name,
                )
                continue
            except httpx.HTTPStatusError as http_error:
                message = (
                    f"HTTP error while disabling user {username.name} using {scheme.upper()}: "
                    f"[{http_error.response.status_code}] {http_error.response.text}"
                )
                await send_logs(message)  # Log to external logs
                logger.error(message)  # Log locally
                continue
            except Exception as error:  # pylint: disable=broad-except
                message = f"An unexpected error occurred: {error}"
                await send_logs(message)
                logger.error(message)
                continue
        await asyncio.sleep(random.randint(2, 5) * (attempt + 1))
    message = (
        f"Failed disable user: {username.name} after 20 attempts. Make sure the panel is running "
        + "and the username and password are correct."
    )
    await send_logs(message)
    logger.error(message)
    raise ValueError(message)


async def get_nodes(panel_data: PanelType) -> list[NodeType] | ValueError:
    """
    Get the IDs of all nodes from the panel API.

    Args:
        panel_data (PanelType): A PanelType object containing
        the username, password, and domain for the panel API.

    Returns:
        list[NodeType]: The list of IDs and other information of all nodes.

    Raises:
        ValueError: If the function fails to get the nodes from both the HTTP
        and HTTPS endpoints.
    """

    def parse_nodes(response_json):
        return [
            NodeType(
                node_id=node["id"],
                node_name=node["name"],
                node_ip=node["address"],
                status=node["status"],
                message=node["message"],
            )
            for node in response_json
        ]

    successful_scheme = None

    for attempt in range(20):
        try:
            get_panel_token = await get_token(panel_data)
            token = get_panel_token.panel_token
        except ValueError as error:
            logger.error("Failed to retrieve token: %s", error)
            raise error

        headers = {
            "Authorization": f"Bearer {token}",
        }

        schemes = ["https", "http"] if not successful_scheme else [successful_scheme]

        for scheme in schemes:
            url = f"{scheme}://{panel_data.panel_domain}/api/nodes"
            try:
                timeout = httpx.Timeout(connect=10.0, read=30.0, write=15.0, pool=10.0)
                async with httpx.AsyncClient(http2=True, timeout=timeout) as client:
                    response = await client.get(url, headers=headers, timeout=10)
                    response.raise_for_status()

                nodes = parse_nodes(response.json())
                successful_scheme = scheme
                logger.info("Successfully retrieved nodes using %s.", scheme.upper())
                return nodes
            except SSLError:
                logger.warning(
                    "SSL error with %s while retrieving nodes. Trying another scheme.",
                    scheme.upper(),
                )
                continue
            except httpx.HTTPStatusError:
                message = f"[{response.status_code}] {response.text}"
                await send_logs(message)
                logger.error(message)
                continue
            except Exception as error:  # pylint: disable=broad-except
                message = f"An unexpected error occurred: {error}"
                await send_logs(message)
                logger.error(message)
                continue
        await asyncio.sleep(random.randint(2, 5) * (attempt + 1))
    message = (
        "Failed to get nodes after 20 attempts. make sure the panel is running "
        + "and the username and password are correct."
    )
    await send_logs(message)
    logger.error(message)
    raise ValueError(message)


async def enable_dis_user(panel_data: PanelType):
    """
    Enable disabled users every 'TIME_TO_ACTIVE_USERS' seconds.
    """
    dis_obj = DisabledUsers()
    while True:
        data = await read_config()
        await asyncio.sleep(int(data["TIME_TO_ACTIVE_USERS"]))
        if DISABLED_USERS:
            await enable_selected_users(panel_data, DISABLED_USERS)
            await dis_obj.read_and_clear_users()
