#!/usr/bin/env python3
"""Unified LLM Client class with cascade multi-provider fallback support across Gemini, OpenRouter, Groq, and OpenAI."""

import logging
import requests
from src.config import (
    LLM_ENDPOINT,
    LLM_TOKEN,
    LLM_MODEL,
    GEMINI_API_KEY,
    OPENROUTER_API_KEY,
    OPENAI_API_KEY,
    GROQ_API_KEY,
)

logger = logging.getLogger("llm_client")


def _call_gemini_direct(api_key: str, model: str, messages: list[dict], temperature: float, timeout: int = 15) -> str:
    """Call Google Gemini generateContent API directly."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}

    # Extract system instruction and user messages
    system_text = ""
    contents = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            system_text += content + "\n"
        elif role == "assistant":
            contents.append({"role": "model", "parts": [{"text": content}]})
        else:
            contents.append({"role": "user", "parts": [{"text": content}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature
        }
    }
    if system_text.strip():
        payload["systemInstruction"] = {
            "parts": [{"text": system_text.strip()}]
        }

    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    response.raise_for_status()
    result_json = response.json()

    candidates = result_json.get("candidates", [])
    if not candidates:
        raise ValueError("No candidates returned from Gemini API")
    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise ValueError("No content parts returned from Gemini API")
    return parts[0].get("text", "").strip()


def _call_openai_compatible(endpoint: str, api_key: str, model: str, messages: list[dict], temperature: float, provider_name: str = "LLM", timeout: int = 15) -> str:
    """Call an OpenAI-compatible endpoint (OpenRouter, Groq, OpenAI)."""
    url = endpoint if endpoint.startswith("http") else f"{endpoint}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature
    }
    logger.info(f"Invoking {provider_name} API with model '{model}'")
    response = requests.post(url, headers=headers, json=payload, timeout=timeout)
    response.raise_for_status()
    result_json = response.json()
    return result_json["choices"][0]["message"]["content"].strip()


class LLMClient:
    """LLM API Client with cascade fallback across Gemini Direct, OpenRouter, Groq, and OpenAI."""

    def __init__(
        self,
        endpoint: str | None = None,
        token: str | None = None,
        default_model: str | None = None,
    ):
        self.gemini_key = token or GEMINI_API_KEY or LLM_TOKEN
        self.default_model = default_model or LLM_MODEL or "gemini-3.5-flash-lite"

    def invoke(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        model: str | None = None,
        timeout: int = 15,
    ) -> str:
        """Execute chat completion with automatic cascade fallback."""
        target_model = model or self.default_model
        errors = []

        # 1. Primary Chain: Gemini Direct API
        if self.gemini_key:
            for gemini_model in ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.6-flash",target_model]:
                try:
                    logger.info(f"Invoking Gemini Direct with model '{gemini_model}'")
                    return _call_gemini_direct(self.gemini_key, gemini_model, messages, temperature, timeout=timeout)
                except Exception as e:
                    err_msg = f"Gemini Direct ({gemini_model}) failed: {e}"
                    logger.warning(err_msg)
                    errors.append(err_msg)

        # 2. Fallback Chain: OpenRouter
        if OPENROUTER_API_KEY:
            for or_model in ["google/gemini-2.5-flash-lite", "nvidia/nemotron-3.5-lightning:free", "openrouter/auto"]:
                try:
                    return _call_openai_compatible("https://openrouter.ai/api/v1/chat/completions", OPENROUTER_API_KEY, or_model, messages, temperature, "OpenRouter", timeout=timeout)
                except Exception as e:
                    err_msg = f"OpenRouter ({or_model}) failed: {e}"
                    logger.warning(err_msg)
                    errors.append(err_msg)

        # 3. Fallback Chain: Groq
        if GROQ_API_KEY:
            for groq_model in ["groq/compound", "groq/compound-mini", "qwen/qwen3.8-27b"]:
                try:
                    return _call_openai_compatible("https://api.groq.com/openai/v1/chat/completions", GROQ_API_KEY, groq_model, messages, temperature, "Groq", timeout=timeout)
                except Exception as e:
                    err_msg = f"Groq ({groq_model}) failed: {e}"
                    logger.warning(err_msg)
                    errors.append(err_msg)

        all_errors = "; ".join(errors)
        raise RuntimeError(f"All configured LLM providers failed. Errors: {all_errors}")


_default_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Return or initialize global singleton LLMClient instance."""
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client


def generate_llm_response(
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int | None = None,
    model: str | None = None,
    timeout: int = 15,
) -> str:
    """Functional wrapper invoking the initialized default LLMClient."""
    client = get_llm_client()
    return client.invoke(
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        model=model,
        timeout=timeout,
    )
