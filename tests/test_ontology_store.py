"""OntologyStore：内置加载、工作区覆盖优先、原子写、宽容加载。"""

from __future__ import annotations

import os
from pathlib import Path

from fde_scope import paths
from fde_scope.ontology.models import Individual, InstanceStore, OntologySchema
from fde_scope.ontology.store import OntologyStore
from fde_scope.ontology.validation import resolve_imports, validate_schema


def test_default_root_resolves_through_paths() -> None:
    store = OntologyStore()
    assert store.root == paths.ontology_dir()
    assert paths.ontology_dir() == Path(os.environ["FDE_SCOPE_HOME"]) / ".fde_scope" / "ontology"


def test_workspace_schema_round_trip(tmp_path: Path) -> None:
    store = OntologyStore(root=tmp_path)
    schema = OntologySchema(
        id="mine",
        version="0.1.0",
        base_iri="https://example.com/",
        namespaces=[],
    )
    store.save_schema(schema)
    loaded = store.load_schema("mine")
    assert loaded == schema
    assert (tmp_path / "schemas" / "mine.yaml").exists()


def test_workspace_store_round_trip(tmp_path: Path) -> None:
    store = OntologyStore(root=tmp_path)
    inst = InstanceStore(
        id="demo",
        ontology_ref="fde-core@1.0.0",
        individuals=[Individual(curie="ex:one", types=[])],
    )
    store.save_store(inst)
    assert store.load_store("demo") == inst


def test_load_missing_returns_none(tmp_path: Path) -> None:
    store = OntologyStore(root=tmp_path)
    assert store.load_schema("ghost") is None
    assert store.load_store("ghost") is None


def test_corrupt_workspace_file_skipped(tmp_path: Path) -> None:
    store = OntologyStore(root=tmp_path)
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas" / "bad.yaml").write_text("{{{{not yaml", encoding="utf-8")
    assert store.load_schema("bad") is None


def test_list_precedence_workspace_over_builtin(tmp_path: Path) -> None:
    store = OntologyStore(root=tmp_path)
    entries = {e["id"]: e for e in store.list_schemas()}
    assert entries["fde-core"]["origin"] == "builtin"
    override = OntologySchema(id="fde-core", version="9.9.9", base_iri="https://example.com/")
    store.save_schema(override)
    entries = {e["id"]: e for e in store.list_schemas()}
    assert entries["fde-core"]["origin"] == "workspace"
    assert entries["fde-core"]["version"] == "9.9.9"
    assert store.load_schema("fde-core").version == "9.9.9"


def test_list_stores_empty(tmp_path: Path) -> None:
    assert OntologyStore(root=tmp_path).list_stores() == []


def test_builtin_schemas_present() -> None:
    schemas = OntologyStore().builtin_schemas()
    assert {"fde-core", "mfg-overlay"} <= set(schemas)


def test_builtin_schemas_self_validate() -> None:
    """狗粮：内置 TBox 必须通过自己的校验器。"""
    store = OntologyStore()
    for sid, schema in store.builtin_schemas().items():
        report = validate_schema(schema, loader=store.load_schema)
        assert report.ok, (sid, [e.model_dump() for e in report.errors])


def test_overlay_merges_core_on_validation() -> None:
    store = OntologyStore()
    overlay = store.load_schema("mfg-overlay")
    merged = resolve_imports(overlay, loader=store.load_schema)
    curies = {c.curie for c in merged.classes}
    assert "fde:Artifact" in curies  # 来自 fde-core
    assert "mfg:OEE" in curies  # overlay 自有
