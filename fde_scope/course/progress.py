"""Course progress that survives the browser.

Origin: reading progress and exercise checkboxes lived only in ``localStorage``,
keyed per chapter. Clearing site data, switching browsers, or opening the course
on another machine reset everything — for a 26-chapter, 8-day course that is not
a preference, it is the learner's record of where they got to. The M1 exit
criterion is explicit: "clear localStorage or change browser, progress is still
there".

Storage is a single small JSON document under the data root, written through
:func:`fde_scope.fsutil.atomic_write_text` like every other user record. The
shape is deliberately loose — ``read`` and ``tasks`` are maps the page owns —
because the course front-end is the authority on what a section id means; the
server's job is to keep those maps safely, not to interpret them.

Why not SQLite here: this is one document per user, read and written whole, and
the file backend already has the atomic-write guarantee. Routing it through
``get_storage_backend`` would add a second storage abstraction for a payload
the engagement store does not need.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

from ..fsutil import atomic_write_text
from ..paths import data_root

#: Keys the page may store. Anything else is dropped on save rather than
#: rejected, so an older page cannot fill the file with debris and a newer one
#: cannot brick the save.
KNOWN_KEYS = ("read", "tasks")

#: Upper bound on the stored document. The course has ~30 chapters and ~240
#: exercises; a few thousand entries is generous and keeps a runaway client
#: from writing an unbounded file.
MAX_BYTES = 256 * 1024


def _path():
    return data_root() / ".fde_scope" / "course_progress.json"


@dataclass
class Progress:
    """The learner's record: which chapters were read, which tasks were done."""

    read: dict[str, bool] = field(default_factory=dict)
    tasks: dict[str, bool] = field(default_factory=dict)
    updated_at: str = ""

    def as_dict(self) -> dict:
        return {"read": self.read, "tasks": self.tasks, "updated_at": self.updated_at}


def _coerce_bool_map(value: object) -> dict[str, bool]:
    """Keep only ``str -> truthy`` entries; the client owns the key format."""
    if not isinstance(value, dict):
        return {}
    out: dict[str, bool] = {}
    for k, v in value.items():
        if isinstance(k, str) and k and isinstance(v, (bool, int)):
            out[k] = bool(v)
    return out


def load() -> Progress:
    """Read the stored progress; a missing or corrupt file is an empty record.

    Corruption is treated as "nothing recorded yet" rather than an error: a
    learner whose file was truncated by a crash should still be able to open
    the course and tick the next box, not meet a 500.
    """
    path = _path()
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return Progress()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return Progress()
    if not isinstance(data, dict):
        return Progress()
    return Progress(
        read=_coerce_bool_map(data.get("read")),
        tasks=_coerce_bool_map(data.get("tasks")),
        updated_at=str(data.get("updated_at") or ""),
    )


def save(payload: dict) -> Progress:
    """Merge-and-replace the stored record and return what was written.

    The client sends the complete maps it holds, so this is a replace, not a
    patch: that keeps the file and the page from disagreeing after a clear.
    Unknown keys are ignored (see ``KNOWN_KEYS``).
    """
    if not isinstance(payload, dict):
        raise ValueError("progress payload must be an object")
    progress = Progress(
        read=_coerce_bool_map(payload.get("read")),
        tasks=_coerce_bool_map(payload.get("tasks")),
        updated_at=datetime.now(UTC).isoformat(),
    )
    body = json.dumps(progress.as_dict(), ensure_ascii=False, indent=2, sort_keys=True)
    if len(body.encode("utf-8")) > MAX_BYTES:
        raise ValueError(f"progress payload exceeds {MAX_BYTES} bytes")
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, body)
    return progress


def clear() -> None:
    """Forget the stored progress (a learner starting over)."""
    _path().unlink(missing_ok=True)
