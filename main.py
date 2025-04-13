import logging
import os
import re
import requests
from telegram import Update
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from config import LOG_GROUP_ID

ROOT_DIR = os.getcwd()
AUTH_CODE, BATCH_LINK = range(2)

def extract_batch_id_from_url(url):
    match = re.search(r'/batch/([a-zA-Z0-9]+)', url)
    return match.group(1) if match else url.strip()

def get_subjects(batch_id, auth_code):
    headers = {
        'authorization': f"Bearer {auth_code}",
        'client-id': '5eb393ee95fab7468a79d189',
        'user-agent': 'Android',
    }
    response = requests.get(f'https://api.penpencil.xyz/v3/batches/{batch_id}/details', headers=headers)
    if response.status_code == 200:
        return response.json().get("data", {}).get("subjects", [])
    return []

def get_batch_contents(batch_id, subject_id, page, auth_code):
    headers = {
        'authorization': f"Bearer {auth_code}",
        'client-id': '5eb393ee95fab7468a79d189',
        'user-agent': 'Android',
    }
    params = {'page': page, 'contentType': 'exercises-notes-videos'}
    response = requests.get(f'https://api.penpencil.xyz/v2/batches/{batch_id}/subject/{subject_id}/contents', params=params, headers=headers)
    if response.status_code == 200:
        return response.json().get("data", [])
    return []

def save_full_batch(batch_id, subjects, auth_code):
    filename = f"{batch_id}_full_batch.txt"
    file_path = os.path.join(ROOT_DIR, filename)
    with open(file_path, 'w', encoding='utf-8') as file:
        for subject in subjects:
            subject_name = subject['subject']
            subject_id = subject['_id']
            file.write(f"\n==== {subject_name.upper()} ====\n")

            page = 1
            while True:
                content = get_batch_contents(batch_id, subject_id, page, auth_code)
                if not content:
                    break
                for item in content:
                    title = item.get("topic", "Untitled")
                    link = item.get("url", "").strip()
                    if link:
                        file.write(f"{title}: {link}\n")
                page += 1
    return file_path

# Telegram Bot Conversation
async def pw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔐 Send your PW Token:")
    return AUTH_CODE

async def handle_auth_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["auth_code"] = update.message.text.strip()
    await update.message.reply_text("🔗 Now send the PW batch URL:")
    return BATCH_LINK

async def handle_batch_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        batch_url = update.message.text.strip()
        batch_id = extract_batch_id_from_url(batch_url)
        auth_code = context.user_data["auth_code"]

        subjects = get_subjects(batch_id, auth_code)
        if not subjects:
            await update.message.reply_text("❌ No subjects found or token is invalid.")
            return ConversationHandler.END

        await update.message.reply_text("📥 Fetching all subjects and contents...")

        file_path = save_full_batch(batch_id, subjects, auth_code)

        # Send to user
        with open(file_path, "rb") as f:
            await update.message.reply_document(f, caption=f"📁 Full batch content extracted.")

        # Send to log group
        try:
            with open(file_path, "rb") as f:
                await context.bot.send_document(
                    chat_id=LOG_GROUP_ID,
                    document=f,
                    caption=f"Log: {batch_id} full content.",
                )
        except Exception as e:
            logging.warning(f"Could not send to log group: {e}")

        os.remove(file_path)

    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text("⚠️ Error occurred. Check token or URL.")
    return ConversationHandler.END

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"Exception: {context.error}")
    try:
        await context.bot.send_message(chat_id=LOG_GROUP_ID, text=f"⚠️ Error: {context.error}")
    except Exception:
        pass

# Final Handler Registration
pw_handler = ConversationHandler(
    entry_points=[CommandHandler("pw", pw_start)],
    states={
        AUTH_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_auth_code)],
        BATCH_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_batch_link)],
    },
    fallbacks=[],
)
