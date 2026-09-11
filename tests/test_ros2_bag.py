"""Tests for the ROS 2 bag connector.

Contract layer: no rosbags dependency needed — fake dicts feed the
normalize/expand/exclude pipeline. Real-file layer: rosbags Writer
self-produces bags (dual format). Integration: env-gated real bag.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fde_scope.connectors.ros2_bag import Ros2BagConnector


# ---------------------------------------------------------------------------
# Path form detection
# ---------------------------------------------------------------------------
def test_bag_directory_detected(tmp_path: Path) -> None:
    """A directory containing metadata.yaml is a standard bag directory."""
    (tmp_path / "metadata.yaml").write_text("rosbag2_bagfile_information:\n", encoding="utf-8")
    c = Ros2BagConnector(str(tmp_path))
    assert c.bag_path == tmp_path
    assert c._path_form == "dir"


def test_mcap_file_detected(tmp_path: Path) -> None:
    c = Ros2BagConnector(str(tmp_path / "recording.mcap"))
    assert c._path_form == "mcap"


def test_db3_directory_rejected(tmp_path: Path) -> None:
    """A directory without metadata.yaml (e.g. bare .db3) must error with guidance."""
    (tmp_path / "data.db3").write_bytes(b"\x00")
    c = Ros2BagConnector(str(tmp_path))
    with pytest.raises(ValueError, match="metadata.yaml"):
        c._validate_path()


def test_unknown_extension_rejected(tmp_path: Path) -> None:
    c = Ros2BagConnector(str(tmp_path / "data.txt"))
    with pytest.raises(ValueError, match="mcap"):
        c._validate_path()


def test_ensure_driver_message_names_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the user forgot the [ros2] extra, the error names the fix."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "rosbags" or name.startswith("rosbags."):
            raise ImportError("simulated missing driver")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    # Need a valid path form to reach _ensure_driver
    c = Ros2BagConnector("dummy.mcap")
    with pytest.raises(ImportError, match=r"fde-scope\[ros2\]"):
        c._ensure_driver()
