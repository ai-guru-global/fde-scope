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
   The AST guard (`test_no_bare_writes_outside_the_atomic_primitive`) scans
   **both** `fde_scope/` and `pawapp/backend/` — the PawApp is a second HTTP
   surface over the same data root (uploads, corpus reports, exported skills,
   runbooks). It scanned only `fde_scope/` until 2026-11-10, which is how four
   bare writes in `pawapp/backend/main.py` shipped.
5. **Rule grants are the only permission channel.** `build_toolkit` never
   flags a deployed tool `is_read_only` (upstream ≥2.0.5 auto-allows
   read-only calls before allow rules — see B5). Unmatched-tool fallback is
   mode-driven: DEFAULT→ASK (HITL), DONT_ASK→DENY.
6. **The AgentScope window is measured, not aspirational.**
   `pyproject.toml`'s `agentscope` extra and `docs/agentscope_api_mapping.md`
   must quote the same specifier verbatim
   (`tests/test_architecture_guard.py` enforces this). Re-measure before
   widening.
7. **Web mutating 路由必须过认证依赖。** 新增 `fde_scope/web/` 路由时确认未被
   auth 白名单（`fde_scope/web/auth.py` 的 `PUBLIC_PATHS`）误放；token 只从
   `FDE_SCOPE_API_TOKEN` env 读，绝不进文件/日志/响应。**认证关闭只对回环生效**：
   未设 token 时从非 loopback 地址到达的请求必须 403（`ApiTokenAuthMiddleware`
   逐请求判 `scope["server"]`，即连接被 accept 时落在哪个地址——不是 `--host`
   绑定值，客户端不可伪造，也覆盖绕过 CLI 直接 `uvicorn`/`gunicorn` 的启动）；
   `fde-scope web` 另外要求非回环绑定同时有 `FDE_SCOPE_ALLOW_REMOTE=1` 和 token。
   同机反向代理落在回环上，不会被这层拦——代理必须自己鉴权。
8. **留出集只放真实数据。** `corpus/pipeline.py` 先切真实样本（三个 split 按比例），
   合成样本只叠在 `train` 上；`eval` / `test` 恒为 `Provenance.REAL`（或 GOLDEN）。
   合成发生在 dedup 之后，因此必须有 `_dedup_against` 这次二次去重。
   报告里任何"质量"数字的分母是 `CorpusReport.heldout_real`；`heldout_trusted`
   为 False 时不得声称准确率。**不允许**把真实/合成混进同一个列表再 shuffle
   （这正是 2026-11 之前 29–38% 泄漏的来源），也不允许在报告里只印 size 不印
   provenance。守卫：`tests/test_corpus_provenance.py`。
9. **async 里不要 await 抛 `StopIteration` 的东西。** `Engagement.advance()` 在
   终态抛内置 `StopIteration`；经 `run_in_threadpool`/`to_thread` 会被 asyncio
   转成 `RuntimeError`，`except StopIteration` 永远不触发（曾经导致最后一次推进
   返回 500）。在协程里用 `advance_or_complete()`（抛 `PhaseComplete`）；
   同步调用点可继续用 `advance()`。守卫：`tests/test_engagement.py`。

## Dangerous operations (ask first / require a test)

- Directly assigning engagement state-machine fields (`phase`, `zone`,
  journal entries, gate results) instead of going through
  `Engagement.advance` / `rollback` — this bypasses gate enforcement.
- Editing `fde_scope/engagement/phases.py` (18 phases) or the default gate
  registry (10 gates) — contract tests fail on purpose; update the contract
  deliberately, with the change described in `docs/`.
- Changing the permission pipeline (`deploy/permission_builder.py`,
  `deploy/toolkit.py`) without running the real-library tests (below).
- Changing the corpus split (`corpus/pipeline.py::_split` / `_dedup_against`) or
  `CorpusSplit` provenance properties — run `tests/test_corpus_provenance.py`
  first; it fails on purpose if generated rows reach eval/test or if the
  held-out denominator stops being derived from the items.
- Loosening the `agentscope` window without per-version runs in an isolated
  env.

## Regression anchors

- Full suite: `make test` (or `.venv/bin/python -m pytest -q`) —
  as of 2026-11-10: **1303 passed, 4 skipped, exit 0** (~64s).
- Coverage gate: `pytest --cov=fde_scope --cov=pawapp/backend`
  → must stay **≥ 90%** (`fail_under` in `pyproject.toml`).
- Real-library runtime tests: `pytest -m agentscope` (needs the
  `agentscope` extra; skipped otherwise).
- Contract guards: `pytest tests/test_architecture_guard.py` (14 guards).
- Lint/format/type — **the CI commands, repo-wide**, not just `fde_scope tests`:
  `ruff check . && ruff format --check . && mypy fde_scope`.
  (This anchor used to say `ruff check fde_scope tests`, which was green while
  CI was red on `GTM/dist_stage.py`. The scope difference is what hid it.)
