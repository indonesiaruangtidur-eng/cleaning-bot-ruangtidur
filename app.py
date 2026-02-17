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
        # Mengubah string JSON dari environment variable menjadi dictionary
        creds_dict = json.loads(GOOGLE_CREDS_RAW)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open(SHEET_NAME).sheet1
    except json.JSONDecodeError as e:
        logger.error(f"ERROR: Google Credentials JSON is invalid: {e}")
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

    # Step 1: Input Room/Area
    if step == "room":
        context.user_data["room"] = update.message.text
        context.user_data["step"] = "photo"
        await update.message.reply_text("📸 Sekarang, silakan *Kirim Foto Area*:", parse_mode="Markdown")

    # Step 2: Receive Photo & Save to Sheet
    elif step == "photo" and update.message.photo:
        if not sheet:
            await update.message.reply_text("❌ Terjadi kesalahan sistem (Sheet tidak terhubung).")
            return

        # Ambil foto dengan resolusi tertinggi
        photo_file = await update.message.photo[-1].get_file()
        # Catatan: Ini hanya menyimpan File ID Telegram, bukan URL permanen.
        photo_id = photo_file.file_id 

        try:
            # SAVE TO SHEET
            sheet.append_row(
