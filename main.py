import logging
from flask import Flask
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from config import BOT_TOKEN
from pw_handler import pw_handler  # Predefined PW handler
from kgs_handler import kgs_handler  # Predefined KGS handler

logging.basicConfig(format="%(asctime)s - %(message)s", level=logging.INFO)

# Flask App
app = Flask(__name__)

# Owner's Telegram ID (replace with your actual ID)
OWNER_ID = 7507228967  # Replace with your Telegram ID
is_function_enabled = False  # Global flag for owner-only mode
enabled_handlers = {"pw": False, "kgs": False}  # Specific handler access flags

@app.route("/")
def home():
    return "Bot is running on Flask server!"

# /start command
async def start(update, context):
    await update.message.reply_text(
        "𝐻𝑒𝑙𝑙𝑜 𝑢𝑠𝑒𝑟 😉 𝐼'𝑚 𝐴 𝑆𝑖𝑚𝑝𝑙𝑒 𝐵𝑎𝑡𝑐ℎ 𝑡𝑜 𝑇𝑥𝑇 𝑒𝑥𝑡𝑟𝑎𝑐𝑡𝑜𝑟 𝐵𝑜𝑡\n\n"
        "𝑈𝑠𝑒 𝑡ℎ𝑒𝑠𝑒 𝑐𝑜𝑚𝑚𝑎𝑛𝑑𝑠:\n"
        "🫠 /pw - 𝑓𝑜𝑟 𝑃𝑊 𝑐𝑜𝑛𝑡𝑒𝑛𝑡\n"
        "🫠 /kgs - 𝑓𝑜𝑟 𝑲𝒉𝒂𝒏 𝑮𝒍𝒐𝒃𝒂𝒍 𝑺𝒕𝑢𝒅𝒊𝒆𝒔 𝑐𝑜𝑛𝑡𝑒𝑛𝑡"
    )

# /onowner command
async def on_owner(update, context):
    global is_function_enabled
    if update.message.from_user.id == OWNER_ID:
        is_function_enabled = True
        await update.message.reply_text(
            "Owner-only access enabled. All handlers are now restricted to the owner."
        )
    else:
        await update.message.reply_text("You are not authorized to enable owner-only access.")

# /offowner command
async def off_owner(update, context):
    global is_function_enabled
    if update.message.from_user.id == OWNER_ID:
        is_function_enabled = False
        await update.message.reply_text(
            "Owner-only access disabled. All handlers are now accessible to everyone."
        )
    else:
        await update.message.reply_text("You are not authorized to disable owner-only access.")

# Enable specific handlers for everyone
async def enable_handler(update, context):
    if update.message.from_user.id == OWNER_ID:
        if context.args:
            handler_name = context.args[0].lower()
            if handler_name in enabled_handlers:
                enabled_handlers[handler_name] = True
                await update.message.reply_text(f"Handler '{handler_name}' is now enabled for everyone.")
            else:
                await update.message.reply_text(f"Handler '{handler_name}' does not exist.")
        else:
            await update.message.reply_text("Please provide a handler name to enable (e.g., /onpw or /onkgs).")
    else:
        await update.message.reply_text("You are not authorized to enable handlers.")

# Middleware to check permissions
async def check_permission(update, context, handler_name):
    if is_function_enabled:
        if update.message.from_user.id != OWNER_ID and not enabled_handlers.get(handler_name, False):
            await update.message.reply_text("You are not authorized to use this command right now.")
            return False  # Deny access
    return True  # Allow access

if __name__ == "__main__":
    from threading import Thread

    # Start Flask server
    flask_thread = Thread(target=lambda: app.run(host="0.0.0.0", port=5000))
    flask_thread.start()

    # Telegram Bot setup
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # Command Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("onowner", on_owner))
    application.add_handler(CommandHandler("offowner", off_owner))
    application.add_handler(CommandHandler("on", enable_handler))
    application.add_handler(pw_handler)

    # Add predefined handlers
    application.add_handler(pw_handler)
    application.add_handler(kgs_handler)

    # Start the bot
    application.run_polling()
