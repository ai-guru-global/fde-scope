"""Unified LLM client — Xiaomi MiMo Token Plan (OpenAI-compatible).

The engagement, corpus and eval layers are LLM-agnostic: they accept an
optional ``llm`` object and fall back to their rule-based v0 paths when none
is provided. This module is that optional object.

Configuration (all optional — no key means the client is simply unavailable
and every caller falls back to rules):

- ``FDE_SCOPE_MIMO_API_KEY``  — the ``tp-...`` Token Plan credential
- ``FDE_SCOPE_MIMO_BASE_URL`` — OpenAI-compatible endpoint
  (default: https://token-plan-cn.xiaomimimo.com/v1)
- ``FDE_SCOPE_MIMO_MODEL``    — model name (default: mimo-v2.5-pro)

The client uses only the standard library (``urllib``) so the core data
layer keeps its zero-extra-dependency promise. Auth follows the MiMo Token
Plan protocol: an ``api-key`` header (the ``tp-`` key is *not* an
``Authorization: Bearer`` token).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

DEFAULT_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
DEFAULT_MODEL = "mimo-v2.5-pro"

_ENV_KEY = "FDE_SCOPE_MIMO_API_KEY"
_ENV_BASE_URL = "FDE_SCOPE_MIMO_BASE_URL"
_ENV_MODEL = "FDE_SCOPE_MIMO_MODEL"

_TIMEOUT_SECONDS = 60
_MAX_TOKENS = 1024


class LLMError(RuntimeError):
    """Raised when the LLM endpoint fails (network, auth, or protocol)."""


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value and value.strip() else default


class MiMoClient:
    """Minimal OpenAI-compatible chat client for Xiaomi MiMo.

    ``available`` is False when no API key is configured; callers use it to
    decide between the LLM path and the rule-based fallback. Every public
    method raises :class:`LLMError` on failure — never silently returns
    partial data.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = _TIMEOUT_SECONDS,
    ) -> None:
        self.api_key = api_key or _env(_ENV_KEY)
        self.base_url = (base_url or _env(_ENV_BASE_URL) or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or _env(_ENV_MODEL) or DEFAULT_MODEL
        self.timeout = timeout

    # -- capability -------------------------------------------------------------
    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def describe(self) -> dict[str, str]:
        """Provider metadata for manifests / reports."""
        return {
            "provider": "xiaomi-mimo",
            "base_url": self.base_url,
            "model": self.model,
            "available": str(self.available),
        }

    # -- chat -------------------------------------------------------------------
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = _MAX_TOKENS,
    ) -> str:
        """One chat-completions round trip; returns the assistant message."""
        if not self.available:
            raise LLMError(
                f"{_ENV_KEY} is not set — configure the MiMo Token Plan key or pass api_key explicitly"
            )
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
        }
        body = self._post("/chat/completions", payload)
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"unexpected MiMo response shape: {str(body)[:300]!r}") from exc
        # OpenAI-compatible endpoints return "content": null on refusals /
        # tool calls — that is a failure, not a silent empty string.
        if not isinstance(content, str) or not content.strip():
            raise LLMError(f"MiMo returned empty content: {str(body)[:300]!r}")
        return content

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = _MAX_TOKENS,
    ) -> str:
        """One-shot completion from a plain prompt (system prompt optional)."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, temperature=temperature, max_tokens=max_tokens)

    # -- transport --------------------------------------------------------------
    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "api-key": self.api_key or "",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise LLMError(f"MiMo API HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LLMError(f"MiMo API request failed: {exc}") from exc
