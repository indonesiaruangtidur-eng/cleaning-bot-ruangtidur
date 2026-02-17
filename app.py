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
PORT = int(os.environ.get("PORT", 8000))

# ===== 2. VALIDASI ENV VARIABLES =====
missing = []
if not TOKEN: missing.append("BOT_TOKEN")
if not SHEET_NAME: missing.append("SHEET_NAME")
if not GOOGLE_CREDS_RAW: missing.append("GOOGLE_CREDENTIALS")

if missing:
    logger.error(f"STARTUP FAILED — Missing environment variables: {', '.join(missing)}")
    exit(1)

# ===== 3. GOOGLE SHEET AUTHENTICATION =====
def get_sheet():
    """Buat koneksi baru ke Google Sheets setiap dipanggil."""
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    try:
        creds_dict = json.loads(GOOGLE_CREDS_RAW)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open(SHEET_NAME).sheet1
    except json.JSONDecodeError:
        logger.error("GOOGLE_CREDENTIALS bukan format JSON yang valid!")
        return None
    except Exception as e:
        logger.error(f"Gagal koneksi ke Google Sheets: {e}")
        return None

# ===== 4. HOTEL LIST =====
# Sesuaikan dengan nama hotel yang Anda manage
HOTELS = [
    "Sans Hotel Cibanteng",
    "Bubulak Inn",
    "Nirmala Resort",
    "Pandu Raya Home",
    "D'Palma Guest House",
]

# ===== 5. SIMPAN KE SHEET =====
async def simpan_ke_sheet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sheet = get_sheet()
    if not sheet:
        await update.message.reply_text("❌ Sistem error: Gagal terhubung ke Google Sheet.")
        return

    try:
        # Resolve foto kamar jadi direct link
        photo_room_link = "-"
        photo_room_id = context.user_data.get("photo_room", "-")
        if photo_room_id != "-":
            photo_room_file = await context.bot.get_file(photo_room_id)
            photo_room_link = photo_room_file.file_path

        # Resolve foto kamar mandi jadi direct link
        photo_bathroom_link = "-"
        photo_bathroom_id = context.user_data.get("photo_bathroom", "-")
        if photo_bathroom_id != "-":
            photo_bathroom_file = await context.bot.get_file(photo_bathroom_id)
            photo_bathroom_link = photo_bathroom_file.file_path

        row_data = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),   # Timestamp
            context.user_data.get("hotel", "N/A"),          # Nama Hotel
            context.user_data.get("room", "N/A"),           # Nomor Kamar/Area
            photo_room_link,                                 # Foto Area Kamar
            photo_bathroom_link,                             # Foto Area Kamar Mandi
            context.user_data.get("remarks", "-"),          # Remarks
            update.message.from_user.first_name             # Staff
        ]

        sheet.append_row(row_data)
        await update.message.reply_text(
            "✅ *Laporan berhasil tersimpan!*\n\nKetik /start untuk laporan baru.",
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Gagal simpan data: {e}")
        await update.message.reply_text(f"❌ Gagal simpan: {e}")

    context.user_data.clear()

# ===== 6. BOT HANDLERS =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    keyboard = [[InlineKeyboardButton(h, callback_data=h)] for h in HOTELS]
    await update.message.reply_text(
        "🏨 *Sistem Laporan Pembersihan Hotel*\n\nSilakan pilih hotel:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Pilih hotel
    if query.data in HOTELS:
        context.user_data["hotel"] = query.data
        context.user_data["step"] = "room"
        await query.message.reply_text(
            f"✅ Hotel: *{query.data}*\n\nMasukkan *Nomor Kamar / Area*:",
            parse_mode="Markdown"
        )

    # Lewati foto kamar mandi
    elif query.data == "skip_bathroom":
        context.user_data["photo_bathroom"] = "-"
        context.user_data["step"] = "remarks"
        await query.message.reply_text(
            "📝 Masukkan *Remarks* / catatan tambahan:\n\nAtau ketik `-` jika tidak ada.",
            parse_mode="Markdown"
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("step")

    # Pesan teks tanpa step — arahkan ke /start
    if not step:
        await update.message.reply_text("Ketik /start untuk memulai laporan baru.")
        return

    # Step 1 — Nomor Kamar / Area
    if step == "room":
        context.user_data["room"] = update.message.text
        context.user_data["step"] = "photo_room"
        await update.message.reply_text(
            "📸 Kirim *Foto Area Kamar*:",
            parse_mode="Markdown"
        )

    # Step 2 — Foto Area Kamar (wajib)
    elif step == "photo_room":
        if not update.message.photo:
            await update.message.reply_text("⚠️ Mohon kirim dalam bentuk *foto*, bukan file.", parse_mode="Markdown")
            return
        photo_file = await update.message.photo[-1].get_file()
        context.user_data["photo_room"] = photo_file.file_id
        context.user_data["step"] = "photo_bathroom"

        keyboard = [[InlineKeyboardButton("⏭ Lewati (tidak ada foto kamar mandi)", callback_data="skip_bathroom")]]
        await update.message.reply_text(
            "📸 Kirim *Foto Area Kamar Mandi* (jika ada):",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    # Step 3 — Foto Kamar Mandi (opsional)
    elif step == "photo_bathroom":
        if not update.message.photo:
            await update.message.reply_text("⚠️ Mohon kirim dalam bentuk *foto*, atau tekan tombol Lewati.", parse_mode="Markdown")
            return
        photo_file = await update.message.photo[-1].get_file()
        context.user_data["photo_bathroom"] = photo_file.file_id
        context.user_data["step"] = "remarks"
        await update.message.reply_text(
            "📝 Masukkan *Remarks* / catatan tambahan:\n\nAtau ketik `-` jika tidak ada.",
            parse_mode="Markdown"
        )

    # Step 4 — Remarks → lalu simpan
    elif step == "remarks":
        context.user_data["remarks"] = update.message.text
        await simpan_ke_sheet(update, context)

# ===== 7. MAIN RUNNER =====
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_message))

    logger.info(f"Bot starting — Webhook: {WEBHOOK_URL} | Port: {PORT}")

    logger.info("Bot starting via Polling...")
app.run_polling()
