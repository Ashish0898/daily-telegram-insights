import os
import re
import html
import logging
import requests
from datetime import datetime, timezone

from src.generate_fact import generate_fact, generate_dynamic_news_query
from src.talivy_search import talivy_search, format_search_results

logger = logging.getLogger("telegram_utils")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

def parse_command(text: str) -> dict:
    """
    Parses dynamic bot text commands and splits them into a dict payload.
    """
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
    """
    Builds the standard HTML formatted /help info text.
    """
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
    """
    Retrieves the formatted response string and its resolved topic/seed for logging.
    """
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
    """
    Sends an HTML formatted message directly to a Telegram chat ID.
    """
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
    except requests.HTTPError:
        logger.error(f"Telegram API Error response: {response.text}")
        logger.error(f"Failed to send text:\n{text}")
        raise
