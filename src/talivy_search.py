#!/usr/bin/env python3
"""Talivy web search helper with customizable payload parameters and LLM synthesis."""

import html
import os
import re
import logging
import requests

logger = logging.getLogger("talivy_search")

TALIVY_API_KEY = os.getenv("TALIVY_API_KEY")
TALIVY_ENDPOINT = os.getenv("TALIVY_ENDPOINT") or "https://api.tavily.com/search"

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_ENDPOINT = "https://models.github.ai/inference/chat/completions"
MODEL_NAME = "openai/gpt-4.1-nano"


def talivy_search(
    query: str,
    limit: int = 5,
    search_depth: str | None = None,
    topic: str | None = None,
    time_range: str | None = None,
    days: int | None = None,
    include_answer: bool | str | None = None,
) -> dict:
    """Search Tavily API with customizable payload parameters and return raw JSON response.

    Supported parameters:
      - query: Search query string
      - limit / max_results: Max number of results to fetch (default: 5)
      - search_depth: 'advanced', 'basic', or 'ultra-fast' (default: env TALIVY_SEARCH_DEPTH or 'advanced')
      - topic: 'news', 'general', or 'finance' (default: env TALIVY_TOPIC or 'news')
      - time_range: 'day' ('d'), 'week' ('w'), 'month' ('m'), 'year' ('y') (default: 'year')
      - days: int days back (e.g. 1, 7, 30) (default: env TALIVY_DAYS)
      - include_answer: True, False, 'advanced', or 'basic' (default: True)
    """
    if not TALIVY_API_KEY:
        raise ValueError("TALIVY_API_KEY must be set in environment variables.")

    endpoint = TALIVY_ENDPOINT or "https://api.tavily.com/search"

    resolved_search_depth = search_depth or os.getenv("TALIVY_SEARCH_DEPTH") or "advanced"
    resolved_topic = topic or os.getenv("TALIVY_TOPIC") or "news"
    resolved_time_range = time_range or os.getenv("TALIVY_TIME_RANGE") or "year"
    
    env_days = os.getenv("TALIVY_DAYS")
    resolved_days = days if days is not None else (int(env_days) if env_days and env_days.isdigit() else None)

    resolved_include_answer = include_answer if include_answer is not None else (
        os.getenv("TALIVY_INCLUDE_ANSWER") or True
    )

    payload = {
        "api_key": TALIVY_API_KEY,
        "query": query,
        "max_results": limit,
        "search_depth": resolved_search_depth,
        "topic": resolved_topic,
    }

    if resolved_include_answer is not None:
        payload["include_answer"] = resolved_include_answer

    if resolved_time_range:
        payload["time_range"] = resolved_time_range

    if resolved_days is not None:
        payload["days"] = resolved_days

    headers = {
        "Authorization": f"Bearer {TALIVY_API_KEY}",
        "Content-Type": "application/json",
    }

    logger.info(
        f"Calling Tavily endpoint: {endpoint} (query: '{query}', depth: '{resolved_search_depth}', topic: '{resolved_topic}', time_range: '{resolved_time_range}')"
    )
    response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
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


