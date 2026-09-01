import re
import html
import logging
import requests
from datetime import datetime, timezone

from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_API_URL
from src.generate_fact import generate_fact, MODES
from src.send_news import generate_dynamic_news_query
from src.talivy_search import talivy_search, format_search_results

logger = logging.getLogger("telegram_utils")


def parse_command(text: str) -> dict:
    """Parses dynamic bot text commands and splits them into a dict payload."""
    if not text:
        return {"type": "insight", "query": None, "mode": None}

    trimmed = text.strip()
    normalized = trimmed.lower()

    if normalized.startswith("/insight") or normalized.startswith("/fact") or normalized.startswith("/daily"):
        return {"type": "insight", "query": None, "mode": None}

    if normalized.startswith("/model") or normalized.startswith("/mentalmodel"):
        return {"type": "insight", "query": None, "mode": "mental_model"}

    if normalized.startswith("/bias") or normalized.startswith("/cognitive"):
        return {"type": "insight", "query": None, "mode": "cognitive_bias"}

    if normalized.startswith("/paradox"):
        return {"type": "insight", "query": None, "mode": "paradox"}

    if normalized.startswith("/brain") or normalized.startswith("/neuro"):
        return {"type": "insight", "query": None, "mode": "neuroscience"}

    if normalized.startswith("/puzzle") or normalized.startswith("/thought"):
        return {"type": "insight", "query": None, "mode": "thought_experiment"}

    if normalized.startswith("/quote"):
        return {"type": "insight", "query": None, "mode": "quote"}

    if normalized.startswith("/news"):
        query = re.sub(r"^/news\s*", "", trimmed, flags=re.IGNORECASE).strip()
        return {
            "type": "news",
            "query": query or None,
            "mode": None
        }

    if normalized.startswith("/search"):
        query = re.sub(r"^/search\s*", "", trimmed, flags=re.IGNORECASE).strip()
        return {
            "type": "search",
            "query": query or "latest news",
            "mode": None
        }

    if normalized.startswith("/help") or normalized.startswith("/start"):
        return {"type": "help", "query": None, "mode": None}

    if normalized.startswith("/allow"):
        query = re.sub(r"^/allow(@\w+)?\s*", "", trimmed, flags=re.IGNORECASE).strip()
        return {
            "type": "allow",
            "query": query or None,
            "mode": None
        }

    if normalized.startswith("/revoke"):
        query = re.sub(r"^/revoke(@\w+)?\s*", "", trimmed, flags=re.IGNORECASE).strip()
        return {
            "type": "revoke",
            "query": query or None,
            "mode": None
        }

    if normalized.startswith("/users"):
        return {"type": "users", "query": None, "mode": None}

    return {"type": "insight", "query": None, "mode": None}


def build_help_message(is_admin: bool = False) -> str:
    """Builds the standard HTML formatted /help info text."""
    msg = (
        "⚡ <b>Daily Cognitive Insights & News Bot</b> 🧠\n\n"
        "I deliver energizing mental models, cognitive biases, paradoxes, neuroscience hacks, and live news to keep your brain firing!\n\n"
        "<b>Available Commands:</b>\n"
        "• /insight — Get an instant brain jolt (mental model, bias, paradox, or fact)\n"
        "• /model — Explore a powerful Mental Model\n"
        "• /bias — Spot a subconscious Cognitive Bias\n"
        "• /paradox — Ponder a mind-bending Paradox\n"
        "• /brain — Learn a Neuroscience & Performance hack\n"
        "• /quote — Read timeless philosophy & modern takeaway\n"
        "• /news — Get a dynamic daily news digest\n"
        "• /news &lt;topic&gt; — Search live news on a specific subject\n"
        "• /help — Show this help message"
    )
    if is_admin:
        msg += (
            "\n\n🛡️ <b>Admin Commands:</b>\n"
            "• /allow &lt;user_id_or_username&gt; [role] — Grant bot access\n"
            "• /revoke &lt;user_id_or_username&gt; — Revoke access\n"
            "• /users — List all registered users"
        )
    return msg


def get_response_text(cmd: dict, is_admin: bool = False) -> tuple:
    """Retrieves the formatted response string and its resolved topic/seed for logging."""
    cmd_type = cmd["type"]
    query = cmd.get("query")
    mode = cmd.get("mode")

    if cmd_type == "help":
        return build_help_message(is_admin), "help"

    if cmd_type in ("insight", "fact"):
        content, topic, resolved_mode = generate_fact(mode=mode, return_topic=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        return f"{content}\n\n<i>{timestamp}</i>", topic

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


def send_telegram_message(chat_id: int | str, text: str) -> None:
    """Sends an HTML formatted message directly to a Telegram chat ID with auto-recovery fallback."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN must be set in environment variables.")

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    api_url = TELEGRAM_API_URL or f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    response = requests.post(api_url, json=payload, timeout=15)
    
    # Auto-recovery: if Telegram fails due to entity parsing (e.g. unclosed tag or stray bracket), retry as clean text
    if response.status_code == 400 and ("can't parse entities" in response.text.lower() or "parsing" in response.text.lower()):
        logger.warning(f"Telegram HTML parse error: {response.text}. Retrying with sanitized text fallback.")
        clean_text = re.sub(r"<[^>]+>", "", text)
        fallback_payload = {
            "chat_id": chat_id,
            "text": clean_text,
            "disable_web_page_preview": False,
        }
        fallback_response = requests.post(api_url, json=fallback_payload, timeout=15)
        fallback_response.raise_for_status()
        return

    try:
        response.raise_for_status()
    except requests.HTTPError:
        logger.error(f"Telegram API Error response: {response.text}")
        logger.error(f"Failed to send text:\n{text}")
        raise
