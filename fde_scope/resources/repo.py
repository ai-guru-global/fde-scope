"""只读加载器：读取随包分发的 ``data/*.yaml``（镜像 ontology/store.py 风格）。

宽容解析：损坏条目跳过并 WARNING（不炸整个目录），与 skills/ontology
store 一致。写盘只在 harvest 侧发生，且一律经 :func:`fsutil.atomic_write_text`
（AGENTS.md 不变量 4）。文件名是本模块的固定常量，不受外部路径参数影响。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from ..fsutil import atomic_write_text
from ..logutil import get_logger
from .models import ResourceRecord, Snapshot

logger = get_logger("resources")

_DATA_DIR = Path(__file__).parent / "data"
RESOURCES_FILE = "resources.yaml"
SNAPSHOT_FILE = "snapshot.yaml"


def data_dir() -> Path:
    return _DATA_DIR


def resources_path() -> Path:
    return _DATA_DIR / RESOURCES_FILE


def snapshot_path() -> Path:
    return _DATA_DIR / SNAPSHOT_FILE


# ---------------------------------------------------------------------------
# 读取
# ---------------------------------------------------------------------------
def load_resources(path: Path | None = None) -> list[ResourceRecord]:
    """读取资源清单；损坏条目跳过并记 WARNING（不返回半成品记录）。"""
    target = path or resources_path()
    if not target.is_file():
        return []
    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        logger.warning("resources manifest unreadable at %s: %s", target, exc)
        return []
    if not isinstance(raw, list):
        logger.warning("resources manifest at %s is not a list", target)
        return []
    records: list[ResourceRecord] = []
    seen: set[str] = set()
    for i, item in enumerate(raw):
        try:
            record = ResourceRecord.model_validate(item)
        except Exception as exc:  # noqa: BLE001 — a bad entry must not sink the catalog
            logger.warning("skipping resources entry #%d: %s", i, exc)
            continue
        if record.slug in seen:
            logger.warning("skipping duplicate slug %r", record.slug)
            continue
        seen.add(record.slug)
        records.append(record)
    return records


def load_snapshot(path: Path | None = None) -> Snapshot | None:
    target = path or snapshot_path()
    if not target.is_file():
        return None
    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8"))
        return Snapshot.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("snapshot unreadable at %s: %s", target, exc)
        return None


# ---------------------------------------------------------------------------
# 写入（harvest 专用；原子）
# ---------------------------------------------------------------------------
def save_resources(records: list[ResourceRecord], path: Path | None = None) -> None:
    target = path or resources_path()
    payload = [r.model_dump(mode="json", exclude_none=True) for r in records]
    text = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=100)
    atomic_write_text(target, text)


def save_snapshot(snapshot: Snapshot, path: Path | None = None) -> None:
    target = path or snapshot_path()
    text = yaml.safe_dump(
        snapshot.model_dump(mode="json", exclude_none=True),
        allow_unicode=True,
        sort_keys=False,
        width=100,
    )
    atomic_write_text(target, text)
