"""Shared filesystem helpers.

Every persisted user record must survive a crash as *either* the previous or
the new complete version — never a truncated mix (architecture risk review,
finding R4 / action A3). :func:`atomic_write_text` is that primitive: the
skills store used it first (inline), now engagement contexts share it too.
"""

from __future__ import annotations

import os
import tempfile
from contextlib import suppress
from pathlib import Path


def atomic_write_text(path: str | Path, content: str, *, encoding: str = "utf-8") -> None:
    """Atomically write *content* to *path* (temp file + ``os.replace``).

    On any failure the temp file is removed and *path* keeps its previous
    complete content. The parent directory is created when missing.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as fh:
            fh.write(content)
        os.replace(tmp, p)
    except BaseException:
        with suppress(OSError):
            os.unlink(tmp)
        raise
