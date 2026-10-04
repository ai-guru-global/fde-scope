#!/bin/sh
# Meoo image deploy — container entrypoint. MUST listen on 0.0.0.0:$PORT
# (the platform sets PORT, defaulting to 9000).
set -e
cd /code

PY=/code/.venv/bin/python
[ -x "$PY" ] || PY=python3

# Meoo container instances are ephemeral, so the data root is scratch by design:
# every engagement/skill/ontology record written at runtime is discarded with the
# instance, and reports_dir(create=True) at import time stays off the source tree.
export FDE_SCOPE_HOME="${FDE_SCOPE_HOME:-/tmp/fde-scope}"

# FDE_SCOPE_API_TOKEN is deliberately left unset. With it set, every /api/* call
# returns 401 (fde_scope/web/auth.py) and the console's main pane renders blank —
# verified. Unset means auth is off and the whole console works.
exec "$PY" -m uvicorn fde_scope.web.app:app --host 0.0.0.0 --port "${PORT:-9000}"
