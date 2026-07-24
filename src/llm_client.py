#!/usr/bin/env python3
"""Unified LLM Client class with explicit initialization and invocation methods."""

import logging
import requests
from src.config import (
    LLM_ENDPOINT,
    LLM_TOKEN,
    LLM_MODEL,
    OPENROUTER_API_KEY,
    OPENAI_API_KEY,
    GROQ_API_KEY,
)

logger = logging.getLogger("llm_client")


class LLMClient:
    """LLM API Client separating credential initialization from chat invocation."""

    def __init__(
        self,
        endpoint: str | None = None,
        token: str | None = None,
        default_model: str | None = None,
    ):
        """Method 1: Initialization - resolves provider endpoint, token, and default model."""
        self.endpoint, self.token, self.default_model = self._resolve_credentials(
            endpoint, token, default_model
        )
        logger.info(
            f"LLMClient initialized: endpoint='{self.endpoint}', default_model='{self.default_model}'"
        )

    def _resolve_credentials(self, endpoint: str | None, token: str | None, default_model: str | None):
        """Determine target endpoint, authorization token, and model from configuration."""
        if token or LLM_TOKEN:
            resolved_token = token or LLM_TOKEN
            raw_endpoint = endpoint or LLM_ENDPOINT or "https://models.github.ai/inference"
            resolved_endpoint = (
                raw_endpoint if raw_endpoint.endswith("/chat/completions")
                else f"{raw_endpoint.rstrip('/')}/chat/completions"
            )
            resolved_model = default_model or LLM_MODEL or "openai/gpt-4.1-nano"
        elif OPENAI_API_KEY:
            resolved_endpoint = "https://api.openai.com/v1/chat/completions"
            resolved_token = OPENAI_API_KEY
            resolved_model = default_model or "gpt-4o-mini"
        elif OPENROUTER_API_KEY:
            resolved_endpoint = "https://openrouter.ai/api/v1/chat/completions"
            resolved_token = OPENROUTER_API_KEY
            resolved_model = default_model or "openai/gpt-4o-mini"
        elif GROQ_API_KEY:
            resolved_endpoint = "https://api.groq.com/openai/v1/chat/completions"
            resolved_token = GROQ_API_KEY
            resolved_model = default_model or "llama-3.3-70b-versatile"
        else:
            raise ValueError(
                "No LLM authorization token found (LLM_TOKEN, OPENAI_API_KEY, OPENROUTER_API_KEY, or GROQ_API_KEY must be set)."
            )

        return resolved_endpoint, resolved_token, resolved_model

    def invoke(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        model: str | None = None,
        timeout: int = 30,
    ) -> str:
        """Method 2: Invocation - executes chat completion HTTP call using initialized settings."""
        target_model = model or self.default_model

        payload = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        logger.info(
            f"Invoking LLM API ({self.endpoint}) with model '{target_model}' (temp: {temperature:.2f})"
        )
        response = requests.post(self.endpoint, json=payload, headers=headers, timeout=timeout)
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            logger.error(f"LLM API invocation failed with status {response.status_code}: {response.text}")
            raise e

        data = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            content = data["choices"][0]["message"]["content"].strip()
            return content
        else:
            raise ValueError(f"Invalid response structure from LLM API: {data}")


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
