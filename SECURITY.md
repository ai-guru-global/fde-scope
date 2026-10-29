# Security Policy

Security model as measured in this checkout on 2026-10-06. Where this file
states a number or a behaviour, it comes from the code and the test suite — not
from an aspiration. If you find a mismatch, that is itself a bug worth
reporting.

## Supported versions

| Version | Supported | Notes |
|---|---|---|
| `0.1.0` (current, `Development Status :: 3 - Alpha`) | ✅ | Only the latest commit gets fixes; there is no backport branch yet. |
| anything older | ❌ | Same for the packaged macOS app and the PawApp host: reproduce against `master` first. |

Python `3.11` and `3.12` are the CI matrix (`.github/workflows/ci.yml:19`).
The `agentscope` extra is a **measured** window, not an open-ended one —
`pyproject.toml` and `docs/agentscope_api_mapping.md` must quote the same
specifier verbatim and `tests/test_architecture_guard.py` fails if they drift.

## Reporting a vulnerability

**Use a private channel. Do not open a public issue, and do not attach a
reproducer that contains real customer data** — engagements, journals, corpora
and uploads are exactly the material this tool handles, and they are other
people's confidential information. A synthetic reproducer is enough.

- Preferred: GitHub's private vulnerability reporting on this repository —
  <https://github.com/ai-guru-global/fde-scope/security/advisories/new>.
  This requires the maintainer to have enabled *private vulnerability
  reporting* in Settings → Security; if the form is unavailable, say so through
  the owner's GitHub profile and we will enable it.
- Fallback: a **draft** security issue or an email to the maintainer, with
  the affected commit, the route or function (`file:line`), the preconditions
  (bind address, token state, `FDE_SCOPE_*` variables) and the impact.

We aim to acknowledge within 5 business days for an alpha-stage project. Fixes
land in `master` with a regression test; the release notes name the reporter
unless asked not to. There is no bounty and no NDA.

## What is enforced

1. **Authentication is on by default wherever it matters.** The token is read
   per request from `FDE_SCOPE_API_TOKEN` only — never from a file, never
   logged, never echoed in a response (`fde_scope/web/auth.py`). Unset means
   *unauthenticated only over loopback*: a request that **arrived on a
   non-loopback address** is answered `403`, so an operator who starts
   `uvicorn fde_scope.web.app:app --host 0.0.0.0` directly does not get an open
   console. The CLI additionally refuses to start a non-loopback bind without
   both `FDE_SCOPE_ALLOW_REMOTE=1` **and** a token (exit 2).
   The judgement uses `scope["server"]`, the address of the socket that
   *accepted* the connection, which a client cannot forge and
   `--proxy-headers` never rewrites. Measured: one `0.0.0.0` listener answers
   `200` to `127.0.0.1` and `403` to the LAN IP. Regression:
   `tests/test_web_auth.py` (22 tests), including a scan that asserts every
   mutating route is token-gated and that the whitelist holds no mutating path.
2. **Store ids cannot escape their directory.** Any caller-supplied identifier
   used as a path segment goes through `fde_scope/fsutil.py::safe_child()`,
   which rejects separators, NUL, `.`/`..` and any resolved result that leaves
   the store root. `UnsafeIdentifier` is a `ValueError`, so the console answers
   `400` rather than leaking a stack trace.
3. **User records are written atomically.** Every on-disk record goes through
   `atomic_write_text` / `atomic_write_bytes` (temp file + `os.replace`), so a
   crash leaves either the old or the new complete file. An AST guard fails the
   build on a bare `write_text`/`write_bytes`/`open(...,"wx+")` anywhere else
   under `fde_scope/`.
4. **Credentials never reach persistent artifacts.** API keys flow through the
   environment (`fde_scope/llm.py`) and are not written into manifests,
   reports, engagement JSON or logs. The console's operations view reports
   *whether* an env var is set, never its value.
