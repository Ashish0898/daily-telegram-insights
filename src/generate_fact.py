#!/usr/bin/env python3
"""Generate dynamic cognitive insights, mental models, paradoxes, neuroscience hacks, facts, and quotes."""

import os
import json
import random
import logging
from datetime import datetime, timezone

from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_API_URL
from src.llm_client import generate_llm_response

logger = logging.getLogger("generate_fact")

# Load external seeds from seeds.json
SEEDS_PATH = os.path.join(os.path.dirname(__file__), "seeds.json")
try:
    with open(SEEDS_PATH, "r", encoding="utf-8") as f:
        SEEDS_DATA = json.load(f)
except Exception as e:
    logger.error(f"Failed to load seeds.json: {e}")
    SEEDS_DATA = {}

MODES = [
    "mental_model",
    "cognitive_bias",
    "paradox",
    "neuroscience",
    "thought_experiment",
    "quote",
    "fact"
]


def _get_seed_entry(category_key: str, fallback_name: str, fallback_hint: str) -> tuple[str, str]:
    """Retrieve random seed from SEEDS_DATA with graceful fallback."""
    items = SEEDS_DATA.get(category_key, [])
    if items:
        entry = random.choice(items)
        if isinstance(entry, dict):
            return entry.get("name", fallback_name), entry.get("hint", fallback_hint)
        elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
            return entry[0], entry[1]
        elif isinstance(entry, str):
            return entry, ""
    return fallback_name, fallback_hint


