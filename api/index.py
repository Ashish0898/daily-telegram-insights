import json
import os
import sys
import re
import html
import traceback
import requests
import logging
import time
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler

# Configure logging to output to stdout (useful for serverless logs on Vercel)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("api")

# Load environment variables from .env file if present
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip().strip("'").strip('"')
                if key not in os.environ:
                    os.environ[key] = val

# Add parent and src directories to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from src.generate_fact import generate_fact, generate_dynamic_news_query
from src.send_news import execute_and_send_news
from src.talivy_search import talivy_search, format_search_results, parse_talivy_results, clean_text_for_telegram
from src.db import log_request, is_user_allowed, is_user_admin, allow_user, revoke_user, register_inactive_user_if_new, resolve_user_details

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
            "query": query or None,
        }

    if normalized.startswith("/search"):
        query = re.sub(r"^/search\s*", "", trimmed, flags=re.IGNORECASE).strip()
        return {
            "type": "search",
            "query": query or "latest news",
        }

    if normalized.startswith("/help") or normalized.startswith("/start"):
        return {"type": "help", "query": None}

    if normalized.startswith("/allow"):
        query = re.sub(r"^/allow(@\w+)?\s*", "", trimmed, flags=re.IGNORECASE).strip()
        return {
            "type": "allow",
            "query": query or None,
        }

    if normalized.startswith("/revoke"):
        query = re.sub(r"^/revoke(@\w+)?\s*", "", trimmed, flags=re.IGNORECASE).strip()
        return {
            "type": "revoke",
            "query": query or None,
        }

    return {"type": "fact", "query": None}


def build_help_message(is_admin: bool = False) -> str:
    msg = (
        "Hello! 🤖\n\n"
        "Use /fact to receive a new random fact.\n"
        "Use /news to get a dynamic daily news digest, or /news &lt;query&gt; for a specific topic.\n"
        "Use /search &lt;query&gt; to search Talivy for custom web results.\n"
        "Use /help to show this message again."
    )
    if is_admin:
        msg += (
            "\n\n🛡️ <b>Admin Commands:</b>\n"
            "Use /allow &lt;user_id_or_username&gt; [role] to allow a user (role defaults to 'regular').\n"
            "Use /revoke &lt;user_id_or_username&gt; to revoke access for a user."
        )
    return msg

