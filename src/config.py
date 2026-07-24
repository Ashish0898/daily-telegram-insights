#!/usr/bin/env python3
"""Centralized configuration settings loaded from environment variables or .env."""

import os
import logging
from pathlib import Path

# Configure logger
logger = logging.getLogger("config")

# Automatically locate and load root .env file if available
root_dir = Path(__file__).resolve().parent.parent
env_path = root_dir / ".env"

if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'").strip('"')
            if key not in os.environ:
                os.environ[key] = val

# LLM Configuration
LLM_ENDPOINT = os.getenv("LLM_ENDPOINT") or os.getenv("GITHUB_ENDPOINT") or "https://models.github.ai/inference"
LLM_TOKEN = os.getenv("LLM_TOKEN") or os.getenv("GITHUB_TOKEN")
LLM_MODEL = os.getenv("LLM_MODEL") or os.getenv("MODEL_NAME") or "openai/gpt-4.1-nano"

# Alternative LLM Provider Keys (for seamless switching)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_KEY = os.getenv("GEMINI_KEY")

# Tavily Search Configuration
TALIVY_API_KEY = os.getenv("TALIVY_API_KEY")
TALIVY_ENDPOINT = os.getenv("TALIVY_ENDPOINT") or "https://api.tavily.com/search"
TALIVY_SEARCH_DEPTH = os.getenv("TALIVY_SEARCH_DEPTH") or "advanced"
TALIVY_TOPIC = os.getenv("TALIVY_TOPIC") or "news"
TALIVY_TIME_RANGE = os.getenv("TALIVY_TIME_RANGE")
TALIVY_DAYS = int(os.getenv("TALIVY_DAYS")) if os.getenv("TALIVY_DAYS", "").isdigit() else None
TALIVY_INCLUDE_ANSWER = os.getenv("TALIVY_INCLUDE_ANSWER") or True

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage" if TELEGRAM_BOT_TOKEN else ""
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")
TELEGRAM_ADMIN_USERNAME = os.getenv("TELEGRAM_ADMIN_USERNAME", "@admin")
TELEGRAM_ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID")
TELEGRAM_ALLOWED_USER_IDS = os.getenv("TELEGRAM_ALLOWED_USER_IDS")

# Database (Supabase) Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Auth0 / Admin Authentication Configuration
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID")
AUTH0_CLIENT_SECRET = os.getenv("AUTH0_CLIENT_SECRET")
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN")
AUTH0_SECRET = os.getenv("AUTH0_SECRET") or "fallback-default-secret-key-123"

# Server / Cron Configuration
CRON_SECRET = os.getenv("CRON_SECRET")
PORT = int(os.getenv("PORT", 3000))
