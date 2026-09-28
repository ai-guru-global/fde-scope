"""LLM client layer — provider abstraction over OpenAI-style chat endpoints.

The engagement, corpus and eval layers are LLM-agnostic: they accept an
optional ``llm`` object and fall back to their rule-based v0 paths when none
is provided. This module is that optional object.

Provider selection (all env-configured; no key means the client is simply
unavailable and every caller falls back to rules):

- **Generic OpenAI-compatible** (checked first): set
  ``FDE_SCOPE_LLM_BASE_URL`` + ``FDE_SCOPE_LLM_API_KEY`` (+ optional
  ``FDE_SCOPE_LLM_MODEL``) to point at any ``/chat/completions`` endpoint
  (vLLM, OpenAI, DeepSeek, …). Auth is the standard
  ``Authorization: Bearer`` header.
- **Xiaomi MiMo Token Plan** (default): ``FDE_SCOPE_MIMO_API_KEY`` (the
  ``tp-...`` credential), ``FDE_SCOPE_MIMO_BASE_URL``,
  ``FDE_SCOPE_MIMO_MODEL``. Auth follows the MiMo Token Plan protocol: an
  ``api-key`` header (the ``tp-`` key is *not* a bearer token).

The client uses only the standard library (``urllib``) so the core data
layer keeps its zero-extra-dependency promise. Credentials flow through the
environment only and never appear in logs, manifests or reports
(AGENTS.md invariant 3).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Protocol, runtime_checkable

DEFAULT_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
DEFAULT_MODEL = "mimo-v2.5-pro"

_ENV_KEY = "FDE_SCOPE_MIMO_API_KEY"
_ENV_BASE_URL = "FDE_SCOPE_MIMO_BASE_URL"
_ENV_MODEL = "FDE_SCOPE_MIMO_MODEL"

_ENV_OAI_BASE_URL = "FDE_SCOPE_LLM_BASE_URL"
_ENV_OAI_KEY = "FDE_SCOPE_LLM_API_KEY"
_ENV_OAI_MODEL = "FDE_SCOPE_LLM_MODEL"

_TIMEOUT_SECONDS = 60
_MAX_TOKENS = 1024


class LLMError(RuntimeError):
    """Raised when the LLM endpoint fails (network, auth, or protocol)."""


@runtime_checkable
class LLMClient(Protocol):
    """The minimal surface every LLM caller relies on.

    Structural typing: :class:`MiMoClient` and :class:`OpenAICompatClient`
    satisfy this without inheritance, and tests keep injecting simple fakes
    (``available`` + ``complete`` + ``describe``).
    """

    @property
    def available(self) -> bool: ...

    def describe(self) -> dict[str, str]: ...

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = _MAX_TOKENS,
    ) -> str: ...

    def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = _MAX_TOKENS,
    ) -> str: ...


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value and value.strip() else default


class _ChatCompletionsClient:
    """Shared transport for OpenAI-style ``/chat/completions`` endpoints.

    ``available`` is False when no API key is configured; callers use it to
    decide between the LLM path and the rule-based fallback. Every public
    method raises :class:`LLMError` on failure — never silently returns
    partial data. Subclasses provide the auth header and provider name.
    """

    provider = "openai-compatible"
    _error_label = "LLM"
    _env_key_hint = _ENV_OAI_KEY

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = _TIMEOUT_SECONDS,
    ) -> None:
        self.api_key = api_key or _env(self._env_key_hint)
        self.base_url = (base_url or self._default_base_url()).rstrip("/")
        self.model = model or self._default_model()
        self.timeout = timeout

    def _default_base_url(self) -> str:
        raise NotImplementedError

    def _default_model(self) -> str:
        raise NotImplementedError

    def _auth_headers(self) -> dict[str, str]:
        raise NotImplementedError

    # -- capability -------------------------------------------------------------
    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def describe(self) -> dict[str, str]:
        """Provider metadata for manifests / reports (never the key itself)."""
        return {
            "provider": self.provider,
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
                f"{self._env_key_hint} is not set — configure the API key or pass api_key explicitly"
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
            raise LLMError(f"unexpected {self._error_label} response shape: {str(body)[:300]!r}") from exc
        # OpenAI-compatible endpoints return "content": null on refusals /
        # tool calls — that is a failure, not a silent empty string.
        if not isinstance(content, str) or not content.strip():
            raise LLMError(f"{self._error_label} returned empty content: {str(body)[:300]!r}")
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
                **self._auth_headers(),
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise LLMError(f"{self._error_label} API HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LLMError(f"{self._error_label} API request failed: {exc}") from exc


class MiMoClient(_ChatCompletionsClient):
    """Minimal chat client for Xiaomi MiMo Token Plan (``api-key`` header auth)."""

    provider = "xiaomi-mimo"
    _error_label = "MiMo"
    _env_key_hint = _ENV_KEY

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = _TIMEOUT_SECONDS,
    ) -> None:
        super().__init__(api_key=api_key, base_url=base_url, model=model, timeout=timeout)

    def _default_base_url(self) -> str:
        return _env(_ENV_BASE_URL) or DEFAULT_BASE_URL

    def _default_model(self) -> str:
        return _env(_ENV_MODEL) or DEFAULT_MODEL

    def _auth_headers(self) -> dict[str, str]:
        return {"api-key": self.api_key or ""}


class OpenAICompatClient(_ChatCompletionsClient):
    """Generic OpenAI-compatible client (``Authorization: Bearer`` auth).

    Configured via ``FDE_SCOPE_LLM_BASE_URL`` + ``FDE_SCOPE_LLM_API_KEY``
    (``FDE_SCOPE_LLM_MODEL`` optional, default ``gpt-4o-mini``). Explicit
    constructor arguments override the environment.
    """

    provider = "openai-compatible"
    _error_label = "LLM"
    _env_key_hint = _ENV_OAI_KEY
    DEFAULT_MODEL = "gpt-4o-mini"

    def _default_base_url(self) -> str:
        return _env(_ENV_OAI_BASE_URL) or "https://api.openai.com/v1"

    def _default_model(self) -> str:
        return _env(_ENV_OAI_MODEL) or self.DEFAULT_MODEL

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key or ''}"}


def get_llm_client() -> LLMClient:
    """Build the LLM client selected by the environment.

    ``FDE_SCOPE_LLM_BASE_URL`` + ``FDE_SCOPE_LLM_API_KEY`` both set →
    :class:`OpenAICompatClient`; otherwise the MiMo default (unchanged
    behaviour for existing deployments). The returned client may still be
    ``available == False`` when no credential is configured — callers fall
    back to rule-based paths as before.
    """
    if _env(_ENV_OAI_BASE_URL) and _env(_ENV_OAI_KEY):
        return OpenAICompatClient()
    return MiMoClient()
