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
    get_all_users,
    get_admin_user_ids
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

    logger.info(f"Incoming webhook request: user_id={from_id}, username={username}, chat_id={chat_id}, command_text='{command_text}'")

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
    logger.info(f"Database lookup for user {from_id}: is_allowed={is_allowed}")

    # Check if the command is /start
    is_start_command = command_text.strip().lower().startswith("/start")
    logger.info(f"Authorization check result: is_allowed={is_allowed} for user_id={from_id}, is_start_command={is_start_command}")

    was_registered = False
    if is_allowed is None and from_id is not None and is_start_command:
        # Check if they are already allowed via environment variables fallback
        allowed_ids = set()
        for env_var in ["TELEGRAM_ALLOWED_USER_ID", "TELEGRAM_ALLOWED_USER_IDS", "TELEGRAM_CHAT_ID"]:
            val = os.getenv(env_var)
            if val:
                logger.info(f"Checking environment variable {env_var}")
                for chunk in val.split(','):
                    chunk = chunk.strip()
                    if chunk:
                        allowed_ids.add(chunk)
        
        # If not in env vars allowlist, register as inactive in db
        if not (allowed_ids and str(from_id) in allowed_ids):
            logger.info(f"User {from_id} is not in allowed_ids={allowed_ids}. Registering inactive...")
            was_registered = register_inactive_user_if_new(from_id, username)
            logger.info(f"Registration result: was_registered={was_registered}")
            is_allowed = False
            
            # Send notification to admins if they just registered as inactive
            if was_registered:
                admin_ids = get_admin_user_ids()
                logger.info(f"Admins to notify: {admin_ids}")
                user_label = f"@{username}" if username else f"User ID {from_id}"
                admin_msg = (
                    f"🔔 <b>New Access Request</b>\n\n"
                    f"User {user_label} (ID: <code>{from_id}</code>) is requesting access to the daily insights bot.\n\n"
                    f"To grant access, send:\n"
                    f"<code>/allow {from_id}</code>"
                )
                for admin_id in admin_ids:
                    try:
                        logger.info(f"Attempting to send access request notification to admin {admin_id}...")
                        send_telegram_message(admin_id, admin_msg)
                        logger.info(f"Successfully notified admin {admin_id}.")
                    except Exception as ex:
                        logger.error(f"Failed to send access request notification to admin {admin_id}: {ex}")
        else:
            logger.info(f"User {from_id} found in environment allowlist. Allowing access.")

    if is_allowed is False:
        access_denied = True
        logger.info(f"Access denied for user {from_id}: is_allowed=False")
    elif is_allowed is True:
        access_denied = False
        logger.info(f"Access granted for user {from_id}: is_allowed=True")
    else:
        # Fallback to checking environment variables
        allowed_ids = set()
        for env_var in ["TELEGRAM_ALLOWED_USER_ID", "TELEGRAM_ALLOWED_USER_IDS", "TELEGRAM_CHAT_ID"]:
            val = os.getenv(env_var)
            if val:
                logger.info(f"Fallback: Checking environment variable {env_var}")
                for chunk in val.split(','):
                    chunk = chunk.strip()
                    if chunk:
                        allowed_ids.add(chunk)
        if allowed_ids:
            access_denied = not from_id or str(from_id) not in allowed_ids
            logger.info(f"Fallback check: allowed_ids={allowed_ids}, user_id={from_id}, access_denied={access_denied}")
        else:
            access_denied = False
            logger.info(f"Fallback: No environment allowlist configured. Allowing access.")

    if access_denied:
        logger.warning(f"User ID {from_id} not in allowlist. Sending Access Denied message and ignoring request.")
        
        # Get admin contact handle from environment
        admin_username_env = os.getenv("TELEGRAM_ADMIN_USERNAME", "").strip()
        admin_contact = ""
        if admin_username_env:
            contact_handle = admin_username_env
            if not contact_handle.startswith("@"):
                contact_handle = "@" + contact_handle
            admin_contact = f" ({contact_handle})"

        if from_id:
            response_text = f"⚠️ <b>Access Denied</b>\n\nYou are not authorized to use this bot. Please contact the administrator{admin_contact} with your User ID: <code>{from_id}</code> to request access."
        else:
            response_text = f"⚠️ <b>Access Denied</b>\n\nYou are not authorized to use this bot. Please contact the administrator{admin_contact} to request access."
        
        logger.info(f"Sending access denied response to user {from_id}")
        if chat_id:
            try:
                send_telegram_message(chat_id, response_text)
                logger.info(f"Successfully sent access denied message to chat {chat_id}")
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

        logger.info(f"Parsed command: type={cmd_type}, query={query}")
        logger.info(f"Executing command: {cmd_type} (query: {query}) for chat: {chat_id}")

        is_admin = is_user_admin(from_id) if from_id is not None else False
        logger.info(f"Admin check for user {from_id}: is_admin={is_admin}")

        # Role check for administrative commands
        if cmd_type in ("allow", "revoke", "users") and not is_admin:
            logger.warning(f"Unauthorized admin command attempt from user ID {from_id}: attempting '{cmd_type}'")
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
            logger.info(f"Executing news/search command with query: {query}")
            count, final_query, sent_texts = execute_and_send_news(chat_id, query, limit=3, summary=False)
            logger.info(f"News command completed: retrieved {count} articles, final_query={final_query}")
            response_text = "\n\n---\n\n".join(sent_texts)
            topic = final_query
        elif cmd_type == "allow":
            logger.info(f"Admin '{username}' (ID: {from_id}) executing allow command with query: {query}")
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

                logger.info(f"Resolving user details for identifier: {target_identifier}")
                target_id, target_username = resolve_user_details(target_identifier)
                logger.info(f"Resolved: target_id={target_id}, target_username={target_username}")
                if target_id is None:
                    response_text = f"❌ <b>Error:</b> Could not find or resolve user <code>{target_identifier}</code> in the database. Please ensure they have started the bot by sending a message."
                else:
                    logger.info(f"Updating user {target_id} to role '{role}'")
                    success, err = allow_user(target_id, role=role)
                    if success:
                        response_text = f"✅ <b>User Allowed Successfully</b>\n\n• <b>User ID:</b> <code>{target_id}</code>\n• <b>Role:</b> {role}"
                        if target_username:
                            response_text += f"\n• <b>Username:</b> @{target_username}"
                        logger.info(f"Successfully allowed user {target_id} with role {role}")
                        try:
                            user_notify_msg = (
                                "🎉 <b>Access Granted</b>\n\n"
                                "You have been authorized to use the daily insights bot. "
                                "Send /start to get started!"
                            )
                            send_telegram_message(target_id, user_notify_msg)
                            logger.info(f"Sent access granted notification to user {target_id}")
                        except Exception as ex:
                            logger.error(f"Failed to send access granted notification to user {target_id}: {ex}")
                    else:
                        response_text = f"❌ <b>Error:</b> Failed to update user <code>{target_id}</code> in database. Details: <code>{html.escape(str(err))}</code>"
                        logger.error(f"Failed to allow user {target_id}: {err}")
            
            send_telegram_message(chat_id, response_text)
            topic = f"allow_user_{query}"
        elif cmd_type == "revoke":
            logger.info(f"Admin '{username}' (ID: {from_id}) executing revoke command with query: {query}")
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
                logger.info(f"Resolving user details for identifier: {target_identifier}")
                target_id, target_username = resolve_user_details(target_identifier)
                logger.info(f"Resolved: target_id={target_id}, target_username={target_username}")
                if target_id is None:
                    response_text = f"❌ <b>Error:</b> Could not find or resolve user <code>{target_identifier}</code> in the database."
                else:
                    logger.info(f"Revoking access for user {target_id}")
                    success, err = revoke_user(target_id)
                    if success:
                        response_text = f"🚫 <b>User Revoked</b>\n\nUser ID <code>{target_id}</code> has been deactivated. They will no longer have access to the bot."
                        if target_username:
                            response_text += f"\n• <b>Username:</b> @{target_username}"
                        logger.info(f"Successfully revoked user {target_id}")
                        try:
                            user_notify_msg = (
                                "🚫 <b>Access Revoked</b>\n\n"
                                "Your access to the daily insights bot has been revoked by the administrator."
                            )
                            send_telegram_message(target_id, user_notify_msg)
                            logger.info(f"Sent access revoked notification to user {target_id}")
                        except Exception as ex:
                            logger.error(f"Failed to send access revoked notification to user {target_id}: {ex}")
                    else:
                        response_text = f"❌ <b>Error:</b> Failed to deactivate user <code>{target_id}</code> in database. Details: <code>{html.escape(str(err))}</code>"
                        logger.error(f"Failed to revoke user {target_id}: {err}")
            
            send_telegram_message(chat_id, response_text)
            topic = f"revoke_user_{query}"
        elif cmd_type == "users":
            logger.info(f"Admin '{username}' (ID: {from_id}) executing users list command")
            users = get_all_users()
            logger.info(f"Retrieved {len(users) if users else 0} users from database")
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
            logger.info(f"Executing standard command: {cmd_type}")
            response_text, topic = get_response_text(cmd, is_admin=is_admin)
            logger.info(f"Standard command response topic: {topic}")
            send_telegram_message(chat_id, response_text)

        logger.info(f"Successfully completed command {cmd_type}. Execution time: {(time.time() - start_time) * 1000:.2f}ms")
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
        logger.error(f"Exception details: {str(e)}")
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
