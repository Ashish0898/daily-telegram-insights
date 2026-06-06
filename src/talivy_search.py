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


def format_markdown_inline_styling(text: str) -> str:
    """Helper to convert markdown bold/italic to HTML tags, ignoring mid-word underscores."""
    # Bold
    text = re.sub(r"\*\*([^*]+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\b__([^_]+)__\b", r"<b>\1</b>", text)
    # Italic
    text = re.sub(r"\*([^*]+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"\b_([^_]+)_\b", r"<i>\1</i>", text)
    return text


def clean_text_for_telegram(text: str) -> str:
    """Sanitize raw text for Telegram HTML output."""
    if not text:
        return ""

    text = str(text)

    placeholders = {}
    placeholder_counter = 0

    # Helper to register placeholders
    def add_placeholder(html_content):
        nonlocal placeholder_counter
        placeholder = f"@@@HTML_PLACEHOLDER_{placeholder_counter}@@@"
        placeholders[placeholder] = html_content
        placeholder_counter += 1
        return placeholder

    # 1. Extract and mask images: ![Alt](URL "Title")
    def replace_image_md(match):
        alt = match.group(1).strip()
        url = match.group(2).strip()
        title = (match.group(3) or "").strip()

        safe_url = html.escape(url, quote=True)
        anchor = alt or title or "Image"
        safe_anchor = html.escape(anchor, quote=False)
        return add_placeholder(f'<a href="{safe_url}">{safe_anchor}</a>')

    text = re.sub(
        r"!\[([^\]]*?)\]\(\s*([^\s\"')]+)(?:\s+[\"'](.*?)[\"'])?\s*\)",
        replace_image_md,
        text
    )

    # 2. Extract and mask markdown links: [Text](URL "Title") or [](URL)
    def replace_link_md(match):
        anchor = match.group(1).strip()
        url = match.group(2).strip()
        title = (match.group(3) or "").strip()

        safe_url = html.escape(url, quote=True)
        if not anchor:
            anchor = title or url

        safe_anchor = html.escape(anchor, quote=False)
        formatted_anchor = format_markdown_inline_styling(safe_anchor)
        return add_placeholder(f'<a href="{safe_url}">{formatted_anchor}</a>')

    text = re.sub(
        r"\[([^\]]*?)\]\(\s*([^\s\"')]+)(?:\s+[\"'](.*?)[\"'])?\s*\)",
        replace_link_md,
        text
    )

    # 3. Extract and mask raw URLs (like https://example.com/...)
    def replace_raw_url(match):
        url = match.group(0)
        safe_url = html.escape(url, quote=True)
        safe_anchor = html.escape(url, quote=False)
        return add_placeholder(f'<a href="{safe_url}">{safe_anchor}</a>')

    text = re.sub(r"https?://[^\s()<>\"']+", replace_raw_url, text)

    # 4. Escape HTML special characters for the rest of the unmasked text (but not quotes)
    text = html.escape(text, quote=False)

    # 5. Apply markdown bold/italic formatting to the remaining text (safely since links & raw URLs are masked!)
    text = format_markdown_inline_styling(text)

    # 6. Restore placeholders
    for placeholder, html_content in placeholders.items():
        text = text.replace(placeholder, html_content)

    # 7. Normalize whitespace/line endings
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
