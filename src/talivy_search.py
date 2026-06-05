#!/usr/bin/env python3
"""Talivy web search helper for fetching news or search summaries."""

import os
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


def format_search_results(query: str, data: dict, limit: int = 3) -> str:
    """Create a Telegram-friendly message from Talivy search results."""
    results = parse_talivy_results(data)
    if not results:
        return f"No search results found for: {query}"

    lines = [f"<b>🔎 Search results for:</b> {query}", ""]
    for item in results[:limit]:
        title = item.get("title") or item.get("headline") or "Untitled"
        snippet = (
            item.get("content")
            or item.get("snippet")
            or item.get("summary")
            or item.get("description")
            or item.get("raw_content")
            or "No description available."
        )
        url = item.get("url")
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
