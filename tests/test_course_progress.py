"""Course progress that outlives the browser (M1-04).

The exit criterion is behavioural, not structural: "clear localStorage or change
browser, and the progress is still there". So these tests exercise the stored
record the way the page does — a whole-map replace — and pin the properties that
make it safe to lose the browser: atomic on disk, corrupt-tolerant on read, and
bounded in size.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from fde_scope.course import progress
from fde_scope.paths import data_root
from fde_scope.web.app import app


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("FDE_SCOPE_HOME", str(tmp_path))
    return tmp_path


def test_progress_round_trips(home) -> None:
    written = progress.save({"read": {"doc-01": True, "doc-02": True}, "tasks": {"doc-01::0": True}})

    assert written.read == {"doc-01": True, "doc-02": True}
    assert written.updated_at, "a save must record when it happened"

    fresh = progress.load()  # a new "browser": no localStorage involved
    assert fresh.read == {"doc-01": True, "doc-02": True}
    assert fresh.tasks == {"doc-01::0": True}


def test_replacing_is_a_replace_not_a_merge(home) -> None:
    """The page sends the complete maps it holds, so un-ticking must stick."""
    progress.save({"read": {"doc-01": True, "doc-02": True}})
    progress.save({"read": {"doc-01": True}})

    assert progress.load().read == {"doc-01": True}, "an unticked chapter came back"


def test_corrupt_file_reads_as_empty_instead_of_raising(home) -> None:
    """A crash-truncated file must not stop a learner from ticking the next box."""
    path = data_root() / ".fde_scope" / "course_progress.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"read": {"doc-01": tr', encoding="utf-8")

    assert progress.load().read == {}
    # and the next save repairs it
    progress.save({"read": {"doc-09": True}})
    assert progress.load().read == {"doc-09": True}


def test_non_mapping_payload_is_rejected(home) -> None:
    with pytest.raises(ValueError):
        progress.save(["not", "a", "map"])  # type: ignore[arg-type]


def test_unknown_and_malformed_entries_are_dropped(home) -> None:
    """The client owns the key format; the store only has to keep it sane."""
    progress.save(
        {
            "read": {"doc-01": True, "": True, 5: True, "doc-02": "yes", "doc-03": False},
            "tasks": {"doc-01::0": 1, "doc-01::1": None},
            "something_else": {"junk": 1},
        }
    )
    loaded = progress.load()
    assert loaded.read == {"doc-01": True, "doc-03": False}
    assert loaded.tasks == {"doc-01::0": True}


def test_write_is_atomic(home, monkeypatch) -> None:
    """Invariant 4: no bare Path.write_text into the data root."""
    from fde_scope import fsutil

    calls: list[str] = []
    real = fsutil.atomic_write_text

    def spy(path, text, **kw):
        calls.append(str(path))
        return real(path, text, **kw)

    monkeypatch.setattr("fde_scope.course.progress.atomic_write_text", spy)
    progress.save({"read": {"doc-01": True}})
    assert calls and calls[0].endswith("course_progress.json")


def test_oversized_payload_is_rejected(home) -> None:
    huge = {f"doc-{i}": True for i in range(progress.MAX_BYTES)}
    with pytest.raises(ValueError):
        progress.save({"read": huge})


def test_clear_forgets_everything(home) -> None:
    progress.save({"read": {"doc-01": True}})
    progress.clear()
    assert progress.load().read == {}


# -- the HTTP surface the page talks to --------------------------------------
def test_progress_api_round_trip(home) -> None:
    client = TestClient(app)

    assert client.get("/api/course/progress").json()["read"] == {}

    put = client.put("/api/course/progress", json={"read": {"doc-01": True}, "tasks": {}})
    assert put.status_code == 200, put.text

    got = client.get("/api/course/progress").json()
    assert got["read"] == {"doc-01": True}

    assert client.delete("/api/course/progress").status_code == 200
    assert client.get("/api/course/progress").json()["read"] == {}


def test_progress_api_rejects_a_non_object(home) -> None:
    client = TestClient(app)
    r = client.put("/api/course/progress", json=["nope"])
    assert r.status_code == 422


def test_progress_api_is_not_public(home) -> None:
    """Invariant 7: progress is user state, so it is not in PUBLIC_PATHS."""
    from fde_scope.web.auth import PUBLIC_PATHS

    assert "/api/course/progress" not in PUBLIC_PATHS


def test_course_page_ships_the_sync_script(home) -> None:
    """The page must prefer the server and fall back without breaking."""
    from fde_scope.web.course import render

    html = render("zh")
    for token in ("syncProgress", "_pushProgress", "/api/course/progress", "localStorage"):
        assert token in html, f"course page lost {token}"
    # a failed or unauthorised sync must not surface as an error state
    assert ".catch(function(){ _synced = false; })" in html


def test_stored_file_lives_under_the_data_root(home) -> None:
    progress.save({"read": {"doc-01": True}})
    path = data_root() / ".fde_scope" / "course_progress.json"
    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert set(payload) == {"read", "tasks", "updated_at"}
