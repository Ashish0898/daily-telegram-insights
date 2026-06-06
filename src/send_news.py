#!/usr/bin/env python3
"""Send Talivy web updates to Telegram."""

import argparse
import html
import os
import requests
from datetime import datetime, timezone

from talivy_search import (
    clean_text_for_telegram,
    talivy_search,
    format_search_results,
    parse_talivy_results,
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"


def send_telegram_message(message: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in environment variables.")

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    response = requests.post(TELEGRAM_API, json=payload, timeout=10)
    try:
        response.raise_for_status()
    except requests.HTTPError:
        print("Telegram request payload:", payload)
        print("Telegram response status:", response.status_code)
        print("Telegram response body:", response.text)
        raise


def build_message(query: str, raw_data: dict, limit: int) -> str:
    summary = format_search_results(query, raw_data, limit=limit)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"<b>📡 Web update</b>\n\n{summary}\n\n<i>{timestamp}</i>"


def build_item_message(query: str, item: dict, index: int, total: int) -> str:
    title = clean_text_for_telegram(
        item.get("title") or item.get("headline") or "Untitled"
    )
    snippet = clean_text_for_telegram(
        item.get("content")
        or item.get("snippet")
        or item.get("summary")
        or item.get("description")
        or item.get("raw_content")
        or "No description available."
    )
    url = item.get("url")
    if url:
        url = html.escape(str(url), quote=True)

    lines = [
        f"<b>📡 Web update ({index}/{total})</b>",
        f"<b>{title}</b>",
    ]
    lines.append(snippet)
    if url:
        lines.append(f"<a href=\"{url}\">Read more</a>")
    return "\n\n".join(lines).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Send Talivy web search results to Telegram.")
    parser.add_argument("--query", default="latest FIFA WC news", help="Search query to send to Telegram")
    parser.add_argument("--limit", type=int, default=5, help="Number of top results to include")
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Send a single summary message instead of individual result messages.",
    )
    args = parser.parse_args()

    if not os.getenv("TALIVY_API_KEY") or not os.getenv("TALIVY_ENDPOINT"):
        raise ValueError("TALIVY_API_KEY and TALIVY_ENDPOINT must be set to use Talivy.")

    print(f"Searching Talivy for: {args.query}")
    raw_data = talivy_search(args.query, limit=args.limit)
    results = parse_talivy_results(raw_data)

    if args.summary or not results:
        message = build_message(args.query, raw_data, limit=args.limit)
        print("Sending news summary to Telegram...")
        send_telegram_message(message)
    else:
        count = min(args.limit, len(results))
        print(f"Sending {count} individual messages to Telegram...")
        for index, item in enumerate(results[:count], start=1):
            message = build_item_message(args.query, item, index, count)
            send_telegram_message(message)

    print("Done!")


if __name__ == "__main__":
    main()
