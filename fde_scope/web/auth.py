"""API token authentication for the web layer (commercialization gap B1).

The token comes from the ``FDE_SCOPE_API_TOKEN`` environment variable only —
never from a file, never logged, never echoed in a response. When the
variable is unset or empty, authentication is *off* — but only for requests
that arrive over loopback: an unauthenticated console reached on a routable
address exposes engagements, journals and the corpus-upload endpoint to the
network, so :class:`ApiTokenAuthMiddleware` answers 403 (see
:func:`routable_local_address`) and the CLI refuses to start a non-loopback
bind without a token (see :func:`host_is_loopback`). Loopback stays
zero-friction: the single-machine experience and the test suite need no token.
When the variable is set, every route outside :data:`PUBLIC_PATHS` requires
either ``Authorization: Bearer <token>`` or ``X-API-Key: <token>``; anything
else gets a bare 401.

The env var is read per request, not at import time, so tests can
``monkeypatch.setenv`` after the app is constructed.
"""

from __future__ import annotations

import hmac
import ipaddress
import os
import re
from collections.abc import Mapping
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

#: Read-only stakeholder share links — ``/share/{eid}`` and its ``/ack`` form
#: target. Their credential is the per-engagement share token in the query
#: string (``?t=``), verified against the sha256 stored in the engagement (see
#: :mod:`fde_scope.web.share`); this is a second, deliberately separate
#: credential from the admin API token above. A failed check answers 404 —
#: never 403 — so an uncredentialed caller cannot even learn whether an
#: engagement id exists.
_SHARE_PATH = re.compile(r"^/share/([A-Za-z0-9._-]+)(/ack)?$")

#: Paths reachable without a token when auth is on. Kept minimal: the health
#: probe plus the static HTML shells (they carry no engagement data; their
#: JSON calls still need the token). The certification, glossary, course, SOP,
#: GitHub-resources, portfolio-registry and repo-docs pages are such shells too:
#: public exam specs, field vocabulary, the Level-1 course text, the full SOP,
#: the harvested GitHub resource index, the registry's *rubric* page and the
#: repository's own documents — no engagement data, no mutating endpoints. The
#: showcase page is public precisely because it lists nothing: the entries and
#: their audits are three ``/api/showcase/`` endpoints behind the token, since a
#: cohort's codenames and certificate numbers are identifying detail (course
#: lesson 11 §6.1). The two skills-handbook portal indexes, the two
#: GitHub-resources portal indexes, the GTM site (page, fonts and the two
#: screenshots it embeds) and the repo screenshot files are static build
#: output / content under the same rule. Matching is
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
        "/showcase",
        "/en/showcase",
        "/resources",
        "/en/resources",
        "/catalog/index.html",
        "/catalog/en/index.html",
        "/gh-resources/site/index.html",
        "/gh-resources/site/en/index.html",
        "/GTM/",
        "/GTM/index.html",
        "/GTM/en/",
        "/GTM/en/index.html",
        "/docs/images/overview.png",
        "/docs/images/console.png",
        # Browsers fetch the tab icon without auth headers; it is a brand
        # glyph, not engagement data.
        "/static/favicon.svg",
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
    # The two screenshots the portal embeds (``GTM/index.html`` as
    # ``images/*.png``, ``GTM/en/index.html`` as ``../images/*.png``; both
    # resolve to these paths). Exact paths only — nothing else under
    # ``GTM/images/`` becomes reachable, and no directory prefix is granted.
    | {f"/GTM/images/{name}" for name in ("console.png", "overview.png")}
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
    # Narrowed before the call: ``compare_digest`` is generic over ``AnyStr`` and
    # cannot accept ``str | None``, and the guard keeps the timing-safe compare
    # the only path that ever touches a real candidate.
    if candidate is None:
        return False
    return hmac.compare_digest(candidate, token)


def token_is_configured() -> bool:
    """True when ``FDE_SCOPE_API_TOKEN`` holds a non-empty token."""
    return _configured_token() is not None


def host_is_loopback(host: str) -> bool:
    """True for loopback bind targets (``localhost``, 127.0.0.0/8, ::1).

    Anything else — including a name that will not resolve right now — counts
    as remote, because this judges the host an operator *typed* on the command
    line and an unrecognised bind must fail closed, not open a listener nobody
    meant to expose.
    """
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def routable_local_address(scope: Mapping[str, Any]) -> str | None:
    """The non-loopback address this request *arrived on*, or ``None``.

    ``scope["server"]`` is the accepting socket's local endpoint (uvicorn:
    ``get_local_addr(transport)``), not the ``--host`` the operator passed: a
    listener bound to ``0.0.0.0`` reports ``127.0.0.1`` for traffic that came in
    over loopback and the routable IP for traffic that came over the network.
    So this is a per-connection judgement, and — unlike the ``Host`` header — a
    client cannot forge it. ``--proxy-headers`` rewrites ``scope["client"]``
    from ``X-Forwarded-For`` but never ``server``, which is why a same-host
    reverse proxy does land on loopback and has to authenticate on its own.

    A host that is not an IP literal means the transport gave us nothing
    judgeable: a unix-socket listener reports an empty or non-numeric address,
    and the in-process ``TestClient`` reports the URL's hostname. Those are not
    network binds this check can reason about, so the request is not blocked on
    a guess — the CLI's pre-flight (:func:`host_is_loopback`) stays the
    authoritative gate for them, and a real uvicorn/gunicorn listener always
    reports the numeric address of the socket that accepted the connection.
    """
    server = scope.get("server")
    if not server:
        return None
    host = server[0]
    if not host:
        return None
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return None
    return None if ip.is_loopback else host


_UNAUTHENTICATED_REMOTE = (
    "authentication is off and this request arrived on the non-loopback address "
    "{addr}. FDE Scope will not serve engagement data unauthenticated over a "
    "network: export a secret token in {env} (then send it as "
    "'Authorization: Bearer <token>' or 'X-API-Key: <token>'), or keep the "
    "console on 127.0.0.1 and authenticate at a reverse proxy."
)


def _routable_denial(addr: str) -> JSONResponse:
    return JSONResponse(
        {"detail": _UNAUTHENTICATED_REMOTE.format(addr=repr(addr), env=ENV_VAR)},
        status_code=403,
    )


class ApiTokenAuthMiddleware(BaseHTTPMiddleware):
    """Require the configured bearer token on all non-public paths.

    With no token configured it still refuses any non-public request that
    arrived on a routable address, so the rule holds for servers started
    directly (``uvicorn``/``gunicorn``) as well as through ``fde-scope web``.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        token = _configured_token()
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)
        share_match = _SHARE_PATH.match(request.url.path)
        if share_match is not None:
            # Share links carry their own per-engagement credential; a bad one
            # must be indistinguishable from a nonexistent engagement (404).
            from .share import verify_share_token

            if verify_share_token(share_match.group(1), request.query_params.get("t")) is not None:
                return await call_next(request)
            return JSONResponse({"detail": "share link invalid or revoked"}, status_code=404)
        if token is None:
            # Auth off is the local default, never the remote one.
            exposed = routable_local_address(request.scope)
            if exposed is not None:
                return _routable_denial(exposed)
            return await call_next(request)
        authorization = request.headers.get("authorization", "")
        scheme, _, bearer = authorization.partition(" ")
        if (scheme.lower() == "bearer" and _matches(bearer.strip(), token)) or _matches(
            request.headers.get("x-api-key"), token
        ):
            return await call_next(request)
        return JSONResponse({"detail": "invalid or missing API token"}, status_code=401)
