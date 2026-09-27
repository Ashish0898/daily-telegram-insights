#!/usr/bin/env python3
"""Generate dynamic cognitive insights, mental models, paradoxes, neuroscience hacks, facts, and quotes."""

import os
import json
import random
import logging
from datetime import datetime, timezone

from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_API_URL
from src.llm_client import generate_llm_response
from src.talivy_search import clean_telegram_html

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
    "cognitive_bias",
    "neuroscience",
    "mental_model",
    "paradox",
    "thought_experiment",
    "fact",
    "quote"
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
    Generate a short, punchy, zero-buzzword cognitive insight, bias trap, or neuro protocol.
    Strictly under 70 words.
    """
    if mode not in MODES:
        # Weighted selection prioritizing Cognitive Traps & Neuroscience / Biology hacks
        mode = random.choices(
            MODES,
            weights=[0.25, 0.25, 0.20, 0.14, 0.06, 0.05, 0.05]
        )[0]

    temperature = random.uniform(0.65, 0.85)

    if mode == "cognitive_bias":
        seed_name, seed_desc = _get_seed_entry("cognitive_biases", "Survivorship Bias", "Focusing on visible winners while overlooking invisible failures.")
        topic = f"Cognitive Bias: {seed_name}"
        system_content = (
            "You are an expert cognitive psychologist. "
            "Write a short, punchy breakdown of a cognitive bias. "
            "STRICT CONSTRAINTS:\n"
            "- MAXIMUM 65 words total.\n"
            "- ZERO buzzwords, zero hype, zero fluff ('brain jolt', 'top-tier engineers', 'where it stings' are strictly forbidden).\n"
            "- Format with clean Telegram HTML (<b>, <i>, <code>). Never use markdown asterisks (**) or markdown formatting.\n"
            "- Do not include greetings or filler preamble."
        )
        user_content = (
            f"Topic: Cognitive Trap '{seed_name}' ({seed_desc}).\n\n"
            "Format the response using this EXACT HTML structure (strictly under 65 words):\n\n"
            f"⚡ <b>Cognitive Trap: {seed_name}</b>\n\n"
            "[1-2 punchy sentences exposing how human intuition is tricked by this blindspot. Grounded and concrete.]\n\n"
            "🛡️ <i>The defense:</i> [1 sharp diagnostic question or practical mental habit to catch and disarm this bias.]"
        )

    elif mode == "neuroscience":
        seed_name, seed_desc = _get_seed_entry("neuroscience", "Attention Residue", "Context switching leaves focus trapped in previous tasks.")
        topic = f"Neuroscience: {seed_name}"
        system_content = (
            "You are a neuroscientist and cognitive performance specialist. "
            "Write a short, punchy insight on a brain mechanism and an immediate micro-protocol. "
            "STRICT CONSTRAINTS:\n"
            "- MAXIMUM 65 words total.\n"
            "- ZERO buzzwords, zero hype, zero pop-science fluff ('brain jolt', 'supercharge', 'game changer' are strictly forbidden).\n"
            "- Format with clean Telegram HTML (<b>, <i>, <code>). Never use markdown asterisks (**) or markdown formatting.\n"
            "- Do not include greetings or filler preamble."
        )
        user_content = (
            f"Topic: Neuroscience & Biology '{seed_name}' ({seed_desc}).\n\n"
            "Format the response using this EXACT HTML structure (strictly under 65 words):\n\n"
            f"🧬 <b>Biology & Focus: {seed_name}</b>\n\n"
            "[1-2 crisp sentences on the actual biological or neural mechanism. Scientifically accurate.]\n\n"
            "⚡ <i>The 60-second protocol:</i> [1 actionable, practical sentence on how to leverage or reset this right now.]"
        )

    elif mode == "mental_model":
        seed_name, seed_desc = _get_seed_entry("mental_models", "Gall's Law", "Complex systems that work evolved from simple systems.")
        topic = f"Mental Model: {seed_name}"
        system_content = (
            "You are a systems thinker and decision-making expert. "
            "Write a short, punchy breakdown of a mental model. "
            "STRICT CONSTRAINTS:\n"
            "- MAXIMUM 65 words total.\n"
            "- ZERO buzzwords, zero corporate clichés, zero hype ('elite leaders', 'brain jolt', 'slashing' are strictly forbidden).\n"
            "- Format with clean Telegram HTML (<b>, <i>, <code>). Never use markdown asterisks (**) or markdown formatting.\n"
            "- Do not include greetings or filler preamble."
        )
        user_content = (
            f"Topic: Mental Model '{seed_name}' ({seed_desc}).\n\n"
            "Format the response using this EXACT HTML structure (strictly under 65 words):\n\n"
            f"🧠 <b>Mental Model: {seed_name}</b>\n\n"
            "[1-2 punchy sentences explaining the core reality clearly and simply.]\n\n"
            "💡 <i>The takeaway:</i> [1 crisp sentence translating this into a practical rule of thumb or decision heuristic.]"
        )

    elif mode == "paradox":
        seed_name, seed_desc = _get_seed_entry("paradoxes", "Braess's Paradox", "Adding network capacity can slow down throughput.")
        topic = f"Paradox: {seed_name}"
        system_content = (
            "You are a mathematician and systems logician. "
            "Explain a counter-intuitive paradox with crisp clarity. "
            "STRICT CONSTRAINTS:\n"
            "- MAXIMUM 65 words total.\n"
            "- ZERO buzzwords, zero fluff.\n"
            "- Format with clean Telegram HTML (<b>, <i>, <code>). Never use markdown asterisks (**) or markdown formatting.\n"
            "- Do not include greetings or filler preamble."
        )
        user_content = (
            f"Topic: Paradox '{seed_name}' ({seed_desc}).\n\n"
            "Format the response using this EXACT HTML structure (strictly under 65 words):\n\n"
            f"🤯 <b>Paradox: {seed_name}</b>\n\n"
            "[1-2 sentences clearly describing the counter-intuitive twist where gut intuition fails.]\n\n"
            "🔍 <i>The lesson:</i> [1 crisp sentence revealing the underlying mechanism and what it teaches about systems or assumptions.]"
        )

    elif mode == "thought_experiment":
        seed_name, seed_desc = _get_seed_entry("thought_experiments", "The Experience Machine (Nozick)", "Would you plug into simulated endless pleasure?")
        topic = f"Thought Experiment: {seed_name}"
        system_content = (
            "You are an analytical philosopher and cognitive scientist. "
            "Present a short, thought-provoking thought experiment. "
            "STRICT CONSTRAINTS:\n"
            "- MAXIMUM 65 words total.\n"
            "- ZERO buzzwords.\n"
            "- Format with clean Telegram HTML (<b>, <i>, <code>). Never use markdown asterisks (**) or markdown formatting.\n"
            "- Do not include greetings or filler preamble."
        )
        user_content = (
            f"Topic: Thought Experiment '{seed_name}' ({seed_desc}).\n\n"
            "Format the response using this EXACT HTML structure (strictly under 65 words):\n\n"
            f"🎯 <b>Thought Experiment: {seed_name}</b>\n\n"
            "[1-2 sentences setting up the scenario and the core tension.]\n\n"
            "❓ <i>The question:</i> [1 sharp question asking how the reader resolves the dilemma.]"
        )

    elif mode == "quote":
        seed_name, seed_desc = _get_seed_entry("quotes", "Charlie Munger", "Avoiding stupidity beats seeking brilliance.")
        topic = f"Quote: {seed_name}"
        system_content = (
            "You are a curator of timeless philosophy and practical wisdom. "
            "Share an authentic, profound quote with a modern takeaway. "
            "STRICT CONSTRAINTS:\n"
            "- MAXIMUM 50 words total.\n"
            "- ZERO clichés.\n"
            "- Format with clean Telegram HTML (<b>, <i>, <code>). Never use markdown asterisks (**) or markdown formatting.\n"
            "- Do not include greetings or filler preamble."
        )
        user_content = (
            f"Provide an authentic, memorable quote from '{seed_name}' (Focus: {seed_desc}).\n\n"
            "Format the response using this EXACT HTML structure (strictly under 50 words):\n\n"
            "💡 <b>Timeless Wisdom</b>\n\n"
            '"[Authentic quote text]"\n'
            f'— <b>{seed_name}</b>\n\n'
            "🎯 <i>The takeaway:</i> [1 punchy sentence applying this to modern work or mindset without clichés.]"
        )

    else:  # fact
        seed_name, seed_desc = _get_seed_entry("facts", "Ant Colony Optimization", "Ants solving routing problems without central planning.")
        topic = f"Curious Discovery: {seed_name}"
        system_content = (
            "You are a science communicator and naturalist. "
            "Share an astonishing natural mechanism or scientific anomaly. "
            "STRICT CONSTRAINTS:\n"
            "- MAXIMUM 60 words total.\n"
            "- ZERO buzzwords.\n"
            "- Format with clean Telegram HTML (<b>, <i>, <code>). Never use markdown asterisks (**) or markdown formatting.\n"
            "- Do not include greetings or filler preamble."
        )
        user_content = (
            f"Topic: Curious Discovery '{seed_name}' ({seed_desc}).\n\n"
            "Format the response using this EXACT HTML structure (strictly under 60 words):\n\n"
            f"🔬 <b>Curious Discovery: {seed_name}</b>\n\n"
            "[1-2 sentences revealing the surprising natural mechanism or scientific anomaly.]\n\n"
            "💡 <i>The insight:</i> [1 sentence on the broader principle or systems parallel.]"
        )

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]

    try:
        content = generate_llm_response(messages, temperature=temperature)
        content = clean_telegram_html(content).strip()
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
        "cognitive_bias": (
            "⚡ <b>Cognitive Trap: Survivorship Bias</b>\n\n"
            "We obsess over visible success stories while ignoring the invisible graveyard of failures that used the exact same strategy.\n\n"
            "🛡️ <i>The defense:</i> Whenever evaluating advice, ask: <code>'What did the people who failed do that looked identical?'</code>"
        ),
        "neuroscience": (
            "🧬 <b>Biology & Focus: Attention Residue</b>\n\n"
            "Checking a message for 10 seconds leaves a fragment of your neural focus trapped in that previous context for up to 20 minutes.\n\n"
            "⚡ <i>The 60-second protocol:</i> When hitting a mental wall, look away at a distant object for 90 seconds instead of tab-switching—letting working memory clear without leaving residue."
        ),
        "mental_model": (
            "🧠 <b>Mental Model: Gall's Law</b>\n\n"
            "A complex system that works invariably evolved from a simple system that worked. "
            "A complex system designed from scratch never works and cannot be patched to make it work.\n\n"
            "💡 <i>The takeaway:</i> Don't build the cathedral on day one. Ship the simplest working prototype, let reality stress-test it, and evolve."
        ),
        "paradox": (
            "🤯 <b>Paradox: Braess's Paradox</b>\n\n"
            "Adding a new road to a congested highway network can actually increase average travel time for all drivers.\n\n"
            "🔍 <i>The lesson:</i> When individual actors greedily choose shortcuts, they bottleneck shared infrastructure. Local optimizations often degrade global performance."
        ),
        "thought_experiment": (
            "🎯 <b>Thought Experiment: The Experience Machine</b>\n\n"
            "If a supercomputer could stimulate your brain to experience any fantasy for life while your body floated in a tank, would you plug in permanently?\n\n"
            "❓ <i>The question:</i> Do you value experiencing feelings of achievement, or actually doing things that matter in reality?"
        ),
        "quote": (
            "💡 <b>Timeless Wisdom</b>\n\n"
            '"It is remarkable how much long-term advantage people like us have gotten by trying to be consistently not stupid, instead of trying to be very intelligent."\n'
            '— <b>Charlie Munger</b>\n\n'
            "🎯 <i>The takeaway:</i> Most lasting success comes from systematically removing unforced errors rather than seeking brilliant moves."
        ),
        "fact": (
            "🔬 <b>Curious Discovery: Ant Colony Optimization</b>\n\n"
            "Ant colonies solve complex traveling-salesperson routing problems with zero central coordination by using evaporating pheromone trails.\n\n"
            "💡 <i>The insight:</i> Simple local feedback loops consistently outperform heavy, brittle centralized architectures."
        ),
    }
    return fallbacks.get(mode, fallbacks["cognitive_bias"])


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
