"""Storage backend tests: FileStorage + SQLiteStorage parity (P5 groundwork)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from fde_scope.engagement import Engagement, EngagementContext
from fde_scope.storage import (
    FileStorage,
    SQLiteStorage,
    get_storage_backend,
    migrate_file_to_sqlite,
)


def _ctx(eid: str, customer: str = "Acme") -> EngagementContext:
    return EngagementContext(id=eid, customer=customer, profile="ticket")


# -- backend selection ---------------------------------------------------------
def test_default_backend_is_file() -> None:
    assert isinstance(get_storage_backend(), FileStorage)


def test_env_selects_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDE_SCOPE_STORAGE", "sqlite")
    assert isinstance(get_storage_backend(), SQLiteStorage)


def test_unknown_backend_falls_back_to_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FDE_SCOPE_STORAGE", "postgresql")
    assert isinstance(get_storage_backend(), FileStorage)


# -- FileStorage ---------------------------------------------------------------
def test_file_roundtrip(tmp_path: Path) -> None:
    be = FileStorage()
    be.save_engagement(_ctx("eng-f1"))
    assert (tmp_path / ".fde_scope" / "engagements" / "eng-f1.json").exists()
    loaded = be.load_engagement("eng-f1")
    assert loaded.customer == "Acme"
    with pytest.raises(KeyError):
        be.load_engagement("eng-missing")


def test_file_list_skips_corrupt(tmp_path: Path) -> None:
    be = FileStorage()
    be.save_engagement(_ctx("eng-ok"))
    eng_dir = tmp_path / ".fde_scope" / "engagements"
    (eng_dir / "eng-bad.json").write_text("{not json", encoding="utf-8")
    assert [c.id for c in be.list_engagements()] == ["eng-ok"]


def test_file_archive_and_delete(tmp_path: Path) -> None:
    be = FileStorage()
    be.save_engagement(_ctx("eng-f2"))
    dest = be.archive_engagement("eng-f2")
    assert Path(dest).exists()
    assert dest.endswith(str(Path("archive") / "eng-f2.json"))
    assert be.list_engagements() == []
    with pytest.raises(KeyError):
        be.archive_engagement("eng-f2")

    be.save_engagement(_ctx("eng-f3"))
    be.delete_engagement("eng-f3")
    with pytest.raises(KeyError):
        be.delete_engagement("eng-f3")


def test_file_rejects_traversal_id() -> None:
    with pytest.raises(ValueError, match="invalid engagement id"):
        FileStorage().load_engagement("../../etc/passwd")


# -- SQLiteStorage ---------------------------------------------------------------
@pytest.fixture
def sqlite_backend(tmp_path: Path):
    be = SQLiteStorage(tmp_path / "eng.db")
    yield be
    be.close()


def test_sqlite_roundtrip(sqlite_backend: SQLiteStorage) -> None:
    ctx = _ctx("eng-s1")
    ctx.success_criteria.append("p95 < 5min")
    sqlite_backend.save_engagement(ctx)
    loaded = sqlite_backend.load_engagement("eng-s1")
    assert loaded == ctx  # full payload roundtrip, byte-identical semantics
    with pytest.raises(KeyError):
        sqlite_backend.load_engagement("eng-missing")


def test_sqlite_summary_columns(sqlite_backend: SQLiteStorage) -> None:
    eng = Engagement(_ctx("eng-s2", "Aurora Motors"))
    eng.ctx.profile = "manufacturing"
    sqlite_backend.save_engagement(eng.ctx)
    row = sqlite_backend._conn.execute(
        "SELECT customer, profile, phase, zone, is_complete FROM engagements WHERE eid = ?",
        ("eng-s2",),
    ).fetchone()
    assert row[:4] == ("Aurora Motors", "manufacturing", "qualification", "pre_engagement")
    assert row[4] == 0
    assert sqlite_backend._conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_sqlite_save_updates_in_place(sqlite_backend: SQLiteStorage) -> None:
    sqlite_backend.save_engagement(_ctx("eng-s3"))
    ctx = _ctx("eng-s3", "Renamed Co")
    sqlite_backend.save_engagement(ctx)
    assert sqlite_backend.load_engagement("eng-s3").customer == "Renamed Co"
    assert [c.id for c in sqlite_backend.list_engagements()] == ["eng-s3"]


def test_sqlite_archive_and_delete(sqlite_backend: SQLiteStorage) -> None:
    sqlite_backend.save_engagement(_ctx("eng-s4"))
    dest = sqlite_backend.archive_engagement("eng-s4")
    assert "archived_engagements" in dest
    assert sqlite_backend.list_engagements() == []
    with pytest.raises(KeyError):
        sqlite_backend.load_engagement("eng-s4")
    with pytest.raises(KeyError):
        sqlite_backend.archive_engagement("eng-s4")
    archived = sqlite_backend._conn.execute(
        "SELECT payload FROM archived_engagements WHERE eid = ?", ("eng-s4",)
    ).fetchone()
    assert EngagementContext.model_validate_json(archived[0]).customer == "Acme"

    sqlite_backend.save_engagement(_ctx("eng-s5"))
    sqlite_backend.delete_engagement("eng-s5")
    with pytest.raises(KeyError):
        sqlite_backend.delete_engagement("eng-s5")


def test_sqlite_concurrent_writes_lose_nothing(tmp_path: Path) -> None:
    """Thread-pool stress: many writers on distinct + shared ids, no lost rows."""
    be = SQLiteStorage(tmp_path / "conc.db")
    eids = [f"eng-c{i}" for i in range(6)]

    def work(n: int) -> None:
        for i in range(10):
            ctx = _ctx(eids[i % len(eids)])
            ctx.assets["n"] = n * 10 + i
            be.save_engagement(ctx)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(work, range(8)))
    assert sorted(c.id for c in be.list_engagements()) == sorted(eids)
    for eid in eids:  # every row is a valid, complete payload
        assert be.load_engagement(eid).customer == "Acme"
    be.close()


def test_sqlite_concurrent_same_id_stays_valid(tmp_path: Path) -> None:
    be = SQLiteStorage(tmp_path / "same.db")

    def work(n: int) -> None:
        ctx = _ctx("eng-shared")
        ctx.assets["writer"] = n
        be.save_engagement(ctx)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(work, range(32)))
    loaded = be.load_engagement("eng-shared")
    assert isinstance(loaded.assets["writer"], int)
    be.close()


# -- cross-backend parity ---------------------------------------------------------
def test_list_consistency_across_backends(tmp_path: Path) -> None:
    file_be = FileStorage()
    sqlite_be = SQLiteStorage(tmp_path / "parity.db")
    for i in (2, 0, 1):  # write unordered; both list sorted by eid
        ctx = _ctx(f"eng-p{i}", customer=f"Co-{i}")
        file_be.save_engagement(ctx)
        sqlite_be.save_engagement(ctx)
    file_list = file_be.list_engagements()
    sqlite_list = sqlite_be.list_engagements()
    assert [c.id for c in file_list] == [c.id for c in sqlite_list]
    assert [c.model_dump_json() for c in file_list] == [c.model_dump_json() for c in sqlite_list]
    sqlite_be.close()


# -- migration -----------------------------------------------------------------
def test_migrate_file_to_sqlite(tmp_path: Path) -> None:
    file_be = FileStorage()
    for eid in ("eng-m1", "eng-m2"):
        file_be.save_engagement(_ctx(eid))
    summary = migrate_file_to_sqlite(tmp_path / "mig.db")
    assert summary["migrated"] == 2
    # source files stay in place (one-way copy, not a move)
    assert len(list((tmp_path / ".fde_scope" / "engagements").glob("*.json"))) == 2
    sqlite_be = SQLiteStorage(tmp_path / "mig.db")
    assert sorted(c.id for c in sqlite_be.list_engagements()) == ["eng-m1", "eng-m2"]
    sqlite_be.close()


def test_cli_storage_migrate(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from fde_scope.cli import app

    FileStorage().save_engagement(_ctx("eng-cli1"))
    result = CliRunner().invoke(app, ["storage-migrate", "--to", "sqlite"])
    assert result.exit_code == 0
    assert "eng-cli1" not in result.output  # ids stay out of stdout; counts only
    sqlite_be = SQLiteStorage(tmp_path / ".fde_scope" / "engagements.db")
    assert [c.id for c in sqlite_be.list_engagements()] == ["eng-cli1"]
    sqlite_be.close()

    bad = CliRunner().invoke(app, ["storage-migrate", "--to", "postgres"])
    assert bad.exit_code == 2


# -- web layer over SQLite --------------------------------------------------------
def test_web_lifecycle_over_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """deps.py routes everything through the backend: same API over sqlite."""
    monkeypatch.setenv("FDE_SCOPE_STORAGE", "sqlite")
    monkeypatch.chdir(tmp_path)
    from fastapi.testclient import TestClient

    from fde_scope.web.app import app

    client = TestClient(app)
    eid = client.post("/api/engagements", data={"customer": "SqlCo", "profile": "ticket"}).json()[
        "engagement_id"
    ]
    assert eid in [e["engagement_id"] for e in client.get("/api/engagements").json()]
    # no JSON file is written in sqlite mode
    assert not (tmp_path / ".fde_scope" / "engagements").exists()
    assert (tmp_path / ".fde_scope" / "engagements.db").exists()

    assert client.post(f"/api/engagements/{eid}/archive").status_code == 200
    assert client.get(f"/api/engagements/{eid}").status_code == 404

    eid2 = client.post("/api/engagements", data={"customer": "SqlCo2"}).json()["engagement_id"]
    r = client.request("DELETE", f"/api/engagements/{eid2}", data={"confirm": "SqlCo2"})
    assert r.status_code == 200
    assert client.get(f"/api/engagements/{eid2}").status_code == 404


def test_web_lifecycle_default_file_backend_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FDE_SCOPE_STORAGE", raising=False)
    monkeypatch.chdir(tmp_path)
    from fastapi.testclient import TestClient

    from fde_scope.web.app import app

    client = TestClient(app)
    eid = client.post("/api/engagements", data={"customer": "FileCo"}).json()["engagement_id"]
    assert (tmp_path / ".fde_scope" / "engagements" / f"{eid}.json").exists()
    assert not (tmp_path / ".fde_scope" / "engagements.db").exists()
