# Changelog

All notable changes to this project are documented in this file.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) ·
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Baseline facts (measured 2026-10-06, not inferred).** `git tag` is empty and
> `fde-scope` is not on PyPI (`https://pypi.org/pypi/fde-scope/json` → `404`).
> So the `version = "0.1.0"` in `pyproject.toml` is the **first publishable
> version**, not a release that already shipped. `## [Unreleased]` below is work
> that has landed in the tree and must be folded into `0.1.0` at publish time.
> History before this file exists is in `git log` (Conventional Commits).
>
> Numbers in this file are deliberately few and each is re-measurable:
> 18 phases and 10 default gates are pinned by `tests/test_architecture_guard.py`;
> so is the console's route count — **86 declared `(verb, path)` pairs, 83 served**
> (measured 2026-10-09). The gap is exactly 3 install-time asset fallbacks
> (`/catalog`, `/GTM`, `/gh-resources` `{rest:path}`): a source checkout serves
> those through `StaticFiles` rather than a decorator, so `app.openapi()` omits
> them. `test_web_route_count_claim_is_honest` guards **11** advertised counts
> across README, `docs/features.md`, `docs/features-en.md`, `web/i18n.py` and
> `app.py`. It does **not** read this file or `docs/api-reference.md` — counts
> here are corrected by hand, which is exactly how they went stale.
>
> **Releasing.** `python -m build` produces artifacts; it does not publish
> anything. Publication is `git tag` + push + an upload to the index — and on PyPI
> **a released version number can never be reused**: a yank leaves `0.1.0` taken
> whether or not the file behind it worked. So the order is: green checks → build →
> install the wheel into a clean venv and exercise it → only then tag and upload.

## [Unreleased]

### ⚠️ Release gate — measured 2026-10-07

Green:

- `pytest` (full suite, `-o addopts=""` so the count is printed):
  **1053 passed / 4 skipped / 2 warnings in 34.6s** — uninstrumented; the same run
  under `--cov` takes roughly three times as long. The 4 skips are the env-gated
  live-IO tests (MySQL, OPC-UA, MQTT broker, rosbag2).
- `pytest tests/test_architecture_guard.py` → 11 passed · `pytest -m agentscope`
  → 13 passed, 1044 deselected · `ruff check fde_scope tests` → all checks passed
  · `ruff format --check fde_scope tests` → 173 files already formatted
  · `mypy fde_scope` → success, 112 source files.

Red — one item, and it is blocking, so nothing gets tagged or published yet:

- **The coverage gate fails: 85.11% against `fail_under = 90`.** 8751 statements,
  1303 uncovered under CI's exact `--cov=fde_scope --cov=pawapp/backend`. This is
  not the suite breaking — it is the denominator growing:

  | scope | statements | coverage |
  |---|---|---|
  | `fde_scope/` excluding the three items below | 7565 | **91.22%** |
  | `fde_scope/course/` | 439 | **0.00%** |
  | `fde_scope/resources/` | 397 | 81.11% |
  | `fde_scope/web/resources.py` | 78 | 96.15% |
  | `pawapp/backend/main.py` | 272 | 55.15% |

  Re-measure with `pytest --cov=fde_scope --cov=pawapp/backend` then
  `coverage report --no-skip-covered`: `[tool.coverage.report] skip_covered` hides
  39 fully-covered files, and summing the visible rows alone under-counts the
  denominator by 919 statements.

  `fde_scope/cli.py` is the largest single uncovered block in the package: 1006
  statements, 338 uncovered (66.4%). Even deleting the three new modules from the
  denominator leaves 7837 statements / 786 uncovered = **89.97%** — 0.03 points
  short — so `pawapp/backend` and `cli.py` need the same follow-up as `course/`,
  and the gate cannot be closed by dropping modules alone.
- **`fde_scope/course/` ships unreachable.** Nothing outside the package imports
  it (no CLI command, no web route — `fde_scope/web/course.py` renders the
  reading room from the `course-level-1/` Markdown and does not import it), no
  test names it, and `packages = ["fde_scope"]` in `pyproject.toml` already puts
  `course/{__init__,catalog,checks,verifier}.py` inside the wheel. 439 statements
  of public surface (`run_lab`, `run_all`, `doctor`, `LABS`) with no caller is a
  packaging decision the maintainer should make deliberately, not one that
  happens because a directory exists.

Mid-round, `fde_scope/course/verifier.py:559` carried an f-string syntax error
that made the module unimportable, `mypy` red, the bare-write guard test red,
and — worst of the four — would have shipped inside the wheel. It is resolved.
It is recorded here because it is the concrete reason the gate above is written
as commands rather than as a badge.

