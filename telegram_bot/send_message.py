"""
Send logs to telegram bot.
"""

from telegram_bot.main import application
from telegram_bot.utils import check_admin
from utils.logs import logger


async def send_logs(msg):
    """Send logs to all admins."""
    admins = await check_admin()
    retries = 2
    if admins:
        for admin in admins:
            for _ in range(retries):
                try:
                    await application.bot.sendMessage(
                        chat_id=admin, text=msg, parse_mode="HTML"
                    )
                    break
                except Exception as e:  # pylint: disable=broad-except
                    logger.error("Failed to send message to admin %s: %s", admin, e)
    else:
        logger.warning("No admins found.")
