import os
import json
import base64
import hmac
import hashlib
import logging
import requests
from http.cookies import SimpleCookie
from src.db import is_email_admin

logger = logging.getLogger("auth")

def sign_session_data(data_str: str, secret: str) -> str:
    """
    Signs data string with secret using HMAC-SHA256.
    """
    signature = hmac.new(secret.encode('utf-8'), data_str.encode('utf-8'), hashlib.sha256).hexdigest()
    return f"{data_str}.{signature}"

def verify_session_data(signed_str: str, secret: str) -> str | None:
    """
    Verifies data signature and returns the raw data if valid.
    """
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
    """
    Retrieves the logged-in user info from the cookies session.
    """
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
    """
    Determines if an Auth0 user email has admin authorization.
    """
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

def get_auth_url(host: str, protocol: str) -> str:
    """
    Generates the Auth0 authorize redirect URL.
    """
    auth0_domain = os.getenv("AUTH0_DOMAIN")
    client_id = os.getenv("AUTH0_CLIENT_ID")
    redirect_uri = f"{protocol}://{host}/api/auth/callback"
    
    logger.info(f"[Auth0 Login] Host: '{host}' | Protocol: '{protocol}' | Generated Redirect URI: '{redirect_uri}'")
    
    return (
        f"https://{auth0_domain}/authorize?"
        f"response_type=code&"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"scope=openid%20profile%20email"
    )

def exchange_code_for_user_info(code: str, host: str, protocol: str) -> dict:
    """
    Exchanges authorization code for access token and retrieves the Auth0 user profile.
    """
    auth0_domain = os.getenv("AUTH0_DOMAIN")
    client_id = os.getenv("AUTH0_CLIENT_ID")
    client_secret = os.getenv("AUTH0_CLIENT_SECRET")
    redirect_uri = f"{protocol}://{host}/api/auth/callback"
    
    logger.info(f"[Auth0 Callback] Exchanging code via redirect_uri: '{redirect_uri}'")
    
    token_url = f"https://{auth0_domain}/oauth/token"
    payload = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri
    }
    
    r = requests.post(token_url, json=payload, timeout=10)
    r.raise_for_status()
    tokens = r.json()
    access_token = tokens.get("access_token")
    
    userinfo_url = f"https://{auth0_domain}/userinfo"
    user_r = requests.get(userinfo_url, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    user_r.raise_for_status()
    return user_r.json()

def get_logout_url(host: str, protocol: str) -> str:
    """
    Generates the Auth0 logout URL.
    """
    auth0_domain = os.getenv("AUTH0_DOMAIN")
    client_id = os.getenv("AUTH0_CLIENT_ID")
    return_to = f"{protocol}://{host}/"
    return f"https://{auth0_domain}/v2/logout?client_id={client_id}&returnTo={return_to}"

def verify_cron_request(headers) -> bool:
    """
    Verifies that the request was triggered by Vercel Cron.
    Only enforces verification if CRON_SECRET is set in environment variables.
    """
    cron_secret = os.getenv("CRON_SECRET")
    if not cron_secret:
        logger.warning("[Cron Auth] CRON_SECRET not set in environment. Skipping verification.")
        return True

    auth_header = headers.get("Authorization")
    if not auth_header:
        logger.warning("[Cron Auth] Authorization header missing.")
        return False

    expected_value = f"Bearer {cron_secret}"
    is_valid = hmac.compare_digest(auth_header.encode('utf-8'), expected_value.encode('utf-8'))
    if not is_valid:
        logger.warning("[Cron Auth] Authorization header token mismatch.")
    
    logger.info(f"[Cron Auth] Verification result: {is_valid}")
    return is_valid
