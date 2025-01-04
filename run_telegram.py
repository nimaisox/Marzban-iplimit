"""Run the telegram bot."""

import asyncio

from telegram_bot.main import application, InvalidToken
from utils.logs import logger

async def run_telegram_bot():
    """Run the telegram bot."""
    while True:
        try:
            async with application:
                await application.start()
                await application.updater.start_polling()
                while True:
                    await asyncio.sleep(40)
        except InvalidToken:
            logger.error("Invalid Token! Please provide a valid token for telegram bot.")
            break
        except Exception:  # pylint: disable=broad-except
            continue
