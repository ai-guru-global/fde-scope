"""Append-only audit log (commercialization gap B4).

Every mutating web operation appends one JSON line to
``<data root>/.fde_scope/audit.jsonl``::

    {"ts": "<ISO8601 UTC>", "actor": "local", "action": "...", "detail": {...}}

Single-line appends are atomic enough for the single-machine deployment
model; a failed write degrades to a logged warning and never interrupts the
business operation. ``detail`` must never carry credentials, env values or
tokens (AGENTS.md invariant 3).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from . import paths
from .logutil import get_logger

logger = get_logger("audit")


def audit_log_path() -> Path:
    """``<data root>/.fde_scope/audit.jsonl`` — resolved per call, like paths.py."""
    return paths.data_root() / paths.DATA_SUBDIR / "audit.jsonl"


def log_event(action: str, actor: str = "local", detail: dict | None = None) -> None:
    """Append one audit record. Best-effort: failures only log a warning."""
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "actor": actor,
        "action": action,
        "detail": detail or {},
    }
    try:
        path = audit_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        logger.warning("audit log write failed for action %r", action, exc_info=True)


def read_events(eid: str | None = None) -> Iterator[dict]:
    """Stream audit records, optionally filtered to one engagement.

    Line-by-line so a large audit.jsonl never lands in memory at once. A
    record belongs to an engagement when ``detail.engagement_id`` matches.
    Malformed lines are skipped (a corrupt line must not blank the trail).
    A missing file yields nothing.
    """
    path = audit_log_path()
    if not path.exists():
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if eid is not None and record.get("detail", {}).get("engagement_id") != eid:
                continue
            yield record


def sha256_file(path: Path) -> tuple[str, int]:
    """``(hex digest, byte size)`` for *path*, read in chunks."""
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def render_markdown(events: list[dict], eid: str | None = None) -> str:
    """Render a human-readable audit report (for compliance review export)."""
    title = f"审计报告 · {eid}" if eid else "审计报告 · 全部事件"
    lines = [
        f"# {title}",
        "",
        f"- 生成时间（UTC）: {datetime.now(UTC).isoformat()}",
        f"- 事件数: {len(events)}",
        "",
        "| 时间 (UTC) | 操作者 | 动作 | 详情 |",
        "|---|---|---|---|",
    ]
    for rec in events:
        detail = json.dumps(rec.get("detail", {}), ensure_ascii=False).replace("|", "\\|")
        lines.append(f"| {rec.get('ts', '')} | {rec.get('actor', '')} | {rec.get('action', '')} | {detail} |")
    return "\n".join(lines) + "\n"
