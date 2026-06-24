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
from src.db import log_request, is_user_allowed, is_user_admin, allow_user, revoke_user, register_inactive_user_if_new, resolve_user_details, get_all_users, is_email_admin

import hmac
import hashlib
import base64
from http.cookies import SimpleCookie

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

def sign_session_data(data_str: str, secret: str) -> str:
    signature = hmac.new(secret.encode('utf-8'), data_str.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"{data_str}.{signature}"

def verify_session_data(signed_str: str, secret: str) -> str | None:
    if not signed_str or '.' not in signed_str:
        return None
    try:
        data_str, signature = signed_str.rsplit('.', 1)
        expected_sig = hmac.new(secret.encode('utf-8'), data_str.encode('utf-8'), hashlib.sha256).hexdigest()
        if hmac.compare_digest(signature, expected_sig):
            return data_str
    except Exception:
        pass
    return None

def get_session_user(headers, secret: str) -> dict | None:
    cookie_header = headers.get('Cookie')
    if not cookie_header:
        return None
    cookie = SimpleCookie()
    cookie.load(cookie_header)
    if 'session' not in cookie:
        return None
    session_value = cookie['session'].value
    verified_data = verify_session_data(session_value, secret)
    if not verified_data:
        return None
    try:
        return json.loads(base64.b64decode(verified_data).decode('utf-8'))
    except Exception:
        return None

def is_auth0_user_admin(user_info: dict) -> bool:
    if not user_info:
        return False
    
    user_email = user_info.get("email")
    if not user_email:
        return False

    # 1. First priority: Check the database by email
    if is_email_admin(user_email):
        return True

    # 2. Fallback check of environment variable list of admin emails (useful for bootstrapping)
    admin_emails_env = os.getenv("ADMIN_EMAILS")
    if admin_emails_env:
        admin_emails = [e.strip().lower() for e in admin_emails_env.split(',') if e.strip()]
        if user_email.lower() in admin_emails:
            return True
    return False


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

    if normalized.startswith("/users"):
        return {"type": "users", "query": None}

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
            "Use /revoke &lt;user_id_or_username&gt; to revoke access for a user.\n"
            "Use /users to list all users and their roles."
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
        elif path == '/api/users/allow':
            self.handle_api_allow_user()
        elif path == '/api/users/revoke':
            self.handle_api_revoke_user()
        else:
            self.send_json(404, {"error": f"Path {self.path} not found"})

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path.rstrip('/')

        if path == '':
            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            index_html_path = os.path.join(root_dir, 'index.html')
            if os.path.exists(index_html_path):
                try:
                    with open(index_html_path, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.send_header('Content-Length', str(len(html_content.encode('utf-8'))))
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    self.wfile.write(html_content.encode('utf-8'))
                    return
                except Exception as e:
                    logger.error(f"Failed to read index.html: {e}")

        if path == '/admin.html':
            auth0_secret = os.getenv("AUTH0_SECRET") or "fallback-default-secret-key-123"
            session_user = get_session_user(self.headers, auth0_secret)
            
            # If not logged in at all, redirect to Auth0 login flow
            if not session_user:
                self.send_response(302)
                self.send_header('Location', '/api/auth/login')
                self.send_header('Connection', 'close')
                self.end_headers()
                return
                
            # If logged in but not an authorized admin, show access denied page instead of redirect loop
            if not is_auth0_user_admin(session_user):
                self.send_error_page(403, f"Access Denied: The user '{session_user.get('email')}' is not authorized as an administrator. Please contact the bot owner to request administrative access.")
                return

            root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            admin_html_path = os.path.join(root_dir, 'admin.html')
            if os.path.exists(admin_html_path):
                try:
                    with open(admin_html_path, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html')
                    self.send_header('Content-Length', str(len(html_content.encode('utf-8'))))
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    self.wfile.write(html_content.encode('utf-8'))
                    return
                except Exception as e:
                    logger.error(f"Failed to read admin.html: {e}")

        if path in ('', '/api', '/api/index'):
            self.send_json(200, {
                "name": "Daily Telegram Insights API",
                "status": "healthy",
                "endpoints": {
                    "webhook": "/api/telegram",
                    "fact_scheduler": "/api/fact",
                    "news_scheduler": "/api/news",
                    "users_list": "/api/users"
                }
            })
        elif path == '/api/auth/login':
            self.handle_login()
        elif path == '/api/auth/callback':
            self.handle_callback()
        elif path == '/api/auth/logout':
            self.handle_logout()
        elif path == '/api/fact':
            self.handle_fact_get()
        elif path == '/api/news':
            self.handle_news_get(parsed_url.query)
        elif path == '/api/users':
            self.handle_users_get(parsed_url.query)
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

            if cmd_type in ("allow", "revoke", "users") and not is_admin:
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
            elif cmd_type == "users":
                users = get_all_users()
                if users is None:
                    response_text = "❌ <b>Error:</b> Failed to retrieve users from database."
                elif len(users) == 0:
                    response_text = "ℹ️ <b>No users found in database.</b>"
                else:
                    response_text = "📋 <b>Registered Users List</b>\n\n"
                    for u in users:
                        uid = u.get("user_id", "")
                        uname = u.get("username", "") or ""
                        uname_display = f"@{uname}" if uname else "<i>N/A</i>"
                        role = u.get("role", "regular")
                        active_status = "🟢 Active" if u.get("is_active") else "🔴 Inactive"
                        role_emoji = "🛡️ admin" if role == "admin" else "👤 regular"
                        
                        response_text += (
                            f"• <b>User:</b> {uname_display}\n"
                            f"  ├ <b>ID:</b> <code>{uid}</code>\n"
                            f"  ├ <b>Role:</b> {role_emoji}\n"
                            f"  └ <b>Status:</b> {active_status}\n\n"
                        )
                    response_text = response_text.rstrip()
                
                send_telegram_message(chat_id, response_text)
                topic = "list_users"
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

    def handle_users_get(self, query_string: str):
        start_time = time.time()
        logger.info("Incoming GET request for users list")

        query_params = parse_qs(query_string)

        auth0_secret = os.getenv("AUTH0_SECRET") or "fallback-default-secret-key-123"
        session_user = get_session_user(self.headers, auth0_secret)
        is_admin = is_auth0_user_admin(session_user)

        if not is_admin:
            admin_id_str = query_params.get("admin_id", [None])[0]

            if admin_id_str:
                try:
                    admin_id = int(admin_id_str)
                    is_admin = is_user_admin(admin_id)
                except ValueError:
                    self.send_json(400, {"error": "admin_id must be a valid integer"})
                    return
            else:
                self.send_json(401, {"error": "Authentication required. Active session or valid admin_id required."})
                return

        if not is_admin:
            self.send_json(403, {"error": "Access Denied: Administrator privileges required"})
            return

        users = get_all_users()
        if users is None:
            self.send_json(500, {"error": "Failed to retrieve users from database"})
            return

        format_type = query_params.get("format", ["json"])[0]
        if format_type == "html":
            html_content = self.generate_users_html_table(users)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(html_content)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))
        else:
            self.send_json(200, {"users": users})

    def generate_users_html_table(self, users: list[dict]) -> str:
        rows_html = ""
        for u in users:
            uid = u.get("user_id", "")
            uname = u.get("username", "") or ""
            uname_display = f"@{uname}" if uname else "<i>N/A</i>"
            role = u.get("role", "regular")
            active = u.get("is_active", True)
            
            role_badge = f'<span class="badge badge-{role}">{role}</span>'
            status_badge = '<span class="badge badge-active">Active</span>' if active else '<span class="badge badge-inactive">Inactive</span>'
            
            rows_html += f"""
            <tr>
                <td><code>{uid}</code></td>
                <td>{uname_display}</td>
                <td>{role_badge}</td>
                <td>{status_badge}</td>
                <td>{u.get("created_at", "")[:19].replace("T", " ")}</td>
            </tr>
            """
            
        html_page = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Registered Users List</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #0f172a;
            color: #e2e8f0;
            padding: 40px 20px;
            margin: 0;
            display: flex;
            justify-content: center;
        }}
        .container {{
            width: 100%;
            max-width: 900px;
            background-color: #1e293b;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            padding: 30px;
            border: 1px solid #334155;
            box-sizing: border-box;
        }}
        h1 {{
            margin-top: 0;
            font-size: 24px;
            color: #f8fafc;
            border-bottom: 2px solid #334155;
            padding-bottom: 15px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .table-responsive {{
            width: 100%;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            min-width: 600px;
        }}
        th, td {{
            padding: 12px 16px;
            border-bottom: 1px solid #334155;
        }}
        th {{
            background-color: #0f172a;
            color: #94a3b8;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 12px;
            letter-spacing: 0.05em;
        }}
        tr:hover {{
            background-color: #334155;
        }}
        code {{
            background-color: #0f172a;
            padding: 2px 6px;
            border-radius: 4px;
            color: #38bdf8;
            font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 9999px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .badge-admin {{
            background-color: rgba(239, 68, 68, 0.2);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.4);
        }}
        .badge-regular {{
            background-color: rgba(59, 130, 246, 0.2);
            color: #3b82f6;
            border: 1px solid rgba(59, 130, 246, 0.4);
        }}
        .badge-active {{
            background-color: rgba(34, 197, 94, 0.2);
            color: #22c55e;
            border: 1px solid rgba(34, 197, 94, 0.4);
        }}
        .badge-inactive {{
            background-color: rgba(107, 114, 128, 0.2);
            color: #9ca3af;
            border: 1px solid rgba(107, 114, 128, 0.4);
        }}
        @media (max-width: 640px) {{
            body {{
                padding: 10px 5px;
            }}
            .container {{
                padding: 15px 10px;
                border-radius: 8px;
            }}
            h1 {{
                font-size: 18px;
                margin-bottom: 15px;
            }}
            th, td {{
                padding: 10px 8px;
                font-size: 12px;
            }}
            .badge {{
                padding: 2px 6px;
                font-size: 9px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ Registered Users Control List</h1>
        <div class="table-responsive">
            <table>
                <thead>
                    <tr>
                        <th>User ID</th>
                        <th>Username</th>
                        <th>Role</th>
                        <th>Status</th>
                        <th>Registered At</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""
        return html_page

    def send_error_page(self, status_code: int, message: str):
        html_err = f"""<!DOCTYPE html>
<html>
<head>
  <title>Error {status_code}</title>
  <style>
    body {{ font-family: sans-serif; background: #030712; color: #f3f4f6; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
    .card {{ background: #111827; padding: 2rem; border-radius: 12px; border: 1px solid rgba(255,255,255,0.08); text-align: center; max-width: 400px; }}
    h1 {{ color: #ef4444; margin-top: 0; }}
    a {{ color: #3b82f6; text-decoration: none; font-weight: bold; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Authentication Error</h1>
    <p>{html.escape(message)}</p>
    <p><a href="/">Return to Home</a></p>
  </div>
</body>
</html>"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', str(len(html_err.encode('utf-8'))))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(html_err.encode('utf-8'))

    def handle_login(self):
        auth0_domain = os.getenv("AUTH0_DOMAIN")
        client_id = os.getenv("AUTH0_CLIENT_ID")
        
        host = self.headers.get('Host')
        protocol = 'https' if self.headers.get('X-Forwarded-Proto') == 'https' else 'http'
        redirect_uri = f"{protocol}://{host}/api/auth/callback"
        
        logger.info(f"[Auth0 Login] Host Header: '{host}' | Protocol: '{protocol}' | Generated Redirect URI: '{redirect_uri}'")
        
        auth_url = (
            f"https://{auth0_domain}/authorize?"
            f"response_type=code&"
            f"client_id={client_id}&"
            f"redirect_uri={redirect_uri}&"
            f"scope=openid%20profile%20email"
        )
        self.send_response(302)
        self.send_header('Location', auth_url)
        self.send_header('Connection', 'close')
        self.end_headers()

    def handle_callback(self):
        parsed_url = urlparse(self.path)
        params = parse_qs(parsed_url.query)
        code_list = params.get('code')
        if not code_list:
            self.send_error_page(400, "Missing authorization code from Auth0.")
            return
        
        code = code_list[0]
        auth0_domain = os.getenv("AUTH0_DOMAIN")
        client_id = os.getenv("AUTH0_CLIENT_ID")
        client_secret = os.getenv("AUTH0_CLIENT_SECRET")
        auth0_secret = os.getenv("AUTH0_SECRET") or "fallback-default-secret-key-123"
        
        host = self.headers.get('Host')
        protocol = 'https' if self.headers.get('X-Forwarded-Proto') == 'https' else 'http'
        redirect_uri = f"{protocol}://{host}/api/auth/callback"
        
        logger.info(f"[Auth0 Callback] Using redirect_uri for code exchange: '{redirect_uri}'")
        
        token_url = f"https://{auth0_domain}/oauth/token"
        payload = {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": redirect_uri
        }
        
        try:
            r = requests.post(token_url, json=payload, timeout=10)
            r.raise_for_status()
            tokens = r.json()
            access_token = tokens.get("access_token")
            
            userinfo_url = f"https://{auth0_domain}/userinfo"
            user_r = requests.get(userinfo_url, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
            user_r.raise_for_status()
            user_info = user_r.json()
            
            user_data_json = json.dumps(user_info)
            encoded_data = base64.b64encode(user_data_json.encode('utf-8')).decode('utf-8')
            signed_session = sign_session_data(encoded_data, auth0_secret)
            
            self.send_response(302)
            self.send_header('Location', '/admin.html')
            
            cookie_str = f"session={signed_session}; Path=/; HttpOnly"
            if protocol == 'https':
                cookie_str += "; Secure; SameSite=Lax"
            
            self.send_header('Set-Cookie', cookie_str)
            self.send_header('Connection', 'close')
            self.end_headers()
            
        except Exception as e:
            logger.exception("Failed during Auth0 callback code exchange")
            self.send_error_page(500, f"Authentication failed: {str(e)}")

    def handle_logout(self):
        auth0_domain = os.getenv("AUTH0_DOMAIN")
        client_id = os.getenv("AUTH0_CLIENT_ID")
        
        host = self.headers.get('Host')
        protocol = 'https' if self.headers.get('X-Forwarded-Proto') == 'https' else 'http'
        return_to = f"{protocol}://{host}/"
        
        logout_url = f"https://{auth0_domain}/v2/logout?client_id={client_id}&returnTo={return_to}"
        self.send_response(302)
        self.send_header('Location', logout_url)
        self.send_header('Set-Cookie', 'session=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly')
        self.send_header('Connection', 'close')
        self.end_headers()

    def handle_api_allow_user(self):
        auth0_secret = os.getenv("AUTH0_SECRET") or "fallback-default-secret-key-123"
        session_user = get_session_user(self.headers, auth0_secret)
        if not is_auth0_user_admin(session_user):
            self.send_json(403, {"error": "Access denied. Administrator privileges required."})
            return

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        try:
            body = json.loads(post_data.decode('utf-8'))
            user_id = int(body.get("user_id"))
            username = body.get("username")
            role = body.get("role", "regular")
            email = body.get("email")
            
            success, err_msg = allow_user(user_id, username, role, email)
            if success:
                self.send_json(200, {"ok": True})
            else:
                self.send_json(500, {"error": err_msg or "Failed to update user in database."})
        except Exception as e:
            self.send_json(400, {"error": f"Invalid request body: {str(e)}"})

    def handle_api_revoke_user(self):
        auth0_secret = os.getenv("AUTH0_SECRET") or "fallback-default-secret-key-123"
        session_user = get_session_user(self.headers, auth0_secret)
        if not is_auth0_user_admin(session_user):
            self.send_json(403, {"error": "Access denied. Administrator privileges required."})
            return

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        try:
            body = json.loads(post_data.decode('utf-8'))
            user_id = int(body.get("user_id"))
            
            success, err_msg = revoke_user(user_id)
            if success:
                self.send_json(200, {"ok": True})
            else:
                self.send_json(500, {"error": err_msg or "Failed to deactivate user in database."})
        except Exception as e:
            self.send_json(400, {"error": f"Invalid request body: {str(e)}"})

if __name__ == '__main__':
    from http.server import HTTPServer
    port = int(os.getenv("PORT", 3000))
    server = HTTPServer(('0.0.0.0', port), handler)
    print(f"Starting unified local server on http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass