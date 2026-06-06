import json
import os
import sys
import html
import requests
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler

# Add parent and src directories to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from src.talivy_search import talivy_search, format_search_results, parse_talivy_results, clean_text_for_telegram

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

def send_telegram_message(chat_id: int, text: str) -> None:
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

    def do_GET(self):
        if not TELEGRAM_CHAT_ID:
            self.send_json(500, {"error": "TELEGRAM_CHAT_ID is not set"})
            return

        # Parse query parameters
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)
        
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
                send_telegram_message(TELEGRAM_CHAT_ID, message)
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
                send_telegram_message(TELEGRAM_CHAT_ID, item_message)

            self.send_json(200, {"ok": True, "mode": "batch", "results": count})
        except Exception as e:
            self.send_json(500, {"error": str(e)})

if __name__ == '__main__':
    from http.server import HTTPServer
    port = int(os.getenv("PORT", 3002))
    server = HTTPServer(('0.0.0.0', port), handler)
    print(f"Starting local server on http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
