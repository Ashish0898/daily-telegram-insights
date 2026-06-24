import json
import os
import sys
import html
import logging
import base64
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler

# Configure logging
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

from src.db import is_user_admin
from src.auth import (
    sign_session_data,
    get_session_user,
    is_auth0_user_admin,
    get_auth_url,
    exchange_code_for_user_info,
    get_logout_url
)
from src.schedulers import execute_fact_scheduler, execute_news_scheduler
from src.telegram_webhook import process_telegram_webhook
from src.admin_handlers import (
    execute_users_get,
    execute_api_allow_user,
    execute_api_revoke_user
)


class handler(BaseHTTPRequestHandler):
    def send_json(self, status_code: int, data: dict):
        response_body = json.dumps(data).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(response_body)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(response_body)

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
</html>
"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', str(len(html_err.encode('utf-8'))))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(html_err.encode('utf-8'))

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
                self.send_error_page(
                    403,
                    f"Access Denied: The user '{session_user.get('email')}' is not authorized as an administrator. Please contact the bot owner to request administrative access."
                )
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

        if path == '/api/fact':
            self.handle_fact_get()
        elif path == '/api/news':
            self.handle_news_get(parsed_url.query)
        elif path == '/api/users':
            self.handle_users_get(parsed_url.query)
        elif path == '/api/auth/login':
            self.handle_login()
        elif path == '/api/auth/callback':
            self.handle_callback()
        elif path == '/api/auth/logout':
            self.handle_logout()
        else:
            self.send_json(404, {"error": f"Path {self.path} not found"})

    def handle_telegram_post(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        try:
            body = json.loads(post_data.decode('utf-8'))
            secret_token = self.headers.get('X-Telegram-Bot-Api-Secret-Token')
            status_code, response_body = process_telegram_webhook(body, secret_token)
            self.send_json(status_code, response_body)
        except Exception as e:
            self.send_json(400, {"error": f"Invalid JSON payload: {str(e)}"})

    def handle_fact_get(self):
        status_code, response_body = execute_fact_scheduler()
        self.send_json(status_code, response_body)

    def handle_news_get(self, query_string: str):
        query_params = parse_qs(query_string)
        status_code, response_body = execute_news_scheduler(query_params)
        self.send_json(status_code, response_body)

    def handle_users_get(self, query_string: str):
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

        status_code, body, content_type = execute_users_get(query_params, is_admin)
        if content_type == "text/html":
            self.send_response(status_code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body.encode('utf-8'))))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body.encode('utf-8'))
        else:
            self.send_json(status_code, body)

    def handle_login(self):
        host = self.headers.get('Host')
        protocol = 'https' if self.headers.get('X-Forwarded-Proto') == 'https' else 'http'
        auth_url = get_auth_url(host, protocol)
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
        auth0_secret = os.getenv("AUTH0_SECRET") or "fallback-default-secret-key-123"
        host = self.headers.get('Host')
        protocol = 'https' if self.headers.get('X-Forwarded-Proto') == 'https' else 'http'
        
        try:
            user_info = exchange_code_for_user_info(code, host, protocol)
            
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
        host = self.headers.get('Host')
        protocol = 'https' if self.headers.get('X-Forwarded-Proto') == 'https' else 'http'
        logout_url = get_logout_url(host, protocol)
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
            status_code, response_body = execute_api_allow_user(body)
            self.send_json(status_code, response_body)
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
            status_code, response_body = execute_api_revoke_user(body)
            self.send_json(status_code, response_body)
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