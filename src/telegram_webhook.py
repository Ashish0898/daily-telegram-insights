import os
import time
import html
import logging

from src.db import (
    log_request,
    is_user_allowed,
    is_user_admin,
    allow_user,
    revoke_user,
    register_inactive_user_if_new,
    resolve_user_details,
    get_all_users
)
from src.send_news import execute_and_send_news
from src.telegram_utils import parse_command, send_telegram_message, get_response_text

logger = logging.getLogger("telegram_webhook")

TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")

def process_telegram_webhook(body: dict, secret_token: str | None) -> tuple[int, dict]:
    """
    Validates, authorizes, parses, and executes interactive Telegram commands.
    Returns (status_code, response_body).
    """
    start_time = time.time()
    
    # 1. Validate incoming payload structure
    message = body.get("message")
    if not message:
        # Ignore non-message updates (e.g. edited_message, channel_post, my_chat_member)
        logger.info("Incoming update does not contain a message field. Ignoring.")
        return 200, {"ok": True, "reason": "ignored_non_message_update"}

    # Validate header token security if TELEGRAM_WEBHOOK_SECRET is set
    if TELEGRAM_WEBHOOK_SECRET and secret_token != TELEGRAM_WEBHOOK_SECRET:
        logger.warning("Secret token header mismatch. Ignoring request.")
        return 403, {"error": "unauthorized"}

    chat = message.get("chat")
    chat_id = chat.get("id") if chat else None
    command_text = message.get("text", "")

    # Extract user information for logging
    from_user = message.get("from")
    from_id = from_user.get("id") if from_user else None
    user_id = from_id
    username = from_user.get("username") if from_user else None

    if not command_text:
        logger.info("Message does not contain any text. Ignoring.")
        log_request(
            endpoint="webhook",
            status="ignored_no_text",
            user_id=user_id,
            username=username,
            chat_id=chat_id,
            execution_time_ms=int((time.time() - start_time) * 1000)
        )
        return 200, {"ok": True, "reason": "ignored_no_text"}

    # 2. Allowlist / Authorization checks
    is_allowed = is_user_allowed(from_id) if from_id is not None else None

    # Check if the command is /start
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
        return 200, {"ok": True, "reason": "ignored_user_not_allowlisted"}

    if not chat_id:
        logger.error("Request missing chat ID.")
        log_request(
            endpoint="webhook",
            status="missing_chat_id",
            user_id=user_id,
            username=username,
            command=command_text,
            execution_time_ms=int((time.time() - start_time) * 1000)
        )
        return 400, {"error": "missing_chat_id"}

    # 3. Parse and execute the command
    try:
        cmd = parse_command(command_text)
        cmd_type = cmd["type"]
        query = cmd["query"]

        logger.info(f"Executing command: {cmd_type} (query: {query}) for chat: {chat_id}")

        is_admin = is_user_admin(from_id) if from_id is not None else False

        # Role check for administrative commands
        if cmd_type in ("allow", "revoke", "users") and not is_admin:
            logger.warning(f"Unauthorized admin command attempt from user ID {from_id}")
            response_text = "⚠️ <b>Access Denied</b>\n\nYou must be an admin to perform this action."
            send_telegram_message(chat_id, response_text)
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
            return 200, {"ok": True}

        # Command Dispatch Router
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
        return 200, {"ok": True}
    except Exception as e:
        logger.exception("Error executing Telegram command webhook")
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
        return 500, {"error": str(e)}
