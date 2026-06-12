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
