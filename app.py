import os
import json
import logging
from datetime import datetime

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

# ===== 1. CONFIGURATION & LOGGING =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
SHEET_NAME = os.getenv("SHEET_NAME")
GOOGLE_CREDS_RAW = os.getenv("GOOGLE_CREDENTIALS")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# ===== 2. GOOGLE SHEET AUTHENTICATION =====
def service_account_login():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    
    if not GOOGLE_CREDS_RAW:
        logger.error("ERROR: GOOGLE_CREDENTIALS environment variable is missing!")
        return None

    try:
        creds_dict = json.loads(GOOGLE_CREDS_RAW)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open(SHEET_NAME).sheet1
    except Exception as e:
        logger.error(f"ERROR: Failed to connect to Google Sheets: {e}")
        return None

# Inisialisasi Sheet
sheet = service_account_login()

# ===== 3. HOTEL LIST =====
HOTELS = [
    "Sans Hotel Cibanteng",
    "Bubulak Inn",
    "Nirmala Resort",
    "Pandu Raya Home",
    "D'Palma Guest House",
]

# ===== 4. BOT HANDLERS =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(h, callback_data=h)] for h in HOTELS]
    await update.message.reply_text(
        "🏨 *Sistem Laporan Hotel*\n\nSilakan pilih hotel:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    context.user_data.clear()

async def hotel_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["hotel"] = query.data
    context.user_data["step"] = "room"
    await query.message.reply_text(f"✅ Hotel: {query.data}\n\nMasukkan *Nomor Kamar / Area*:", parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("step")

    if step == "room":
        context.user_data["room"] = update.message.text
        context.user_data["step"] = "photo"
        await update.message.reply_text("📸 Sekarang, silakan *Kirim Foto Area*:", parse_mode="Markdown")

    elif step == "photo" and update.message.photo:
        if not sheet:
            await update.message.reply_text("❌ Sistem error: Google Sheet tidak terhubung.")
            return

        photo_file = await update.message.photo[-1].get_file()
        photo_id = photo_file.file_id 

        try:
            # Menyiapkan data untuk baris baru
            row_data = [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                context.user_data.get("hotel", "N/A"),
                context.user_data.get("room", "N/A"),
                f"Telegram_ID: {photo_id}",
                update.message.from_user.first_name
            ]
            
            # Memasukkan ke Google Sheet
            sheet.append_row(row_data)

            await update.message.reply_text("✅ *Laporan tersimpan ke Google Sheets!*", parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Gagal simpan data: {e}")
            await update.message.reply_text(f"❌ Gagal simpan: {e}")
        
        context.user_data.clear()

# ===== 5. MAIN RUNNER =====
if __name__ == "__main__":
    if not TOKEN:
        print("Error: BOT_TOKEN not found!")
    else:
        app = ApplicationBuilder().token(TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(hotel_selected))
        app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_message))

        logger.info("Bot is starting via Webhook...")
        
        app.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get("PORT", 8000)),
            webhook_url=WEBHOOK_URL
        )
