"""Guard: every direct dependency in pyproject.toml is covered by NOTICE.

Prevents a newly added dependency from shipping without a license-audit entry.
Name matching only (no versions — too brittle).
"""

from __future__ import annotations

import re
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parent.parent


def _norm(name: str) -> str:
    """PEP 503 normalization."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _direct_dependency_names() -> set[str]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    reqs = list(data["project"].get("dependencies", []))
    reqs += [r for group in data["project"].get("optional-dependencies", {}).values() for r in group]
    names: set[str] = set()
    for req in reqs:
        name = re.split(r"[<>=!~;\[]", req, maxsplit=1)[0].strip()
        if _norm(name) == "fde-scope":  # self-reference in the `full` meta-extra
            continue
        names.add(_norm(name))
    return names


def test_notice_covers_every_direct_dependency() -> None:
    notice = (ROOT / "NOTICE").read_text(encoding="utf-8").lower()
    missing = [n for n in sorted(_direct_dependency_names()) if n not in notice]
    assert not missing, f"NOTICE is missing license entries for: {missing}"


def test_direct_dependencies_are_audited_in_docs() -> None:
    audit = (ROOT / "docs" / "license-audit.md").read_text(encoding="utf-8").lower()
    missing = [n for n in sorted(_direct_dependency_names()) if n not in audit]
    assert not missing, f"docs/license-audit.md is missing rows for: {missing}"
