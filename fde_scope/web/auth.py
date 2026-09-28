"""API token authentication for the web layer (commercialization gap B1).

The token comes from the ``FDE_SCOPE_API_TOKEN`` environment variable only —
never from a file, never logged, never echoed in a response. When the
variable is unset or empty, authentication is *off* and every request passes:
that keeps the local single-machine experience (and the existing test suite)
untouched. When it is set, every route outside :data:`PUBLIC_PATHS` requires
either ``Authorization: Bearer <token>`` or ``X-API-Key: <token>``; anything
else gets a bare 401.

The env var is read per request, not at import time, so tests can
``monkeypatch.setenv`` after the app is constructed.
"""

from __future__ import annotations

import hmac
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

#: Paths reachable without a token when auth is on. Kept minimal: the health
#: probe plus the static HTML shells (they carry no engagement data; their
#: JSON calls still need the token).
PUBLIC_PATHS = frozenset({"/api/health", "/", "/console", "/en/", "/en/console"})

ENV_VAR = "FDE_SCOPE_API_TOKEN"


def _configured_token() -> str | None:
    token = os.environ.get(ENV_VAR, "").strip()
    return token or None


def _matches(candidate: str | None, token: str) -> bool:
    return bool(candidate) and hmac.compare_digest(candidate, token)


class ApiTokenAuthMiddleware(BaseHTTPMiddleware):
    """Require the configured bearer token on all non-public paths."""

    async def dispatch(self, request: Request, call_next) -> Response:
        token = _configured_token()
        if token is None or request.url.path in PUBLIC_PATHS:
            return await call_next(request)
        authorization = request.headers.get("authorization", "")
        scheme, _, bearer = authorization.partition(" ")
        if (scheme.lower() == "bearer" and _matches(bearer.strip(), token)) or _matches(
            request.headers.get("x-api-key"), token
        ):
            return await call_next(request)
        return JSONResponse({"detail": "invalid or missing API token"}, status_code=401)
