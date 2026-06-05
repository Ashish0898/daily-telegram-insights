#!/usr/bin/env python3
"""Handle a Telegram repository_dispatch event from GitHub Actions."""

import json
import os
import requests

from generate_fact import generate_fact
from talivy_search import format_search_results, talivy_search

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"


def load_event_payload() -> dict:
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path:
        raise RuntimeError("GITHUB_EVENT_PATH is not set")

    with open(event_path, "r", encoding="utf-8") as event_file:
        event = json.load(event_file)

    return event.get("client_payload", {})


def send_telegram_message(chat_id: int, text: str) -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN must be set")

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    response = requests.post(TELEGRAM_API, json=payload, timeout=15)
    response.raise_for_status()


def build_response(command: str, query: str | None) -> str:
    if command == "news":
        search_query = query or "latest FIFA WC news"
        raw = talivy_search(search_query, limit=3)
        return format_search_results(search_query, raw, limit=3)

    if command == "search":
        search_query = query or "latest news"
        raw = talivy_search(search_query, limit=3)
        return format_search_results(search_query, raw, limit=3)

    if command == "help":
        return (
            "Hello! 🤖\n\n"
            "Use /fact to receive a new random fact.\n"
            "Use /news to get the latest Talivy news summary.\n"
            "Use /search <query> to search something specific."
        )

    return generate_fact()


def main() -> None:
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        raise ValueError("TELEGRAM_BOT_TOKEN must be set in GitHub Actions environment")

    payload = load_event_payload()
    chat_id = payload.get("chat_id")
    if not chat_id:
        raise RuntimeError("No chat_id found in repository_dispatch payload")

    command = payload.get("command", "fact")
    query = payload.get("query")

    message = build_response(command, query)
    send_telegram_message(chat_id, message)


if __name__ == "__main__":
    main()