5. **Permissions come from rules, and only from rules.** A deployed tool is
   never marked `is_read_only`, because upstream AgentScope ≥2.0.5 fast-tracks
   read-only calls ahead of allow-rules. Unmatched tools follow the mode
   fallback: HITL → `ASK` (a human decides), unattended → `DENY`.
6. **Gate evaluation is live.** `Engagement.advance()` re-evaluates the current
   phase's gates on every call; a stale `passed` record never grants passage,
   and a forced advance still evaluates and records, with `reason` required.

## What is deliberately out of scope

Read this before threatening-modeling the tool as a multi-tenant service.

- **One shared token, no identities.** There is no user account, no role, no
  session, no per-route authorization. `FDE_SCOPE_API_TOKEN` is a single secret:
  everyone who holds it is the operator. `TenantConfig` (`fde_scope/config.py`)
  is a *deployment descriptor* the FDE hands to the deploy step — **it is not a
  tenant isolation boundary** and provides no separation between tenants.
  Multi-user/RBAC/SSO is tracked as a separate architecture decision
  (`docs/commercialization-roadmap.md` P5).
- **No CSRF token on form endpoints, by design.** With a token set,
  authentication travels in `Authorization`/`X-API-Key` headers, which a
  cross-site form cannot send, so a driven POST cannot reach a data route. In
  the token-free loopback mode the local browser *can* be tricked into a
  same-origin POST — which is why the console is a loopback tool, and why the
  network path requires a token.
- **No TLS, no rate limiting, no lockout in-process.** Terminate TLS and apply
  throttling at a reverse proxy. Note the consequence of the accept-address
  rule: a proxy on the *same host* connects over loopback, so the middleware
  cannot see a routable address and the **proxy must authenticate on its own**
  (forward `X-API-Key`, or gate with `auth_request`/Basic Auth in front).
- **The audit log is evidence, not a signature.** `fde_scope/audit.py` appends
  JSONL to `<data root>/.fde_scope/audit.jsonl` and stores `sha256` file
  hashes; it is not a digital signature and has no tamper-evidence chain, and
  the `actor` field is a caller-supplied label (default `local`), not an
  authenticated identity. Anyone with write access to the data root can alter
  it — filesystem access is the trust boundary for every claim above.
- **Corpus and upload data are stored unencrypted**, with no field-level PII
  protection and no retention schedule (roadmap P4). Use an encrypted volume
  for `FDE_SCOPE_HOME`.
- **`fde_scope/license.py` is a commercial tier boundary, not a security
  control.** Its own docstring calls it "an honesty mechanism, not DRM": keys
  are offline HMAC-signed payloads, there is no phone-home, and nothing stops a
  determined user from patching the check out of MIT-licensed code. Do not
  build a trust boundary on a license tier.
- **Static mounts** (`/reports`, `/catalog`, `/GTM`) serve build output from the
  repository; the exact-path whitelist grants individual files, not directory
  prefixes. Do not place engagement data under those paths.

## Hardening a real deployment

```bash
export FDE_SCOPE_API_TOKEN="$(openssl rand -hex 32)"   # only in the environment
fde-scope web --host 127.0.0.1 --port 8080             # keep the bind on loopback
# LAN demo: put an authenticating, TLS-terminating proxy in front, and make the
# proxy itself check the token — the middleware will not see it as remote.
export FDE_SCOPE_HOME="$HOME/secure/FDE Scope"         # encrypted volume
```

Treat `<data root>/.fde_scope/` as confidential: it holds engagements,
journals, uploads, skills and the audit log. `FDE_SCOPE_ALLOW_REMOTE=1` alone no
longer disables authentication; a token is still required.

## For contributors

[AGENTS.md](AGENTS.md) is the machine-readable list of the invariants above, and
`tests/test_architecture_guard.py` plus `tests/test_web_auth.py` are the
regression anchors. When adding a web route: mutating routes must not be added
to `PUBLIC_PATHS`, and the guard tests will fail if they are.
