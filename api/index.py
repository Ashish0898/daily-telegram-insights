import json
import os
import sys
import re
import html
import requests
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler

# Add parent and src directories to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from src.generate_fact import generate_fact
from src.talivy_search import talivy_search, format_search_results, parse_talivy_results, clean_text_for_telegram

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

def parse_command(text: str) -> dict:
    if not text:
        return {"type": "fact", "query": None}

    trimmed = text.strip()
    normalized = trimmed.lower()

    if normalized.startswith("/fact"):
        return {"type": "fact", "query": None}

    if normalized.startswith("/news"):
        query = re.sub(r"^/news\s*", "", trimmed, flags=re.IGNORECASE).strip()
        return {
            "type": "news",
            "query": query or "latest FIFA WC news",
        }

    if normalized.startswith("/search"):
        query = re.sub(r"^/search\s*", "", trimmed, flags=re.IGNORECASE).strip()
        return {
            "type": "search",
            "query": query or "latest news",
        }

    if normalized.startswith("/help") or normalized.startswith("/start"):
        return {"type": "help", "query": None}

    return {"type": "fact", "query": None}

def build_help_message() -> str:
    return (
        "Hello! 🤖\n\n"
        "Use /fact to receive a new random fact.\n"
        "Use /news or /news <query> to get Talivy news.\n"
        "Use /search <query> to search Talivy for a custom topic.\n"
        "Use /help to show this message again."
    )

def get_response_text(cmd: dict) -> str:
    cmd_type = cmd["type"]
    query = cmd["query"]

    if cmd_type == "help":
        return build_help_message()

    if cmd_type == "fact":
        fact = generate_fact()
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return f"<b>🎯 Daily Fact</b>\n\n{fact}\n\n<i>{timestamp}</i>"

    search_query = query or "latest news"
    try:
        raw = talivy_search(search_query, limit=3)
        return format_search_results(search_query, raw, limit=3)
    except Exception as e:
        return f"Error performing search for '{search_query}': {str(e)}"

def send_telegram_message(chat_id: int, text: str) -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN must be set")

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    response = requests.post(TELEGRAM_API, json=payload, timeout=15)
    response.raise_for_status()

class handler(BaseHTTPRequestHandler):
    def send_json(self, status_code: int, data: dict):
        response_body = json.dumps(data).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response_body)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(response_body)

    def do_POST(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path.rstrip('/')

        if path in ('/api/telegram', '/api/index', '/api', ''):
            self.handle_telegram_post()
        else:
            self.send_json(404, {"error": f"Path {self.path} not found"})

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path.rstrip('/')

        if path in ('', '/api', '/api/index'):
            self.send_json(200, {
                "name": "Daily Telegram Insights API",
                "status": "healthy",
                "endpoints": {
                    "webhook": "/api/telegram",
                    "fact_scheduler": "/api/fact",
                    "news_scheduler": "/api/news"
                }
            })
        elif path == '/api/fact':
            self.handle_fact_get()
        elif path == '/api/news':
            self.handle_news_get(parsed_url.query)
        else:
            self.send_json(404, {"error": f"Path {self.path} not found"})

    def handle_telegram_post(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            body = json.loads(post_data.decode('utf-8'))
        except Exception:
            self.send_json(400, {"error": "Invalid JSON"})
            return

        message = body.get("message") or body.get("edited_message")
        if not message or "text" not in message:
            self.send_json(200, {"ok": True, "reason": "no_text"})
            return

        chat = message.get("chat")
        chat_id = chat.get("id") if chat else None
        if not chat_id:
            self.send_json(400, {"error": "missing_chat_id"})
            return

        text = message.get("text", "")
        
        try:
            cmd = parse_command(text)
            response_text = get_response_text(cmd)
            send_telegram_message(chat_id, response_text)
            self.send_json(200, {"ok": True})
        except Exception as e:
            self.send_json(500, {"error": str(e)})

    def handle_fact_get(self):
        if not TELEGRAM_CHAT_ID:
            self.send_json(500, {"error": "TELEGRAM_CHAT_ID is not set"})
            return

        try:
            fact = generate_fact()
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            message = f"<b>🎯 Daily Fact</b>\n\n{fact}\n\n<i>{timestamp}</i>"

            send_telegram_message(int(TELEGRAM_CHAT_ID), message)
            self.send_json(200, {"ok": True})
        except Exception as e:
            self.send_json(500, {"error": str(e)})

    def handle_news_get(self, query_string: str):
        if not TELEGRAM_CHAT_ID:
            self.send_json(500, {"error": "TELEGRAM_CHAT_ID is not set"})
            return

        query_params = parse_qs(query_string)
        query = query_params.get("query", [None])[0] or os.getenv("NEWS_QUERY") or "latest FIFA WC news"
        limit_str = query_params.get("limit", [None])[0] or os.getenv("NEWS_LIMIT") or "5"
        try:
            limit = int(limit_str)
        except ValueError:
            limit = 5

        summary_str = query_params.get("summary", [None])[0] or os.getenv("NEWS_SUMMARY") or "false"
        summary = summary_str.lower() == "true"

        try:
            data = talivy_search(query, limit=limit)
            results = parse_talivy_results(data)

            if summary or not results:
                message = format_search_results(query, data, limit=limit)
                send_telegram_message(int(TELEGRAM_CHAT_ID), message)
                self.send_json(200, {"ok": True, "mode": "summary", "results": len(results)})
                return

            count = min(limit, len(results))
            for index, item in enumerate(results[:count], start=1):
                title = clean_text_for_telegram(item.get("title") or item.get("headline") or "Untitled")
                snippet = clean_text_for_telegram(
                    item.get("content") or item.get("snippet") or item.get("summary") or
                    item.get("description") or item.get("raw_content") or "No description available."
                )
                url = item.get("url")
                if url:
                    url = html.escape(str(url), quote=True)
                
                lines = [
                    f"<b>📡 Web update ({index}/{count})</b>",
                    f"<b>{title}</b>",
                ]
                lines.append(snippet)
                if url:
                    lines.append(f'<a href="{url}">Read more</a>')
                
                item_message = "\n\n".join(lines).strip()
                send_telegram_message(int(TELEGRAM_CHAT_ID), item_message)

            self.send_json(200, {"ok": True, "mode": "batch", "results": count})
        except Exception as e:
            self.send_json(500, {"error": str(e)})

if __name__ == '__main__':
    from http.server import HTTPServer
    port = int(os.getenv("PORT", 3000))
    server = HTTPServer(('0.0.0.0', port), handler)
    print(f"Starting unified local server on http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
