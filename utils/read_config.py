"""
Read config file and return data.
"""
import json
import os
import sys
import time
import asyncio

from utils.logs import logger

class ConfigManager:
    """
    A class to manage reading and validating configuration data from a JSON file.

    This class provides functionality to:
    - Read the configuration file only when needed (lazy loading).
    - Cache the configuration data for performance optimization.
    - Validate the presence of required configuration elements.
    
    Attributes:
        config_file (str): Path to the configuration file.
        config_data (dict): Cached configuration data from the file.
        last_read_time (float): Timestamp of the last successful read from the file.
    """

    def __init__(self, config_file="config.json"):
        """
        Initialize the ConfigManager with the specified configuration file.

        Args:
            config_file (str): Path to the JSON configuration file. Defaults to "config.json".
        """
        self.config_file = config_file
        self.config_data = None
        self.last_read_time = 0

    async def read_config(self, check_required_elements=None, max_retries=3, retry_delay=5) -> dict:
        """
        Read and return configuration data from the JSON file.

        This method reads the file only if it has been modified since the last read
        or if no data is currently cached. Optionally, it can validate the presence
        of specific required elements in the configuration.

        Args:
            check_required_elements (list, optional): A list of keys that must be present
                in the configuration data. Defaults to None.
            max_retries (int): Maximum number of retries in case of failure. Defaults to 3.
            retry_delay (int): Delay in seconds between retries. Defaults to 5.

        Returns:
            dict: The configuration data.

        Raises:
            ValueError: If a required element is missing from the configuration.
            SystemExit: If the file is missing or lacks critical keys after retries.
        """
        for attempt in range(max_retries):
            try:
                if not os.path.exists(self.config_file):
                    logger.error("Config file not found.")
                    raise FileNotFoundError(f"Config file '{self.config_file}' does not exist.")

                file_mod_time = os.path.getmtime(self.config_file)
                if self.config_data is None or file_mod_time > self.last_read_time:
                    with open(self.config_file, "r", encoding="utf-8") as f:
                        self.config_data = json.load(f)

                    if "BOT_TOKEN" not in self.config_data:
                        logger.error("BOT_TOKEN is not set in the config file.")
                        raise KeyError("BOT_TOKEN is missing in the config file.")
                    if "ADMINS" not in self.config_data:
                        logger.error("ADMINS is not set in the config file.")
                        raise KeyError("ADMINS is missing in the config file.")
                    if "ADMINS" not in self.config_data:
                        logger.error("ADMINS is not set in the config file.")
                        raise KeyError("ADMINS is missing in the config file.")

                    self.last_read_time = time.time()

                if check_required_elements:
                    if check_required_elements is True:
                        check_required_elements = ["PANEL_USERNAME",
                                                    "PANEL_PASSWORD", "PANEL_DOMAIN"]
                    elif not isinstance(check_required_elements, (list, tuple)):
                        raise TypeError("check_required_elements must be a list, tuple, or True.")
                    for element in check_required_elements:
                        if element not in self.config_data:
                            raise ValueError(
                                f"Missing required element '{element}' in the config file."
                            )

                return self.config_data
            except (json.JSONDecodeError, FileNotFoundError, KeyError, ValueError) as error:
                logger.error(
                    "Attempt %d/%d failed with error: %s. Retrying in %d seconds...",
                    attempt + 1, max_retries, error, retry_delay,
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    logger.critical("All attempts to read the config file have failed.")
                    sys.exit()


    async def update_config(self, updated_data: dict, max_retries=3, retry_delay=5):
        """
        Updates the configuration file with the provided data.

        Args:
            updated_data (dict): The data to merge into the existing configuration.
            max_retries (int): Maximum number of retries in case of failure. Defaults to 3.
            retry_delay (int): Delay in seconds between retries. Defaults to 5.

        Returns:
            None
        """
        if self.config_data is None:
            await self.read_config()

        self.config_data.update(updated_data)

        for attempt in range(max_retries):
            try:
                with open(self.config_file, "w", encoding="utf-8") as f:
                    json.dump(self.config_data, f, indent=4)
                self.last_read_time = time.time()
                logger.info("Configuration file updated successfully.")
                return  # Exit after a successful update
            except Exception as e:  # pylint: disable=broad-except
                logger.error(
                    "Attempt %d/%d to update the config file failed: %s. Retrying in %d seconds...",
                    attempt + 1,
                    max_retries,
                    e,
                    retry_delay,
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    logger.critical("All attempts to update the config file have failed.")
                    raise
