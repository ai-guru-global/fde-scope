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


#: The one mutating route that is *not* admin-token gated on purpose:
#: ``POST /share/{eid}/ack`` is gated by the per-engagement share token in the
#: query string (a second credential, verified by the middleware's share
#: branch). With no credential it must fail closed as 404 — indistinguishable
#: from a nonexistent engagement — never 401, which would confirm the
#: engagement exists. The share-ack also cannot advance the state machine: it
#: only appends a ``share.ack`` audit line (see tests/test_share.py).
_SHARE_ACK = "/share/__probe__/ack"


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
    assert _SHARE_ACK in paths, "the share-ack route went missing — update the exception"
    for path in paths:
        for method in sorted(MUTATING):
            r = client.request(method, path)
            if path == _SHARE_ACK:
                # fails closed on a missing share credential — 404 for every
                # method (the middleware answers before routing), never 401
                assert r.status_code == 404, f"{method} {path} returned {r.status_code}, expected 404"
                continue
            assert r.status_code == 401, f"{method} {path} returned {r.status_code}, expected 401"
            assert TOKEN not in r.text


def test_public_paths_hold_no_mutating_route() -> None:
    """Belt and braces: the whitelist itself must not contain a write route."""
    from fde_scope.web.auth import PUBLIC_PATHS

    overlap = sorted(set(PUBLIC_PATHS) & set(_route_paths()))
    assert overlap == [], f"mutating routes are whitelisted: {overlap}"


# -- an unauthenticated listener must never be routable ----------------------
# FDE_SCOPE_ALLOW_REMOTE opts into a bind; it is not an authentication switch,
# so clearing it used to be enough to serve engagements, journals and the
# corpus-upload API to the whole network with no credentials. Two layers now
# refuse that: the CLI at start-up, and the middleware per request — because
# ``fde_scope.web.app:app`` can also be started through uvicorn or gunicorn
# directly, which never runs the CLI check.
#
# ``scope["server"]`` is the accepting socket's own address, so unlike the
# ``Host`` header a client cannot forge it into looking loopback; TestClient
# fills it from the request URL, which is how these tests pick the bind.
REMOTE_IP = "10.0.0.7"


@pytest.fixture
def remote_client(tmp_path, monkeypatch):
    """The app reached over a routable address with auth off.

    ``client``'s base URL (``http://testserver``) is a non-IP name, which is
    exactly the case the middleware refuses to judge — so this fixture spells
    a real bind instead.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FDE_SCOPE_API_TOKEN", raising=False)
    from fastapi.testclient import TestClient

    from fde_scope.web.app import app

    return TestClient(app, base_url=f"http://{REMOTE_IP}:8000")


def test_unauthenticated_routable_bind_is_403(remote_client) -> None:
    assert remote_client.get("/api/profiles").status_code == 403
    r = remote_client.post("/api/engagements", data={"customer": "Exposed", "profile": "ticket"})
    assert r.status_code == 403


def test_denial_names_the_env_var_and_the_bind(remote_client) -> None:
    """Actionable, and it never invents a token to hand out."""
    detail = remote_client.get("/api/profiles").json()["detail"]
    assert "FDE_SCOPE_API_TOKEN" in detail
    assert REMOTE_IP in detail
    assert "reverse proxy" in detail


def test_routable_bind_with_a_token_is_served(remote_client, monkeypatch) -> None:
    """The address alone is not forbidden — serving it without credentials is."""
    monkeypatch.setenv("FDE_SCOPE_API_TOKEN", TOKEN)
    assert remote_client.get("/api/profiles").status_code == 401
    assert remote_client.get("/api/profiles", headers={"X-API-Key": TOKEN}).status_code == 200


def test_health_probe_stays_open_on_a_routable_bind(remote_client) -> None:
    """/api/health is in PUBLIC_PATHS: a load balancer must reach it either way."""
    assert remote_client.get("/api/health").status_code == 200


def test_a_name_the_transport_cannot_judge_is_not_blocked(client) -> None:
    """``http://testserver`` (and a unix-socket listener) reports no IP.

    Blocking on that guess would break the in-process suite and ``--uds``
    deployments, so the CLI pre-flight stays the only gate for them.
    """
    assert client.get("/api/profiles").status_code == 200


def test_loopback_bind_needs_no_token(tmp_path, monkeypatch) -> None:
    """The single-machine default is untouched: 127.0.0.1 stays zero-friction."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FDE_SCOPE_API_TOKEN", raising=False)
    from fastapi.testclient import TestClient

    from fde_scope.web.app import app

    loopback = TestClient(app, base_url="http://127.0.0.1:8000")
    assert loopback.get("/api/profiles").status_code == 200
    r = loopback.post("/api/engagements", data={"customer": "Local", "profile": "ticket"})
    assert r.status_code == 200


