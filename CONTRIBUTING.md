# Contributing

Thanks for getting to the details. This is an alpha-stage, single-maintainer
project that encodes a real delivery methodology, so the bar for "green" is
specific: the invariants below are guarded by tests, not by review comments.

## 1. Set up

```bash
git clone https://github.com/ai-guru-global/fde-scope.git && cd fde-scope
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,mysql]"          # what CI installs
pip install ruff mypy                  # the Makefile notes these are NOT in .[dev]
```

`make install-full` installs everything (`.[full]`: dev + agentscope + mysql +
opcua + mqtt + ros2 + web). With [uv](https://docs.astral.sh/uv/), use
`uv sync --extra dev --extra agentscope` — `uv.lock` is committed and CI resolves
from it, so a dependency change must be accompanied by `uv lock` in the same PR.

Core layer runs with zero optional dependencies: `fde-scope --help` and the
whole engagement/SOP/gate path need no `agentscope`, and
`pytest -m "not agentscope"` is the no-extras contract.

## 2. Run the four regression anchors

CI runs these; a PR that is red here is not ready.

```bash
pytest -q                                          # full suite (coverage gate: fail_under=90)
pytest -m agentscope                               # real-library runtime tests (needs the extra)
pytest tests/test_architecture_guard.py            # contract guards
ruff check . && ruff format --check . && mypy fde_scope
```

Also useful, and part of CI in other jobs:

```bash
make check-catalog        # docs/skills-catalog counts, sections, index, links
node --check pawapp/ui/index.js
```

Two things worth knowing before you read a green run:

- Coverage is only enforced with `--cov` (CI: `pytest --cov=fde_scope
  --cov=pawapp/backend`). Local `pytest -q` is faster without it.
- Integration markers self-skip unless their env is set: `mysql`
  (`FDE_SCOPE_MYSQL_DSN`), `opcua` (`FDE_SCOPE_OPCUA_URL`), `mqtt`
  (`FDE_SCOPE_MQTT_URL`), `ros2` (`FDE_SCOPE_ROS2_BAG`). A skip is not a pass —
  if your change touches a connector, say in the PR description whether you ran
  it against a real endpoint.

## 3. The rules that are tested, not just requested

[AGENTS.md](AGENTS.md) is the machine-readable list. The ones that catch
well-intentioned contributions:

- **Gates are re-evaluated live.** `Engagement.advance()` re-checks the current
  phase's gates on every advance, and a forced advance still evaluates and
  records. Do not add caching or a short-circuit around `evaluate_phase_gates`.
- **Ids are server-generated.** `SkillRecord.id` and `EngagementContext.id` are
  assigned by the owning store; no mass-assignment path may accept an external id.
- **Credentials live in env vars only.** They must never land in a manifest, a
  report, engagement JSON, a log line or a response body. The console's
  operations view reports *whether* an env var is set, never its value.
- **User records are written atomically**, through `fde_scope/fsutil.py`
  (`atomic_write_text` / `atomic_write_bytes`). An AST guard fails the suite on a
  bare `write_text`/`write_bytes`/`open(..., "wx+")` anywhere under `fde_scope/`.
- **Any caller-supplied id used as a path segment goes through `safe_child()`**
  (skills, ontology, corpus, uploads). `UnsafeIdentifier` is a `ValueError` so
  the web layer answers `400`.
- **Rule grants are the only permission channel.** Never set `is_read_only` on a
  deployed `FunctionTool`: upstream AgentScope ≥2.0.5 fast-tracks read-only
  calls ahead of allow-rules. Unmatched tools must fall back to the mode
  (HITL → `ASK`, unattended → `DENY`).
- **The `agentscope` window is measured.** `pyproject.toml`'s `agentscope` extra
  and `docs/agentscope_api_mapping.md` quote the same specifier verbatim and the
  guard test compares them character by character. Widening it requires running
  `pytest -m agentscope` per version in an isolated environment, and recording
  the result in `docs/agentscope_api_mapping.md`.
- **A new mutating web route must not join `PUBLIC_PATHS`.** `tests/
  test_web_auth.py` enumerates the route table and asserts every write operation
  is token-gated.

`fde_scope/engagement/phases.py` (18 phases) and the default gate registry
(10 gates) are contract-pinned: the guard tests fail **on purpose**. Changing
them is allowed, but only as a deliberate contract update, described in `docs/`,
with the counts updated in the same commit — including the 11 places that
advertise the console's route count (the guard names them).

## 4. Code style

- Python 3.11+ (`requires-python`), ruff with `line-length = 110`, double quotes,
  `select = ["E","W","F","I","C4","B","SIM","UP"]`. `ruff format` is the
  formatter; do not hand-wrap to appease `E501` (it is ignored).
- `from __future__ import annotations` and modern `X | None` unions.
- Comments explain *why* a constraint exists — the repo's convention is a short
  note naming the risk or the measured surprise ("upstream ≥2.0.5 fast-tracks
  read-only calls"), never a restatement of what the line does.
- Docstrings and user-facing docs are bilingual by intent: Chinese text uses
  「」 for quoting, not curly quotes.

## 5. Tests

Every fix ships with a test that fails before it. Prefer the existing style: a
named test per contract, with the reason in the docstring. For filesystem
behaviour use `tmp_path` and the autouse `_isolated_data_root` fixture in
`tests/conftest.py`, which pins `FDE_SCOPE_HOME` per test — do not rely on the
developer's real `~/Documents/FDE Scope`.

**Fixtures must be synthetic.** This tool's whole job is handling a client's
corpus, so no real company names, no real ticket data, no personal data of any
real person may enter the repository — not in a test, not in a screenshot, not
in a commit message or a PR discussion.

## 6. Commits and pull requests

Conventional Commits with a scope, as the history shows:
`feat(ros2): normalize pipeline + binary exclusion table`,
`fix(ros2): address code review — docstring, schema types, type annotation, error test`,
`docs(features): sync lists with the shipped rosbag2 replay + pin doc-drift guards`.
One concern per commit; "update" is not a message.

Before opening the PR, run the four anchors and paste their real output (counts
and failures included). For anything touching the state machine, the permission
pipeline, the auth defaults or the dependency window, open an issue first —
those are the four areas where a silent change costs the most.

`docs/` is part of the product here: a claim in a feature list, the roadmap or
the landing page is a claim the guards check. When behaviour changes, update
`README.md`, the relevant `docs/*.md`, `CHANGELOG.md` and `SECURITY.md` in the
same PR rather than "later".

## 7. Reporting bugs

Ordinary bugs go to public issues; anything that exposes engagement data,
bypasses a gate or escapes a store root goes through
[SECURITY.md](SECURITY.md) instead. Include the commit, `file:line`, the bind
address and token state, and the Python version.
