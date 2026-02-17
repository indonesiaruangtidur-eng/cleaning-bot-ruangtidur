import os
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

TOKEN = os.getenv("BOT_TOKEN")
SHEET_NAME = os.getenv("SHEET_NAME")

logging.basicConfig(level=logging.INFO)

# ===== GOOGLE SHEET SETUP =====
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

import json

creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

HOTELS = [
    "Sans Hotel Cibanteng",
    "Bubulak Inn",
    "Nirmala Resort",
    "Pandu Raya Home",
    "D'Palma Guest House",
]

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(h, callback_data=h)] for h in HOTELS]
    await update.message.reply_text(
        "🏨 Pilih Hotel:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    context.user_data.clear()

# ===== HOTEL SELECT =====
async def hotel_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["hotel"] = query.data
    context.user_data["step"] = "room"

    await query.message.reply_text("Masukkan Nomor Kamar / Area:")

# ===== MESSAGE HANDLER =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("step")

    if step == "room":
        context.user_data["room"] = update.message.text
        context.user_data["step"] = "photo"
        await update.message.reply_text("Kirim Foto Area:")
    
    elif step == "photo" and update.message.photo:
        file = await update.message.photo[-1].get_file()
        file_path = f"photos/{file.file_id}.jpg"
        os.makedirs("photos", exist_ok=True)
        await file.download_to_drive(file_path)

        # SAVE TO SHEET
        sheet.append_row([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            context.user_data["hotel"],
            context.user_data["room"],
            file_path,
            update.message.from_user.first_name
        ])

        await update.message.reply_text("✅ Laporan tersimpan!")
        context.user_data.clear()

# ===== MAIN =====
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(hotel_selected))
app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_message))

app.run_webhook(
    listen="0.0.0.0",
    port=int(os.environ.get("PORT", 8000)),
    webhook_url=os.getenv("WEBHOOK_URL"),
)