def generate_fact(mode: str = None, return_topic: bool = False):
    """
    Generate an energizing, high-signal cognitive insight, mental model, paradox, quote, or fact.
    """
    if mode not in MODES:
        # Weighted random selection: prioritizing high-impact mental models & cognitive jolts
        mode = random.choices(
            MODES,
            weights=[0.22, 0.20, 0.18, 0.16, 0.10, 0.07, 0.07]
        )[0]

    temperature = random.uniform(0.6, 0.85)
    current_date = datetime.now(timezone.utc).strftime('%B %Y')

    if mode == "mental_model":
        seed_name, seed_desc = _get_seed_entry("mental_models", "Chesterton's Fence", "Never remove a rule until you understand why it was built.")
        topic = f"Mental Model: {seed_name}"
        system_content = (
            "You are a cognitive science and decision-making expert. "
            "Your goal is to write a crisp, energizing, high-impact breakdown of a mental model that delivers an instant 'brain jolt'."
        )
        user_content = (
            f"Current date: {current_date}.\n"
            f"Topic: Mental Model '{seed_name}' ({seed_desc}).\n\n"
            "Format the response using clean HTML tags (<b>, <i>, <code>) matching this EXACT structure:\n\n"
            f"🧠 <b>Mental Model: {seed_name}</b>\n\n"
            "💡 <b>The Core Principle:</b>\n"
            "[1-2 punchy sentences explaining the core truth clearly and simply]\n\n"
            "🎯 <b>Real-World Application:</b>\n"
            "[1-2 practical sentences on how smart engineers/leaders apply this to avoid costly mistakes or solve tough problems]\n\n"
            "❓ <b>Brain Jolt:</b>\n"
            "[1 thought-provoking question or reflection prompt for the reader]"
        )

    elif mode == "cognitive_bias":
        seed_name, seed_desc = _get_seed_entry("cognitive_biases", "Survivorship Bias", "Focusing on visible winners while overlooking invisible failures.")
        topic = f"Cognitive Bias: {seed_name}"
        system_content = (
            "You are a behavioral economics and cognitive bias expert. "
            "Your goal is to explain a cognitive blind spot with punchy clarity and provide an actionable defense."
        )
        user_content = (
            f"Current date: {current_date}.\n"
            f"Topic: Cognitive Bias '{seed_name}' ({seed_desc}).\n\n"
            "Format the response using clean HTML tags (<b>, <i>, <code>) matching this EXACT structure:\n\n"
            f"⚡ <b>Cognitive Trap: {seed_name}</b>\n\n"
            "🪤 <b>The Brain Trick:</b>\n"
            "[1-2 punchy sentences explaining how our subconscious intuition deceives us]\n\n"
            "💥 <b>Where It Stings:</b>\n"
            "[1-2 realistic sentences showing a scenario in tech, work, or decision-making where people fall for it]\n\n"
            "🛡️ <b>Mental Defense:</b>\n"
            "[1 concrete rule or mental habit to catch and disarm this bias]"
        )

    elif mode == "paradox":
        seed_name, seed_desc = _get_seed_entry("paradoxes", "The Fermi Paradox", "If the universe is so vast, where are all the extraterrestrials?")
        topic = f"Paradox: {seed_name}"
        system_content = (
            "You are a mathematician, physicist, and logic enthusiast. "
            "Your goal is to explain a fascinating counter-intuitive paradox that challenges conventional common sense."
        )
        user_content = (
            f"Current date: {current_date}.\n"
            f"Topic: Paradox '{seed_name}' ({seed_desc}).\n\n"
            "Format the response using clean HTML tags (<b>, <i>, <code>) matching this EXACT structure:\n\n"
            f"🤯 <b>Mind-Bending Paradox: {seed_name}</b>\n\n"
            "🌀 <b>The Counter-Intuitive Twist:</b>\n"
            "[1-2 sentences clearly describing the scenario that defies gut intuition]\n\n"
            "🔍 <b>Why It Actually Works:</b>\n"
            "[1-2 crisp sentences revealing the mathematical, physical, or logical mechanism behind it]\n\n"
            "💡 <b>The Takeaway:</b>\n"
            "[1 sentence on what this reveals about assumptions and complex systems]"
        )

    elif mode == "neuroscience":
        seed_name, seed_desc = _get_seed_entry("neuroscience", "Default Mode Network", "Creative breakthroughs occur when disengaging from active focus.")
        topic = f"Neuroscience: {seed_name}"
        system_content = (
            "You are a neuroscientist and cognitive performance specialist. "
            "Your goal is to share a fascinating brain mechanism coupled with a 60-second high-performance habit."
        )
        user_content = (
            f"Current date: {current_date}.\n"
            f"Topic: Neuroscience & Brain Performance '{seed_name}' ({seed_desc}).\n\n"
            "Format the response using clean HTML tags (<b>, <i>, <code>) matching this EXACT structure:\n\n"
            f"🧬 <b>Brain & Performance: {seed_name}</b>\n\n"
            "🔬 <b>The Underlying Biology:</b>\n"
            "[1-2 sentences on what actually happens in the brain/neural circuitry]\n\n"
            "⚡ <b>60-Second Protocol:</b>\n"
            "[1-2 actionable, practical sentences explaining how to leverage this right now to boost focus, clarity, or recovery]"
        )

    elif mode == "thought_experiment":
        seed_name, seed_desc = _get_seed_entry("thought_experiments", "The Experience Machine", "Would you plug into a simulation of endless pleasure?")
        topic = f"Thought Experiment: {seed_name}"
        system_content = (
            "You are a philosopher and cognitive psychologist. "
            "Your goal is to pose an engaging, 1-minute lateral thought experiment."
        )
        user_content = (
            f"Current date: {current_date}.\n"
            f"Topic: Thought Experiment '{seed_name}' ({seed_desc}).\n\n"
            "Format the response using clean HTML tags (<b>, <i>, <code>) matching this EXACT structure:\n\n"
            f"🎯 <b>Micro Thought Experiment: {seed_name}</b>\n\n"
            "🎭 <b>The Scenario:</b>\n"
            "[2 sentences setting up the dilemma or thought experiment]\n\n"
            "⚖️ <b>The Tension:</b>\n"
            "[1-2 sentences on why this breaks ordinary logic or why reasonable minds disagree]\n\n"
            "❓ <b>Your Verdict:</b>\n"
            "[1 direct question asking the reader how they would solve or view this]"
        )

    elif mode == "quote":
        seed_name, seed_desc = _get_seed_entry("quotes", "Marcus Aurelius", "Stoic focus on what is within your control.")
        topic = f"Quote: {seed_name}"
        system_content = (
            "You are a curator of timeless philosophy and practical wisdom. "
            "Provide an authentic, profound quote accompanied by a punchy modern takeaway."
        )
        user_content = (
            f"Current date: {current_date}.\n"
            f"Provide an inspiring, authentic quote from '{seed_name}' (Focus: {seed_desc}).\n\n"
            "Format the response using clean HTML tags (<b>, <i>, <code>) matching this EXACT structure:\n\n"
            "💡 <b>Timeless Wisdom</b>\n\n"
            f'"[Quote text]"\n'
            f'— <b>{seed_name}</b>\n\n'
            "🎯 <b>Modern Takeaway:</b>\n"
            "[1-2 sentences translating this timeless insight into modern engineering, work, or mindset]"
        )

    else: # fact
        seed_name, seed_desc = _get_seed_entry("facts", "Fungal Mycorrhizal Networks", "Underground tree communication networks.")
        topic = f"Curious Discovery: {seed_name}"
        system_content = (
            "You are a curator of rare scientific oddities and astonishing natural discoveries. "
            "Focus on mind-expanding phenomena that spark wonder and curiosity."
        )
        user_content = (
            f"Current date: {current_date}.\n"
            f"Topic: Unusual discovery in '{seed_name}' ({seed_desc}).\n\n"
            "Format the response using clean HTML tags (<b>, <i>, <code>) matching this EXACT structure:\n\n"
            "🔬 <b>Curious Discovery</b>\n\n"
            "🌌 <b>The Phenomenon:</b>\n"
            "[2 sentences revealing a surprising, lesser-known scientific truth or natural mechanism]\n\n"
            "💡 <b>Why It Matters:</b>\n"
            "[1 sentence explaining the deeper beauty or engineering wonder behind it]"
        )

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]

    try:
        content = generate_llm_response(messages, temperature=temperature)
        if return_topic:
            return content, topic, mode
        return content, mode
    except Exception as e:
        logger.error(f"Error generating insight with LLM: {e}")
        # Return high quality curated fallback so user always receives insight
        fallback_content = _get_curated_fallback(mode, seed_name)
        if return_topic:
            return fallback_content, topic, mode
        return fallback_content, mode


