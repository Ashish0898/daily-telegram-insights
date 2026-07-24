#!/usr/bin/env python3
"""Handle a Telegram repository_dispatch event from GitHub Actions."""

import json
import os
import requests
import logging
from datetime import datetime, timezone

from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_API_URL
from src.generate_fact import generate_fact
from src.send_news import execute_and_send_news

logger = logging.getLogger("handle_telegram")


def load_event_payload() -> dict:
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path:
        raise RuntimeError("GITHUB_EVENT_PATH is not set")

    with open(event_path, "r", encoding="utf-8") as event_file:
        event = json.load(event_file)

    return event.get("client_payload", {})


def send_telegram_message(chat_id: int | str, text: str) -> None:
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
    response.raise_for_status()


def build_response(command: str, query: str | None) -> str:
    if command == "help":
        return (
            "Hello! 🤖\n\n"
            "Use /fact to receive a new random fact.\n"
            "Use /news to get a dynamic daily news digest, or /news <query> for a specific topic.\n"
            "Use /search <query> to search Talivy for custom web results.\n"
            "Use /help to show this message again."
        )

    content, insight_type = generate_fact()
    header = "<b>🎯 Daily Fact</b>" if insight_type == "fact" else "<b>💡 Daily Quote</b>"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"{header}\n\n{content}\n\n<i>{timestamp}</i>"


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN must be set in environment")

    payload = load_event_payload()
    chat_id = payload.get("chat_id")
    if not chat_id:
        raise RuntimeError("No chat_id found in repository_dispatch payload")

    command = payload.get("command", "fact")
    query = payload.get("query")

    if command in ("news", "search"):
        execute_and_send_news(chat_id, query, limit=3)
    else:
        message = build_response(command, query)
        send_telegram_message(chat_id, message)


if __name__ == "__main__":
    main()