def clean_telegram_html(text: str) -> str:
    """Sanitize raw or LLM-generated text into 100% valid Telegram HTML format.

    Telegram supports ONLY: <b>, <i>, <a>, <code>, <pre>, <u>, <s>, <tg-spoiler>.
    All other tags are stripped/converted and special characters (<, >, &) escaped.
    Markdown headers (#), horizontal rules (---), and blockquotes (>) are converted or cleaned.
    """
    if not text:
        return ""

    text = str(text)

    # 1. Normalize line breaks from HTML container tags
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?(p|div|h[1-6]|ul|ol|li)\b[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?span\b[^>]*>", "", text, flags=re.IGNORECASE)

    # 2. Convert markdown headings (# Heading, ## Heading) to bold lines
    text = re.sub(r"^[ \t]*#+\s*(.*?)[ \t]*$", r"<b>\1</b>", text, flags=re.MULTILINE)

    # 3. Clean horizontal rules (---, ***, ___)
    text = re.sub(r"^[ \t]*[-*_]{3,}[ \t]*$", "", text, flags=re.MULTILINE)

    # 4. Clean blockquote markers (> Quote)
    text = re.sub(r"^[ \t]*>\s*", "", text, flags=re.MULTILINE)

    # 5. Convert markdown links: [text](url) -> <a href="url">text</a>
    def convert_md_link(match):
        anchor = match.group(1).strip()
        url = match.group(2).strip()
        safe_url = html.escape(url, quote=True)
        safe_anchor = anchor or url
        return f'<a href="{safe_url}">{safe_anchor}</a>'

    text = re.sub(
        r'\[([^\]]+)\]\(\s*([^\s\"\'\)]+)(?:\s+[\"\'].*?[\"\'])?\s*\)',
        convert_md_link,
        text,
    )

    # 6. Convert markdown bold and italic formatting
    text = re.sub(r"\*\*([^*]+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*([^*]+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"(?<!\w)_([^_]+?)_(?!\w)", r"<i>\1</i>", text)

    # 7. Mask valid Telegram HTML tags before escaping
    valid_tag_pattern = (
        r"</?(?:b|i|code|pre|u|s|strike|del|em|strong|tg-spoiler)\b[^>]*>"
        r'|<a\s+href="[^"]*"[^>]*>|<a\s+href=\'[^\']*\'[^>]*>|</a>'
    )
    placeholders = {}
    counter = 0

    def mask_tag(match):
        nonlocal counter
        ph = f"___TG_TAG_{counter}___"
        placeholders[ph] = match.group(0)
        counter += 1
        return ph

    masked_text = re.sub(valid_tag_pattern, mask_tag, text, flags=re.IGNORECASE)

    # 8. Escape remaining raw unmasked HTML characters (<, >, &)
    escaped_text = html.escape(masked_text, quote=False)

    # 9. Unmask valid Telegram tags
    for ph, tag in placeholders.items():
        escaped_text = escaped_text.replace(ph, tag)

    # 10. Normalize multiple blank lines
    escaped_text = re.sub(r"\n{3,}", "\n\n", escaped_text).strip()
    return escaped_text


def clean_text_for_telegram(text: str) -> str:
    """Backward compatibility alias for clean_telegram_html."""
    return clean_telegram_html(text)


def clean_news_title(title: str) -> str:
    """Clean news article titles by stripping long SEO suffix trails (| site name, etc)."""
    if not title:
        return "Untitled"
    title = str(title).strip()
    if "|" in title:
        parts = [p.strip() for p in title.split("|") if p.strip()]
        if parts:
            title = parts[0]
    elif " - " in title and len(title) > 80:
        parts = [p.strip() for p in title.split(" - ") if p.strip()]
        if len(parts) > 1:
            title = parts[0]
    return clean_telegram_html(title)


def summarize_item_with_llm(item: dict) -> str:
    """Generate a crisp 1-2 sentence news summary for a single search item."""
    if not GITHUB_TOKEN:
        return ""

    title = item.get("title") or "Untitled"
    content = (
        item.get("snippet")
        or item.get("summary")
        or item.get("description")
        or item.get("content")
        or ""
    )

    if not content:
        return ""

    prompt = (
        f"Article Title: {title}\n"
        f"Scraped Article Excerpt: {content[:1000]}\n\n"
        "Write a concise, high-value 1-2 sentence news summary explaining the key event/fact reported in this article. "
        "Do NOT include website navigation text like 'Join Us', 'Subscribe', or 'e-Paper'. Return ONLY the 1-2 sentence summary text."
    )

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "system",
                "content": "You are a news editor writing a 1-2 sentence summary for a Telegram news card.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        res = requests.post(GITHUB_ENDPOINT, json=payload, headers=headers, timeout=15)
        res.raise_for_status()
        summary = res.json()["choices"][0]["message"]["content"].strip()
        return clean_telegram_html(summary)
    except Exception as e:
        logger.error(f"Failed to summarize item with LLM: {e}")
        return ""


def synthesize_search_with_llm(query: str, tavily_data: dict, limit: int = 5) -> str:
    """Synthesize Tavily search results into a clean, concise Telegram HTML digest using LLM."""
    if not GITHUB_TOKEN:
        raise ValueError("GITHUB_TOKEN is not set; cannot run LLM search synthesis.")

    answer = tavily_data.get("answer", "")
    results = parse_talivy_results(tavily_data)[:limit]

    sources_text = ""
    for idx, item in enumerate(results, 1):
        title = item.get("title") or item.get("headline") or "Untitled"
        url = item.get("url", "")
        content = (
            item.get("snippet")
            or item.get("summary")
            or item.get("description")
            or item.get("content")
            or ""
        )
        if len(content) > 300:
            content = content[:300].rsplit(" ", 1)[0] + "..."
        sources_text += f"\nSource [{idx}]: {title}\nURL: {url}\nExcerpt: {content}\n"

    system_prompt = (
        "You are a concise, high-impact news editor formatting daily update digests for Telegram.\n"
        "Your goal is to provide a brief, easy-to-read summary without unnecessary fluff, excessive length, or markdown headers.\n\n"
        "STRICT FORMATTING RULES:\n"
        "1. Start with a single bold header line with a relevant emoji, e.g., '<b>📡 News Update: <Topic></b>'.\n"
        "2. Follow with a 1-sentence executive overview.\n"
        "3. Provide 2-3 short, high-density bullet points highlighting core developments.\n"
        "4. For each bullet point, naturally embed the source name as an HTML hyperlink using '<a href=\"URL\">Source Name</a>' (e.g., '• <b>OpenAI Release:</b> Speed increased by 50% (<a href=\"https://...\">TechCrunch</a>).').\n"
        "5. NEVER use Markdown headings (#, ##, ###). Use bold <b> for titles.\n"
        "6. ONLY use Telegram-compatible HTML tags: <b>, <i>, <a href=\"...\">, <code>, <pre>.\n"
        "7. Keep total output concise (under 150 words total)."
    )

    user_prompt = (
        f"Search Topic / Query: {query}\n"
        f"Tavily AI Summary Overview: {answer}\n\n"
        f"Search Result Sources:\n{sources_text}\n\n"
        "Synthesize this into a concise Telegram HTML digest following all formatting rules."
    )

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.5,
    }

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Content-Type": "application/json",
    }

    logger.info(f"Calling GitHub LLM API to synthesize news digest for query: '{query}'")
    res = requests.post(GITHUB_ENDPOINT, json=payload, headers=headers, timeout=30)
    res.raise_for_status()
    raw_content = res.json()["choices"][0]["message"]["content"].strip()

    return clean_telegram_html(raw_content)


