#!/usr/bin/env python3
"""Generate dynamic cognitive insights, mental models, paradoxes, neuroscience hacks, facts, and quotes."""

import os
import json
import random
import re
import html
import logging
from datetime import datetime, timezone

from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_API_URL
from src.llm_client import generate_llm_response
from src.talivy_search import clean_telegram_html
from src.db import get_recent_topics_history, record_recent_topic

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
    Generate an autonomous, dynamic, short, punchy, zero-buzzword cognitive insight.
    Strictly under 65 words.
    Informed by recent topics history to guarantee fresh, non-repetitive exploration.
    """
    # 1. Fetch recent history to inform the LLM and rotate categories
    recent_history = get_recent_topics_history(limit=25)
    if recent_history:
        history_bullets = "\n".join(
            f"- {t} ({d} days ago)" if d > 0 else f"- {t} (today)"
            for t, d in recent_history
        )
    else:
        history_bullets = "- None recorded yet."

    # 2. Select mode with category rotation
    if mode not in MODES:
        last_mode = None
        if recent_history:
            last_top = recent_history[0][0].lower()
            if "cognitive" in last_top or "trap" in last_top or "bias" in last_top:
                last_mode = "cognitive_bias"
            elif "neuro" in last_top or "biology" in last_top or "focus" in last_top or "brain" in last_top:
                last_mode = "neuroscience"
            elif "mental" in last_top or "model" in last_top:
                last_mode = "mental_model"
            elif "paradox" in last_top:
                last_mode = "paradox"
            elif "thought" in last_top or "experiment" in last_top:
                last_mode = "thought_experiment"
            elif "quote" in last_top or "wisdom" in last_top:
                last_mode = "quote"
            elif "curious" in last_top or "discovery" in last_top or "fact" in last_top:
                last_mode = "fact"

        candidate_modes = [m for m in MODES if m != last_mode]
        base_weights = {
            "cognitive_bias": 0.26,
            "neuroscience": 0.26,
            "mental_model": 0.20,
            "paradox": 0.14,
            "thought_experiment": 0.05,
            "fact": 0.05,
            "quote": 0.04
        }
        weights = [base_weights[m] for m in candidate_modes]
        mode = random.choices(candidate_modes, weights=weights)[0]

    temperature = random.uniform(0.7, 0.9)

    # 3. Dynamic Prompts for each mode passing previous topics history
    if mode == "cognitive_bias":
        system_content = (
            "You are an expert cognitive psychologist. "
            "Autonomously select and break down a fascinating, high-signal cognitive bias or mental trap. "
            "STRICT CONSTRAINTS:\n"
            "- MAXIMUM 65 words total.\n"
            "- ZERO buzzwords, zero hype, zero fluff ('brain jolt', 'top-tier engineers', 'where it stings' are strictly forbidden).\n"
            "- Format with clean Telegram HTML (<b>, <i>, <code>). Never use markdown asterisks (**) or markdown formatting.\n"
            "- Do not include greetings or filler preamble."
        )
        user_content = (
            f"Topics covered recently (YOU MUST NOT repeat or pick anything similar to these):\n"
            f"{history_bullets}\n\n"
            "Autonomously select a FRESH, lesser-known cognitive bias or decision trap from psychology or behavioral economics that has NOT been covered recently.\n\n"
            "Format the response using this EXACT HTML structure (strictly under 65 words):\n\n"
            "⚡ <b>Cognitive Trap: [Bias Name]</b>\n\n"
            "[1-2 punchy sentences exposing how human intuition is tricked by this blindspot. Grounded and concrete.]\n\n"
            "🛡️ <i>The defense:</i> [1 sharp diagnostic question or practical mental habit to catch and disarm this bias.]"
        )

    elif mode == "neuroscience":
        system_content = (
            "You are a neuroscientist and cognitive performance specialist. "
            "Autonomously select and share a fascinating biological or neural mechanism coupled with a 60-second micro-protocol. "
            "STRICT CONSTRAINTS:\n"
            "- MAXIMUM 65 words total.\n"
            "- ZERO buzzwords, zero hype, zero pop-science fluff ('brain jolt', 'supercharge', 'game changer' are strictly forbidden).\n"
            "- Format with clean Telegram HTML (<b>, <i>, <code>). Never use markdown asterisks (**) or markdown formatting.\n"
            "- Do not include greetings or filler preamble."
        )
        user_content = (
            f"Topics covered recently (YOU MUST NOT repeat or pick anything similar to these):\n"
            f"{history_bullets}\n\n"
            "Autonomously select a FRESH biological mechanism, circadian phenomenon, or focus circuit that has NOT been covered recently.\n\n"
            "Format the response using this EXACT HTML structure (strictly under 65 words):\n\n"
            "🧬 <b>Biology & Focus: [Mechanism Name]</b>\n\n"
            "[1-2 crisp sentences on the actual biological or neural mechanism. Scientifically accurate.]\n\n"
            "⚡ <i>The 60-second protocol:</i> [1 actionable, practical sentence on how to leverage or reset this right now.]"
        )

    elif mode == "mental_model":
        system_content = (
            "You are a systems thinker and decision-making expert. "
            "Autonomously select and break down a powerful mental model or systems law. "
            "STRICT CONSTRAINTS:\n"
            "- MAXIMUM 65 words total.\n"
            "- ZERO buzzwords, zero corporate clichés, zero hype ('elite leaders', 'brain jolt', 'slashing' are strictly forbidden).\n"
            "- Format with clean Telegram HTML (<b>, <i>, <code>). Never use markdown asterisks (**) or markdown formatting.\n"
            "- Do not include greetings or filler preamble."
        )
        user_content = (
            f"Topics covered recently (YOU MUST NOT repeat or pick anything similar to these):\n"
            f"{history_bullets}\n\n"
            "Autonomously select a FRESH mental model, cybernetic feedback concept, or systems dynamic law that has NOT been covered recently.\n\n"
            "Format the response using this EXACT HTML structure (strictly under 65 words):\n\n"
            "🧠 <b>Mental Model: [Model Name]</b>\n\n"
            "[1-2 punchy sentences explaining the core reality clearly and simply.]\n\n"
            "💡 <i>The takeaway:</i> [1 crisp sentence translating this into a practical rule of thumb or decision heuristic.]"
        )

    elif mode == "paradox":
        system_content = (
            "You are a mathematician and systems logician. "
            "Autonomously select and explain a counter-intuitive paradox with crisp clarity. "
            "STRICT CONSTRAINTS:\n"
            "- MAXIMUM 65 words total.\n"
            "- ZERO buzzwords, zero fluff.\n"
            "- Format with clean Telegram HTML (<b>, <i>, <code>). Never use markdown asterisks (**) or markdown formatting.\n"
            "- Do not include greetings or filler preamble."
        )
        user_content = (
            f"Topics covered recently (YOU MUST NOT repeat or pick anything similar to these):\n"
            f"{history_bullets}\n\n"
            "Autonomously select a FRESH mathematical, philosophical, or systemic paradox that has NOT been covered recently.\n\n"
            "Format the response using this EXACT HTML structure (strictly under 65 words):\n\n"
            "🤯 <b>Paradox: [Paradox Name]</b>\n\n"
            "[1-2 sentences clearly describing the counter-intuitive twist where gut intuition fails.]\n\n"
            "🔍 <i>The lesson:</i> [1 crisp sentence revealing the underlying mechanism and what it teaches about systems or assumptions.]"
        )

    elif mode == "thought_experiment":
        system_content = (
            "You are an analytical philosopher and cognitive scientist. "
            "Autonomously select and present a short, thought-provoking thought experiment. "
            "STRICT CONSTRAINTS:\n"
            "- MAXIMUM 65 words total.\n"
            "- ZERO buzzwords.\n"
            "- Format with clean Telegram HTML (<b>, <i>, <code>). Never use markdown asterisks (**) or markdown formatting.\n"
            "- Do not include greetings or filler preamble."
        )
        user_content = (
            f"Topics covered recently (YOU MUST NOT repeat or pick anything similar to these):\n"
            f"{history_bullets}\n\n"
            "Autonomously select a FRESH classic or modern thought experiment that has NOT been covered recently.\n\n"
            "Format the response using this EXACT HTML structure (strictly under 65 words):\n\n"
            "🎯 <b>Thought Experiment: [Name]</b>\n\n"
            "[1-2 sentences setting up the scenario and the core tension.]\n\n"
            "❓ <i>The question:</i> [1 sharp question asking how the reader resolves the dilemma.]"
        )

    elif mode == "quote":
        system_content = (
            "You are a curator of timeless philosophy and practical wisdom. "
            "Select an authentic, profound quote with a modern takeaway. "
            "STRICT CONSTRAINTS:\n"
            "- MAXIMUM 50 words total.\n"
            "- ZERO clichés.\n"
            "- Format with clean Telegram HTML (<b>, <i>, <code>). Never use markdown asterisks (**) or markdown formatting.\n"
            "- Do not include greetings or filler preamble."
        )
        user_content = (
            f"Topics covered recently (YOU MUST NOT repeat thinkers or themes covered recently):\n"
            f"{history_bullets}\n\n"
            "Autonomously select an authentic, memorable quote from a profound thinker (philosopher, scientist, or polymath) that has NOT been covered recently.\n\n"
            "Format the response using this EXACT HTML structure (strictly under 50 words):\n\n"
            "💡 <b>Timeless Wisdom</b>\n\n"
            '"[Authentic quote text]"\n'
            '— <b>[Thinker Name]</b>\n\n'
            "🎯 <i>The takeaway:</i> [1 punchy sentence applying this to modern work or mindset without clichés.]"
        )

    else:  # fact
        system_content = (
            "You are a science communicator and naturalist. "
            "Autonomously select and share an astonishing natural mechanism or scientific anomaly. "
            "STRICT CONSTRAINTS:\n"
            "- MAXIMUM 60 words total.\n"
            "- ZERO buzzwords.\n"
            "- Format with clean Telegram HTML (<b>, <i>, <code>). Never use markdown asterisks (**) or markdown formatting.\n"
            "- Do not include greetings or filler preamble."
        )
        user_content = (
            f"Topics covered recently (YOU MUST NOT repeat or pick anything similar to these):\n"
            f"{history_bullets}\n\n"
            "Autonomously select a FRESH natural mechanism or rare scientific discovery that has NOT been covered recently.\n\n"
            "Format the response using this EXACT HTML structure (strictly under 60 words):\n\n"
            "🔬 <b>Curious Discovery: [Discovery Name]</b>\n\n"
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

        # Extract topic from the first line HTML tags, e.g. <b>Cognitive Trap: Choice Blindness</b>
        topic_match = re.search(r"<b>(.*?)</b>", content)
        if topic_match:
            topic = html.unescape(topic_match.group(1).strip())
        else:
            topic = f"{mode.replace('_', ' ').title()}: Dynamic Insight"

        # Record newly generated topic locally as persistent history
        try:
            record_recent_topic(topic)
        except Exception:
            pass

        if return_topic:
            return content, topic, mode
        return content, mode
    except Exception as e:
        logger.error(f"Error generating dynamic insight with LLM: {e}")
        # Return high quality curated fallback so user always receives insight
        fallback_content = _get_curated_fallback(mode, "Fallback")
        topic = f"{mode.replace('_', ' ').title()}: Curated Insight"
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
