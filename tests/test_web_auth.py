"""Tests for the web-layer API token authentication (commercialization B1)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.filterwarnings("ignore")

TOKEN = "test-token-0123456789"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FDE_SCOPE_API_TOKEN", raising=False)
    from fastapi.testclient import TestClient

    from fde_scope.web.app import app

    return TestClient(app)


def test_auth_disabled_by_default(client) -> None:
    """Without FDE_SCOPE_API_TOKEN every request passes (local experience)."""
    assert client.get("/api/profiles").status_code == 200
    assert (
        client.post("/api/engagements", data={"customer": "NoAuth", "profile": "ticket"}).status_code == 200
    )


def test_health_never_requires_token(client, monkeypatch) -> None:
    monkeypatch.setenv("FDE_SCOPE_API_TOKEN", TOKEN)
    assert client.get("/api/health").status_code == 200


def test_static_pages_never_require_token(client, monkeypatch) -> None:
    monkeypatch.setenv("FDE_SCOPE_API_TOKEN", TOKEN)
    for path in (
        "/",
        "/console",
        "/en/",
        "/en/console",
        "/certification",
        "/en/certification",
        "/course",
        "/en/course",
    ):
        assert client.get(path).status_code == 200


def test_missing_header_is_401(client, monkeypatch) -> None:
    monkeypatch.setenv("FDE_SCOPE_API_TOKEN", TOKEN)
    r = client.get("/api/profiles")
    assert r.status_code == 401
    assert TOKEN not in r.text  # the token never leaks into responses


def test_wrong_token_is_401(client, monkeypatch) -> None:
    monkeypatch.setenv("FDE_SCOPE_API_TOKEN", TOKEN)
    assert client.get("/api/profiles", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/profiles", headers={"X-API-Key": "wrong"}).status_code == 401


def test_bearer_token_accepted(client, monkeypatch) -> None:
    monkeypatch.setenv("FDE_SCOPE_API_TOKEN", TOKEN)
    r = client.get("/api/profiles", headers={"Authorization": f"Bearer {TOKEN}"})
    assert r.status_code == 200


def test_x_api_key_accepted(client, monkeypatch) -> None:
    monkeypatch.setenv("FDE_SCOPE_API_TOKEN", TOKEN)
    r = client.get("/api/profiles", headers={"X-API-Key": TOKEN})
    assert r.status_code == 200


def test_mutating_route_requires_token(client, monkeypatch) -> None:
    monkeypatch.setenv("FDE_SCOPE_API_TOKEN", TOKEN)
    assert client.post("/api/engagements", data={"customer": "Sec", "profile": "ticket"}).status_code == 401
    r = client.post(
        "/api/engagements",
        data={"customer": "Sec", "profile": "ticket"},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert r.status_code == 200


def test_blank_token_disables_auth(client, monkeypatch) -> None:
    monkeypatch.setenv("FDE_SCOPE_API_TOKEN", "   ")
    assert client.get("/api/profiles").status_code == 200


#: Methods that change state. A route using one of these must never land in
#: ``PUBLIC_PATHS`` by accident — AGENTS.md invariant 7.
MUTATING = frozenset({"POST", "PATCH", "PUT", "DELETE"})


def _route_paths() -> list[str]:
    from fde_scope.web.app import app

    out: list[str] = []
    for route in app.routes:
        if not MUTATING.intersection(getattr(route, "methods", None) or set()):
            continue
        # ``{eid}`` / ``{rest:path}`` are filled with a placeholder: the auth
        # middleware runs before routing, so the value is never resolved.
        path = route.path
        while "{" in path:
            path = path[: path.index("{")] + "__probe__" + path[path.index("}", path.index("{")) + 1 :]
        out.append(path)
    return sorted(set(out))


def test_every_mutating_route_is_token_gated(client, monkeypatch) -> None:
    """Enumerate the app's mutating routes instead of trusting a hand-picked list.

    ``test_mutating_route_requires_token`` only probes ``POST /api/engagements``,
    so a new endpoint added to ``PUBLIC_PATHS`` — or a middleware change that
    lets writes through — would go unnoticed. This walks ``app.routes`` so the
    guarantee follows the code (invariant 7).
    """
    monkeypatch.setenv("FDE_SCOPE_API_TOKEN", TOKEN)
    paths = _route_paths()
    assert paths, "no mutating routes found — the enumeration itself is broken"
    for path in paths:
        for method in sorted(MUTATING):
            r = client.request(method, path)
            assert r.status_code == 401, f"{method} {path} returned {r.status_code}, expected 401"
            assert TOKEN not in r.text


def test_public_paths_hold_no_mutating_route() -> None:
    """Belt and braces: the whitelist itself must not contain a write route."""
    from fde_scope.web.auth import PUBLIC_PATHS

    overlap = sorted(set(PUBLIC_PATHS) & set(_route_paths()))
    assert overlap == [], f"mutating routes are whitelisted: {overlap}"
