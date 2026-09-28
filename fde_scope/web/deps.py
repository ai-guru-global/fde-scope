"""Shared persistence helpers for the web layer.

Extracted verbatim from ``fde_scope.web.app`` so both the main app and the
guided-mode router can load/save engagements without a circular import
(app.py includes guided_api's router; guided_api needs these helpers).

Note: ``pawapp/backend/main.py`` keeps its own dependency-light mirror of
these helpers (see its "mirror fde_scope.web.app" comment). If the PawApp
ever grows a guided mode, point it at ``fde_scope.engagement.guided`` (pure
domain logic, no FastAPI) and copy the routes — do not import this module.
"""

from __future__ import annotations

import re
import threading
from pathlib import Path

from fastapi import HTTPException

from .. import paths
from ..engagement import Engagement, EngagementContext


def _slugify(value: str) -> str:
    """Whitelist-sanitize a value for use in an engagement id / file name."""
    return re.sub(r"[^a-z0-9-]", "-", value.lower().replace(" ", "-"))


_eng_locks: dict[str, threading.Lock] = {}
_eng_locks_guard = threading.Lock()


def engagement_lock(eid: str) -> threading.Lock:
    """Per-engagement process lock (commercialization gap B3).

    Every load→modify→save sequence in the web layer must hold this lock for
    the whole read-modify-write so concurrent requests cannot clobber each
    other's engagement JSON. Process-local by design: still no database.
    """
    with _eng_locks_guard:
        return _eng_locks.setdefault(eid, threading.Lock())


def _eng_path(eid: str) -> Path:
    eng_dir = paths.engagements_dir()
    path = (eng_dir / f"{eid}.json").resolve()
    base = eng_dir.resolve()
    if not path.is_relative_to(base):
        raise HTTPException(status_code=400, detail=f"invalid engagement id: {eid!r}")
    return path


def _load(eid: str) -> Engagement:
    p = _eng_path(eid)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"engagement '{eid}' not found")
    return Engagement(EngagementContext.load(p))


def _save(eng: Engagement) -> None:
    _eng_path(eng.ctx.id).parent.mkdir(parents=True, exist_ok=True)
    eng.ctx.save(_eng_path(eng.ctx.id))


def _all_engagements() -> list[Engagement]:
    eng_dir = paths.engagements_dir()
    if not eng_dir.exists():
        return []
    out = []
    for p in sorted(eng_dir.glob("*.json")):
        try:
            out.append(Engagement(EngagementContext.load(p)))
        except ValueError:
            continue  # skip a corrupt file instead of 500ing the whole list
    return out


def catalog_site_dir() -> Path | None:
    """The generated skills-catalog portal dir, or None when unavailable.

    Resolved against the repo layout (read-only asset, absolute path — unlike
    the CWD-relative reports dir). An installed wheel without ``docs/`` gets
    None and the console degrades to GitHub links.
    """
    d = Path(__file__).resolve().parents[2] / "docs" / "skills-catalog" / "site"
    return d if d.is_dir() else None
