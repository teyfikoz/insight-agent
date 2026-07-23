"""Base LLM agent — NIM primary → Groq fallback → rule-based."""

from __future__ import annotations

import os
from typing import Any


class BaseLLMAgent:
    """Routes requests: NIM → Groq → rule-based fallback."""

    NIM_BASE = "https://integrate.api.nvidia.com/v1"
    GROQ_BASE = "https://api.groq.com/openai/v1"
    NIM_MODEL = "meta/llama-3.3-70b-instruct"
    GROQ_MODEL = "llama-3.3-70b-versatile"

    def __init__(self):
        self._nim_key = os.environ.get("NVIDIA_NIM_API_KEY") or os.environ.get("NIM_API_KEY")
        self._groq_key = os.environ.get("GROQ_API_KEY")
        self._provider = "none"

    def _call_nim(self, system: str, user: str, max_tokens: int = 1500) -> str | None:
        if not self._nim_key:
            return None
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self._nim_key, base_url=self.NIM_BASE)
            resp = client.chat.completions.create(
                model=self.NIM_MODEL,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                max_tokens=max_tokens,
                temperature=0.3,
            )
            self._provider = "NVIDIA NIM"
            return resp.choices[0].message.content or ""
        except Exception:
            return None

    def _call_groq(self, system: str, user: str, max_tokens: int = 1500) -> str | None:
        if not self._groq_key:
            return None
        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=self._groq_key,
                base_url=self.GROQ_BASE,
                default_headers={"User-Agent": "OpenAI/Python 1.0.0"},
            )
            resp = client.chat.completions.create(
                model=self.GROQ_MODEL,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                max_tokens=max_tokens,
                temperature=0.3,
            )
            self._provider = "Groq"
            return resp.choices[0].message.content or ""
        except Exception:
            return None

    def generate(self, system: str, user: str, max_tokens: int = 1500,
                 fallback_fn=None) -> str:
        """Try NIM → Groq → rule-based fallback."""
        result = self._call_nim(system, user, max_tokens)
        if result:
            return result

        result = self._call_groq(system, user, max_tokens)
        if result:
            return result

        self._provider = "rule-based"
        if fallback_fn:
            return fallback_fn()
        return "[AI analysis unavailable — set NVIDIA_NIM_API_KEY or GROQ_API_KEY]"

    @property
    def provider(self) -> str:
        return self._provider
