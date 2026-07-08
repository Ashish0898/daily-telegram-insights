import os
import logging
from supabase import create_client, Client

logger = logging.getLogger("db")

BOT_NAME = "insights"

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
    Checks if a Telegram user ID is present and active in the 'user_bot_access' table for this bot.
    Returns:
        True: if the user exists and is active for this bot.
        False: if the user exists but is inactive for this bot.
        None: if the user is not found, or the database is not configured, or query fails.
    """
    client = get_supabase_client()
    if not client:
        return None

    try:
        response = client.table("user_bot_access").select("is_active").eq("user_id", user_id).eq("bot_name", BOT_NAME).execute()
        if response.data is not None:
            if len(response.data) > 0:
                return response.data[0].get("is_active", True)
            return None
    except Exception as e:
        logger.warning(f"Could not query 'user_bot_access' table in Supabase: {e}. Falling back to env variables.")
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


def get_admin_user_ids() -> list[int]:
    """
    Retrieves all Telegram user IDs of active admins from the database.
    Also falls back to the bootstrap env variables if none are found.
    """
    admin_ids = []
    client = get_supabase_client()
    if client:
        try:
            response = client.table("allowed_users").select("user_id").eq("role", "admin").eq("is_active", True).execute()
            if response.data:
                for row in response.data:
                    uid = row.get("user_id")
                    if uid:
                        admin_ids.append(int(uid))
        except Exception as e:
            logger.warning(f"Could not query database for admin user IDs: {e}")

    # If no database admins found, fall back to environment variables
    if not admin_ids:
        for env_var in ["TELEGRAM_ALLOWED_USER_ID", "TELEGRAM_ALLOWED_USER_IDS", "TELEGRAM_CHAT_ID"]:
            val = os.getenv(env_var)
            if val:
                for chunk in val.split(','):
                    chunk = chunk.strip()
                    if chunk.isdigit() or (chunk.startswith('-') and chunk[1:].isdigit()):
                        admin_ids.append(int(chunk))
    return list(set(admin_ids))


def allow_user(user_id: int, username: str = None, role: str = "regular", email: str = None) -> tuple[bool, str | None]:
    """
    Inserts or updates a user profile in the 'allowed_users' table, and
    sets the user's status to active in 'user_bot_access' for this bot.
    Returns (True, None) if successful, (False, error_message) otherwise.
    """
    client = get_supabase_client()
    if not client:
        err_msg = "Supabase client is not available. Cannot allow user."
        logger.error(err_msg)
        return False, err_msg

    user_payload = {
        "user_id": user_id
    }
    if username is not None:
        user_payload["username"] = username.lstrip('@')
    if role in ("admin", "regular"):
        user_payload["role"] = role
    if email is not None:
        user_payload["email"] = email

    access_payload = {
        "user_id": user_id,
        "bot_name": BOT_NAME,
        "is_active": True
    }

    try:
        # Upsert the user profile first
        client.table("allowed_users").upsert(user_payload).execute()
        # Upsert the bot access record next
        client.table("user_bot_access").upsert(access_payload).execute()
        return True, None
    except Exception as e:
        logger.exception(f"Failed to allow user {user_id} for bot {BOT_NAME}")
        return False, str(e)


def revoke_user(user_id: int) -> tuple[bool, str | None]:
    """
    Deactivates a user's bot access in 'user_bot_access' table (setting is_active to False).
    Returns (True, None) if successful, (False, error_message) otherwise.
    """
    client = get_supabase_client()
    if not client:
        err_msg = "Supabase client is not available. Cannot revoke user."
        logger.error(err_msg)
        return False, err_msg

    try:
        client.table("user_bot_access").upsert({
            "user_id": user_id,
            "bot_name": BOT_NAME,
            "is_active": False
        }).execute()
        return True, None
    except Exception as e:
        logger.exception(f"Failed to update user active status to False for user {user_id}")
        return False, str(e)


def register_inactive_user_if_new(user_id: int, username: str = None) -> bool:
    """
    Checks if a Telegram user is present in 'user_bot_access' for this bot.
    If not present:
      - Upserts the user profile in 'allowed_users'.
      - Inserts the access record in 'user_bot_access' with is_active = False.
    Returns True if a new bot access was registered, False otherwise.
    """
    client = get_supabase_client()
    if not client:
        logger.error("Supabase client is not available. Cannot register inactive user.")
        return False

    try:
        # Check if they already have access record for this bot
        response = client.table("user_bot_access").select("user_id").eq("user_id", user_id).eq("bot_name", BOT_NAME).execute()
        if response.data is not None and len(response.data) > 0:
            logger.info(f"User {user_id} already has access record for {BOT_NAME} in database. No need to register.")
            return False

        # Upsert allowed_users profile first
        user_payload = {
            "user_id": user_id,
            "role": "regular",
            "is_active": False
        }
        if username is not None:
            user_payload["username"] = username.lstrip('@')
        client.table("allowed_users").upsert(user_payload).execute()


        # Insert inactive access record for this bot
        payload = {
            "user_id": user_id,
            "bot_name": BOT_NAME,
            "is_active": False
        }
        client.table("user_bot_access").insert(payload).execute()
        logger.info(f"Registered new inactive user access: {user_id} (bot: {BOT_NAME})")
        return True
    except Exception as e:
        logger.exception(f"Failed to register inactive user access for {user_id} on {BOT_NAME}")
        return False


def resolve_user_details(identifier: str) -> tuple[int | None, str | None]:
    """
    Resolves a string identifier to a numeric Telegram User ID and their username.
    The identifier can be a numeric string or a Telegram username (with or without '@').
    Queries the database if needed.
    Returns (user_id, username) or (None, None) if not found.
    """
    if not identifier:
        return None, None

    identifier = identifier.strip()

    client = get_supabase_client()
    if not client:
        logger.error("Supabase client is not available. Cannot resolve user details.")
        return None, None

    # Check if it's already a numeric ID
    try:
        user_id = int(identifier)
        # Fetch the username from database for this user_id if they exist
        try:
            response = client.table("allowed_users").select("username").eq("user_id", user_id).execute()
            if response.data and len(response.data) > 0:
                return user_id, response.data[0].get("username")
        except Exception:
            pass
        return user_id, None
    except ValueError:
        pass

    # Clean username prefix if any
    username = identifier.lstrip('@')

    try:
        # Query database case-insensitively or exactly
        response = client.table("allowed_users").select("user_id, username").eq("username", username).execute()
        if response.data and len(response.data) > 0:
            row = response.data[0]
            return row.get("user_id"), row.get("username")

        response = client.table("allowed_users").select("user_id, username").ilike("username", username).execute()
        if response.data and len(response.data) > 0:
            row = response.data[0]
            return row.get("user_id"), row.get("username")

        logger.info(f"Username '{username}' not found in database.")
        return None, None
    except Exception as e:
        logger.exception(f"Failed to resolve username '{username}' to user ID and username")
        return None, None


def get_all_users() -> list[dict] | None:
    """
    Retrieves all users from the 'allowed_users' table in Supabase, merging their
    active status from 'user_bot_access' for this bot.
    Returns a list of dicts, or None if the operation fails.
    """
    client = get_supabase_client()
    if not client:
        logger.error("Supabase client is not available. Cannot fetch all users.")
        return None

    try:
        # Fetch all user profiles
        response = client.table("allowed_users").select("*").order("created_at").execute()
        users = response.data or []

        # Fetch access status for this bot
        access_resp = client.table("user_bot_access").select("user_id, is_active").eq("bot_name", BOT_NAME).execute()
        access_map = {row["user_id"]: row["is_active"] for row in (access_resp.data or [])}

        # Merge is_active status
        for u in users:
            u["is_active"] = access_map.get(u["user_id"], False)

        return users
    except Exception as e:
        logger.exception("Failed to fetch all users from database")
        return None


def is_email_admin(email: str) -> bool:
    """
    Checks if an email address is associated with an active admin in the 'allowed_users' table.
    """
    if not email:
        return False
    client = get_supabase_client()
    if not client:
        return False
    try:
        response = client.table("allowed_users").select("user_id, role").eq("email", email).execute()
        if response.data and len(response.data) > 0:
            user_data = response.data[0]
            user_id = user_data.get("user_id")
            role = user_data.get("role")
            if role != "admin":
                return False
            
            # Check if active for insights
            if user_id:
                access_resp = client.table("user_bot_access").select("is_active").eq("user_id", user_id).eq("bot_name", BOT_NAME).execute()
                if access_resp.data and len(access_resp.data) > 0:
                    return access_resp.data[0].get("is_active", False)
            return True
    except Exception as e:
        logger.error(f"Failed to query 'allowed_users' by email {email}: {e}")
    return False




