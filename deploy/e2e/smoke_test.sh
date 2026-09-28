#!/usr/bin/env bash
# e2e smoke for `fde-scope deploy --serve` — see deploy/e2e/README.md.
#
# Brings up Redis (docker compose, or a local redis-server fallback), starts the
# zero-dependency fake model, serves the real AgentScope app via the CLI, then
# drives one chat turn through the HTTP API and asserts the fake model received
# at least one /v1/chat/completions call.
#
# CI-optional: requires the agentscope extra and uvicorn installed, plus Docker
# (or a local redis-server) — wire it into CI only on runners that have both.
#
# Env overrides: PY (interpreter), FAKE_PORT (default 19100), TENANT, TIMEOUT.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="${PY:-$REPO/.venv/bin/python}"
FAKE_PORT="${FAKE_PORT:-19100}"
REDIS_PORT=6379  # build_app() hardcodes RedisStorage(port=6379); no CLI override
APP_URL="http://127.0.0.1:8000"  # _serve_app() uvicorn port is fixed at 8000
TENANT="${TENANT:-e2e-smoke}"
TIMEOUT="${TIMEOUT:-90}"
USER_HEADER="X-User-ID: e2e"

WORKDIR="$(mktemp -d)"
APP_PID=""
FAKE_PID=""
REDIS_MODE=""

log() { printf '[smoke] %s\n' "$*"; }
fail() { printf '[smoke] FAIL: %s\n' "$*" >&2; exit 1; }

cleanup() {
  [ -n "$APP_PID" ] && kill "$APP_PID" 2>/dev/null || true
  [ -n "$FAKE_PID" ] && kill "$FAKE_PID" 2>/dev/null || true
  case "$REDIS_MODE" in
    docker) docker compose -f "$REPO/deploy/docker-compose.e2e.yml" down -v >/dev/null 2>&1 || true ;;
    local)  redis-cli -p "$REDIS_PORT" shutdown nosave >/dev/null 2>&1 || true ;;
  esac
  rm -rf "$WORKDIR"
}
trap cleanup EXIT

# --- prerequisite checks ---------------------------------------------------
"$PY" -c "import agentscope" 2>/dev/null || fail "agentscope extra not installed (pip install 'fde-scope[agentscope]')"
"$PY" -c "import uvicorn" 2>/dev/null || fail "uvicorn not installed (pip install 'fde-scope[web]')"
command -v curl >/dev/null || fail "curl not found"

# --- 1. Redis ---------------------------------------------------------------
if docker info >/dev/null 2>&1; then
  log "starting redis via docker compose"
  docker compose -f "$REPO/deploy/docker-compose.e2e.yml" up -d --wait redis >/dev/null
  REDIS_MODE="docker"
elif command -v redis-server >/dev/null 2>&1; then
  log "docker daemon unavailable; starting local redis-server on :$REDIS_PORT"
  redis-server --port "$REDIS_PORT" --daemonize yes --save '' --appendonly no >/dev/null
  REDIS_MODE="local"
else
  fail "no redis available (need docker daemon or a redis-server binary)"
fi
for _ in $(seq "$TIMEOUT"); do
  if command -v redis-cli >/dev/null 2>&1; then
    redis-cli -p "$REDIS_PORT" ping 2>/dev/null | grep -q PONG && break
  else
    (exec 3<>"/dev/tcp/127.0.0.1/$REDIS_PORT") 2>/dev/null && { exec 3>&- 3<&-; break; }
  fi
  sleep 1
done

# --- 2. fake model ------------------------------------------------------------
"$PY" "$REPO/deploy/e2e/fake_model.py" --port "$FAKE_PORT" &
FAKE_PID=$!
for _ in $(seq "$TIMEOUT"); do
  curl -sf "http://127.0.0.1:$FAKE_PORT/healthz" >/dev/null 2>&1 && break
  sleep 1
done
curl -sf "http://127.0.0.1:$FAKE_PORT/healthz" >/dev/null || fail "fake model did not start"
log "fake model up on :$FAKE_PORT"

