"""
Send logs to telegram bot.
"""
import html
import re
from telegram_bot.main import application, BadRequest,asyncio
from telegram_bot.utils import check_admin
from utils.logs import logger

def sanitize_message(msg: str, parse_mode: str = "HTML") -> str:
    """
    Sanitize the message to ensure it conforms to Telegram's formatting rules.

    Args:
        msg (str): The original message text.
        parse_mode (str): The formatting mode, e.g., "HTML" or "Markdown".

    Returns:
        str: The sanitized message.
    """
    if parse_mode == "HTML":
        msg = html.escape(msg)

        allowed_tags = ["b", "i", "u", "a", "code", "pre"]
        tag_pattern = re.compile(r"</?([a-zA-Z]+)[^>]*>")
        msg = re.sub(
            tag_pattern,
            lambda match: match.group(0) if match.group(1) in allowed_tags else "",
            msg,
        )

    elif parse_mode == "Markdown":
        pass

    max_length = 4096
    if len(msg) > max_length:
        msg = msg[:max_length] + "..."

    return msg

async def send_logs(msg):
    """Send logs to all admins."""
    admins = await check_admin()
    retries = 3
    delay_between_retries = 2
    delay_between_messages = 1

    if not admins:
        logger.warning("No admins found.")
        return

    sanitized_msg = sanitize_message(msg, parse_mode="HTML")

    for admin in admins:
        for attempt in range(retries):
            try:
                await application.bot.sendMessage(
                    chat_id=admin, text=sanitized_msg, parse_mode="HTML"
                )
                logger.info("Message sent successfully to admin %s.", admin)
                break
            except BadRequest as e:
                logger.error(
                    "BadRequest error while sending message to admin %s: %s",
                    admin, e
                )
                break
            except Exception as e:  # pylint: disable=broad-except
                logger.error(
                    "Unexpected error while sending message to admin %s: %s",
                    admin, e
                )
                if attempt < retries - 1:
                    await asyncio.sleep(delay_between_retries)
                else:
                    logger.error("All attempts failed for admin %s.", admin)
        await asyncio.sleep(delay_between_messages)
