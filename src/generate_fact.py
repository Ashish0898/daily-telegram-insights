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


FACT_SEEDS = [
    "ancient shipwrecks", "deep-sea biology", "weird medieval laws", "unusual geography",
    "history of mapmaking", "early ballooning and flight", "space exploration accidents",
    "plant communication and intelligence", "insect behavior", "origin of everyday phrases",
    "forgotten inventors", "extreme weather phenomena", "unique languages and linguistics",
    "traditional instruments", "historical hoaxes", "animal cooperation", "bioluminescent organisms",
    "ancient libraries", "history of writing systems", "unusual archaeological discoveries",
    "history of cryptography and codes", "forgotten cities", "astronomical anomalies",
    "micro-nations and self-declared states", "history of medical practices", "deep space signals",
    "strange physics phenomena (like superfluidity)", "subterranean places (caves, catacombs)",
    "animal migrations", "historical sports and games", "history of timekeeping (clocks, calendars)",
    "fungal networks (mycelium)", "architectural marvels of the ancient world", "deep-ocean trenches",
    "history of glassmaking", "bird intelligence and tool use", "volcanic islands",
    "unique desert adaptations", "seed banks and botanical history", "origins of tea and coffee culture",
    "optical illusions in nature", "sleep patterns in animals", "history of the printing press",
    "sound and acoustic wonders (echoes, singing sands)", "ancient metallurgy", "history of paper and origami",
    "navigation techniques of Polynesian sailors", "deep ice cores and climate history", "carnivorous plants",
    "history of color pigments and dyes"
]

EXCLUDE_CLICHES = (
    "Do NOT generate extremely common or overused trivia clichés, such as: "
    "honey never spoiling, octopuses having three hearts/blue blood, Cleopatra living closer to the iPhone than "
    "the pyramids, bananas being berries, strawberries not being berries, tomatoes being fruits, Wombat poop "
    "being cubic, sloths holding their breath, or the invention of the match after the lighter."
)


def generate_fact():
    """Generate a random fact using GitHub LLM API."""
    headers = {
        "Content-Type": "application/json",
    }

    # Randomize parameters for each call to increase diversity
    temperature = random.uniform(0.7, 1.5)
    top_p = random.uniform(0.75, 0.95)

    seed = random.choice(FACT_SEEDS)
    print(f"Selected seed topic: {seed}")

    user_content = (
        f"Generate one highly interesting, concise, and surprising random fact (max 2 sentences) "
        f"related to this specific topic: '{seed}'.\n\n"
        f"IMPORTANT: {EXCLUDE_CLICHES}\n\n"
        "Focus on lesser-known details, surprising historical oddities, or unique scientific findings."
    )

    payload = {
        "messages": [
            {
                "role": "system",
                "content": "You are a fact generator that creates unique, diverse, and interesting random facts. Focus on unusual trivia, surprising scientific discoveries, historical oddities, and lesser-known information from various domains. Never repeat the same fact twice.",
            },
            {
                "role": "user",
                "content": user_content,
            },
        ],
        "temperature": temperature,
        # "top_p": top_p,
        # "max_tokens": 200,
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


def generate_dynamic_news_query() -> str:
    """Generate a dynamic, interesting news search query using GitHub LLM API."""
    if not GITHUB_TOKEN:
        print("GITHUB_TOKEN not set, returning fallback query.")
        return "world news at a glance today"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GITHUB_TOKEN}"
    }

    categories = [
        "artificial intelligence", "space exploration", "renewable energy",
        "marine biology", "archaeological discoveries", "medical breakthroughs",
        "quantum computing", "fusion energy", "consumer tech innovations",
        "paleontology", "astrophysics", "robotics"
    ]
    selected_cat = random.choice(categories)

    user_content = (
        f"Generate a short (3-6 words) search query to find the latest, most interesting news, "
        f"discoveries, or breakthroughs in the field of: '{selected_cat}'.\n\n"
        f"Do NOT include any punctuation, quotes, or conversational text. Return ONLY the search query string itself. "
        f"Example output: 'JWST new galaxy discoveries' or 'solid state battery breakthroughs'."
    )

    payload = {
        "messages": [
            {
                "role": "system",
                "content": "You are a concise search query generator. You output only the raw search query string.",
            },
            {
                "role": "user",
                "content": user_content,
            },
        ],
        "temperature": 0.9,
        "model": MODEL_NAME,
    }

    try:
        response = requests.post(
            f"{GITHUB_ENDPOINT}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        query = data["choices"][0]["message"]["content"].strip()
        query = query.strip('\'"`.?! ')
        print(f"Generated dynamic news query: '{query}'")
        return query or "world news at a glance today"
    except Exception as e:
        print(f"Error calling GitHub LLM API for news query: {e}")
        return "world news at a glance today"


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
