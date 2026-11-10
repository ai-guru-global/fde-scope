"""Lab run history — what each day's grading actually returned, over time.

Today a lab run is printed and forgotten: `course check D3` tells you the score
once, and re-running it tells you the score again with no way to see whether you
improved, or when you last passed. For a course whose whole promise is "each day
ends in a machine-checked gate", that is the one record the learner most wants.

This module appends a compact record per run (day, when, passed/failed/manual
counts, the ids that failed) to the data root, through the same atomic write as
every other user record. The full :class:`LabResult` is deliberately *not*
stored: check details can carry workspace paths from a throwaway run, and the
useful question is "did this get better", which the counts answer.

Capacity is bounded per day: a learner retrying a broken environment twenty
times should keep the twenty *latest* attempts, not an ever-growing log.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from ..fsutil import atomic_write_text
from ..paths import data_root

#: Runs kept per day. Enough to show a trend, small enough to stay readable.
KEEP_PER_DAY = 20


def _path():
    return data_root() / ".fde_scope" / "course_lab_history.json"


@dataclass
class LabRun:
    """One graded run, reduced to what a learner needs to compare two of them."""

    day: str
    at: str
    passed: int
    failed: int
    manual: int
    ok: bool
    failed_ids: list[str] = field(default_factory=list)

    @property
    def score(self) -> int:
        return self.passed + self.failed


def _load_all() -> dict[str, list[LabRun]]:
    try:
        raw = _path().read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, list[LabRun]] = {}
    for day, runs in data.items():
        if not isinstance(runs, list):
            continue
        kept: list[LabRun] = []
        for r in runs:
            if not isinstance(r, dict):
                continue
            try:
                kept.append(
                    LabRun(
                        day=str(r["day"]),
                        at=str(r["at"]),
                        passed=int(r["passed"]),
                        failed=int(r["failed"]),
                        manual=int(r.get("manual", 0)),
                        ok=bool(r.get("ok", False)),
                        failed_ids=[str(x) for x in r.get("failed_ids", [])],
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        if kept:
            out[str(day)] = kept
    return out


def _save_all(data: dict[str, list[LabRun]]) -> None:
    payload = {day: [asdict(r) for r in runs] for day, runs in sorted(data.items())}
    body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, body)


def record(result) -> LabRun:
    """Append one :class:`LabResult`, returning the stored record.

    Takes the verifier's result by duck type rather than importing it, so this
    module (and its tests) do not need a course catalog to exist.
    """
    failed_ids = [r.id for r in getattr(result, "results", []) if r.scored and r.status == "fail"]
    run = LabRun(
        day=result.day,
        at=datetime.now(UTC).isoformat(),
        passed=int(result.passed),
        failed=int(result.failed),
        manual=int(result.manual),
        ok=bool(result.failed == 0),
        failed_ids=failed_ids,
    )
    data = _load_all()
    runs = data.get(run.day, [])
    runs.append(run)
    data[run.day] = runs[-KEEP_PER_DAY:]
    _save_all(data)
    return run


def history(day: str | None = None) -> dict[str, list[LabRun]]:
    """Stored runs, newest last, for one day or all of them."""
    data = _load_all()
    if day is not None:
        return {day: data.get(day, [])} if day in data else {}
    return data


def latest(day: str) -> LabRun | None:
    runs = _load_all().get(day) or []
    return runs[-1] if runs else None


def clear(day: str | None = None) -> None:
    """Forget one day's history, or all of it."""
    if day is None:
        _path().unlink(missing_ok=True)
        return
    data = _load_all()
    if data.pop(day, None) is not None:
        _save_all(data)
