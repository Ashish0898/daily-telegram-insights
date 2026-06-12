#!/usr/bin/env python3
"""Send Talivy web updates to Telegram."""

import argparse
import html
import os
import requests
import logging
from datetime import datetime, timezone

from talivy_search import (
    clean_text_for_telegram,
    talivy_search,
    format_search_results,
    parse_talivy_results,
)

logger = logging.getLogger("send_news")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage" if TELEGRAM_BOT_TOKEN else ""


def send_telegram_message(chat_id: int | str, message: str) -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN must be set in environment variables.")

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    logger.info(f"Sending message to Telegram chat {chat_id} (size: {len(message)} chars)")
    response = requests.post(TELEGRAM_API, json=payload, timeout=15)
    try:
        response.raise_for_status()
    except requests.HTTPError:
        logger.error(f"Telegram API response status: {response.status_code}")
        logger.error(f"Telegram response body: {response.text}")
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


def execute_and_send_news(chat_id: int | str, query: str | None = None, limit: int = 3, summary: bool = False):
    """Fetch news from Talivy and send to Telegram (either as a single summary or batch messages).

    Returns:
        tuple: (count of news results sent, final search query used, list of message texts sent)
    """
    if not query:
        try:
            from generate_fact import generate_dynamic_news_query
            query = generate_dynamic_news_query()
        except Exception as e:
            logger.error(f"Failed to generate dynamic query: {e}. Using fallback.")
            query = "world news at a glance today"

    logger.info(f"Searching Talivy for: {query}")
    raw_data = talivy_search(query, limit=limit)
    results = parse_talivy_results(raw_data)

    sent_texts = []
    if summary or not results:
        message = build_message(query, raw_data, limit=limit)
        logger.info("Sending news summary to Telegram...")
        send_telegram_message(chat_id, message)
        sent_texts.append(message)
        return len(results), query, sent_texts
    else:
        count = min(limit, len(results))
        logger.info(f"Sending {count} individual messages to Telegram...")
        for index, item in enumerate(results[:count], start=1):
            message = build_item_message(query, item, index, count)
            send_telegram_message(chat_id, message)
            sent_texts.append(message)
        return count, query, sent_texts


def main() -> None:
    parser = argparse.ArgumentParser(description="Send Talivy web search results to Telegram.")
    parser.add_argument("--query", default=None, help="Search query to send to Telegram (defaults to a dynamic LLM-generated query)")
    parser.add_argument("--limit", type=int, default=3, help="Number of top results to include")
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Send a single summary message instead of individual result messages.",
    )
    args = parser.parse_args()

    # If running as command line, configure root logger to output to stdout
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )

    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not telegram_chat_id:
        raise ValueError("TELEGRAM_CHAT_ID must be set in environment variables.")

    execute_and_send_news(
        chat_id=telegram_chat_id,
        query=args.query,
        limit=args.limit,
        summary=args.summary,
    )
    logger.info("Done!")


if __name__ == "__main__":
    main()
