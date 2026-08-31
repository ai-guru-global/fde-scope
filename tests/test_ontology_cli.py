"""ontology CLI：list / validate / check / export 的 CliRunner 覆盖。"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from fde_scope.cli import app
from fde_scope.ontology.models import Individual, InstanceStore
from fde_scope.ontology.store import OntologyStore

runner = CliRunner()


def test_list_shows_builtin_schemas() -> None:
    result = runner.invoke(app, ["ontology", "list"])
    assert result.exit_code == 0, result.stdout
    assert "fde-core" in result.stdout
    assert "mfg-overlay" in result.stdout


def test_validate_builtin_schema_passes() -> None:
    result = runner.invoke(app, ["ontology", "validate", "fde-core"])
    assert result.exit_code == 0, result.stdout
    assert "VALID" in result.stdout


def test_validate_overlay_passes() -> None:
    result = runner.invoke(app, ["ontology", "validate", "mfg-overlay"])
    assert result.exit_code == 0, result.stdout


def test_validate_unknown_schema_exit_2() -> None:
    result = runner.invoke(app, ["ontology", "validate", "ghost"])
    assert result.exit_code == 2


def test_validate_broken_workspace_schema_exit_1(tmp_path: Path) -> None:
    store = OntologyStore()
    schema = store.load_schema("fde-core").model_copy(deep=True)
    schema.id = "broken"
    schema.classes[0].sub_class_of = ["fde:Ghost"]  # 引用未声明类 → ONTO-010
    store.save_schema(schema)
    result = runner.invoke(app, ["ontology", "validate", "broken"])
    assert result.exit_code == 1
    assert "ONTO-010" in result.stdout


def test_check_store_passes(tmp_path: Path) -> None:
    store = OntologyStore()
    core = store.load_schema("fde-core")
    store.save_store(
        InstanceStore(
            id="demo",
            ontology_ref="fde-core@1.0.0",
            individuals=[
                Individual(
                    curie="ex:phase-a",
                    types=["fde:Phase"],
                    data_assertions={"fde:slug": ["connect"], "fde:phase_index": [1]},
                ),
                Individual(
                    curie="ex:eng",
                    types=["fde:Engagement"],
                    object_assertions={"fde:has_phase": ["ex:phase-a"]},
                ),
            ],
        )
    )
    assert core is not None
    result = runner.invoke(app, ["ontology", "check", "demo"])
    assert result.exit_code == 0, result.stdout
    assert "VALID" in result.stdout


def test_check_store_version_mismatch_exit_1(tmp_path: Path) -> None:
    OntologyStore().save_store(InstanceStore(id="stale", ontology_ref="fde-core@9.9.9"))
    result = runner.invoke(app, ["ontology", "check", "stale"])
    assert result.exit_code == 1
    assert "ONTO-040" in result.stdout


def test_check_unknown_store_exit_2() -> None:
    result = runner.invoke(app, ["ontology", "check", "ghost"])
    assert result.exit_code == 2


def test_export_schema_to_stdout() -> None:
    result = runner.invoke(app, ["ontology", "export", "fde-core"])
    assert result.exit_code == 0, result.stdout
    assert '"@graph"' in result.stdout


def test_export_store_to_file(tmp_path: Path) -> None:
    OntologyStore().save_store(InstanceStore(id="empty", ontology_ref="fde-core@1.0.0"))
    out = tmp_path / "out.jsonld"
    result = runner.invoke(app, ["ontology", "export", "empty", "--out", str(out)])
    assert result.exit_code == 0, result.stdout
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["@context"]["fde"] == "https://ai-guru-global.github.io/fde-scope/ontology/core#"


def test_export_unsupported_format_exit_2() -> None:
    result = runner.invoke(app, ["ontology", "export", "fde-core", "--format", "turtle"])
    assert result.exit_code == 2
