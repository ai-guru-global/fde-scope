"""Training backends for the flywheel retrain scheduler.

Defines the :class:`TrainingBackend` protocol plus two implementations:

- :class:`HTTPTrainingBackend` — generic webhook-style training service:
  ``POST {url}/jobs`` with the JSON job spec, ``GET {url}/jobs/{id}`` for
  status, ``POST {url}/jobs/{id}/cancel`` to cancel. Pure ``urllib``, zero
  new dependencies, same transport discipline as ``connectors/zammad.py``.
- :class:`NoopBackend` — explicit placeholder when no backend is configured;
  it never pretends a job was really submitted (``backend=noop`` everywhere).

Configuration (AGENTS.md invariant 3 — credentials live in env vars only and
never appear in logs, exceptions or persisted records):

- ``FDE_SCOPE_TRAINING_URL`` — e.g. ``https://training.example.com``
- ``FDE_SCOPE_TRAINING_TOKEN`` — bearer token for the training service

:func:`get_training_backend` picks HTTP when both env vars resolve, otherwise
Noop. Partial configuration logs a WARNING and falls back to Noop — never
raises at import level.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Protocol, runtime_checkable

from ..logutil import get_logger

logger = get_logger("flywheel.backends")

ENV_TRAINING_URL = "FDE_SCOPE_TRAINING_URL"
ENV_TRAINING_TOKEN = "FDE_SCOPE_TRAINING_TOKEN"

# urllib's urlopen() takes a single timeout covering connect + read; 30s is
# the read budget (a hung connect typically fails well inside it).
_TIMEOUT_SECONDS = 30.0


class TrainingBackendError(RuntimeError):
    """Raised when a training-backend call fails (network, auth, protocol).

    Messages carry HTTP status and endpoint context only — never the token.
    """


@runtime_checkable
class TrainingBackend(Protocol):
    """Minimal surface a model-training backend must provide."""

    name: str

    def submit(self, job_spec: dict[str, Any]) -> str:
        """Submit a training job; returns the backend-assigned job id."""
        ...

    def status(self, job_id: str) -> dict[str, Any]:
        """Return the current status dict for a previously submitted job."""
        ...

    def cancel(self, job_id: str) -> dict[str, Any]:
        """Cancel a previously submitted job; returns the resulting status."""
        ...


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    return value.strip() if value and value.strip() else None


class HTTPTrainingBackend:
    """Webhook-style training service over HTTP (urllib only)."""

    name = "http"

    def __init__(self, base_url: str, token: str) -> None:
        if not base_url or not token:
            raise ValueError("HTTPTrainingBackend requires both base_url and token")
        self.base_url = base_url.rstrip("/")
        self._token = token

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method=method,
        )
        logger.debug("training backend request: %s %s", method, path)
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            logger.warning("training backend request failed: HTTP %d (%s %s)", exc.code, method, path)
            raise TrainingBackendError(f"training API HTTP {exc.code} ({method} {path})") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            logger.warning("training backend request failed: %s (%s %s)", type(exc).__name__, method, path)
            raise TrainingBackendError(
                f"training API request failed ({method} {path}): {type(exc).__name__}"
            ) from exc
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TrainingBackendError(f"training API returned invalid JSON ({method} {path})") from exc

    def submit(self, job_spec: dict[str, Any]) -> str:
        body = self._request("POST", "/jobs", payload=job_spec)
        if not isinstance(body, dict) or not (body.get("job_id") or body.get("id")):
            raise TrainingBackendError(
                f"unexpected training API response shape (POST /jobs): {str(body)[:200]!r}"
            )
        return str(body.get("job_id") or body.get("id"))

    def status(self, job_id: str) -> dict[str, Any]:
        body = self._request("GET", f"/jobs/{urllib.parse.quote(job_id, safe='')}")
        if not isinstance(body, dict):
            raise TrainingBackendError(
                f"unexpected training API response shape (GET /jobs/<id>): {str(body)[:200]!r}"
            )
        body.setdefault("job_id", job_id)
        body["backend"] = self.name
        return body

    def cancel(self, job_id: str) -> dict[str, Any]:
        path = f"/jobs/{urllib.parse.quote(job_id, safe='')}/cancel"
        body = self._request("POST", path, payload={})
        if not isinstance(body, dict):
            raise TrainingBackendError(
                f"unexpected training API response shape (POST /jobs/<id>/cancel): {str(body)[:200]!r}"
            )
        body.setdefault("job_id", job_id)
        body["backend"] = self.name
        return body


class NoopBackend:
    """Explicit placeholder when no training backend is configured.

    Honest about it: every result carries ``backend="noop"`` and a detail
    string, so callers can never mistake a no-op for a real submission.
    """

    name = "noop"

    def submit(self, job_spec: dict[str, Any]) -> str:  # noqa: ARG002
        logger.info(
            "no training backend configured (set %s and %s); job not submitted",
            ENV_TRAINING_URL,
            ENV_TRAINING_TOKEN,
        )
        return "noop-unsubmitted"

    def status(self, job_id: str) -> dict[str, Any]:
        return {
            "job_id": job_id,
            "status": "submitted-stub",
            "backend": self.name,
            "detail": "no training backend configured; job was not actually submitted",
        }

    def cancel(self, job_id: str) -> dict[str, Any]:
        return {
            "job_id": job_id,
            "status": "cancelled",
            "backend": self.name,
            "detail": "no training backend configured; nothing to cancel",
        }


def get_training_backend() -> TrainingBackend:
    """Factory: env fully configured → HTTP, otherwise an explicit Noop."""
    url = _env(ENV_TRAINING_URL)
    token = _env(ENV_TRAINING_TOKEN)
    if url and token:
        return HTTPTrainingBackend(url, token)
    if bool(url) != bool(token):
        logger.warning(
            "incomplete training backend configuration (%s without %s); falling back to noop",
            ENV_TRAINING_URL if url else ENV_TRAINING_TOKEN,
            ENV_TRAINING_TOKEN if url else ENV_TRAINING_URL,
        )
    return NoopBackend()
