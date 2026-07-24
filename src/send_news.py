#!/usr/bin/env python3
"""Send web updates and news digests to Telegram."""

import argparse
import random
import os
import requests
import logging
from datetime import datetime, timezone

from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_API_URL, TELEGRAM_CHAT_ID
from src.llm_client import generate_llm_response
from src.talivy_search import (
    talivy_search,
    format_search_results,
    parse_talivy_results,
)

logger = logging.getLogger("send_news")


def generate_dynamic_news_query() -> str:
    """Generate a dynamic, interesting news search query using LLM client wrapper."""
    categories = [
        "artificial intelligence", "space exploration", "renewable energy",
        "marine biology", "archaeological discoveries", "medical breakthroughs",
        "quantum computing", "fusion energy", "consumer tech innovations",
        "paleontology", "astrophysics", "robotics"
    ]
    selected_cat = random.choice(categories)
    current_date = datetime.now(timezone.utc).strftime("%B %Y")

    user_content = (
        f"The current date is {current_date}.\n"
        f"Generate a short (3-6 words) search query to find the latest, most interesting news, "
        f"discoveries, or breakthroughs in the field of: '{selected_cat}'.\n\n"
        f"Do NOT include any punctuation, quotes, or conversational text. Return ONLY the search query string itself. "
        f"Example output: 'JWST new galaxy discoveries' or 'solid state battery breakthroughs'."
    )

    messages = [
        {
            "role": "system",
            "content": "You are a concise search query generator. You output only the raw search query string.",
        },
        {
            "role": "user",
            "content": user_content,
        },
    ]

    try:
        logger.info(f"Calling LLM for dynamic news query in category: '{selected_cat}'")
        query = generate_llm_response(messages, temperature=0.9)
        query = query.strip('\'"`.?! ')
        logger.info(f"Generated dynamic news query: '{query}'")
        return query or "world news at a glance today"
    except Exception as e:
        logger.error(f"Error calling LLM for news query: {e}")
        return "world news at a glance today"


def send_telegram_message(chat_id: int | str, message: str) -> None:
    """Send an HTML-formatted message to Telegram."""
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN must be set in environment variables.")

    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    api_url = TELEGRAM_API_URL or f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    logger.info(f"Sending news message to Telegram chat {chat_id} (size: {len(message)} chars)")
    response = requests.post(api_url, json=payload, timeout=15)
    try:
        response.raise_for_status()
    except requests.HTTPError:
        logger.error(f"Telegram API response status: {response.status_code}")
        logger.error(f"Telegram response body: {response.text}")
        raise


def build_message(query: str, raw_data: dict, limit: int) -> str:
    """Format Tavily raw search results into a clean bulleted Telegram HTML digest."""
    summary = format_search_results(query, raw_data, limit=limit, use_llm=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"{summary}\n\n<i>{timestamp}</i>"


def execute_and_send_news(
    chat_id: int | str | list[int | str],
    query: str | None = None,
    limit: int = 3,
    summary: bool = True,
):
    """Fetch news from Talivy search and send to Telegram as a single bulleted digest.

    Args:
        chat_id: Single chat ID or a list of chat IDs.
        query: Optional search query string (auto-generates dynamic query if None).
        limit: Max results count.
        summary: Retained for backward compatibility.

    Returns:
        tuple: (count of news results sent, final search query used, list of message texts sent)
    """
    chat_ids = [chat_id] if not isinstance(chat_id, list) else chat_id

    if not query:
        query = generate_dynamic_news_query()

    logger.info(f"Searching Tavily for query: '{query}'")
    raw_data = talivy_search(query, limit=limit)
    results = parse_talivy_results(raw_data)

    message = build_message(query, raw_data, limit=limit)
    sent_texts = []

    logger.info(f"Sending news digest message to {len(chat_ids)} recipient(s)...")
    for cid in chat_ids:
        try:
            send_telegram_message(cid, message)
            sent_texts.append(message)
        except Exception as e:
            logger.error(f"Failed to send news message to chat {cid}: {e}")

    return len(results), query, sent_texts


def main() -> None:
    """CLI entrypoint for sending news update."""
    parser = argparse.ArgumentParser(description="Send Talivy web search results to Telegram.")
    parser.add_argument("--query", default=None, help="Search query string")
    parser.add_argument("--limit", type=int, default=3, help="Number of top results to include")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    target_chat_id = TELEGRAM_CHAT_ID or os.getenv("TELEGRAM_CHAT_ID")
    if not target_chat_id:
        raise ValueError("TELEGRAM_CHAT_ID must be set in environment variables.")

    execute_and_send_news(
        chat_id=target_chat_id,
        query=args.query,
        limit=args.limit,
    )
    logger.info("Done!")


if __name__ == "__main__":
    main()