### 🔒 Security

- **Authentication is now on by default wherever the console can be reached from
  off-loopback.** Previously a single environment variable was the whole remote
  story: `FDE_SCOPE_ALLOW_REMOTE=1` let the server bind a non-loopback interface
  *with no token*, which is an unauthenticated console — holding customer corpus
  and engagement state — on the network. Two independent gates replace it:
  the CLI refuses to start on a routable bind without a token
  (`FDE_SCOPE_API_TOKEN`, exit 2 with a pointer), and the middleware rejects
  per-request traffic that *arrives* on a non-loopback socket (`403`), which also
  covers direct `uvicorn`/`gunicorn` launches that never go through the CLI.
  Judgement uses the accepted socket's local address, so one `0.0.0.0` listener
  serves local traffic (`127.0.0.1` → `200`) and LAN traffic
  (`192.168.x.x` → `403`) differently. `--proxy-headers` rewrites the *client*
  address only, so the check is not forgeable by a spoofed `X-Forwarded-For`;
  a same-host reverse proxy connects over loopback and must authenticate itself.
- **Path traversal in store identifiers closed.** `fsutil.safe_child()` is now the
  single gate for caller-supplied ids used as filesystem path segments (skill ids,
  ontology ids, corpus/upload paths, qwenpaw export targets). It rejects
  separators, NUL, `.` and `..`, and re-checks containment after resolution.
  Violations surface as `400` (via `UnsafeIdentifier(ValueError)`), not `500`.
- **The atomic-write invariant is now enforced, not just documented.** An AST
  guard fails the suite if any module writes user state with `Path.write_text()`
  / `Path.write_bytes()` / exclusive `open(...)` instead of
  `fsutil.atomic_write_text` / `atomic_write_bytes`. A module that cannot be
  parsed is recorded as an offender — invisible ≠ passing.
- **Gate engine robustness at the input boundary.** Malformed `assets` supplied
  over `POST /api/engagements/{id}/context` (a string where a mapping is
  expected, a list, etc.) previously raised `AttributeError` inside
  `Engagement.advance()` and surfaced as a `500`. Gates now fail closed with a
  readable blocker, and the web boundary validates the `assets` container type.
- **Storage connection lifecycle.** SQLite connections are pooled per data root
  and released deterministically (`close()` is idempotent and self-evicting),
  removing a leaked-handle path; `storage-migrate` is now safely repeatable and
  reports `{"migrated", "skipped", "db_path"}`.

### Added

- `SECURITY.md` — supported-version policy, private reporting channel, an explicit
  split between *what the code enforces* and *what is deliberately out of scope*
  (no CSRF, no TLS, no rate limiting, one shared token, audit log is evidence not
  a signature, license tiers are a commercial boundary not a security control).
- `CONTRIBUTING.md` — setup that matches what CI installs, the four regression
  anchors, the tested rules restated per invariant, style and test conventions,
  and the rule that **fixtures must be synthetic**.
- `CHANGELOG.md` (this file).
- **Stakeholder read-only share links — the customer finally has a seat.**
  Phases 8 (stakeholder validation) and 18 (customer sign-off) need the
  customer, but the console was a single-user local tool. A share link is a
  **second credential** next to the admin API token: `POST
  /api/engagements/{eid}/share` mints a `secrets.token_urlsafe` token shown in
  plaintext exactly once — the engagement stores only its sha256 and an 8-char
  prefix (`assets["share_access"]`, atomic write); regenerating rotates (the
  old link dies instantly), `DELETE` revokes, `GET` reports status without the
  token. `GET /share/{eid}?t=…` renders a read-only page — progress, SLA
  milestones, live gate status, the acknowledgement form — validated by a new
  branch in `ApiTokenAuthMiddleware` (a failed check answers **404**, never
  401/403, so nobody can probe whether an engagement exists; the branch also
  covers direct `uvicorn` starts). `POST /share/{eid}/ack` appends a
  `share.ack` audit line (actor `stakeholder`, optional label) — evidence, not
  authorization: it never advances the state machine, and the
  `handoff_signoff` gate still runs on the authed accept flow. The console's
  engagement overview grows a 只读分享 card (create/reveal-once/revoke). The
  mutating-route auth guard now pins the exception: the ack path must fail
  closed with 404 on a missing share credential for every method.
