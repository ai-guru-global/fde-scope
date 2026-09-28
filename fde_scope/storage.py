"""Engagement storage backends — file (default) or SQLite (P5 groundwork).

Engagement persistence used to be hand-rolled JSON file access in
``fde_scope.web.deps``. This module abstracts it behind the
``StorageBackend`` protocol so a future multi-tenant deployment can swap
storage without touching the web layer:

- :class:`FileStorage` — the existing behaviour, verbatim: one atomic JSON
  file per engagement under ``.fde_scope/engagements/``, archives moved to
  ``.fde_scope/archive/``. Default; behaviour is unchanged.
- :class:`SQLiteStorage` — stdlib ``sqlite3`` (zero new dependencies), one
  row per engagement with indexed summary columns and the full
  ``EngagementContext.model_dump_json`` payload. WAL mode, one
  ``check_same_thread=False`` connection guarded by a lock, one transaction
  per mutation.

Backend selection is env-driven: ``FDE_SCOPE_STORAGE=file|sqlite``
(default ``file``). Selection is re-read on every call (like
``fde_scope.paths``) so tests can monkeypatch the environment.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from . import paths
from .fsutil import atomic_write_text
from .logutil import get_logger

if TYPE_CHECKING:
    from .engagement import EngagementContext

logger = get_logger("storage")

ENV_STORAGE = "FDE_SCOPE_STORAGE"
VALID_BACKENDS = ("file", "sqlite")


@runtime_checkable
class StorageBackend(Protocol):
    """Persistence contract for engagement contexts.

    ``load_engagement`` raises ``KeyError`` for a missing id; corrupt
    payloads raise ``ValueError`` (same as the pre-existing file behaviour).
    ``list_engagements`` skips corrupt records instead of failing the whole
    listing. ``archive_engagement`` returns a human-readable destination for
    the audit trail.
    """

    def load_engagement(self, eid: str) -> EngagementContext: ...

    def save_engagement(self, ctx: EngagementContext) -> None: ...

    def list_engagements(self) -> list[EngagementContext]: ...

    def delete_engagement(self, eid: str) -> None: ...

    def archive_engagement(self, eid: str) -> str: ...


class FileStorage:
    """The existing JSON-file behaviour, wrapped unchanged."""

    def _path(self, eid: str) -> Path:
        path = (paths.engagements_dir() / f"{eid}.json").resolve()
        base = paths.engagements_dir().resolve()
        if not path.is_relative_to(base):
            raise ValueError(f"invalid engagement id: {eid!r}")
        return path

    def load_engagement(self, eid: str) -> EngagementContext:
        from .engagement import EngagementContext

        p = self._path(eid)
        if not p.exists():
            raise KeyError(eid)
        return EngagementContext.load(p)

    def save_engagement(self, ctx: EngagementContext) -> None:
        p = self._path(ctx.id)
        p.parent.mkdir(parents=True, exist_ok=True)
        ctx.save(p)  # atomic write (AGENTS.md invariant 4)

    def list_engagements(self) -> list[EngagementContext]:
        from .engagement import EngagementContext

        eng_dir = paths.engagements_dir()
        if not eng_dir.exists():
            return []
        out: list[EngagementContext] = []
        for p in sorted(eng_dir.glob("*.json")):
            try:
                out.append(EngagementContext.load(p))
            except ValueError:
                continue  # skip a corrupt file instead of failing the list
        return out

    def delete_engagement(self, eid: str) -> None:
        self.load_engagement(eid)  # raises KeyError when missing
        self._path(eid).unlink()

    def archive_engagement(self, eid: str) -> str:
        src = self._path(eid)
        if not src.exists():
            raise KeyError(eid)
        dest = paths.archive_dir(create=True) / f"{eid}.json"
        atomic_write_text(dest, src.read_text(encoding="utf-8"))
        src.unlink()
        return str(dest)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS engagements (
    eid TEXT PRIMARY KEY,
    customer TEXT NOT NULL,
    profile TEXT NOT NULL,
    phase TEXT NOT NULL,
    zone TEXT NOT NULL,
    is_complete INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS archived_engagements (
    eid TEXT PRIMARY KEY,
    customer TEXT NOT NULL,
    profile TEXT NOT NULL,
    phase TEXT NOT NULL,
    zone TEXT NOT NULL,
    is_complete INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    archived_at TEXT NOT NULL,
    payload TEXT NOT NULL
);
"""


