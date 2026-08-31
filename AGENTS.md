# AGENTS.md — machine-readable invariants for AI collaborators

Scope: `fde-scope` repo (Python 3.12, uv, pydantic v2). Read this before
changing engagement, deploy or persistence code. Full context:
`docs/architecture.md`, `docs/agentscope_api_mapping.md`,
`docs/architecture-model/remediation-plan.md`.

## Invariants (never break silently)

1. **Gate re-evaluation is live.** `Engagement.advance()` re-evaluates the
   current phase's gates on *every* advance; a stale `passed` record never
   grants passage, and even forced advances evaluate and record. Do not add
   caching or short-circuits around `evaluate_phase_gates`.
2. **IDs are server-generated.** `SkillRecord.id` and `EngagementContext.id`
   are assigned by the owning service/store. External input must never be
   able to set them (no `SkillDraft.id`, no id-bearing mass assignment).
3. **Credentials live in env vars only.** API keys flow through the
   environment (`fde_scope/llm.py` `_ENV_KEY` / `_env()`); they must never be
   persisted into manifests, reports, engagement JSON or logs.
4. **Persisted records are written atomically.** Every on-disk user record
   goes through `fde_scope/fsutil.atomic_write_text` (temp file +
   `os.replace`). Never write user state with bare `Path.write_text`.
5. **Rule grants are the only permission channel.** `build_toolkit` never
   flags a deployed tool `is_read_only` (upstream ≥2.0.5 auto-allows
   read-only calls before allow rules — see B5). Unmatched-tool fallback is
   mode-driven: DEFAULT→ASK (HITL), DONT_ASK→DENY.
6. **The AgentScope window is measured, not aspirational.**
   `pyproject.toml`'s `agentscope` extra and `docs/agentscope_api_mapping.md`
   must quote the same specifier verbatim
   (`tests/test_architecture_guard.py` enforces this). Re-measure before
   widening.

## Dangerous operations (ask first / require a test)

- Directly assigning engagement state-machine fields (`phase`, `zone`,
  journal entries, gate results) instead of going through
  `Engagement.advance` / `rollback` — this bypasses gate enforcement.
- Editing `fde_scope/engagement/phases.py` (18 phases) or the default gate
  registry (10 gates) — contract tests fail on purpose; update the contract
  deliberately, with the change described in `docs/`.
- Changing the permission pipeline (`deploy/permission_builder.py`,
  `deploy/toolkit.py`) without running the real-library tests (below).
- Loosening the `agentscope` window without per-version runs in an isolated
  env.

## Regression anchors

- Full suite: `make test` (or `.venv/bin/python -m pytest -q`).
- Real-library runtime tests: `pytest -m agentscope` (needs the
  `agentscope` extra; skipped otherwise).
- Contract guards: `pytest tests/test_architecture_guard.py`.
- Lint/format: `ruff check fde_scope tests && ruff format --check fde_scope tests`.
