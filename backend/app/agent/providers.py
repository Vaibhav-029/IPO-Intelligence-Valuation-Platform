"""LLM provider abstraction. Deterministic tools remain the source of truth;
the LLM explains and reasons about pre-computed data, never calculates its own."""
from __future__ import annotations

import logging
from typing import Any, Protocol

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LLMProvider(Protocol):
    """Protocol that every LLM backend must satisfy."""

    @property
    def is_available(self) -> bool: ...

    def generate_sync(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 0.15,
        max_tokens: int = 1500,
    ) -> str: ...


class DisabledProvider:
    """Safe local default when no API key is configured.
    Returns a sentinel so the caller can detect 'no LLM' and fall back
    to deterministic mode gracefully."""

    @property
    def is_available(self) -> bool:
        return False

    def generate_sync(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 0.15,
        max_tokens: int = 1500,
    ) -> str:
        return ""


class GroqProvider:
    """Groq Cloud — uses the OpenAI-compatible chat completions endpoint."""

    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    @property
    def is_available(self) -> bool:
        return True

    def generate_sync(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 0.15,
        max_tokens: int = 1500,
    ) -> str:
        """Synchronous LLM call — suitable for use inside FastAPI sync routes."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            response = httpx.post(
                self.BASE_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=45.0,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as exc:
            logger.warning("LLM HTTP error %s: %s", exc.response.status_code, exc.response.text[:200])
            return ""
        except Exception as exc:
            logger.warning("LLM call failed: %s", exc)
            return ""


def get_llm_provider() -> LLMProvider:
    """Factory — returns the configured provider or DisabledProvider."""
    settings = get_settings()
    if settings.llm_provider.lower() == "groq" and settings.groq_api_key:
        return GroqProvider(settings.groq_api_key, settings.llm_model)
    return DisabledProvider()