- **Lab grading on the web — the course page can now clear gates, not just read
  about them.** `fde_scope/course/` (registry + verifier + doctor) was already
  the machine-scored rubric behind the CLI's `fde-scope course check`; this
  wires the same `run_lab` to `GET /api/course/labs` (the D1–D8 registry),
  `GET /api/course/doctor` (the G0 environment probe) and
  `POST /api/course/labs/{day}/grade` (run one day's checks against the real
  CLI in a throwaway workspace, via `run_in_threadpool`; unknown day → 404;
  `manual` items reported but excluded from the denominator). The `/course`
  and `/en/course` readers grow a 实验判分 panel: server-rendered day chips
  (day, gate, deliverable, check count), a G0 button, and per-check results
  with hints on failures. Grading uses a private `FDE_SCOPE_HOME`, so a
  student's real engagements are never touched; the grading API is token-gated
  like every other mutating route (the page itself stays public).
- **Engagement retrospective — SLA clock + replay report, read-only.**
  `GET /api/engagements/{eid}/retrospective` and
  `fde-scope engage retrospective <id> [--json] [--out report.md]` aggregate
  two records that already exist — the append-only audit trail
  (`engagement.create/advance/rollback/gate_evaluate`) and the engagement
  context — into one `RetrospectiveReport` (`fde_scope/engagement/
  retrospective.py`): a phase timeline (visits, per-phase dwell including the
  still-open visit), SLA milestones (≤14d first integration / ≤90d production
  / ≤120d disengage; per-engagement override via
  `assets["success_criteria_sla"]`, source labelled per milestone), and gate
  stats (evaluation counts + first-pass from the audit stream; projects
  without a trail fall back to context-only latest state, labelled as such —
  history is never invented). Honesty flags: `timeline_consistent` marks a
  replay that does not end at the engagement's current phase (partial trail),
  and `start_source`/`data_sources` name where every number came from. Zero
  new persistence. The console grows a 复盘 tab (lazy fetch, like
  evidence/audit). CLI mutations (`engage init/advance/rollback`,
  `gate check`) now append the same audit events the web layer writes
  (`actor: "cli"`), so CLI-driven engagements get a replayable timeline; a
  "complete" advance attempt is logged with `reason: "complete"` and the
  retrospective does not count it as blocked.

### Changed

- Corrected two stale route-count claims in `docs/api-reference.md` and
  `docs/commercialization-gap-analysis.md` to the measured counts, and marked the
  gap-analysis numbers as a dated snapshot with the re-measure command alongside.
- Documentation updated for the new authentication default across the user guide,
  onboarding, features (zh + en) and the course READMEs — including a sentence
  that claimed the tool has "no authentication by design", which was no longer
  true.
