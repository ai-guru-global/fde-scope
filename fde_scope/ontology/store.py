"""本体文件存储：内置只读 schema（data/*.yaml）+ 工作区 schemas/stores。

风格与 skills store 一致：加载宽容（损坏条目跳过不炸），写入原子
（fsutil.atomic_write_text）。查找优先级：工作区 > 内置（用户可覆盖内置
schema，如 corpus_taxonomy 的现场扩展）。
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from .. import paths
from ..fsutil import atomic_write_text
from .models import InstanceStore, OntologySchema

_DATA_DIR = Path(__file__).parent / "data"


class OntologyStore:
    """内置 + 工作区本体的统一读写入口。"""

    def __init__(self, root: Path | str | None = None) -> None:
        # 默认经 fde_scope.paths 惰性解析（B1：不缓存 data-root 决策）
        self.root = Path(root) if root is not None else paths.ontology_dir()
        self.schemas_dir = self.root / "schemas"
        self.stores_dir = self.root / "stores"

    # -- 内置 ----------------------------------------------------------------
    def builtin_schemas(self) -> dict[str, OntologySchema]:
        out: dict[str, OntologySchema] = {}
        if not _DATA_DIR.is_dir():
            return out
        for p in sorted(_DATA_DIR.glob("*.yaml")):
            schema = self._parse_schema(p)
            if schema is not None:
                out.setdefault(schema.id, schema)
        return out

    # -- 读写 schema -----------------------------------------------------------
    def load_schema(self, schema_id: str) -> OntologySchema | None:
        p = self.schemas_dir / f"{schema_id}.yaml"
        if p.exists():
            return self._parse_schema(p)
        return self.builtin_schemas().get(schema_id)

    def save_schema(self, schema: OntologySchema) -> None:
        text = yaml.safe_dump(schema.model_dump(mode="json"), allow_unicode=True, sort_keys=False)
        atomic_write_text(self.schemas_dir / f"{schema.id}.yaml", text)

    def list_schemas(self) -> list[dict]:
        workspace: dict[str, dict] = {}
        if self.schemas_dir.is_dir():
            for p in sorted(self.schemas_dir.glob("*.yaml")):
                schema = self._parse_schema(p)
                if schema is not None:
                    workspace[schema.id] = self._schema_entry(schema, origin="workspace")
        builtin = {
            sid: self._schema_entry(s, origin="builtin")
            for sid, s in self.builtin_schemas().items()
            if sid not in workspace
        }
        return [*workspace.values(), *builtin.values()]

    # -- 读写 store ------------------------------------------------------------
    def load_store(self, store_id: str) -> InstanceStore | None:
        p = self.stores_dir / f"{store_id}.json"
        if not p.exists():
            return None
        try:
            return InstanceStore.model_validate(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return None

    def save_store(self, store: InstanceStore) -> None:
        text = json.dumps(store.model_dump(mode="json"), ensure_ascii=False, indent=2)
        atomic_write_text(self.stores_dir / f"{store.id}.json", text)

    def list_stores(self) -> list[dict]:
        entries: list[dict] = []
        if not self.stores_dir.is_dir():
            return entries
        for p in sorted(self.stores_dir.glob("*.json")):
            inst = self.load_store(p.stem)
            if inst is not None:
                entries.append(
                    {
                        "id": inst.id,
                        "ontology_ref": inst.ontology_ref,
                        "individuals": len(inst.individuals),
                    }
                )
        return entries

    # -- 内部 ----------------------------------------------------------------
    @staticmethod
    def _parse_schema(path: Path) -> OntologySchema | None:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            return OntologySchema.model_validate(data)
        except (OSError, ValueError, yaml.YAMLError):
            return None  # 损坏条目跳过，不让 CLI 炸

    @staticmethod
    def _schema_entry(schema: OntologySchema, *, origin: str) -> dict:
        return {
            "id": schema.id,
            "version": schema.version,
            "origin": origin,
            "imports": schema.imports,
            "classes": len(schema.classes),
            "object_properties": len(schema.object_properties),
            "data_properties": len(schema.data_properties),
            "concept_schemes": len(schema.concept_schemes),
        }
