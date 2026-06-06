#!/usr/bin/env python3
"""Generate a random fact using GitHub LLM and send to Telegram."""

import os
import requests
import json
import random
from datetime import datetime,timezone

# GitHub LLM API config
GITHUB_ENDPOINT = "https://models.github.ai/inference"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
MODEL_NAME = "openai/gpt-4.1-nano"

# Telegram config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"


def generate_fact():
    """Generate a random fact using GitHub LLM API."""
    headers = {
        "Content-Type": "application/json",
    }

    prompt_variants = [
        "Generate one interesting, concise random fact (max 2 sentences). Make it engaging and fun, and avoid very common or repeated facts.",
        "Share a fresh, unusual fact in one or two sentences. Do not repeat common trivia; make it feel new and surprising.",
        "Give me a unique random fact that's unlikely to be repeated if asked again soon. Keep it short and fun.",
    ]

    # Randomize parameters for each call to increase diversity
    temperature = random.uniform(0.7, 1.5)
    top_p = random.uniform(0.75, 0.95)

    payload = {
        "messages": [
            {
                "role": "system",
                "content": "You are a fact generator that creates unique, diverse, and interesting random facts. Each fact should be completely different from previous facts. Focus on unusual trivia, surprising scientific discoveries, historical oddities, and lesser-known information from various domains. Never repeat the same fact twice.",
            },
            {
                "role": "user",
                "content": random.choice(prompt_variants),
            },
        ],
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": 200,
        "model": MODEL_NAME,
    }

    try:
        print(f"API Parameters - Temperature: {temperature:.2f}, Top_p: {top_p:.2f}")
        response = requests.post(
            f"{GITHUB_ENDPOINT}/chat/completions",
            headers={**headers, "Authorization": f"Bearer {GITHUB_TOKEN}"},
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        fact = data["choices"][0]["message"]["content"]
        return fact.strip()
    except Exception as e:
        print(f"Error calling GitHub LLM API: {e}")
        raise


def send_telegram_message(message):
    """Send message to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in environment variables.")

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }

    response = requests.post(TELEGRAM_API, json=payload, timeout=10)
    try:
        response.raise_for_status()
        print("Message sent successfully to Telegram")
        return True
    except requests.HTTPError as e:
        error_body = response.text
        print(f"Error sending to Telegram: {e}")
        print(f"Telegram response body: {error_body}")
        raise


def main():
    """Main function: generate fact and send to Telegram."""
    try:
        if not GITHUB_TOKEN:
            raise ValueError("GITHUB_TOKEN is not set")

        print("Generating random fact...")
        fact = generate_fact()
        print(f"Fact generated: {fact}")

        # Format message with emoji and title
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        message = f"<b>🎯 Daily Fact</b>\n\n{fact}\n\n<i>{timestamp}</i>"

        print("Sending to Telegram...")
        send_telegram_message(message)
        print("Done!")

    except Exception as e:
        print(f"Failed to complete workflow: {e}")
        exit(1)


if __name__ == "__main__":
    main()
