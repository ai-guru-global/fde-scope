# deploy --serve e2e smoke

Reproducible verification harness for `fde-scope deploy --serve` — the opt-in
runtime path (`fde_scope.cli._serve_app` → `fde_scope.deploy.build_app` →
`agentscope.app.create_app` + uvicorn) that README's checklist previously marked
as untested end-to-end. It substitutes the two external dependencies with local
stand-ins so the whole run stays on loopback:

- **Redis** — real server via `deploy/docker-compose.e2e.yml`
  (`docker compose -f deploy/docker-compose.e2e.yml up -d redis`), or a local
  `redis-server` binary as fallback. Must listen on `127.0.0.1:6379`:
  `build_app()` hardcodes `RedisStorage(host="localhost", port=6379)` and the
  CLI exposes no override.
- **Model** — `fake_model.py`, a zero-dependency (stdlib `http.server`)
  OpenAI-compatible endpoint returning a fixed completion. It serves
  `POST /v1/chat/completions` (streaming and non-streaming), `GET /healthz`,
  and `GET /_stats` (call counter used for the "model was actually hit"
  assertion).

## Prerequisites

- `.venv` with the `agentscope` extra, the `web` extra (uvicorn), **and the
  `redis` Python package** — `agentscope[service]` does not pull it in, and
  `RedisStorage.__aenter__` raises `ImportError` without it:
  `uv pip install 'fde-scope[agentscope,serve,web]'`（`serve` extra 即 redis 客户端）
- Docker daemon (for compose) **or** a `redis-server` on PATH
- Port 8000 free (`_serve_app` runs uvicorn on `127.0.0.1:8000`, fixed)

## Three steps (manual)

```bash
# 1. Redis + fake model
docker compose -f deploy/docker-compose.e2e.yml up -d redis      # or: redis-server --port 6379 --daemonize yes
.venv/bin/python deploy/e2e/fake_model.py --port 19100 &

# 2. Serve the real app, LLM env pointed at the fake model
export FDE_SCOPE_LLM_BASE_URL=http://127.0.0.1:19100/v1
export FDE_SCOPE_LLM_API_KEY=e2e-fake-key-not-a-secret
export FDE_SCOPE_LLM_MODEL=fde-fake-model
.venv/bin/python -m fde_scope.cli deploy -t e2e-smoke --name E2ESmoke --serve

# 3. Verify (from another shell; every API call needs the X-User-ID header)
curl -H 'X-User-ID: e2e' http://127.0.0.1:8000/health            # expect {"status":"ok",...}
curl -H 'X-User-ID: e2e' -H 'Content-Type: application/json' \
  -d '{"data":{"type":"openai_credential","api_key":"e2e-fake-key-not-a-secret","base_url":"http://127.0.0.1:19100/v1"}}' \
  http://127.0.0.1:8000/credential/                              # -> {"credential_id": "..."}
curl -H 'X-User-ID: e2e' -H 'Content-Type: application/json' \
  -d '{"name":"smoke-agent","system_prompt":"Reply briefly."}' \
  http://127.0.0.1:8000/agent/                                   # -> {"agent_id": "..."}
curl -H 'X-User-ID: e2e' -H 'Content-Type: application/json' \
  -d '{"agent_id":"<agent_id>","name":"smoke","chat_model_config":{"type":"openai_credential","credential_id":"<credential_id>","model":"fde-fake-model","parameters":{}}}' \
  http://127.0.0.1:8000/sessions/                                # -> {"session_id": "..."}
curl -H 'X-User-ID: e2e' -H 'Content-Type: application/json' \
  -d '{"agent_id":"<agent_id>","session_id":"<session_id>","input":{"name":"user","role":"user","content":[{"type":"text","text":"ping"}]}}' \
  http://127.0.0.1:8000/chat/                                    # -> {"status":"started",...}
curl http://127.0.0.1:19100/_stats                               # expect {"chat_completions": >=1}
```

## Automated

```bash
deploy/e2e/smoke_test.sh
```

The script does all of the above (docker compose when the daemon is up, local
`redis-server` otherwise), runs in a `mktemp -d` workdir with `FDE_SCOPE_HOME`
pointed there so no repo/user data is touched, asserts `/health` reports
`"ok"`, drives one chat turn, and fails unless the fake model's
`/_stats.chat_completions` reaches ≥ 1. **CI-optional**: only enable on runners
with Docker and the agentscope extra installed.

## Stopping

`--serve` is a foreground uvicorn process: Ctrl-C (or `kill`) stops it. The
programmatic equivalent for the assembly path is:

```python
from fde_scope.config import TenantConfig
from fde_scope.deploy import TenantDeployer

deployer = TenantDeployer()
deployed = deployer.deploy(TenantConfig(id="e2e-smoke", name="E2ESmoke"))
print(TenantDeployer.stop(deployed))  # {"closed": [...]} + manifest["started"]=False
```

`TenantDeployer.stop` closes whatever has a close handle (workspace, permission
engine) and flips `manifest["started"]` to `False`; the served app's remaining
lifecycle is owned by the uvicorn process itself.

## Verification status

已验证 @2026-09-28 — 本机实际跑通：agentscope 2.0.8（`agentscope[ollama,service]`），
uvicorn 0.53.0，redis（Python 包）8.1.0，Docker daemon 不可用故走
`redis-server`（Homebrew）fallback。`smoke_test.sh` 输出 `PASS`：
`/health` 返回 `{"status":"ok"}`，credential/agent/session 均创建成功，
一次 `/chat/` 触发后 fake model `/_stats.chat_completions >= 1`。

注意：`redis` Python 包不在 `agentscope[service]` 传递依赖里，是本基建发现的
真实前置缺口，已在上文 Prerequisites 标注。
