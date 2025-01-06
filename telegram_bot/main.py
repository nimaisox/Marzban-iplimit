"""
This module contains the main functionality of a Telegram bot.
It includes functions for adding admins,
listing admins, setting special limits, and creating a config and more...
"""

import asyncio
import os
import sys
import zipfile
from utils.logs import logger
from utils.read_config import ConfigManager

try:
    from telegram import Update
    from telegram.ext import (
        ApplicationBuilder,
        CommandHandler,
        ContextTypes
    )
    from telegram.error import InvalidToken, BadRequest # pylint: disable=unused-import
except ImportError:
    logger.warning(
        "Module 'python-telegram-bot' is not installed use:"
        + " 'pip install python-telegram-bot' to install it"
    )
    sys.exit()

config_manager = ConfigManager(config_file="config.json")

async def initialize_bot():
    """
    Initialize the bot by loading configuration data.
    """
    try:
        data = await config_manager.read_config(check_required_elements=["BOT_TOKEN"])
        return data["BOT_TOKEN"]
    except KeyError as exc:
        logger.error("BOT_TOKEN is missing in the config file. Error: %s", exc)
        sys.exit()
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit()

bot_token = asyncio.run(initialize_bot())
application = ApplicationBuilder().token(bot_token).build()

START_MESSAGE = """
✨<b>Commands List:</b>

<b>/start</b>
<code>Start the bot</code>

<b>/add_special_limit</b>
<code>Add a user-specific IP limit, e.g., test_user limit: 5 IPs</code>

<b>/remove_special_limit</b>
<code>Remove a user-specific IP limit, e.g., test_user limit: 5 IPs</code>

<b>/show_special_limit</b>
<code>Display the list of special limits</code>

<b>/add_admin</b>
<code>Grant access to another chat ID and create a new admin for the bot</code>

<b>/remove_admin</b>
<code>Revoke admin access from a chat ID</code>

<b>/show_admins</b>
<code>Display the list of active bot admins</code>

<b>/add_except_user</b>
<code>Add a user to the exception list</code>

<b>/remove_except_user</b>
<code>Remove a user from the exception list</code>

<b>/show_except_users</b>
<code>Display the list of exception users</code>

<b>/setup</b>
<code>Configure panel information (username, password, domain.)</code>

<b>/country_code</b>
<code>Set your country code. Only IPs from the specified country are considered to improve accuracy</code>

<b>/set_general_limit_number</b>
<code>Set the default limit for users not in the special limit list</code>

<b>/set_check_interval</b>
<code>Define the interval time for user checks</code>

<b>/set_time_to_active_users</b>
<code>Define the activity timeout for users</code>

<b>/backup</b>
<code>Sends a zip file containing 'config.json' & '.disable_users.json'.</code>
"""