# --- 3. deploy --serve ----------------------------------------------------------
# Hermetic cwd: FDE_SCOPE_HOME + cwd both point at a tmp dir so no repo data is touched.
export FDE_SCOPE_HOME="$WORKDIR"
export FDE_SCOPE_LLM_BASE_URL="http://127.0.0.1:$FAKE_PORT/v1"
export FDE_SCOPE_LLM_API_KEY="e2e-fake-key-not-a-secret"
export FDE_SCOPE_LLM_MODEL="fde-fake-model"
export PYTHONPATH="$REPO${PYTHONPATH:+:$PYTHONPATH}"
(cd "$WORKDIR" && "$PY" -m fde_scope.cli deploy -t "$TENANT" --name E2ESmoke --serve) >"$WORKDIR/serve.log" 2>&1 &
APP_PID=$!
log "serving agentscope app (pid $APP_PID), waiting for /health"
ready=""
for _ in $(seq "$TIMEOUT"); do
  if curl -sf -H "$USER_HEADER" "$APP_URL/health" >"$WORKDIR/health.json" 2>/dev/null; then
    ready=1; break
  fi
  kill -0 "$APP_PID" 2>/dev/null || { cat "$WORKDIR/serve.log" >&2; fail "serve process died"; }
  sleep 1
done
[ -n "$ready" ] || { cat "$WORKDIR/serve.log" >&2; fail "app did not become healthy"; }
"$PY" -c "import json,sys; d=json.load(open('$WORKDIR/health.json')); assert d['status']=='ok', d" \
  || fail "health endpoint not ok"
log "health ok"

# --- 4. drive one chat turn -----------------------------------------------------
api() { # api METHOD PATH JSONBODY -> prints response body
  local method="$1" path="$2" body="${3:-}"
  if [ -n "$body" ]; then
    curl -sf -X "$method" -H "$USER_HEADER" -H 'Content-Type: application/json' -d "$body" "$APP_URL$path"
  else
    curl -sf -X "$method" -H "$USER_HEADER" "$APP_URL$path"
  fi
}
json_field() { "$PY" -c "import json,sys; print(json.load(sys.stdin)$1)"; }

CRED_ID="$(api POST /credential/ "{\"data\":{\"type\":\"openai_credential\",\"api_key\":\"$FDE_SCOPE_LLM_API_KEY\",\"base_url\":\"$FDE_SCOPE_LLM_BASE_URL\"}}" | json_field "['credential_id']")" \
  || fail "create credential"
AGENT_ID="$(api POST /agent/ '{"name":"smoke-agent","system_prompt":"You are a smoke-test agent. Reply briefly."}' | json_field "['agent_id']")" \
  || fail "create agent"
SESSION_ID="$(api POST /sessions/ "{\"agent_id\":\"$AGENT_ID\",\"name\":\"smoke\",\"chat_model_config\":{\"type\":\"openai_credential\",\"credential_id\":\"$CRED_ID\",\"model\":\"fde-fake-model\",\"parameters\":{}}}" | json_field "['session_id']")" \
  || fail "create session"
log "credential=$CRED_ID agent=$AGENT_ID session=$SESSION_ID"

api POST /chat/ "{\"agent_id\":\"$AGENT_ID\",\"session_id\":\"$SESSION_ID\",\"input\":{\"name\":\"user\",\"role\":\"user\",\"content\":[{\"type\":\"text\",\"text\":\"ping\"}]}}" >/dev/null \
  || fail "chat trigger"

# --- 5. assert the fake model was called ----------------------------------------
hits=0
for _ in $(seq "$TIMEOUT"); do
  hits="$(curl -sf "http://127.0.0.1:$FAKE_PORT/_stats" | json_field "['chat_completions']" 2>/dev/null || echo 0)"
  [ "$hits" -ge 1 ] && break
  sleep 1
done
[ "$hits" -ge 1 ] || fail "fake model received no /v1/chat/completions call within ${TIMEOUT}s"
log "fake model received $hits completion call(s) — OK"
log "PASS"
