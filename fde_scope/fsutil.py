"""Shared filesystem helpers.

Every persisted user record must survive a crash as *either* the previous or
the new complete version — never a truncated mix (architecture risk review,
finding R4 / action A3). :func:`atomic_write_text` is that primitive: the
skills store used it first (inline), now engagement contexts share it too, and
:func:`atomic_write_bytes` extends it to binary assets.

:func:`safe_child` is the counterpart for *reads and deletes*: it keeps a
caller-supplied identifier from escaping the directory it was meant to address.
"""

from __future__ import annotations

import os
import re
import tempfile
from contextlib import suppress
from pathlib import Path

# A path segment that reaches the filesystem must carry no separator: "/" and
# "\\" would address a different directory, a NUL byte would be rejected
# downstream in confusing ways.
_SEGMENT_UNSAFE = re.compile(r"[/\\\x00]")


class UnsafeIdentifier(ValueError):
    """A caller-supplied id that cannot be used as a filesystem path segment.

    Subclasses :class:`ValueError` so the web layer's existing bad-request
    handling treats it as a 400 rather than a server fault, while still being
    catchable on its own (see the handler in ``web.app``).
    """


def safe_child(base: str | Path, *parts: str) -> Path:
    """Resolve ``base/...`` refusing to leave *base*.

    Store ids (skill ids, ontology schema/store ids) arrive from HTTP path
    parameters, CLI arguments and parsed YAML — never from the server. Using
    one as a path component without checking lets ``..`` or an encoded
    separator walk outside the store root and read, overwrite or delete files
    the store does not own (same failure mode as the engagement-id guard in
    ``web.deps``, which this generalises).

    Raises :class:`UnsafeIdentifier` for a segment containing a separator or
    NUL, for the ``.``/``..`` names, and — as a final backstop after
    resolution — for any result that no longer sits under *base*.
    """
    for part in parts:
        if part in (os.curdir, os.pardir) or _SEGMENT_UNSAFE.search(part):
            raise UnsafeIdentifier(f"unsafe identifier: {part!r}")
    root = Path(base).resolve()
    candidate = root.joinpath(*parts).resolve()
    if not candidate.is_relative_to(root):
        raise UnsafeIdentifier(f"unsafe identifier: {list(parts)!r} escapes {root}")
    return candidate


def atomic_write_text(path: str | Path, content: str, *, encoding: str = "utf-8") -> None:
    """Atomically write *content* to *path* (temp file + ``os.replace``).

    On any failure the temp file is removed and *path* keeps its previous
    complete content. The parent directory is created when missing.
    """
    _atomic_write(path, content, encoding=encoding)


def atomic_write_bytes(path: str | Path, content: bytes) -> None:
    """Byte-for-byte sibling of :func:`atomic_write_text` for binary assets.

    Uploads (images, bags, archives) are the same crash-consistency problem as
    JSON records, so they go through the same primitive instead of a second
    hand-rolled copy of it.
    """
    _atomic_write(path, content)


def _atomic_write(path: str | Path, data: str | bytes, *, encoding: str = "utf-8") -> None:
    binary = isinstance(data, bytes)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb" if binary else "w", encoding=None if binary else encoding) as fh:
            fh.write(data)
        os.replace(tmp, p)
    except BaseException:
        with suppress(OSError):
            os.unlink(tmp)
        raise
