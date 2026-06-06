import json
import os
import sys
import requests
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler

# Add parent and src directories to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from src.generate_fact import generate_fact

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

class handler(BaseHTTPRequestHandler):
    def send_json(self, status_code: int, data: dict):
        response_body = json.dumps(data).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response_body)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(response_body)

    def do_GET(self):
        if not TELEGRAM_CHAT_ID:
            self.send_json(500, {"error": "TELEGRAM_CHAT_ID is not set"})
            return

        try:
            fact = generate_fact()
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            message = f"<b>🎯 Daily Fact</b>\n\n{fact}\n\n<i>{timestamp}</i>"

            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
            }
            response = requests.post(TELEGRAM_API, json=payload, timeout=15)
            response.raise_for_status()
            self.send_json(200, {"ok": True})
        except Exception as e:
            self.send_json(500, {"error": str(e)})

if __name__ == '__main__':
    from http.server import HTTPServer
    port = int(os.getenv("PORT", 3001))
    server = HTTPServer(('0.0.0.0', port), handler)
    print(f"Starting local server on http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
