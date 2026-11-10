"""Lab run history (M1-05).

The acceptance criterion is literal: "run D3 twice, the history has two
entries". A lab run used to be printed and forgotten, so a learner could not
tell whether a retry improved anything — on a course whose promise is "each day
ends in a machine-checked gate", that is the one record they most want.

These tests drive the real :class:`LabResult` shape (via a tiny stand-in, so no
course catalog or subprocess is needed) through the real storage layer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from fde_scope.course import lab_history
from fde_scope.paths import data_root


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("FDE_SCOPE_HOME", str(tmp_path))
    return tmp_path


@dataclass
class _Check:
    id: str
    status: str

    @property
    def scored(self) -> bool:
        return self.status in ("pass", "fail")


@dataclass
class _Result:
    """The subset of ``LabResult`` the history reads."""

    day: str
    passed: int
    failed: int
    manual: int = 0
    results: list[_Check] = field(default_factory=list)


def _run(day: str, passed: int, failed: int, failed_ids: list[str] | None = None, manual: int = 0):
    checks = [_Check(f"ok{i}", "pass") for i in range(passed)]
    checks += [_Check(i, "fail") for i in (failed_ids or [])]
    return _Result(day=day, passed=passed, failed=failed, manual=manual, results=checks)


def test_two_runs_leave_two_entries(home) -> None:
    """The documented exit criterion, verbatim."""
    lab_history.record(_run("D3", 12, 1, ["report"]))
    lab_history.record(_run("D3", 13, 0))

    runs = lab_history.history("D3")["D3"]
    assert len(runs) == 2
    assert [r.ok for r in runs] == [False, True], "history keeps chronological order"
    assert runs[0].failed_ids == ["report"]
    assert runs[1].failed_ids == []


def test_latest_returns_the_newest_run(home) -> None:
    lab_history.record(_run("D3", 10, 3))
    lab_history.record(_run("D3", 13, 0))

    latest = lab_history.latest("D3")
    assert latest is not None and latest.ok is True


def test_history_is_per_day(home) -> None:
    lab_history.record(_run("D1", 10, 0))
    lab_history.record(_run("D3", 12, 1))

    everything = lab_history.history()
    assert set(everything) == {"D1", "D3"}
    assert len(lab_history.history("D1")["D1"]) == 1
    assert lab_history.history("D7") == {}


def test_history_is_capped_per_day(home) -> None:
    """A learner retrying a broken environment keeps the recent attempts."""
    for i in range(lab_history.KEEP_PER_DAY + 8):
        lab_history.record(_run("D3", i, 0))

    runs = lab_history.history("D3")["D3"]
    assert len(runs) == lab_history.KEEP_PER_DAY
    # the most recent survive, not the first ones
    assert runs[-1].passed == lab_history.KEEP_PER_DAY + 7


def test_corrupt_history_reads_as_empty(home) -> None:
    path = data_root() / ".fde_scope" / "course_lab_history.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")

    assert lab_history.history() == {}
    lab_history.record(_run("D1", 10, 0))
    assert len(lab_history.history("D1")["D1"]) == 1


def test_malformed_entries_are_skipped_not_fatal(home) -> None:
    path = data_root() / ".fde_scope" / "course_lab_history.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "D1": [
                    {"day": "D1", "at": "t", "passed": 10, "failed": 0},
                    {"nope": 1},
                    "string",
                    {"day": "D1", "at": "t", "passed": "x", "failed": 0},
                ],
                "D2": "not a list",
            }
        ),
        encoding="utf-8",
    )

    data = lab_history.history()
    assert len(data["D1"]) == 1, "only the well-formed run survives"
    assert "D2" not in data


def test_clear_one_day_or_everything(home) -> None:
    lab_history.record(_run("D1", 10, 0))
    lab_history.record(_run("D3", 12, 1))

    lab_history.clear("D1")
    assert set(lab_history.history()) == {"D3"}

    lab_history.clear()
    assert lab_history.history() == {}


def test_history_write_is_atomic(home, monkeypatch) -> None:
    """Invariant 4: user state goes through the atomic primitive."""
    from fde_scope import fsutil

    calls: list[str] = []
    real = fsutil.atomic_write_text

    def spy(path, text, **kw):
        calls.append(str(path))
        return real(path, text, **kw)

    monkeypatch.setattr("fde_scope.course.lab_history.atomic_write_text", spy)
    lab_history.record(_run("D3", 12, 1))
    assert calls and calls[0].endswith("course_lab_history.json")


def test_manual_items_are_counted_but_not_failures(home) -> None:
    run = lab_history.record(_run("D3", 12, 0, manual=1))
    assert run.ok is True
    assert run.manual == 1
    assert run.score == 12


# -- the surfaces that read it ----------------------------------------------
def test_history_api_lists_each_run(home) -> None:
    from fastapi.testclient import TestClient

    from fde_scope.web.app import app

    lab_history.record(_run("D3", 12, 1, ["report"]))
    lab_history.record(_run("D3", 13, 0))

    body = TestClient(app).get("/api/course/lab-history?day=D3").json()
    runs = body["days"]["D3"]
    assert len(runs) == 2
    assert runs[0]["failed_ids"] == ["report"]
    assert runs[0]["score"] == 13


def test_history_api_is_not_public(home) -> None:
    from fde_scope.web.auth import PUBLIC_PATHS

    assert "/api/course/lab-history" not in PUBLIC_PATHS


def test_run_lab_records_even_when_setup_fails(monkeypatch) -> None:
    """A run that dies on a setup command is the one worth seeing twice."""
    from fde_scope.course import verifier

    recorded: list[str] = []
    real_record = lab_history.record

    def spy(result):
        recorded.append(result.day)
        return real_record(result)

    monkeypatch.setattr("fde_scope.course.lab_history.record", spy)

    result = verifier.LabResult(day="D9", title="t", gate="G9", deliverable="d")
    result.failed = 1
    verifier._record_and_return(result)
    assert recorded == ["D9"]


def test_a_history_write_failure_never_swallows_the_result(monkeypatch) -> None:
    """Grading is the product; the history is a convenience."""
    from fde_scope.course import verifier

    def boom(_result):
        raise OSError("disk full")

    monkeypatch.setattr("fde_scope.course.lab_history.record", boom)
    result = verifier.LabResult(day="D9", title="t", gate="G9", deliverable="d")
    result.passed = 7

    assert verifier._record_and_return(result) is result