def _get_curated_fallback(mode: str, seed_name: str) -> str:
    """High-quality offline fallback if all LLM providers fail."""
    fallbacks = {
        "mental_model": (
            f"🧠 <b>Mental Model: Chesterton's Fence</b>\n\n"
            "💡 <b>The Core Principle:</b>\n"
            "Never destroy a fence, delete legacy code, or dismantle a rule until you understand the exact problem it was originally created to solve.\n\n"
            "🎯 <b>Real-World Application:</b>\n"
            "Before refactoring 'ugly' production systems, deduce what silent race condition or edge case it was designed to prevent.\n\n"
            "❓ <b>Brain Jolt:</b>\n"
            "What 'redundant' step in your daily workflow might secretly be saving you from failure?"
        ),
        "cognitive_bias": (
            f"⚡ <b>Cognitive Trap: Survivorship Bias</b>\n\n"
            "🪤 <b>The Brain Trick:</b>\n"
            "We obsess over visible success stories while ignoring the invisible graveyard of failures that used the exact same strategy.\n\n"
            "💥 <b>Where It Stings:</b>\n"
            "Copying the work habits of a billionaire tech founder while ignoring the thousands of bankrupt founders who did the same.\n\n"
            "🛡️ <b>Mental Defense:</b>\n"
            "Always ask: <code>'Where is the graveyard?'</code> and study what failed, not just what survived."
        ),
        "paradox": (
            f"🤯 <b>Mind-Bending Paradox: Braess's Paradox</b>\n\n"
            "🌀 <b>The Counter-Intuitive Twist:</b>\n"
            "Adding an extra road to a congested traffic network can actually increase the average travel time for all drivers.\n\n"
            "🔍 <b>Why It Actually Works:</b>\n"
            "When individual actors choose optimal self-interested shortcuts, they create new bottleneck externalities across the entire network.\n\n"
            "💡 <b>The Takeaway:</b>\n"
            "Local optimizations frequently degrade global system performance."
        ),
        "neuroscience": (
            f"🧬 <b>Brain & Performance: Default Mode Network</b>\n\n"
            "🔬 <b>The Underlying Biology:</b>\n"
            "When you step away from active task-focus, the brain's Default Mode Network links disparate memories and delivers creative breakthroughs.\n\n"
            "⚡ <b>60-Second Protocol:</b>\n"
            "When stuck on a problem, take a 5-minute walk without your phone or headphones to activate subconscious problem solving."
        ),
        "quote": (
            "💡 <b>Timeless Wisdom</b>\n\n"
            '"You have power over your mind - not outside events. Realize this, and you will find strength."\n'
            '— <b>Marcus Aurelius</b>\n\n'
            "🎯 <b>Modern Takeaway:</b>\n"
            "Focus 100% of your energy on your reaction and execution, rather than raging against external noise."
        )
    }
    return fallbacks.get(mode, fallbacks["mental_model"])


def send_telegram_message(message: str) -> bool:
    """Send message to Telegram using configured bot token and chat ID."""
    import requests
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in environment variables.")

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }

    response = requests.post(TELEGRAM_API_URL, json=payload, timeout=15)
    response.raise_for_status()
    logger.info("Message sent successfully to Telegram")
    return True


def main():
    """Main function: generate insight and send to Telegram."""
    try:
        logger.info("Generating dynamic brain-jolt insight...")
        content, insight_type = generate_fact()
        logger.info(f"Insight generated (type: {insight_type}):\n{content}")

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        message = f"{content}\n\n<i>{timestamp}</i>"

        logger.info("Sending to Telegram...")
        send_telegram_message(message)
        logger.info("Done!")
    except Exception as e:
        logger.error(f"Failed to complete insight generation workflow: {e}")
        exit(1)


if __name__ == "__main__":
    main()
