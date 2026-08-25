"""技能文件库存储：.fde_scope/skills/<id>/{skill.md, meta.json} + index.json。

原子写（临时文件 + rename），损坏条目跳过不炸，index.json 可由目录重建。
零新增依赖，目录即备份可携带。
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .models import SkillRecord


class SkillStore:
    """按 skill 目录组织的本地文件库。"""

    def __init__(self, root: Path = Path(".fde_scope/skills")) -> None:
        self.root = Path(root)
        self._index_path = self.root / "index.json"

    # -- 路径 ---------------------------------------------------------------
    def _dir_for(self, skill_id: str) -> Path:
        return self.root / skill_id

    def _meta_path(self, skill_id: str) -> Path:
        return self._dir_for(skill_id) / "meta.json"

    def _body_path(self, skill_id: str) -> Path:
        return self._dir_for(skill_id) / "skill.md"

    # -- 写 ------------------------------------------------------------------
    def save(self, record: SkillRecord) -> None:
        """原子写入一个技能（目录 + meta.json + skill.md + 更新索引）。"""
        d = self._dir_for(record.id)
        d.mkdir(parents=True, exist_ok=True)
        meta = record.model_dump(exclude={"body_md"}, mode="json")
        self._atomic_write(self._meta_path(record.id), json.dumps(meta, ensure_ascii=False, indent=2))
        self._atomic_write(self._body_path(record.id), record.body_md)
        self._touch_index(record)

    def delete(self, skill_id: str) -> None:
        """删除技能目录并重建索引。"""
        d = self._dir_for(skill_id)
        if d.exists():
            for p in d.iterdir():
                p.unlink()
            d.rmdir()
        self.rebuild_index()

    # -- 读 ------------------------------------------------------------------
    def load(self, skill_id: str) -> SkillRecord | None:
        meta_path = self._meta_path(skill_id)
        if not meta_path.exists():
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["body_md"] = self._body_path(skill_id).read_text(encoding="utf-8")
            return SkillRecord.model_validate(meta)
        except (ValueError, KeyError, OSError):
            return None  # 损坏条目跳过

    def load_all(self) -> list[SkillRecord]:
        if not self.root.exists():
            return []
        return [
            r
            for r in (self.load(p.name) for p in self.root.iterdir() if p.is_dir())
            if r is not None
        ]

    # -- 索引 ----------------------------------------------------------------
    def index_entries(self) -> list[dict]:
        if not self._index_path.exists():
            self.rebuild_index()
            return self.index_entries()
        try:
            return json.loads(self._index_path.read_text(encoding="utf-8"))
        except ValueError:
            self.rebuild_index()
            return self.index_entries()

    def rebuild_index(self) -> None:
        """从目录重建索引（index.json 缺失/损坏/删除后调用）。"""
        entries = [
            {
                "id": r.id,
                "title": r.title,
                "category": r.category.value,
                "status": r.status.value,
                "tags": r.tags,
                "updated_at": r.updated_at.isoformat(),
            }
            for r in self.load_all()
        ]
        self.root.mkdir(parents=True, exist_ok=True)
        self._atomic_write(self._index_path, json.dumps(entries, ensure_ascii=False, indent=2))

    def _touch_index(self, record: SkillRecord) -> None:
        entries = [e for e in self.index_entries() if e["id"] != record.id]
        entries.append(
            {
                "id": record.id,
                "title": record.title,
                "category": record.category.value,
                "status": record.status.value,
                "tags": record.tags,
                "updated_at": record.updated_at.isoformat(),
            }
        )
        self._atomic_write(self._index_path, json.dumps(entries, ensure_ascii=False, indent=2))

    # -- 原子写 --------------------------------------------------------------
    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
