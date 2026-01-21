# api/webhook.py
from http.server import BaseHTTPRequestHandler
import json
import telebot
from bot_core import get_bot

bot = get_bot()

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('content-length', 0))
        body = self.rfile.read(length).decode("utf-8")

        try:
            update = telebot.types.Update.de_json(body)
            bot.process_new_updates([update])
        except Exception as e:
            print("Webhook error:", e)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))

    def do_GET(self):
        # simple health check
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True, "message": "Telegram webhook endpoint"}).encode("utf-8"))
