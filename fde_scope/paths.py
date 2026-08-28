"""Single resolution point for every on-disk data location (remediation-plan B1).

The CLI, web console, PawApp backend and macOS app launcher used to each
hardcode ``Path(".fde_scope/...")`` relative to the process CWD — which is why
an engagement created by double-clicking the app was invisible to a terminal
run of the CLI (review risk R1). Every entry point now resolves data
locations through :func:`data_root`:

1. ``FDE_SCOPE_HOME`` when set — what the macOS app exports at startup, and
   what tests pin for isolation;
2. the process CWD when it already carries its own ``.fde_scope`` — a project
   directory keeps its own engagement/skill data even on a machine where the
   app is installed (per-project CLI workflow);
3. ``~/Documents/FDE Scope`` when that directory exists — the app's install
   footprint, so a CLI run *outside* any project still sees app data;
4. the process CWD, kept as a *relative* path so per-use resolution keeps
   tracking ``chdir``.

Helpers re-resolve on every call: the environment may legitimately change
between module import and use (tests monkeypatch it), so nothing here is
cached at import time.
"""

from __future__ import annotations

import os
from pathlib import Path

DATA_SUBDIR = ".fde_scope"


def app_data_dir() -> Path:
    """The macOS app's default data home (the launcher creates it)."""
    return Path.home() / "Documents" / "FDE Scope"


def data_root() -> Path:
    """``FDE_SCOPE_HOME`` > CWD with data > app dir (if present) > CWD."""
    override = os.environ.get("FDE_SCOPE_HOME")
    if override:
        return Path(override).expanduser()
    cwd = Path()
    if (cwd / DATA_SUBDIR).is_dir():
        return cwd
    home = app_data_dir()
    if home.is_dir():
        return home
    return cwd  # relative on purpose — see module docstring


def _under_root(*parts: str, create: bool = False) -> Path:
    path = data_root().joinpath(DATA_SUBDIR, *parts)
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def engagements_dir(create: bool = False) -> Path:
    """``<root>/.fde_scope/engagements`` — engagement state JSON."""
    return _under_root("engagements", create=create)


def skills_dir(create: bool = False) -> Path:
    """``<root>/.fde_scope/skills`` — the skill library."""
    return _under_root("skills", create=create)


def skills_export_dir(create: bool = False) -> Path:
    """``<root>/.fde_scope/skills/export`` — exported SKILL.md files."""
    return _under_root("skills", "export", create=create)


def uploads_dir(create: bool = False) -> Path:
    """``<root>/.fde_scope/uploads`` — uploaded raw files."""
    return _under_root("uploads", create=create)


def reports_dir(create: bool = False) -> Path:
    """``<root>/reports`` — generated runbooks / corpus reports."""
    path = data_root() / "reports"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path