# -- the same rule at the CLI boundary ---------------------------------------
# The middleware is the backstop; the CLI is what the operator actually runs,
# and a start-up refusal beats a 403 arriving after the port is already open.


@pytest.fixture
def runner():
    """``uvicorn.run`` captured instead of a socket bound."""
    from typer.testing import CliRunner

    return CliRunner()


@pytest.fixture
def no_serve(monkeypatch) -> list[tuple]:
    calls: list[tuple] = []
    monkeypatch.setattr("uvicorn.run", lambda *a, **kw: calls.append((a, kw)))
    return calls


@pytest.fixture
def clean_bind_env(monkeypatch):
    monkeypatch.delenv("FDE_SCOPE_API_TOKEN", raising=False)
    monkeypatch.delenv("FDE_SCOPE_ALLOW_REMOTE", raising=False)


def test_cli_refuses_a_routable_bind_even_with_allow_remote(
    runner, no_serve, clean_bind_env, monkeypatch
) -> None:
    """The pre-existing opt-in flag must not double as an authentication switch."""
    from fde_scope.cli import app as cli_app

    monkeypatch.setenv("FDE_SCOPE_ALLOW_REMOTE", "1")
    result = runner.invoke(cli_app, ["web", "--host", REMOTE_IP])
    assert result.exit_code == 2
    assert not no_serve, "uvicorn.run ran despite the refused bind"
    assert "FDE_SCOPE_API_TOKEN" in result.stdout
    assert REMOTE_IP in result.stdout


def test_cli_serves_a_routable_bind_with_token_and_opt_in(runner, no_serve, monkeypatch) -> None:
    from fde_scope.cli import app as cli_app

    monkeypatch.setenv("FDE_SCOPE_ALLOW_REMOTE", "1")
    monkeypatch.setenv("FDE_SCOPE_API_TOKEN", TOKEN)
    result = runner.invoke(cli_app, ["web", "--host", REMOTE_IP])
    assert result.exit_code == 0, result.stdout
    assert no_serve and no_serve[0][1]["host"] == REMOTE_IP


def test_cli_loopback_bind_needs_neither_flag(runner, no_serve, clean_bind_env) -> None:
    from fde_scope.cli import app as cli_app

    result = runner.invoke(cli_app, ["web"])
    assert result.exit_code == 0, result.stdout
    assert no_serve and no_serve[0][1]["host"] == "127.0.0.1"


def test_cli_still_refuses_an_un_opted_routable_bind(runner, no_serve, clean_bind_env, monkeypatch) -> None:
    """A token is necessary, not sufficient: the bind still needs its opt-in."""
    from fde_scope.cli import app as cli_app

    monkeypatch.setenv("FDE_SCOPE_API_TOKEN", TOKEN)
    result = runner.invoke(cli_app, ["web", "--host", "0.0.0.0"])
    assert result.exit_code == 2
    assert not no_serve
    assert "FDE_SCOPE_ALLOW_REMOTE" in result.stdout


def test_cli_treats_an_unrecognised_bind_name_as_remote(runner, no_serve, clean_bind_env) -> None:
    """``--host buildhost`` fails closed: the operator typed it, and a name that
    does not resolve right now may still resolve to a routable address."""
    from fde_scope.cli import app as cli_app

    result = runner.invoke(cli_app, ["web", "--host", "buildhost.internal"])
    assert result.exit_code == 2
    assert not no_serve
