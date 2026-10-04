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
#: JSON calls still need the token). The certification, glossary, course, SOP
#: and repo-docs pages are such shells too: public exam specs, field
#: vocabulary, the Level-1 course text, the full SOP and the repository's own
#: documents, no engagement data, no mutating endpoints. The two
#: skills-handbook portal indexes, the GTM site and the repo screenshot files
#: are static build output / content under the same rule. Matching is
#: exact-path (``request.url.path in PUBLIC_PATHS``), so sibling paths such as
#: ``/catalog/`` or ``/docs/`` itself are still gated.
public_html = frozenset(
    {
        "/api/health",
        "/",
        "/en/",
        "/console",
        "/en/console",
        "/certification",
        "/en/certification",
        "/glossary",
        "/en/glossary",
        "/course",
        "/en/course",
        "/sop",
        "/en/sop",
        "/catalog/index.html",
        "/catalog/en/index.html",
        "/GTM/",
        "/GTM/index.html",
        "/GTM/en/",
        "/GTM/en/index.html",
        "/docs/images/overview.png",
        "/docs/images/console.png",
    }
)
_gtm_assets = frozenset(
    {
        f"/GTM/fonts/{name}"
        for name in (
            "big-shoulders-display-latin-700-normal.woff2",
            "big-shoulders-display-latin-800-normal.woff2",
            "big-shoulders-display-latin-900-normal.woff2",
            "public-sans-latin-400-normal.woff2",
            "public-sans-latin-600-normal.woff2",
            "public-sans-latin-700-normal.woff2",
            "spline-sans-mono-latin-400-normal.woff2",
            "spline-sans-mono-latin-600-normal.woff2",
        )
    }
)
#: Local reader routes for the repository's documents — the slug list lives in
#: ``docs_reader.py``, and the read-only pages it renders carry no engagement
#: data, so both locales are public alongside the other reading shells.
doc_slugs = frozenset(
    {
        "readme",
        "fde-research",
        "fde_playbook",
        "features",
        "features-en",
        "user-guide",
        "api-reference",
        "onboarding-customer",
        "architecture",
        "ontology",
        "agentscope_api_mapping",
        "manufacturing_scenario",
        "llm_integration",
        "qwenpaw_integration",
        "skills",
        "code_review_checklist",
        "examples",
        "course-en",
        "license",
        "notice",
    }
)
PUBLIC_PATHS = (
    public_html
    | _gtm_assets
    | {f"/docs/{slug}" for slug in doc_slugs}
    | {f"/en/docs/{slug}" for slug in doc_slugs}
)

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
