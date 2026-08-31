"""P2.1 内置语料概念体系：corpus_taxonomy 狗粮校验。

覆盖规格 docs/superpowers/specs/2026-08-31-ontology-module-design.md §7（corpus_taxonomy）。
"""

from __future__ import annotations

from fde_scope.ontology.models import OntologySchema
from fde_scope.ontology.store import OntologyStore
from fde_scope.ontology.validation import validate_schema


def _taxonomy() -> OntologySchema:
    schema = OntologyStore().load_schema("fde-corpus-taxonomy")
    assert schema is not None, "builtin fde-corpus-taxonomy missing"
    return schema


def test_corpus_taxonomy_self_validate() -> None:
    schema = _taxonomy()
    report = validate_schema(schema, loader=OntologyStore().load_schema)
    assert report.ok, [e.model_dump() for e in report.errors]


def test_corpus_taxonomy_first_layer_has_keywords() -> None:
    concepts = {c.curie: c for c in _taxonomy().concept_schemes[0].concepts}
    for curie in (
        "fde:cc-billing",
        "fde:cc-outage",
        "fde:cc-onboarding",
        "fde:cc-quality",
        "fde:cc-logistics",
        "fde:cc-safety",
    ):
        assert curie in concepts, curie
        assert concepts[curie].match_keywords, f"{curie} lacks match_keywords"


def test_corpus_taxonomy_narrower_tree() -> None:
    concepts = {c.curie: c for c in _taxonomy().concept_schemes[0].concepts}
    child = concepts["fde:cc-billing-refund"]
    assert "fde:cc-billing" in child.broader
