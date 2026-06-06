#!/usr/bin/env python3
"""Talivy web search helper for fetching news or search summaries."""

import html
import os
import re
import requests

TALIVY_API_KEY = os.getenv("TALIVY_API_KEY")
TALIVY_ENDPOINT = os.getenv("TALIVY_ENDPOINT")


def talivy_search(query: str, limit: int = 3) -> dict:
    """Search Talivy and return the raw response JSON."""
    if not TALIVY_API_KEY or not TALIVY_ENDPOINT:
        raise ValueError("TALIVY_API_KEY and TALIVY_ENDPOINT must be set")

    payload = {
        "query": query,
        "limit": limit,
    }
    headers = {
        "Authorization": f"Bearer {TALIVY_API_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.post(TALIVY_ENDPOINT, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def parse_talivy_results(data: dict) -> list[dict]:
    """Extract a list of search result items from Talivy response."""
    if not isinstance(data, dict):
        return []

    results = []
    if "results" in data and isinstance(data["results"], list):
        results = data["results"]
    elif "items" in data and isinstance(data["items"], list):
        results = data["items"]
    elif "data" in data and isinstance(data["data"], list):
        results = data["data"]
    return results


def clean_text_for_telegram(text: str) -> str:
    """Sanitize raw text for Telegram HTML output."""
    if not text:
        return ""

    text = str(text)

    # 1. Escape HTML special characters (but not quotes for better telegram reading)
    text = html.escape(text, quote=False)

    # 2. Convert markdown links: [Text](URL) -> <a href="URL">Text</a>
    def replace_link(match):
        anchor = match.group(1)
        url = match.group(2)
        safe_url = html.escape(url, quote=True)
        return f'<a href="{safe_url}">{anchor}</a>'

    text = re.sub(r"\[([^\]]*?)\]\(([^\s)]+)\)", replace_link, text)

    # 3. Convert empty markdown links: [](URL) -> <a href="URL">URL</a>
    def replace_empty_link(match):
        url = match.group(1)
        safe_url = html.escape(url, quote=True)
        return f'<a href="{safe_url}">{safe_url}</a>'

    text = re.sub(r"\[\]\(([^\s)]+)\)", replace_empty_link, text)

    # 4. Convert image markdown: ![Alt](URL) -> <a href="URL">Alt</a>
    def replace_image(match):
        alt = match.group(1) or "Image"
        url = match.group(2)
        safe_url = html.escape(url, quote=True)
        return f'<a href="{safe_url}">{alt}</a>'

    text = re.sub(r"!\[(.*?)\]\(([^\s)]+)\)", replace_image, text)

    # 5. Convert markdown bold/italic formatting to HTML tags
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"__([^_]+)__", r"<b>\1</b>", text)
    text = re.sub(r"_([^_]+)_", r"<i>\1</i>", text)

    # 6. Normalize whitespace/line endings
    text = re.sub(r"\s*\n\s*", "\n", text).strip()
    return text


def format_search_results(query: str, data: dict, limit: int = 3) -> str:
    """Create a Telegram-friendly message from Talivy search results."""
    results = parse_talivy_results(data)
    if not results:
        return f"No search results found for: {query}"

    lines = [f"<b>🔎 Search results for:</b> {html.escape(str(query), quote=False)}", ""]
    for item in results[:limit]:
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
        lines.append(f"<b>{title}</b>")
        if url:
            lines.append(f"<a href=\"{url}\">Link</a>")
        lines.append(snippet)
        lines.append("")

    return "\n".join(lines).strip()


def latest_football_news(limit: int = 3) -> tuple[str, dict]:
    """Fetch the latest football news via Talivy."""
    query = "latest football news"
    raw = talivy_search(query, limit=limit)
    message = format_search_results(query, raw, limit=limit)
    return message, raw
