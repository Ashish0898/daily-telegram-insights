import os
import logging
from supabase import create_client, Client

logger = logging.getLogger("db")

SUPABASE_URL = os.getenv("SUPABASE_URL")
# We prefer SUPABASE_SERVICE_ROLE_KEY for audit logging because it bypasses RLS
# and is safe since it's a backend environment.
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

_client = None

def get_supabase_client() -> Client:
    """
    Initializes and returns the Supabase client.
    Returns None if credentials are not configured or if initialization fails.
    """
    global _client
    if _client is not None:
        return _client

    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("Supabase credentials not configured (SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY is missing). Skipping database operation.")
        return None

    try:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
        return _client
    except Exception as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        return None

def log_request(
    endpoint: str,
    status: str,
    user_id: int = None,
    username: str = None,
    chat_id: int = None,
    command: str = None,
    error_message: str = None,
    execution_time_ms: int = None,
    response_content: str = None,
    topic: str = None
):
    """
    Logs request information to the 'request_audit' table in Supabase.
    Fails gracefully if the database operation fails.
    """
    client = get_supabase_client()
    if not client:
        return

    payload = {
        "endpoint": endpoint,
        "status": status,
        "user_id": user_id,
        "username": username,
        "chat_id": chat_id,
        "command": command,
        "error_message": error_message,
        "execution_time_ms": execution_time_ms,
        "response_content": response_content,
        "topic": topic
    }

    # Clean up None values if they shouldn't be explicitly sent or let them be NULL in db
    try:
        # Use Supabase client to insert the audit record
        client.table("request_audit").insert(payload).execute()
        logger.info(f"Successfully logged request metadata to Supabase for endpoint: {endpoint}")
    except Exception as e:
        logger.error(f"Failed to insert audit log into Supabase: {e}")

def is_user_allowed(user_id: int) -> bool:
    """
    Checks if a Telegram user ID is present and active in the 'allowed_users' table in Supabase.
    Returns:
        True: if the user exists in the allowed list database and is active.
        False: if the user exists in the database but is inactive.
        None: if the user is not found in the database, or the database is not configured,
              or the query fails (triggers fallback to environment variables allowlist).
    """
    client = get_supabase_client()
    if not client:
        return None

    try:
        response = client.table("allowed_users").select("is_active").eq("user_id", user_id).execute()
        if response.data is not None:
            if len(response.data) > 0:
                return response.data[0].get("is_active", True)
            return None
    except Exception as e:
        logger.warning(f"Could not query 'allowed_users' table in Supabase: {e}. Falling back to env variables.")
        return None
    return None

def is_user_admin(user_id: int) -> bool:
    """
    Checks if a Telegram user ID is an admin in the 'allowed_users' table.
    If the database is not configured or the user is not in the database,
    falls back to checking the environment variable bootstrap admin IDs.
    """
    client = get_supabase_client()
    if client:
        try:
            response = client.table("allowed_users").select("role, is_active").eq("user_id", user_id).execute()
            if response.data is not None and len(response.data) > 0:
                user_data = response.data[0]
                return user_data.get("role") == "admin" and user_data.get("is_active", True)
        except Exception as e:
            logger.warning(f"Could not query 'allowed_users' for admin status: {e}. Falling back to env variables.")

    # Fallback to bootstrap environment variables
    allowed_ids = set()
    for env_var in ["TELEGRAM_ALLOWED_USER_ID", "TELEGRAM_ALLOWED_USER_IDS", "TELEGRAM_CHAT_ID"]:
        val = os.getenv(env_var)
        if val:
            for chunk in val.split(','):
                chunk = chunk.strip()
                if chunk:
                    allowed_ids.add(chunk)
    return str(user_id) in allowed_ids

def allow_user(user_id: int, username: str = None, role: str = "regular") -> bool:
    """
    Inserts or updates a user in the 'allowed_users' table, setting them to active.
    Returns True if successful, False otherwise.
    """
    client = get_supabase_client()
    if not client:
        logger.error("Supabase client is not available. Cannot allow user.")
        return False

    payload = {
        "user_id": user_id,
        "is_active": True
    }
    if username is not None:
        payload["username"] = username
    if role in ("admin", "regular"):
        payload["role"] = role

    try:
        client.table("allowed_users").upsert(payload).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to upsert allowed user: {e}")
        return False

def revoke_user(user_id: int) -> bool:
    """
    Deactivates a user in the 'allowed_users' table (setting is_active to False).
    Returns True if successful, False otherwise.
    """
    client = get_supabase_client()
    if not client:
        logger.error("Supabase client is not available. Cannot revoke user.")
        return False

    try:
        client.table("allowed_users").update({"is_active": False}).eq("user_id", user_id).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to update user active status to False: {e}")
        return False