async def is_admin(update: Update) -> bool:
    """
    Check if the user is an admin.
    """
    chat_id = update.message.chat_id
    config = await config_manager.read_config()
    admins = config.get("ADMINS", [])

    if str(chat_id) in admins:  # Chat IDs are typically strings in the config
        return True

    await update.message.reply_html(
        text="🚫 You are not an admin.\nContact an admin to get access."
    )
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Start function for the bot. Checks if the user is an admin and responds accordingly.
    """
    if not await is_admin(update):
        await update.message.reply_html(
            text="🚫 You are not an admin.\nContact an admin to get access."
        )
        return
    else:
        await update.message.reply_html(START_MESSAGE)

async def backup(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """
    Create a zip file containing 'config.json' & '.disable_users.json' 
    and send it to the user. If a file is missing, it will skip it 
    and notify the user.

    Args:
        update (Update): Incoming update object from Telegram.
        _context (ContextTypes.DEFAULT_TYPE): Context for the current conversation.
    """
    if not await is_admin(update):
        return

    files_to_zip = ["config.json", ".disable_users.json"]
    backup_filename = "backup.zip"
    with zipfile.ZipFile(backup_filename, "w") as zipf:
        for file in files_to_zip:
            if os.path.exists(file):
                zipf.write(file)
            else:
                await update.message.reply_html(
                    text=f"⚠️ File <code>{file}</code> not found. Skipping..."
                )
    try:
        await update.message.reply_document(
            document=open(backup_filename, "rb"),
            caption="📦 Here is your backup file containing the requested files."
        )
    except Exception as e:  # pylint: disable=broad-except
        await update.message.reply_html(
            text=f"🚨 Error occurred while sending the backup file: <code>{str(e)}</code>"
        )
    if os.path.exists(backup_filename):
        os.remove(backup_filename)

async def add_admin(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """
    Grant access to another chat ID and create a new admin for the bot.
    """
    try:
        if not await is_admin(update):
            return


        text = update.message.text.strip().split()
        if len(text) < 2 or not text[1].isdigit():
            await update.message.reply_html(
                text="🚫 Invalid format! Use: <code>/add_admin chat_id</code>"
            )
            return

        chat_id = text[1]
        config = await config_manager.read_config()
        admins = config.get("ADMINS", [])

        if chat_id in admins:
            await update.message.reply_html(
                text=f"⚠️ Chat ID <b>{chat_id}</b> is already an admin."
            )
            return

        admins.append(chat_id)
        config["ADMINS"] = admins
        await config_manager.update_config(config)

        await update.message.reply_html(
            text=f"✅ Chat ID <b>{chat_id}</b> has been successfully added as an admin."
        )
    except Exception as e: # pylint: disable=broad-except
        await update.message.reply_html(
            text=f"🚨 Error occurred while adding admin: <code>{str(e)}</code>"
        )

async def remove_admin(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """
    Revoke admin access from a chat ID.
    """
    try:
        if not await is_admin(update):
            return

        text = update.message.text.strip().split()
        if len(text) < 2 or not text[1].isdigit():
            await update.message.reply_html(
                text="🚫 Invalid format! Use: <code>/remove_admin chat_id</code>"
            )
            return

        chat_id = text[1]
        config = await config_manager.read_config()
        admins = config.get("ADMINS", [])

        if chat_id not in admins:
            await update.message.reply_html(
                text=f"⚠️ Chat ID <b>{chat_id}</b> is not an admin."
            )
            return

        admins.remove(chat_id)
        config["ADMINS"] = admins
        await config_manager.update_config(config)

        await update.message.reply_html(
            text=f"✅ Chat ID <b>{chat_id}</b> has been successfully removed from admin list."
        )
    except Exception as e: # pylint: disable=broad-except
        await update.message.reply_html(
            text=f"🚨 Error occurred while removing admin: <code>{str(e)}</code>"
        )

async def show_admins(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """
    Display the list of active bot admins.
    """
    if not await is_admin(update):
        return

    try:
        config = await config_manager.read_config()
        admins = config.get("ADMINS", [])

        if not admins:
            await update.message.reply_html(
                text="ℹ️ There are no admins configured for this bot."
            )
            return

        admins_list = "\n".join([f"🔹 <code>{admin}</code>" for admin in admins])
        await update.message.reply_html(
            text=f"👥 Active Admins:\n{admins_list}"
        )
    except Exception as e: # pylint: disable=broad-except
        await update.message.reply_html(
            text=f"🚨 Error occurred while fetching admin list: <code>{str(e)}</code>"
        )


async def add_special_limit(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """
    Adds or updates the special limit for a given username in the config file.
    """
    try:
        if not await is_admin(update):
            return

        text = update.message.text.strip().split()
        if len(text) != 3 or not text[1].isdigit():
            await update.message.reply_html(
                text="🚫 Invalid format! Use: <code>/add_special_limit username limit</code>"
            )
            return

        _, username, limit = text
        limit = int(limit)

        config = await config_manager.read_config()
        special_limit = config.get("SPECIAL_LIMIT", {})
        set_before = 1 if username in special_limit else 0
        special_limit[username] = limit
        config["SPECIAL_LIMIT"] = special_limit
        await config_manager.update_config(config)

        if set_before:
            await update.message.reply_html(
                text=f"⚠️ Limit for <b>{username}</b> updated to <code>{limit}</code> IPs."
            )
        else:
            await update.message.reply_html(
                text=f"✅ Special limit for <b>{username}</b> set to <code>{limit}</code> IPs."
            )
    except Exception as e:  # pylint: disable=broad-except
        await update.message.reply_html(
            text=f"🚨 Error occurred while adding limit: <code>{str(e)}</code>"
        )


async def remove_special_limit(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """
    Removes a user-specific special limit from the config file.
    """
    try:
        if not await is_admin(update):
            return

        username = update.message.text.strip().split()[1]

        config = await config_manager.read_config()
        special_limit = config.get("SPECIAL_LIMIT", {})
        if username in special_limit:
            del special_limit[username]
            config["SPECIAL_LIMIT"] = special_limit
            await config_manager.update_config(config)
            await update.message.reply_html(
                text=f"✅ Special limit for <b>{username}</b> removed successfully."
            )
        else:
            await update.message.reply_html(
                text=f"🚫 No special limit found for <b>{username}</b>."
            )
    except Exception as e:  # pylint: disable=broad-except
        await update.message.reply_html(
            text=f"🚨 Error occurred while removing limit: <code>{str(e)}</code>"
        )


async def show_special_limit(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """
    Retrieves and formats the special limits from the config file for display.
    """
    try:
        if not await is_admin(update):
            return

        config = await config_manager.read_config()
        special_limit = config.get("SPECIAL_LIMIT", {})
        if not special_limit:
            await update.message.reply_html(
                text="🚫 No special limits found."
            )
            return

        formatted_limits = [
            f"<b>{user}</b>: <code>{limit}</code>" for user, limit in special_limit.items()
        ]
        messages = [
            "\n".join(formatted_limits[i:i + 100]) for i in range(0, len(formatted_limits), 100)
        ]
        for message in messages:
            await update.message.reply_html(text=message)
    except Exception as e:  # pylint: disable=broad-except
        await update.message.reply_html(
            text=f"🚨 Error occurred while retrieving limits: <code>{str(e)}</code>"
        )

async def add_except_user(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """
    Add or update a user in the exception list in the config file.
    """
    try:
        if not await is_admin(update):
            return

        text = update.message.text.strip().split()
        if len(text) < 2:
            await update.message.reply_html(
                text="🚫 Invalid format! Use: <code>/add_except_user username</code>"
            )
            return

        username = text[1]
        config = await config_manager.read_config()
        except_users = config.get("EXCEPT_USERS", {})

        if username in except_users:
            await update.message.reply_html(
                text=f"⚠️ User <b>{username}</b> is already in the exception list. Updating entry."
            )
        except_users[username] = "Updated info"
        config["EXCEPT_USERS"] = except_users
        await config_manager.update_config(config)
        await update.message.reply_html(
            text=f"✅ User <b>{username}</b> added/updated in the exception list."
        )
    except IndexError:
        await update.message.reply_html(
            text="🚫 Invalid format! Use: <code>/add_except_user username</code>"
        )
    except Exception as e:  # pylint: disable=broad-except
        await update.message.reply_html(
            text=f"🚨 Error occurred while adding/updating exception user: <code>{str(e)}</code>"
        )

async def remove_except_user(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """
    Remove a user from the exception list in the config file.
    """
    try:
        if not await is_admin(update):
            return

        username = update.message.text.strip().split()[1]
        config = await config_manager.read_config()
        except_users = config.get("EXCEPT_USERS", [])
        if username in except_users:
            except_users.remove(username)
            config["EXCEPT_USERS"] = except_users
            await config_manager.update_config(config)
            await update.message.reply_html(
                text=f"✅ User <b>{username}</b> removed from the exception list."
            )
        else:
            await update.message.reply_html(
                text=f"🚫 User <b>{username}</b> is not in the exception list."
            )
    except IndexError:
        await update.message.reply_html(
            text="🚫 Invalid format! Use: <code>/remove_except_user username</code>"
        )
    except Exception as e:  # pylint: disable=broad-except
        await update.message.reply_html(
            text=f"🚨 Error occurred while removing exception user: <code>{str(e)}</code>"
        )


async def show_except_users(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """
    Display the list of exception users.
    """
    try:
        if not await is_admin(update):
            return

        config = await config_manager.read_config()
        except_users = config.get("EXCEPT_USERS", [])
        if not except_users:
            await update.message.reply_html(
                text="🚫 No exception users found."
            )
            return

        formatted_users = [f"<b>{user}</b>" for user in except_users]
        messages = [
            "\n".join(formatted_users[i:i + 100]) for i in range(0, len(formatted_users), 100)
        ]
        for message in messages:
            await update.message.reply_html(
                text=f"📋 <b>Exception Users:</b>\n{message}"
            )
    except Exception as e:  # pylint: disable=broad-except
        await update.message.reply_html(
            text=f"🚨 Error occurred while retrieving exception users: <code>{str(e)}</code>"
        )

async def set_general_limit_number(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """
    Set the default limit for users not in the special limit list.
    """
    try:
        if not await is_admin(update):
            return

        text = update.message.text.strip().split()
        if len(text) < 2 or not text[1].isdigit():
            await update.message.reply_html(
                text="🚫 Invalid format! Use: <code>/set_general_limit_number limit</code>"
            )
            return

        limit = int(text[1])
        config = await config_manager.read_config()
        previous_limit = config.get("GENERAL_LIMIT")

        config["GENERAL_LIMIT"] = limit
        await config_manager.update_config(config)

        if previous_limit is not None:
            await update.message.reply_html(
                text=f"✅ General limit updated to <code>{limit}</code> successfully."
            )
        else:
            await update.message.reply_html(
                text=f"✅ General limit set to <code>{limit}</code> successfully."
            )
    except Exception as e:  # pylint: disable=broad-except
        await update.message.reply_html(
            text=f"🚨 Error occurred while setting general limit: <code>{str(e)}</code>"
        )

async def set_country_code(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """
    Set the country code (IP_LOCATION) for the bot.
    """
    try:
        if not await is_admin(update):
            return

        text = update.message.text.strip().split()
        if len(text) < 2:
            await update.message.reply_html(
                text="🚫 Invalid format! Use: <code>/country_code code</code>\n"
                     "Examples:\n<code>/country_code IR</code> (Iran)\n"
                     "<code>/country_code US</code> (United States)"
            )
            return

        country_code = text[1].upper()
        config = await config_manager.read_config()
        previous_code = config.get("IP_LOCATION")

        config["IP_LOCATION"] = country_code
        await config_manager.update_config(config)

        if previous_code:
            await update.message.reply_html(
                text=f"✅ Country code updated to <code>{country_code}</code> successfully."
            )
        else:
            await update.message.reply_html(
                text=f"✅ Country code set to <code>{country_code}</code> successfully."
            )
    except Exception as e: # pylint: disable=broad-except
        await update.message.reply_html(
            text=f"🚨 Error occurred while setting IP_LOCATION: <code>{str(e)}</code>"
        )


async def set_check_interval(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """
    Set the interval time (CHECK_INTERVAL) for user checks.
    """
    try:
        if not await is_admin(update):
            return

        text = update.message.text.strip().split()
        if len(text) < 2 or not text[1].isdigit():
            await update.message.reply_html(
                text="🚫 Invalid format! Use: <code>/set_check_interval seconds</code>\n"
                     "Example: <code>/set_check_interval 300</code> (5 minutes)"
            )
            return

        interval = int(text[1])
        config = await config_manager.read_config()
        previous_interval = config.get("CHECK_INTERVAL")

        config["CHECK_INTERVAL"] = interval
        await config_manager.update_config(config)

        if previous_interval is not None:
            await update.message.reply_html(
                text=f"✅ CHECK_INTERVAL updated to <code>{interval}</code> seconds successfully."
            )
        else:
            await update.message.reply_html(
                text=f"✅ CHECK_INTERVAL set to <code>{interval}</code> seconds successfully."
            )
    except Exception as e: # pylint: disable=broad-except
        await update.message.reply_html(
            text=f"🚨 Error occurred while setting CHECK_INTERVAL: <code>{str(e)}</code>"
        )


async def set_time_to_active_users(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """
    Set the activity timeout (TIME_TO_ACTIVE_USERS) for users.
    """
    try:
        if not await is_admin(update):
            return

        text = update.message.text.strip().split()
        if len(text) < 2 or not text[1].isdigit():
            await update.message.reply_html(
                text="🚫 Invalid format! Use: <code>/set_time_to_active_users seconds</code>\n"
                     "Example: <code>/set_time_to_active_users 7200</code> (2 hours)"
            )
            return

        timeout = int(text[1])
        config = await config_manager.read_config()
        previous_timeout = config.get("TIME_TO_ACTIVE_USERS")

        config["TIME_TO_ACTIVE_USERS"] = timeout
        await config_manager.update_config(config)

        if previous_timeout is not None:
            await update.message.reply_html(
               text=f"✅ TIME_TO_ACTIVE_USERS set to <code>{timeout}</code> seconds."
            )
        else:
            await update.message.reply_html(
                text=f"✅ TIME_TO_ACTIVE_USERS set to <code>{timeout}</code> seconds."
            )
    except Exception as e: # pylint: disable=broad-except
        await update.message.reply_html(
            text=f"🚨 Error occurred while setting TIME_TO_ACTIVE_USERS: <code>{str(e)}</code>"
        )


async def setup_panel(update: Update, _context: ContextTypes.DEFAULT_TYPE):
    """
    Setup or update panel information including domain, username, and password.
    """
    try:
        if not await is_admin(update):
            return

        text = update.message.text.strip().split(maxsplit=3)
        if len(text) < 4:
            await update.message.reply_html(
                text="🚫 Invalid format! Use:\n"
                     "<code>/setup_panel domain username password</code>\n"
                     "Example:\n<code>/setup_panel https://example.com:443 admin admin123</code>"
            )
            return

        _, domain, username, password = text
        config = await config_manager.read_config()

        is_update = all(
            key in config and config[key]
            for key in ["PANEL_DOMAIN", "PANEL_USERNAME", "PANEL_PASSWORD"]
        )

        config["PANEL_DOMAIN"] = domain
        config["PANEL_USERNAME"] = username
        config["PANEL_PASSWORD"] = password
        await config_manager.update_config(config)

        if is_update:
            status_message = "✅ Panel information updated successfully:"
        else:
            status_message = "✅ Panel information set successfully:"

        await update.message.reply_html(
            text=f"{status_message}\n"
                 f"<b>Domain:</b> <code>{domain}</code>\n"
                 f"<b>Username:</b> <code>{username}</code>\n"
                 f"<b>Password:</b> <code>{password}</code>"
        )
    except Exception as e:  # pylint: disable=broad-except
        await update.message.reply_html(
            text=f"🚨 Error occurred while setting up panel: <code>{str(e)}</code>"
        )

# ثبت هندلر در برنامه
application.add_handler(CommandHandler("backup", backup))
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("add_special_limit", add_special_limit))
application.add_handler(CommandHandler("remove_special_limit", remove_special_limit))
application.add_handler(CommandHandler("show_special_limit", show_special_limit))
application.add_handler(CommandHandler("set_general_limit_number", set_general_limit_number))
application.add_handler(CommandHandler("country_code", set_country_code))
application.add_handler(CommandHandler("set_check_interval", set_check_interval))
application.add_handler(CommandHandler("set_time_to_active_users", set_time_to_active_users))
application.add_handler(CommandHandler("setup_panel", setup_panel))
