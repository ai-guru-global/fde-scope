"""Precedence contract for ``fde_scope.paths.data_root`` (remediation-plan B1).

``data_root`` must resolve identically on a CI runner (no app dir) and on a
dev machine where the macOS app has been run — otherwise tests silently read
real app data and a project directory loses its own engagement/skill state.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fde_scope import paths


@pytest.fixture
def fake_app_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Pretend ``~/Documents/FDE Scope`` exists without touching the real home."""
    home = tmp_path / "app-home" / "FDE Scope"
    home.mkdir(parents=True)
    monkeypatch.setattr(paths, "app_data_dir", lambda: home)
    return home


@pytest.fixture
def no_app_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend the app was never installed (its footprint does not exist)."""
    monkeypatch.setattr(paths, "app_data_dir", lambda: tmp_path / "app-home" / "absent")


def test_env_override_wins_over_everything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_app_dir: Path
) -> None:
    (tmp_path / "project" / paths.DATA_SUBDIR).mkdir(parents=True)
    override = tmp_path / "override"
    override.mkdir()
    monkeypatch.chdir(tmp_path / "project")
    monkeypatch.setenv("FDE_SCOPE_HOME", str(override))
    assert paths.data_root() == override


def test_project_data_beats_app_footprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_app_dir: Path
) -> None:
    """A directory with its own ``.fde_scope`` keeps its own data (per-project workflow)."""
    project = tmp_path / "project"
    (project / paths.DATA_SUBDIR).mkdir(parents=True)
    monkeypatch.chdir(project)
    monkeypatch.delenv("FDE_SCOPE_HOME", raising=False)
    # The CWD branch stays relative by design (it must keep tracking chdir).
    assert paths.data_root() == Path()
    assert (paths.data_root() / paths.DATA_SUBDIR).is_dir()


def test_app_footprint_serves_runs_outside_any_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_app_dir: Path
) -> None:
    """Outside a project, a CLI still sees the app's data (the B1 goal)."""
    monkeypatch.chdir(tmp_path)  # no .fde_scope here
    monkeypatch.delenv("FDE_SCOPE_HOME", raising=False)
    assert paths.data_root() == fake_app_dir


def test_bare_cwd_when_nothing_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, no_app_dir: None
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FDE_SCOPE_HOME", raising=False)
    assert paths.data_root() == Path()
    assert paths.engagements_dir().name == "engagements"


def test_helpers_re_resolve_each_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing is cached at import time: changing the env changes the answer."""
    monkeypatch.delenv("FDE_SCOPE_HOME", raising=False)
    first = paths.engagements_dir()
    monkeypatch.setenv("FDE_SCOPE_HOME", str(tmp_path))
    second = paths.engagements_dir()
    assert first != second
    assert second == tmp_path / paths.DATA_SUBDIR / "engagements"
