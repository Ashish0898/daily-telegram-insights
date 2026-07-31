#!/usr/bin/env python3
"""Unified LLM Client class with automatic provider fallback support."""

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


class LLMClient:
    """LLM API Client with automatic fallback across Gemini, Groq, OpenRouter, and OpenAI."""

    def __init__(
        self,
        endpoint: str | None = None,
        token: str | None = None,
        default_model: str | None = None,
    ):
        """Initialize provider chain based on available credentials."""
        self.providers = self._build_provider_chain(endpoint, token, default_model)
        if not self.providers:
            raise ValueError(
                "No LLM authorization token found (GEMINI_API_KEY, LLM_TOKEN, GROQ_API_KEY, OPENROUTER_API_KEY, or OPENAI_API_KEY must be set)."
            )
        self.primary = self.providers[0]
        self.endpoint = self.primary["endpoint"]
        self.token = self.primary["token"]
        self.default_model = self.primary["model"]
        logger.info(
            f"LLMClient initialized with {len(self.providers)} provider(s). Primary: '{self.primary['name']}' ({self.default_model})"
        )

    def _build_provider_chain(
        self, endpoint: str | None, token: str | None, default_model: str | None
    ) -> list[dict]:
        """Build ordered list of provider settings for execution and fallback."""
        chain = []

        # Primary Provider (Gemini / Custom LLM_TOKEN)
        gemini_token = token or GEMINI_API_KEY or LLM_TOKEN
        if gemini_token:
            raw_endpoint = (
                endpoint
                or LLM_ENDPOINT
                or "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            )
            if "interactions" in raw_endpoint or "models.github.ai" in raw_endpoint:
                if GEMINI_API_KEY or gemini_token.startswith("AIza"):
                    raw_endpoint = (
                        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
                    )
            resolved_endpoint = raw_endpoint.rstrip("/")
            resolved_model = default_model or LLM_MODEL or "gemini-3.6-flash"
            chain.append({
                "name": "Gemini",
                "endpoint": resolved_endpoint,
                "token": gemini_token,
                "model": resolved_model,
            })

        # Fallback Provider: Groq
        if GROQ_API_KEY and (not chain or chain[0]["token"] != GROQ_API_KEY):
            chain.append({
                "name": "Groq",
                "endpoint": "https://api.groq.com/openai/v1/chat/completions",
                "token": GROQ_API_KEY,
                "model": "llama-3.3-70b-versatile",
            })

        # Fallback Provider: OpenRouter
        if OPENROUTER_API_KEY and (not chain or chain[0]["token"] != OPENROUTER_API_KEY):
            chain.append({
                "name": "OpenRouter",
                "endpoint": "https://openrouter.ai/api/v1/chat/completions",
                "token": OPENROUTER_API_KEY,
                "model": "openai/gpt-4o-mini",
            })

        # Fallback Provider: OpenAI
        if OPENAI_API_KEY and (not chain or chain[0]["token"] != OPENAI_API_KEY):
            chain.append({
                "name": "OpenAI",
                "endpoint": "https://api.openai.com/v1/chat/completions",
                "token": OPENAI_API_KEY,
                "model": "gpt-4o-mini",
            })

        return chain

    def invoke(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        model: str | None = None,
        timeout: int = 30,
    ) -> str:
        """Execute chat completion with automatic fallback to secondary providers upon error/rate-limit."""
        errors = []

        for index, provider in enumerate(self.providers):
            p_name = provider["name"]
            p_endpoint = provider["endpoint"]
            p_token = provider["token"]
            target_model = model if (model and index == 0) else provider["model"]

            payload = {
                "model": target_model,
                "messages": messages,
                "temperature": temperature,
            }
            if max_tokens:
                payload["max_tokens"] = max_tokens

            headers = {
                "Authorization": f"Bearer {p_token}",
                "Content-Type": "application/json",
            }

            try:
                logger.info(
                    f"Invoking LLM provider '{p_name}' ({p_endpoint}) with model '{target_model}' (temp: {temperature:.2f})"
                )
                response = requests.post(p_endpoint, json=payload, headers=headers, timeout=timeout)
                response.raise_for_status()

                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    content = data["choices"][0]["message"]["content"].strip()
                    if index > 0:
                        logger.warning(
                            f"LLM call succeeded using fallback provider '{p_name}' after earlier failures."
                        )
                    return content
                else:
                    raise ValueError(f"Invalid response structure from provider '{p_name}': {data}")

            except Exception as e:
                err_msg = f"Provider '{p_name}' ({target_model}) failed: {e}"
                logger.warning(err_msg)
                errors.append(err_msg)

        all_errors = "; ".join(errors)
        raise RuntimeError(f"All configured LLM providers failed. Errors: {all_errors}")


# Singleton client instance
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
    timeout: int = 30,
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