class SQLiteStorage:
    """SQLite backend: one row per engagement, WAL, lock-guarded connection."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._path = Path(db_path) if db_path else paths.engagements_db()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @staticmethod
    def _row(ctx: EngagementContext, now: str) -> tuple:
        from .engagement import Engagement

        return (
            ctx.id,
            ctx.customer,
            ctx.profile,
            ctx.current_phase,
            ctx.current_zone.value,
            int(Engagement(ctx).is_complete),
            now,
            ctx.model_dump_json(),
        )

    @staticmethod
    def _ctx(payload: str) -> EngagementContext:
        from .engagement import EngagementContext

        return EngagementContext.model_validate_json(payload)

    def load_engagement(self, eid: str) -> EngagementContext:
        with self._lock:
            row = self._conn.execute("SELECT payload FROM engagements WHERE eid = ?", (eid,)).fetchone()
        if row is None:
            raise KeyError(eid)
        return self._ctx(row[0])

    def save_engagement(self, ctx: EngagementContext) -> None:
        now = datetime.now(UTC).isoformat(timespec="seconds")
        with self._lock:
            with self._conn:
                self._conn.execute(
                    "INSERT INTO engagements"
                    " (eid, customer, profile, phase, zone, is_complete, updated_at, payload)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                    " ON CONFLICT(eid) DO UPDATE SET"
                    " customer=excluded.customer, profile=excluded.profile,"
                    " phase=excluded.phase, zone=excluded.zone,"
                    " is_complete=excluded.is_complete, updated_at=excluded.updated_at,"
                    " payload=excluded.payload",
                    self._row(ctx, now),
                )

    def list_engagements(self) -> list[EngagementContext]:
        with self._lock:
            rows = self._conn.execute("SELECT payload FROM engagements ORDER BY eid").fetchall()
        out: list[EngagementContext] = []
        for (payload,) in rows:
            try:
                out.append(self._ctx(payload))
            except ValueError:
                continue  # skip corrupt payloads like the file backend does
        return out

    def delete_engagement(self, eid: str) -> None:
        with self._lock:
            with self._conn:
                cur = self._conn.execute("DELETE FROM engagements WHERE eid = ?", (eid,))
        if cur.rowcount == 0:
            raise KeyError(eid)

    def archive_engagement(self, eid: str) -> str:
        now = datetime.now(UTC).isoformat(timespec="seconds")
        with self._lock:
            with self._conn:
                row = self._conn.execute(
                    "SELECT customer, profile, phase, zone, is_complete, updated_at, payload"
                    " FROM engagements WHERE eid = ?",
                    (eid,),
                ).fetchone()
                if row is None:
                    raise KeyError(eid)
                self._conn.execute(
                    "INSERT INTO archived_engagements"
                    " (eid, customer, profile, phase, zone, is_complete, updated_at,"
                    " archived_at, payload)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
                    " ON CONFLICT(eid) DO UPDATE SET"
                    " customer=excluded.customer, profile=excluded.profile,"
                    " phase=excluded.phase, zone=excluded.zone,"
                    " is_complete=excluded.is_complete, updated_at=excluded.updated_at,"
                    " archived_at=excluded.archived_at, payload=excluded.payload",
                    (eid, *row[:6], now, row[6]),
                )
                self._conn.execute("DELETE FROM engagements WHERE eid = ?", (eid,))
        return f"sqlite://{self._path}#archived_engagements/{eid}"


def get_storage_backend() -> StorageBackend:
    """Resolve the active backend from ``FDE_SCOPE_STORAGE`` (default file).

    Re-resolved on every call — like ``fde_scope.paths`` — so tests and
    entry points can change the environment between calls.
    """
    name = os.environ.get(ENV_STORAGE, "file").strip().lower() or "file"
    if name == "file":
        return FileStorage()
    if name == "sqlite":
        return SQLiteStorage()
    logger.warning("unknown %s=%r — falling back to file storage", ENV_STORAGE, name)
    return FileStorage()


def migrate_file_to_sqlite(db_path: str | Path | None = None) -> dict:
    """One-way migration: copy every file-backend engagement into SQLite.

    Source files are left in place; existing SQLite rows are overwritten.
    Returns a summary ``{"migrated": n, "skipped": m, "db_path": ...}``.
    """
    src = FileStorage()
    dst = SQLiteStorage(db_path)
    migrated = 0
    try:
        for ctx in src.list_engagements():
            dst.save_engagement(ctx)
            migrated += 1
    finally:
        dst.close()
    return {"migrated": migrated, "db_path": str(dst._path)}
