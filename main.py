import logging
import os
import requests
from telegram import Update
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Constants
LOG_GROUP_ID = -10012345678  # Replace with your log group ID
ROOT_DIR = os.getcwd()

# Conversation states
AUTH_CODE, BATCH_URL, SUBJECT_IDS = range(3)

# Helper Functions
def extract_batch_id(url: str) -> str:
    """Extracts Batch ID from PW URL."""
    if "pw.live/study/batches/" not in url:
        return None
    parts = url.strip("/").split("/")
    return parts[-2] if len(parts) >= 2 else None

def get_batch_details(batch_id: str, auth_token: str):
    """Fetches batch details (name, subjects)."""
    headers = {
        "authorization": f"Bearer {auth_token}",
        "client-id": "5eb393ee95fab7468a79d189",
    }
    url = f"https://api.penpencil.xyz/v3/batches/{batch_id}/details"
    res = requests.get(url, headers=headers)
    return res.json().get("data") if res.status_code == 200 else None

def get_subject_contents(batch_id: str, subject_id: str, auth_token: str):
    """Fetches all content (videos/notes) for a subject."""
    headers = {
        "authorization": f"Bearer {auth_token}",
        "client-id": "5eb393ee95fab7468a79d189",
    }
    contents = []
    page = 1
    while True:
        url = f"https://api.penpencil.xyz/v2/batches/{batch_id}/subject/{subject_id}/contents?page={page}"
        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            break
        data = res.json().get("data", [])
        if not data:
            break
        contents.extend(data)
        page += 1
    return contents

def save_to_file(batch_name: str, subject_name: str, contents: list):
    """Saves content links to a file."""
    filename = f"PW_{batch_name}_{subject_name}.txt"
    filepath = os.path.join(ROOT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        for item in contents:
            title = item.get("topic", "Untitled")
            url = item.get("url", "").strip()
            if url:
                f.write(f"{title}: {url}\n")
    return filepath

# Telegram Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔑 Send your **PW Auth Token**:")
    return AUTH_CODE

async def handle_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = update.message.text.strip()
    context.user_data["auth_token"] = token
    await update.message.reply_text("🌐 Send the **Batch URL** (e.g., https://pw.live/study/batches/BATCH_ID/lectures):")
    return BATCH_URL

async def handle_batch_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    batch_id = extract_batch_id(url)
    if not batch_id:
        await update.message.reply_text("❌ Invalid URL. Send a valid PW batch URL.")
        return BATCH_URL

    token = context.user_data["auth_token"]
    batch_data = get_batch_details(batch_id, token)
    if not batch_data:
        await update.message.reply_text("🚫 Failed to fetch batch. Check token/batch ID.")
        return ConversationHandler.END

    context.user_data["batch_id"] = batch_id
    context.user_data["batch_name"] = batch_data.get("name", "Unknown Batch")
    subjects = batch_data.get("subjects", [])

    if not subjects:
        await update.message.reply_text("📭 No subjects found in this batch.")
        return ConversationHandler.END

    subject_list = "\n".join([f"{sub['_id']}: {sub['subject']}" for sub in subjects])
    await update.message.reply_text(
        f"📚 Subjects in **{context.user_data['batch_name']}**:\n\n{subject_list}\n\n"
        "🔢 Reply with **Subject IDs** (separate multiples with '&'):"
    )
    context.user_data["subjects"] = subjects
    return SUBJECT_IDS

async def handle_subjects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = context.user_data["auth_token"]
    batch_id = context.user_data["batch_id"]
    batch_name = context.user_data["batch_name"]
    subject_ids = [sid.strip() for sid in update.message.text.split("&")]

    await update.message.reply_text("⏳ Fetching content...")

    for subject_id in subject_ids:
        subject_name = next(
            (sub["subject"] for sub in context.user_data["subjects"] if sub["_id"] == subject_id),
            f"Subject_{subject_id}"
        )
        contents = get_subject_contents(batch_id, subject_id, token)
        if not contents:
            await update.message.reply_text(f"❌ No content found for **{subject_name}**.")
            continue

        filepath = save_to_file(batch_name, subject_name, contents)
        with open(filepath, "rb") as f:
            await update.message.reply_document(
                f,
                caption=f"📂 {subject_name} ({len(contents)} items)"
            )
        os.remove(filepath)  # Cleanup

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operation cancelled.")
    return ConversationHandler.END

# Main Handler
pw_handler = ConversationHandler(
    entry_points=[CommandHandler("pw", start)],
    states={
        AUTH_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_token)],
        BATCH_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_batch_url)],
        SUBJECT_IDS: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_subjects)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
