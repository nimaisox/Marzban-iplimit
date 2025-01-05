"""
This module contains functions to parse and validate logs.
"""

import ipaddress
import random
import re
import sys

from utils.check_usage import ACTIVE_USERS
from utils.read_config import ConfigManager
from utils.types import UserType
from utils.logs import logger

try:
    import httpx
except ImportError:
    print("Module 'httpx' is not installed use: 'pip install httpx' to install it")
    sys.exit()

INVALID_EMAILS = [
    "API]",
    "Found",
    "(normal)",
    "timeout",
    "EOF",
    "address",
    "INFO",
    "request",
]
INVALID_IPS = {
    "1.1.1.1",
    "8.8.8.8",
}
VALID_IPS = []
CACHE = {}

API_ENDPOINTS = {
    "http://ip-api.com/json/": "countryCode",
    "https://ipinfo.io/": "country",
    "https://api.iplocation.net/?ip=": "country_code2",
    "https://ipapi.co/": None,
}


async def remove_id_from_username(username: str) -> str:
    """
    Remove the ID from the start of the username.
    Args:
        username (str): The username string from which to remove the ID.

    Returns:
        str: The username with the ID removed.
    """
    return re.sub(r"^\d+\.", "", username)


def is_valid_proxy(proxy_url: str) -> bool:
    """
    Validate the proxy format to ensure it's either socks5 or http.
    Proxy format:
      - Protocol: socks5 or http
      - Optional username and password
      - Host: IP or domain
      - Port: Mandatory

    Examples of valid formats:
      - socks5://username:password@127.0.0.1:8080
      - http://127.0.0.1:3128
    """
    proxy_regex = re.compile(
        r"^(?P<protocol>socks5|http)://"
        r"(?:(?P<username>[\w\-._~]+):(?P<password>[\w\-._~]+)@)?"
        r"(?P<host>[\w\-._~]+|\d{1,3}(\.\d{1,3}){3})"
        r":(?P<port>\d{2,5})$"
    )
    return bool(proxy_regex.match(proxy_url))


async def check_ip(ip_address: str, config_manager: ConfigManager) -> None | str:
    """
    Check the geographical location of an IP address.

    Get the location of the IP address.
    The result is cached to avoid unnecessary requests for the same IP address.

    Args:
        ip_address (str): The IP address to check.
        config_manager (ConfigManager): Instance of ConfigManager to fetch configuration.

    Returns:
        str: The country code of the IP address location, or None.
    """
    if ip_address in CACHE:
        return CACHE[ip_address]

    endpoint, key = random.choice(list(API_ENDPOINTS.items()))
    url = endpoint + ip_address
    if "ipapi.co" in endpoint:
        url += "/country"

    try:
        config_data = await config_manager.read_config()
        proxy_url = config_data.get("PROXY_FOR_API", None)

        if proxy_url and not is_valid_proxy(proxy_url):
            logger.error(
                "Invalid proxy format: %s. A valid proxy must follow one of these formats: "
                "'socks5://username:password@host:port' or 'http://username:password@host:port', "
                "where username and password are optional.",
                proxy_url
            )
            sys.exit(1)

        timeout = httpx.Timeout(connect=10.0, read=30.0, write=15.0, pool=10.0)

        async with httpx.AsyncClient(http2=True,
                                      proxy=proxy_url if proxy_url else None,
                                        timeout=timeout) as client:
            logger.info("Fetching IP info for %s using %s",
                         ip_address, "proxy" if proxy_url else "direct connection")
            resp = await client.get(url)

        resp.raise_for_status()

        if "ipapi.co" in endpoint:
            country = resp.text.strip()
            if not country or len(country) != 2:
                logger.error("Invalid response from ipapi.co: %s", resp.text)
                return None
        else:
            info = resp.json()
            country = info.get(key) if key else resp.text.strip()

        if country:
            CACHE[ip_address] = country
        return country

    except (httpx.ProxyError,
             httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
        proxy_info = f" using proxy {proxy_url}" if proxy_url else ""
        logger.error("HTTP error%s: %s", proxy_info, e)
        if isinstance(e, httpx.HTTPStatusError):
            logger.error("HTTP status %s for %s: %s", e.response.status_code, url, e.response.text)

    except Exception as e: # pylint: disable=broad-except
        proxy_info = f" using proxy {proxy_url}" if proxy_url else ""
        logger.error("Unexpected error%s: %s", proxy_info, e)

    return None


async def is_valid_ip(ip: str) -> bool:
    """
    Check if a string is a valid IP address.

    This function uses the ipaddress module to try to create an IP address object from the string.

    Args:
        ip (str): The string to check.

    Returns:
        bool: True if the string is a valid IP address, False otherwise.
    """
    try:
        ip_obj = ipaddress.ip_address(ip)
        return not ip_obj.is_private
    except ValueError:
        return False


IP_V6_REGEX = re.compile(r"\[([0-9a-fA-F:]+)\]:\d+\s+accepted")
IP_V4_REGEX = re.compile(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")
EMAIL_REGEX = re.compile(r"email:\s*([A-Za-z0-9._%+-]+)")


async def parse_logs(log: str, config_manager: ConfigManager) -> dict[str, UserType]:
    """
    Asynchronously parse logs to extract and validate IP addresses and emails.

    Args:
        log (str): The log to parse.
        config_manager (ConfigManager): Instance of ConfigManager to fetch configuration.

    Returns:
        dict[str, UserType]: A dictionary of active users with their associated IPs.
    """
    try:
        config_data = await config_manager.read_config()
        invalid_ips = config_data.get("INVALID_IPS", set())
        ip_location = config_data.get("IP_LOCATION", "None")

        if invalid_ips:
            INVALID_IPS.update(invalid_ips)

        lines = log.splitlines()

        for line in lines:
            if "accepted" not in line or "BLOCK]" in line:
                continue

            ip_v6_match = IP_V6_REGEX.search(line)
            ip_v4_match = IP_V4_REGEX.search(line)
            email_match = EMAIL_REGEX.search(line)

            ip = None
            if ip_v6_match:
                ip = ip_v6_match.group(1)
            elif ip_v4_match:
                ip = ip_v4_match.group(1)

            if not ip:
                continue

            if ip not in VALID_IPS:
                is_valid_ip_test = await is_valid_ip(ip)
                if not is_valid_ip_test or ip in INVALID_IPS:
                    INVALID_IPS.add(ip)
                    continue

                if ip_location != "None":
                    country = await check_ip(ip, config_manager)
                    if country and country == ip_location:
                        VALID_IPS.append(ip)
                    else:
                        INVALID_IPS.add(ip)
                        continue

            if email_match:
                email = email_match.group(1)
                email = await remove_id_from_username(email)
                if email in INVALID_EMAILS:
                    continue
            else:
                continue

            user = ACTIVE_USERS.get(email)
            if user:
                user.ip.append(ip)
            else:
                ACTIVE_USERS[email] = UserType(name=email, ip=[ip])

        return ACTIVE_USERS

    except KeyError as error:
        logger.error("Missing key in configuration: %s", error)
        raise ValueError(f"Configuration error: missing key {error}") from error
    except ValueError as error:
        logger.error("Invalid value in configuration: %s", error)
        raise
    except Exception as error:
        logger.error("Unexpected error in parse_logs: %s", error)
        raise