- **`docs/api-reference.md` no longer overstates itself.** Its opening claimed the
  file had been reconciled "逐条" against the real routes, but it carried no
  exhaustive table — only the endpoints the prose chose to explain. It now carries
  a **69-row route table generated from `app.openapi()`** (verb, path, read/write,
  the handler docstring's first paragraph), marks the **28** rows whose handler has
  no docstring and was therefore described by hand (each ends in `†`), and states
  where the advertised **72 declared vs 69 served** difference comes from: the 3
  install-time asset fallbacks are deliberately outside `app.openapi()`.
- Corrected a claim that was simply wrong: the reference said OpenAPI/Swagger
  export was "暂未支持", but `GET /openapi.json`, `/docs` and `/redoc` all answer
  200 (and 401 once a token is configured, since none is in `PUBLIC_PATHS`).
  The doc now names them and says `/openapi.json` wins on any conflict.
- `POST /api/skills/{sid}/export` documented to what the code does: `fmt` is
  exactly `agentscope` or `qwenpaw`, it returns one `<slug>/SKILL.md`, and the
  web layer never passes an `ontology`, so exported frontmatter has no TBox
  context. The `SkillPatch` row listed 3 of its 6 fields; `GET /api/skills/facets`
  was missing from the Skills table entirely.
- `docs/api-reference.md` also gained a 免认证白名单 section that measures
  `auth.PUBLIC_PATHS` — **76 exact paths**, matched with
  `request.url.path in PUBLIC_PATHS` (exact, not prefix: `/docs/` itself and
  `/catalog/` stay gated) — and a 「文档自身的已知缺口」 section recording how the doc
  is still incomplete, including that the route table carries **no test guard** and
  the command that regenerates it.
- **Claims removed from this file.** An earlier draft of these bullets described
  work that is not in the tree: `NOTICE` runtime-licence statements, a
  `pyproject.toml` `license = { file = "LICENSE" }` + `license_dependencies`
  change, an `SPDX-License-Identifier` line in `LICENSE`, added `License` /
  `Source Code` classifiers, a CI step split, README links to `SECURITY.md` /
  `CONTRIBUTING.md` / this file, two README-count guard tests, and a reading of the
  installed AgentScope as 2.0.4. Re-measured 2026-10-06: `LICENSE`,
  `pyproject.toml` and `.github/` are **unmodified** in `git status`;
  `pyproject.toml` has no `license_dependencies` and no `Source Code` classifier;
  `ci.yml` has no `serve` job and its `agentscope` steps are already separate; the
  installed AgentScope is **2.0.8**; and the atomic-write guard is
  `test_no_bare_writes_outside_the_atomic_primitive` — already covered under
  Security above — with no README command-count or doc-count guard beside it.
- Still open, and deliberately not closed under someone else's editor session:
  `README.md` links `LICENSE` (badge) and nothing else from this release set — no
  `SECURITY.md`, `CONTRIBUTING.md` or `CHANGELOG.md` link; `NOTICE`'s new
  "Vendored third-party content" section is the `docs/github-resources/` mirror
  work, not a licence-statement pass. No `git push`, no tag, no `twine upload`, no
  GitHub settings change.

### Packaging — built locally 2026-10-07, not published

`uv build` (run inside `.venv`, which has no `build` module) produces both
artifacts from the current tree with no errors and no warnings:

| artifact | size | contents |
|---|---|---|
| `dist/fde_scope-0.1.0-py3-none-any.whl` | 945 KB | 177 entries, **112** `.py` modules — the same count `mypy fde_scope` reports |
| `dist/fde_scope-0.1.0.tar.gz` | 941 KB | top level: `.gitignore`, `LICENSE`, `NOTICE`, `README.md`, `pyproject.toml`, `PKG-INFO` |

Three questions this closes by measurement rather than by editing:

- **Licence files ship without any `pyproject.toml` change.** The wheel carries
  `fde_scope-0.1.0.dist-info/licenses/LICENSE` and `…/NOTICE`, and `METADATA`
  declares `Metadata-Version: 2.5`, `License: MIT`,
  `License-File: LICENSE` + `License-File: NOTICE`. So the licence-metadata edits
  retracted above were never needed — hatchling collects the licence files itself.
  `pyproject.toml` is modified again as of this writing, but only in two comments
  and not in any metadata: the `force-include` note below, and
  `[tool.coverage.report]`, whose stale "Q1 gate: 92% today" line was replaced with
  the measured 85.11% / 91.22% split and a pointer to the gate section above.
- **The bundled course data is complete.** `force-include` puts all
  **42** `*.md` under `course-level-1/` into `fde_scope/_data/course-level-1/` —
  compared NFC-normalised against the checkout, **zero** missing. The comment said
  "the same 25 chapters": 25 is the top-level lesson count, and the directory also
  holds 17 lab/en files, so the comment now states both numbers.
  **Superseded 2026-10-08 by the open-source benchmark round**, which landed a
  26th top-level lesson (`24-开源对标与来源清单.md`): re-measured with `uv build
  --wheel` + Python `zipfile` (NFC-normalised, because `unzip | grep -c` mis-counts
  UTF-8 names) the directory holds **47** `*.md` — **26 top-level + 20 labs + 1 en** —
  and the wheel carries all 47, missing none, extra none. `pyproject.toml:100-102`
  now states the 47/26/20/1 split with the re-measure instruction, and the two
  `docs/features*.md` sentences that still said "25" say **26**.
- **`fde_scope/course/` really is inside the wheel** — `__init__.py`,
  `catalog.py`, `checks.py`, `verifier.py`, ~90 KB — which is why the release gate
  treats shipping it as a decision rather than a side effect.

`METADATA` also confirms `Requires-Python: >=3.11`, the five core requirements
(`jinja2`, `pydantic`, `pyyaml`, `rich`, `typer`), `Development Status :: 3 - Alpha`,
and the `fde-scope = fde_scope.cli:app` console script.

The wheel was then installed into a clean venv (`uv venv`, no project dependencies,
no extras) and exercised: **14 distributions total** — `fde-scope 0.1.0` plus 13
transitive packages, which is the "core installs lean and runs offline" claim
measured rather than asserted. `fde-scope --version` prints `fde-scope 0.1.0`, the
root help renders **17** top-level commands, and subcommand trees work.

One caveat about what these artifacts *are*: `uv build` packages the working tree,
so `dist/*` contains the concurrent editor's uncommitted changes — verified by
`fde-scope engage --help` listing the new `stakeholder` / `criterion` / `slo`
commands. That makes them a **build check, not a release candidate**: nothing here
should be tagged or uploaded, and nothing has been.

## [0.1.0] — not yet released

First public release. One Python package, one binary (`fde-scope`), core installs
with **zero** optional dependencies and runs offline.

### What it is

An FDE (Forward-Deployed Engineer) toolkit that turns the delivery work of an
agent project into an enforced engineering process rather than a checklist: raw
customer data in, a governed engagement in the middle, a deployed agent and a
skill record at the end.

### Core

- **Engagement engine** — 4 zones / **18 phases** / **10 default gates**. Gates are
  re-evaluated live on *every* `advance()`; a stale `passed` record never grants
  passage, and forced advances still evaluate and record. Rollback is part of the
  state machine.
- **CLI** — Typer + Rich; `--version`, `--json` on the machine-readable commands,
  shared agent-resolution and gate accessors for scripting.
- **Web console** — single-page FastAPI app, **72 declared route pairs**
  (69 served; the 3 extras are install-time catalog/GTM/gh-resources asset
  fallbacks),
  token auth on every mutating route.
- **Connectors** — `csv`, `documents`, `mysql`, `opcua`, `mqtt_sparkplug`,
  `ros2_bag`, `mes`, `historian`, `salesforce`, `zammad`. Real IO drivers where the
  dependency is declared (`asyncua`, `paho-mqtt`, `rosbags`, HTTP REST), each with
  env-var configuration and a JSONL replay fallback so a demo never depends on a
  live plant.
- **Corpus pipeline** — ingestion, LLM-assisted synthesis and quality scoring,
  category-stratified train/eval/test splits.
- **Ontology** — cross-cutting semantic layer: TBox + ABox, SKOS concept scheme,
  SHACL-lite validation with `ONTO-*` error codes, JSON-LD 1.1 export, no new
  runtime dependency.
- **Skills** — skill record store with a four-category taxonomy and lifecycle,
  dual export (AgentScope / QwenPaw), plus a hand-authored
  [skills catalog](docs/skills-catalog/README.md) organized by zone, cross-cutting
  concerns, MCP and tools, gated by `make check-catalog`.
- **Deploy layer** — real agent assembly on AgentScope 2.0 (three-pillar toolkit /
  memory / hooks), model wiring, `SubAgentTemplate` blueprints. Permission model is
  rule-grant-only: a deployed tool is never flagged read-only (upstream ≥2.0.5
  auto-allows read-only calls before allow rules), and the unmatched-tool fallback
  is mode-driven — `DEFAULT` → ASK for human-in-the-loop, `DONT_ASK` → DENY.
- **Eval & flywheel** — regression scoring plus a training-backend interface
  (`TrainingBackend` Protocol) with an HTTP webhook backend and an explicit `noop`
  fallback, so nothing silently pretends a training run happened.
- **Offline license module** — HMAC-SHA256 signed keys, `community` / `pro` /
  `enterprise` feature tiers (`fde-scope license`, `license-issue`). A commercial
  tier boundary, not a security control.
- **Storage abstraction** — `FDE_SCOPE_STORAGE=file|sqlite` (stdlib + WAL, no ORM),
  with `fde-scope storage-migrate` for the one-time move.
- **Persistence discipline** — a single data root resolved by `fde_scope/paths.py`
  (`FDE_SCOPE_HOME` > app-directory convention > cwd), and every user record written
  atomically (crash leaves either the previous or the new complete version).
- **LLM integration** — optional outbound calls configured through environment
  variables only; keys are never persisted into manifests, reports, engagement JSON
  or logs; deterministic fallback on failure.
- **QwenPaw integration** — export + validation, and a PawApp desktop host
  (`pawapp/`) verified on a real machine.
- **Delivery artifacts** — console product page and GTM landing page
  (`GTM/index.html`), bilingual documentation, a customer onboarding guide and a
  72-hour on-site playbook.

### Packaging

- `requires-python >= 3.11`; CI runs 3.11 and 3.12.
- Extras: `agentscope`, `serve`, `mysql`, `opcua`, `mqtt`, `ros2`, `web`, `dev`,
  `full` (aggregate).
- `agentscope = "agentscope[ollama,service]>=2.0.4.post1,<3"` — a **measured**
  window, per-version results recorded in `pyproject.toml` and asserted against
  `docs/agentscope_api_mapping.md` by the guard tests.
- `uv.lock` committed; CI installs from the lock and asserts the resolved versions.

### Deliberately not in 0.1.0

Multi-tenancy, per-user identities, RBAC/SSO, field-level encryption, retention
policy, TLS termination and digital signatures are out of scope for an Alpha
single-operator tool; see `SECURITY.md` for the reasoning and the deployment-side
mitigations that stand in their place.
