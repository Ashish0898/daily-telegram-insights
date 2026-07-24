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
    clean_news_title,
    summarize_item_with_llm,
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
    summary = format_search_results(query, raw_data, limit=limit, use_llm=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"{summary}\n\n<i>{timestamp}</i>"


def execute_and_send_news(chat_id: int | str | list[int | str], query: str | None = None, limit: int = 3, summary: bool = True):
    """Fetch news from Talivy and send to Telegram as a unified bulleted digest.

    Args:
        chat_id: Single chat ID or a list of chat IDs.
        query: Optional search query string.
        limit: Max results count.
        summary: Retained for backward compatibility.

    Returns:
        tuple: (count of news results sent, final search query used, list of message texts sent)
    """
    chat_ids = [chat_id] if not isinstance(chat_id, list) else chat_id

    if not query:
        try:
            from generate_fact import generate_dynamic_news_query
            query = generate_dynamic_news_query()
        except Exception as e:
            logger.error(f"Failed to generate dynamic query: {e}. Using fallback.")
            query = "world news at a glance today"

    logger.info(f"Searching Talivy for: {query}")
    raw_data = talivy_search(query, limit=limit, topic="news", search_depth="advanced")
    results = parse_talivy_results(raw_data)

    message = build_message(query, raw_data, limit=limit)
    messages_to_send = [message]

    sent_texts = []
    logger.info(f"Sending news digest message to {len(chat_ids)} recipient(s)...")
    for cid in chat_ids:
        for msg in messages_to_send:
            try:
                send_telegram_message(cid, msg)
                sent_texts.append(msg)
            except Exception as e:
                logger.error(f"Failed to send news message to chat {cid}: {e}")

    return len(results), query, sent_texts


def main() -> None:
    parser = argparse.ArgumentParser(description="Send Talivy web search results to Telegram.")
    parser.add_argument("--query", default=None, help="Search query to send to Telegram (defaults to a dynamic LLM-generated query)")
    parser.add_argument("--limit", type=int, default=3, help="Number of top results to include")
    args = parser.parse_args()

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
    )
    logger.info("Done!")


if __name__ == "__main__":
    main()
