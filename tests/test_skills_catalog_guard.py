"""Guard for docs/skills-catalog/: the per-skill dossier library stays consistent.

The catalog is maintained by hand (one Markdown page per skill, five fixed
sections, plus a README index). ``scripts/check_skills_catalog.py`` encodes the
rules; this test just runs it so ``make test`` and CI catch the drift a human
editing 80+ pages will eventually introduce (unregistered page, renamed file,
dead relative link, README status disagreeing with the page).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "check_skills_catalog.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_skills_catalog", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_catalog_pages_follow_the_five_section_template() -> None:
    ck = _load()
    assert ck.pages(), "skills-catalog has no pages"
    for page in ck.pages():
        heads = [ln for ln in page.read_text(encoding="utf-8").splitlines() if ln.startswith("## ")]
        for required in ck.REQUIRED_HEADS:
            assert any(h.startswith(required) for h in heads), f"{page.name} misses {required}"


def test_catalog_index_matches_pages_and_states_agree() -> None:
    """Exit code 0 means: README counts match disk, every page is registered
    exactly once, page status == README status, no dead relative links."""
    assert _load().main(local=False) == 0


def test_default_mode_never_reads_the_home_directory(monkeypatch) -> None:
    """CI checkouts have no ~/.qoder, so the repo self-check must not reach for
    it: only --local may reconcile against local installs."""
    ck = _load()

    def boom(*args, **kwargs):
        raise AssertionError("reconcile_local must not run without --local")

    monkeypatch.setattr(ck, "reconcile_local", boom)
    assert ck.main(local=False) == 0