def get_response_text(cmd: dict, is_admin: bool = False) -> tuple:
    cmd_type = cmd["type"]
    query = cmd["query"]

    if cmd_type == "help":
        return build_help_message(is_admin), "help"

    if cmd_type == "fact":
        fact, seed = generate_fact(return_topic=True)
        fact_escaped = html.escape(fact, quote=False)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return f"<b>🎯 Daily Fact</b>\n\n{fact_escaped}\n\n<i>{timestamp}</i>", seed

    if cmd_type == "news" and not query:
        search_query = generate_dynamic_news_query()
    else:
        search_query = query or "latest news"

    try:
        raw = talivy_search(search_query, limit=3)
        formatted = format_search_results(search_query, raw, limit=3)
        return formatted, search_query
    except Exception as e:
        return f"Error performing search for '{search_query}': {str(e)}", search_query

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
    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        print(f"Telegram API Error response: {response.text}")
        print(f"Failed to send text:\n{text}")
        raise

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
        start_time = time.time()
        logger.info(f"Incoming POST request to webhook endpoint: {self.path}")
        
        # Initialize variables for database logging
        user_id = None
        username = None
        chat_id = None
        command_text = None

        telegram_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET") or os.getenv("TELEGRAM_SECRET_TOKEN")
        if telegram_secret:
            received_secret = self.headers.get('X-Telegram-Bot-Api-Secret-Token')
            if received_secret != telegram_secret:
                logger.warning("Secret token mismatch. Request ignored.")
                self.send_json(200, {"ok": True, "reason": "ignored_secret_mismatch"})
                log_request(
                    endpoint="webhook",
                    status="ignored_secret_mismatch",
                    execution_time_ms=int((time.time() - start_time) * 1000)
                )
                return

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            body = json.loads(post_data.decode('utf-8'))
        except Exception as e:
            logger.error("Failed to parse incoming request body as JSON.")
            self.send_json(400, {"error": "Invalid JSON"})
            log_request(
                endpoint="webhook",
                status="invalid_json",
                error_message=str(e),
                execution_time_ms=int((time.time() - start_time) * 1000)
            )
            return

        message = body.get("message") or body.get("edited_message")
        if not message or "text" not in message:
            logger.info("Ignoring webhook payload: no message body or no text content found.")
            self.send_json(200, {"ok": True, "reason": "no_text"})
            if message:
                chat = message.get("chat")
                chat_id = chat.get("id") if chat else None
                from_user = message.get("from")
                user_id = from_user.get("id") if from_user else None
                username = from_user.get("username") if from_user else None
            log_request(
                endpoint="webhook",
                status="ignored_no_text",
                user_id=user_id,
                username=username,
                chat_id=chat_id,
                execution_time_ms=int((time.time() - start_time) * 1000)
            )
            return

        # 2. Allowlist Telegram user ID
        from_user = message.get("from")
        from_id = from_user.get("id") if from_user else None
        user_id = from_id
        username = from_user.get("username") if from_user else None

        chat = message.get("chat")
        chat_id = chat.get("id") if chat else None
        command_text = message.get("text", "")

        # Check allowlist in Supabase allowed_users table
        is_allowed = is_user_allowed(from_id) if from_id is not None else None

        # Check if the command is /start
        is_start_command = False
        if command_text:
            is_start_command = command_text.strip().lower().startswith("/start")

        if is_allowed is None and from_id is not None and is_start_command:
            # Check if they are already allowed via environment variables fallback
            allowed_ids = set()
            for env_var in ["TELEGRAM_ALLOWED_USER_ID", "TELEGRAM_ALLOWED_USER_IDS", "TELEGRAM_CHAT_ID"]:
                val = os.getenv(env_var)
                if val:
                    for chunk in val.split(','):
                        chunk = chunk.strip()
                        if chunk:
                            allowed_ids.add(chunk)
            
            # If not in env vars allowlist, register as inactive in db
            if not (allowed_ids and str(from_id) in allowed_ids):
                register_inactive_user_if_new(from_id, username)
                is_allowed = False

        if is_allowed is False:
            access_denied = True
        elif is_allowed is True:
            access_denied = False
        else:
            # Fallback to checking environment variables
            allowed_ids = set()
            for env_var in ["TELEGRAM_ALLOWED_USER_ID", "TELEGRAM_ALLOWED_USER_IDS", "TELEGRAM_CHAT_ID"]:
                val = os.getenv(env_var)
                if val:
                    for chunk in val.split(','):
                        chunk = chunk.strip()
                        if chunk:
                            allowed_ids.add(chunk)
            if allowed_ids:
                access_denied = not from_id or str(from_id) not in allowed_ids
            else:
                access_denied = False

        if access_denied:
            logger.warning(f"User ID {from_id} not in allowlist. Sending Access Denied message and ignoring request.")
            if from_id:
                response_text = f"⚠️ <b>Access Denied</b>\n\nYou are not authorized to use this bot. Please contact the administrator with your User ID: <code>{from_id}</code>"
            else:
                response_text = "⚠️ <b>Access Denied</b>\n\nYou are not authorized to use this bot."
            if chat_id:
                try:
                    send_telegram_message(chat_id, response_text)
                except Exception as e:
                    logger.error(f"Failed to send access denied message: {e}")
            self.send_json(200, {"ok": True, "reason": "ignored_user_not_allowlisted"})
            log_request(
                endpoint="webhook",
                status="access_denied",
                user_id=user_id,
                username=username,
                chat_id=chat_id,
                command=command_text,
                response_content=response_text,
                execution_time_ms=int((time.time() - start_time) * 1000)
            )
            return

        if not chat_id:
            logger.error("Request missing chat ID.")
            self.send_json(400, {"error": "missing_chat_id"})
            log_request(
                endpoint="webhook",
                status="missing_chat_id",
                user_id=user_id,
                username=username,
                command=command_text,
                execution_time_ms=int((time.time() - start_time) * 1000)
            )
            return

        try:
            cmd = parse_command(command_text)
            cmd_type = cmd["type"]
            query = cmd["query"]

            logger.info(f"Executing command: {cmd_type} (query: {query}) for chat: {chat_id}")

            is_admin = is_user_admin(from_id) if from_id is not None else False

            if cmd_type in ("allow", "revoke") and not is_admin:
                logger.warning(f"Unauthorized admin command attempt from user ID {from_id}")
                response_text = "⚠️ <b>Access Denied</b>\n\nYou must be an admin to perform this action."
                send_telegram_message(chat_id, response_text)
                self.send_json(200, {"ok": True})
                log_request(
                    endpoint="webhook",
                    status="admin_denied",
                    user_id=user_id,
                    username=username,
                    chat_id=chat_id,
                    command=command_text,
                    response_content=response_text,
                    execution_time_ms=int((time.time() - start_time) * 1000)
                )
                return

            if cmd_type in ("news", "search"):
                count, final_query, sent_texts = execute_and_send_news(chat_id, query, limit=3, summary=False)
                response_text = "\n\n---\n\n".join(sent_texts)
                topic = final_query
            elif cmd_type == "allow":
                if not query:
                    response_text = (
                        "⚠️ <b>Usage:</b>\n"
                        "<code>/allow &lt;user_id_or_username&gt; [role]</code>\n\n"
                        "Examples:\n"
                        "• <code>/allow @username admin</code>\n"
                        "• <code>/allow 123456789</code>"
                    )
                else:
                    parts = query.split()
                    target_identifier = parts[0]
                    role = "regular"
                    if len(parts) >= 2:
                        val = parts[1].lower()
                        if val in ("admin", "regular"):
                            role = val

                    target_id, target_username = resolve_user_details(target_identifier)
                    if target_id is None:
                        response_text = f"❌ <b>Error:</b> Could not find or resolve user <code>{target_identifier}</code> in the database. Please ensure they have started the bot by sending a message or clicking /start first."
                    else:
                        success, err = allow_user(target_id, role=role)
                        if success:
                            response_text = f"✅ <b>User Allowed Successfully</b>\n\n• <b>User ID:</b> <code>{target_id}</code>\n• <b>Role:</b> {role}"
                            if target_username:
                                response_text += f"\n• <b>Username:</b> @{target_username}"
                        else:
                            response_text = f"❌ <b>Error:</b> Failed to update user <code>{target_id}</code> in database. Details: <code>{html.escape(str(err))}</code>"
                
                send_telegram_message(chat_id, response_text)
                topic = f"allow_user_{query}"
            elif cmd_type == "revoke":
                if not query:
                    response_text = (
                        "⚠️ <b>Usage:</b>\n"
                        "<code>/revoke &lt;user_id_or_username&gt;</code>\n\n"
                        "Example:\n"
                        "<code>/revoke @username</code>"
                    )
                else:
                    parts = query.split()
                    target_identifier = parts[0]
                    target_id, target_username = resolve_user_details(target_identifier)
                    if target_id is None:
                        response_text = f"❌ <b>Error:</b> Could not find or resolve user <code>{target_identifier}</code> in the database."
                    else:
                        success, err = revoke_user(target_id)
                        if success:
                            response_text = f"🚫 <b>User Revoked</b>\n\nUser ID <code>{target_id}</code> has been deactivated. They will no longer have access to the bot."
                            if target_username:
                                response_text += f"\n• <b>Username:</b> @{target_username}"
                        else:
                            response_text = f"❌ <b>Error:</b> Failed to deactivate user <code>{target_id}</code> in database. Details: <code>{html.escape(str(err))}</code>"
                
                send_telegram_message(chat_id, response_text)
                topic = f"revoke_user_{query}"
            else:
                response_text, topic = get_response_text(cmd, is_admin=is_admin)
                send_telegram_message(chat_id, response_text)
            self.send_json(200, {"ok": True})
            log_request(
                endpoint="webhook",
                status="success",
                user_id=user_id,
                username=username,
                chat_id=chat_id,
                command=command_text,
                response_content=response_text,
                topic=topic,
                execution_time_ms=int((time.time() - start_time) * 1000)
            )
        except Exception as e:
            logger.exception("Error executing Telegram command webhook")
            self.send_json(500, {"error": str(e)})
            log_request(
                endpoint="webhook",
                status="error",
                user_id=user_id,
                username=username,
                chat_id=chat_id,
                command=command_text,
                error_message=str(e),
                execution_time_ms=int((time.time() - start_time) * 1000)
            )

    def handle_fact_get(self):
        start_time = time.time()
        logger.info("Incoming GET request for daily fact scheduler")
        if not TELEGRAM_CHAT_ID:
            logger.error("TELEGRAM_CHAT_ID is not configured in environment.")
            self.send_json(500, {"error": "TELEGRAM_CHAT_ID is not set"})
            log_request(
                endpoint="fact_scheduler",
                status="error",
                error_message="TELEGRAM_CHAT_ID is not set",
                execution_time_ms=int((time.time() - start_time) * 1000)
            )
            return

        try:
            fact, seed = generate_fact(return_topic=True)
            fact_escaped = html.escape(fact, quote=False)
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            message = f"<b>🎯 Daily Fact</b>\n\n{fact_escaped}\n\n<i>{timestamp}</i>"

            send_telegram_message(int(TELEGRAM_CHAT_ID), message)
            self.send_json(200, {"ok": True})
            log_request(
                endpoint="fact_scheduler",
                status="success",
                chat_id=int(TELEGRAM_CHAT_ID),
                command="scheduler_run",
                response_content=message,
                topic=seed,
                execution_time_ms=int((time.time() - start_time) * 1000)
            )
        except Exception as e:
            logger.exception("Error during daily fact scheduler invocation")
            self.send_json(500, {"error": str(e)})
            log_request(
                endpoint="fact_scheduler",
                status="error",
                chat_id=int(TELEGRAM_CHAT_ID) if TELEGRAM_CHAT_ID else None,
                command="scheduler_run",
                error_message=str(e),
                execution_time_ms=int((time.time() - start_time) * 1000)
            )

    def handle_news_get(self, query_string: str):
        start_time = time.time()
        logger.info("Incoming GET request for daily news scheduler")
        if not TELEGRAM_CHAT_ID:
            logger.error("TELEGRAM_CHAT_ID is not configured in environment.")
            self.send_json(500, {"error": "TELEGRAM_CHAT_ID is not set"})
            log_request(
                endpoint="news_scheduler",
                status="error",
                error_message="TELEGRAM_CHAT_ID is not set",
                execution_time_ms=int((time.time() - start_time) * 1000)
            )
            return

        query_params = parse_qs(query_string)
        query = query_params.get("query", [None])[0] or os.getenv("NEWS_QUERY")
        limit_str = query_params.get("limit", [None])[0] or os.getenv("NEWS_LIMIT") or "5"
        try:
            limit = int(limit_str)
        except ValueError:
            limit = 5

        summary_str = query_params.get("summary", [None])[0] or os.getenv("NEWS_SUMMARY") or "false"
        summary = summary_str.lower() == "true"

        command_desc = f"query={query}, limit={limit}, summary={summary}"

        try:
            count, final_query, sent_texts = execute_and_send_news(
                chat_id=int(TELEGRAM_CHAT_ID),
                query=query,
                limit=limit,
                summary=summary
            )
            response_content = "\n\n---\n\n".join(sent_texts)
            mode = "summary" if summary else "batch"
            self.send_json(200, {"ok": True, "mode": mode, "results": count})
            log_request(
                endpoint="news_scheduler",
                status="success",
                chat_id=int(TELEGRAM_CHAT_ID),
                command=command_desc,
                response_content=response_content,
                topic=final_query,
                execution_time_ms=int((time.time() - start_time) * 1000)
            )
        except Exception as e:
            logger.exception("Error during daily news scheduler invocation")
            self.send_json(500, {"error": str(e)})
            log_request(
                endpoint="news_scheduler",
                status="error",
                chat_id=int(TELEGRAM_CHAT_ID),
                command=command_desc,
                error_message=str(e),
                execution_time_ms=int((time.time() - start_time) * 1000)
            )

if __name__ == '__main__':
    from http.server import HTTPServer
    port = int(os.getenv("PORT", 3000))
    server = HTTPServer(('0.0.0.0', port), handler)
    print(f"Starting unified local server on http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass