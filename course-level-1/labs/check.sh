#!/usr/bin/env bash
# Thin forwarder for `python -m fde_scope course check`.
#
# Why it exists: `06` prints the check as a command, and a learner who has to
# retype `python -m fde_scope course check D3` every morning will retype it
# wrong. This file only picks an interpreter and forwards — the scoring logic
# lives in fde_scope/course/verifier.py, never here.
set -euo pipefail

# Prefer python3 (what 11-工具与环境准备.md tells students to install); fall
# back to python. FDE_SCOPE_PYTHON overrides both, e.g. a venv path.
PY="${FDE_SCOPE_PYTHON:-}"
if [ -z "$PY" ]; then
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then PY="$candidate"; break; fi
  done
fi
if [ -z "$PY" ]; then
  echo "找不到 python3/python。先装 Python 3.11+（见 course-level-1/11-工具与环境准备.md）。" >&2
  exit 127
fi
if ! "$PY" -c 'import fde_scope' >/dev/null 2>&1; then
  echo "这个解释器里没有 fde_scope（$PY）。装好后重试，或用 FDE_SCOPE_PYTHON 指向正确的解释器。" >&2
  echo "先跑 '$PY -m fde_scope course doctor' 看它到底缺什么。" >&2
  exit 127
fi

args=("$@")
if [ ${#args[@]} -eq 0 ]; then args=(all); fi
exec "$PY" -m fde_scope course check "${args[@]}"
