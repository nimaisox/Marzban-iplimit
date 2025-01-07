"""
This module contains the DisabledUsers class
which provides methods for managing disabled users
"""

import json
import os
from datetime import datetime
from utils.logs import logger

DISABLED_USERS = {}


class DisabledUsers:
    """
    A class used to represent the Disabled Users.
    """

    def __init__(self, filename=".disable_users.json"):
        self.filename = filename
        self.disabled_users = self.load_disabled_users()

    def load_disabled_users(self):
        """
        Loads the disabled users from the JSON file.
        """
        try:
            if os.path.exists(self.filename):
                with open(self.filename, "r", encoding="utf-8") as file:
                    data = json.load(file)
                    if isinstance(data, dict) and "disable_user" in data:
                        return {
                            user: datetime.fromisoformat(date)
                            for user, date in data.get("disable_user", {}).items()
                        }
                    else:
                        logger.error("Invalid format in .disable_users.json. Resetting file.")
                        os.remove(self.filename)  # حذف فایل معیوب
                        logger.info("Invalid file removed: %s", self.filename)
                        return {}
            else:
                return {}
        except Exception as error:  # pylint: disable=broad-except
            logger.error("Error loading disabled users: %s", error)
            os.remove(self.filename)  # حذف فایل در صورت بروز خطا
            logger.info("Corrupted file removed: %s", self.filename)
            return {}


    async def save_disabled_users(self):
        """
        Saves the disabled users to the JSON file.
        """
        with open(self.filename, "w", encoding="utf-8") as file:
            json.dump(
                {
                    "disable_user": {
                        user: date.isoformat()
                        for user, date in self.disabled_users.items()
                    }
                },
                file,
            )

    async def add_user(self, username: str):
        """
        Adds a user to the dictionary of disabled users
        with the current timestamp and saves the updated dictionary
        to the JSON file.
        """
        current_time = datetime.now()
        DISABLED_USERS[username] = current_time
        self.disabled_users[username] = current_time
        await self.save_disabled_users()

    async def remove_user(self, username: str):
        """
        Removes a specific user from the dictionary of disabled users
        and saves the updated dictionary to the JSON file.
        """
        if username in self.disabled_users:
            del self.disabled_users[username]
            DISABLED_USERS.pop(username, None)
            await self.save_disabled_users()
            logger.info("User %s has been removed from disabled users.", username)
        else:
            logger.warning("User %s is not in the disabled users list.", username)

    async def get_all_users(self):
        """
        Returns a dictionary of all disabled users with their disable times.
        """
        return self.disabled_users

    async def get_and_remove_expired_users(self, duration_seconds: int):
        """
        Returns a list of users whose disable time has expired
        and removes them from the disabled users list.
        """
        now = datetime.now()
        expired_users = [
            user for user, disabled_time in self.disabled_users.items()
            if (now - disabled_time).total_seconds() >= duration_seconds
        ]
        for user in expired_users:
            del self.disabled_users[user]
            DISABLED_USERS.pop(user, None)
        await self.save_disabled_users()
        return expired_users
