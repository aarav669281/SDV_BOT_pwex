import logging
import os
import re
import requests
import itertools
from telegram import Update
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from config import LOG_GROUP_ID  # Make sure this exists in config.py

# Constants
ROOT_DIR = os.getcwd()
AUTH_CODE, BATCH_LINK, SUBJECT_IDS = range(3)

# Helper Functions
def extract_batch_id_from_url(url):
    """Extract batch ID from PW batch URL."""
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

def save_batch_contents(batch_name, subject_name, subject_data):
    filename = f"{batch_name}_{subject_name}.txt"
    file_path = os.path.join(ROOT_DIR, filename)
    with open(file_path, 'w', encoding='utf-8') as file:
        for data in subject_data:
            title = data.get("topic", "Untitled")
            link = data.get("url", "")
            if link:
                file.write(f"{title}: {link.strip()}\n")
    return file_path

# Bot Handlers
async def pw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔐 Send your PW Token:")
    return AUTH_CODE

async def handle_auth_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["auth_code"] = update.message.text.strip()
    await update.message.reply_text("🔗 Now send the PW batch link or batch ID:")
    return BATCH_LINK

async def handle_batch_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        batch_url = update.message.text.strip()
        batch_id = extract_batch_id_from_url(batch_url)
        context.user_data["batch_id"] = batch_id

        auth_code = context.user_data["auth_code"]
        subjects = get_subjects(batch_id, auth_code)
        if not subjects:
            await update.message.reply_text("❌ No subjects found or access denied.")
            return ConversationHandler.END

        context.user_data["subjects"] = subjects
        subject_list = "\n".join([f"{sub['_id']}: {sub['subject']}" for sub in subjects])
        await update.message.reply_text(f"📚 Subjects Found:\n\n{subject_list}\n\nSend Subject ID(s) (use `&` to separate multiple):")
        return SUBJECT_IDS
    except Exception as e:
        logging.error(f"Error in handle_batch_link: {e}")
        await update.message.reply_text("⚠️ Error processing your link. Try again.")
        return ConversationHandler.END

async def handle_subject_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth_code = context.user_data["auth_code"]
    batch_id = context.user_data["batch_id"]
    subjects = context.user_data["subjects"]

    subject_ids = update.message.text.strip().split("&")
    await update.message.reply_text("📥 Fetching contents, please wait...")

    for subject_id in subject_ids:
        all_data = []
        page = 1
        while True:
            content = get_batch_contents(batch_id, subject_id.strip(), page, auth_code)
            if not content:
                break
            all_data.extend(content)
            page += 1

        if all_data:
            subject_name = next((s['subject'] for s in subjects if s['_id'] == subject_id.strip()), f"Subject_{subject_id}")
            file_path = save_batch_contents(batch_id, subject_name, all_data)

            try:
                with open(file_path, "rb") as f:
                    await update.message.reply_document(f, caption=f"📁 {subject_name} content extracted.")
            except Exception as e:
                await update.message.reply_text(f"Error sending file: {e}")
                continue

            try:
                with open(file_path, "rb") as f:
                    await context.bot.send_document(
                        chat_id=LOG_GROUP_ID,
                        document=f,
                        caption=f"Log: {subject_name} content sent.",
                    )
            except Exception as e:
                logging.warning(f"Failed to send to log group: {e}")

            os.remove(file_path)
        else:
            await update.message.reply_text(f"❌ No content found for subject ID {subject_id.strip()}")

    return ConversationHandler.END

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"Exception: {context.error}")
    try:
        await context.bot.send_message(chat_id=LOG_GROUP_ID, text=f"⚠️ Error: {context.error}")
    except Exception:
        pass

# Register Handler
pw_handler = ConversationHandler(
    entry_points=[CommandHandler("pw", pw_start)],
    states={
        AUTH_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_auth_code)],
        BATCH_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_batch_link)],
        SUBJECT_IDS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_subject_ids)],
    },
    fallbacks=[],
)