def format_search_results(query: str, data: dict, limit: int = 3, use_llm: bool = True) -> str:
    """Create a Telegram-friendly message from Talivy search results.

    Attempts LLM synthesis if enabled and GITHUB_TOKEN is available;
    otherwise formats clean HTML fallback with inline domain links.
    """
    results = parse_talivy_results(data)
    if not results and not data.get("answer"):
        return f"No search results found for: {clean_telegram_html(query)}"

    if use_llm and GITHUB_TOKEN:
        try:
            return synthesize_search_with_llm(query, data, limit=limit)
        except Exception as e:
            logger.error(f"LLM synthesis failed, falling back to structured HTML format: {e}")

    # Fallback formatting (clean HTML without raw dumped URLs or excessive text)
    lines = [f"<b>🔎 Search results for:</b> {html.escape(str(query), quote=False)}", ""]

    answer = data.get("answer")
    if answer:
        lines.append(f"<i>{clean_telegram_html(answer)}</i>")
        lines.append("")

    for item in results[:limit]:
        title = clean_news_title(item.get("title") or item.get("headline") or "Untitled")
        snippet = (
            item.get("snippet")
            or item.get("summary")
            or item.get("description")
            or item.get("content")
            or "No description available."
        )
        snippet = str(snippet).strip()
        if len(snippet) > 250:
            snippet = snippet[:250].rsplit(" ", 1)[0] + "..."

        url = item.get("url")

        clean_snippet = clean_telegram_html(snippet)

        if url:
            safe_url = html.escape(str(url), quote=True)
            lines.append(f"• <b><a href=\"{safe_url}\">{title}</a></b>")
        else:
            lines.append(f"• <b>{title}</b>")

        lines.append(clean_snippet)
        lines.append("")

    return "\n".join(lines).strip()
