"""P3.1 — skills_bridge：SkillRecord ↔ SKOS 概念桥接（category 映射 + tag CURIE）。"""

from __future__ import annotations

from fde_scope.ontology.skills_bridge import CATEGORY_CONCEPT, expand_concept, skill_concepts
from fde_scope.skills.models import SkillCategory, SkillRecord


def _schema(schema_id: str):
    from fde_scope.ontology.store import OntologyStore

    schema = OntologyStore().load_schema(schema_id)
    assert schema is not None
    return schema


def _record(category: SkillCategory = SkillCategory.RESEARCH, tags: list[str] | None = None) -> SkillRecord:
    return SkillRecord(title="t", category=category, tags=tags or [])


def test_category_concept_table_covers_all_skill_categories() -> None:
    assert set(CATEGORY_CONCEPT) == {c.value for c in SkillCategory}


def test_skill_concepts_category_maps_to_concept() -> None:
    assert skill_concepts(_record(), _schema("fde-core")) == ["fde:cat-research"]


def test_skill_concepts_tag_curie_declared_merged_undeclared_ignored() -> None:
    rec = _record(category=SkillCategory.OPTIMIZATION, tags=["fde:cat-methodology", "billing"])
    assert skill_concepts(rec, _schema("fde-core")) == ["fde:cat-optimization", "fde:cat-methodology"]


def test_skill_concepts_dedup_keeps_stable_order() -> None:
    rec = _record(category=SkillCategory.RESEARCH, tags=["fde:cat-research"])
    assert skill_concepts(rec, _schema("fde-core")) == ["fde:cat-research"]


def test_skill_concepts_without_category_scheme_tags_only() -> None:
    # corpus_taxonomy 没有 SkillCategoryScheme：不映射 category，仅收声明的 tag CURIE
    rec = _record(category=SkillCategory.IMPLEMENTATION, tags=["fde:cc-billing", "refund"])
    assert skill_concepts(rec, _schema("fde-corpus-taxonomy")) == ["fde:cc-billing"]


def test_expand_concept_narrower_closure() -> None:
    assert expand_concept("fde:cc-billing", _schema("fde-corpus-taxonomy")) == {
        "fde:cc-billing",
        "fde:cc-billing-refund",
        "fde:cc-billing-invoice",
    }


def test_expand_concept_unknown_returns_self() -> None:
    assert expand_concept("fde:cc-nothing", _schema("fde-corpus-taxonomy")) == {"fde:cc-nothing"}


def test_expand_concept_terminates_on_broader_cycle() -> None:
    # 环状分类法（A broader B, B broader A）：闭包有限终止而非死循环
    from fde_scope.ontology.models import Concept, ConceptScheme, Namespace, OntologySchema

    cyclic = OntologySchema(
        id="cyclic",
        version="1.0.0",
        base_iri="https://example.com/o/",
        namespaces=[Namespace(prefix="c", iri="https://example.com/o/c#")],
        concept_schemes=[
            ConceptScheme(
                curie="c:Scheme",
                label="Scheme",
                concepts=[
                    Concept(curie="c:A", label="A", broader=["c:B"]),
                    Concept(curie="c:B", label="B", broader=["c:A"]),
                ],
            )
        ],
    )
    assert expand_concept("c:A", cyclic) == {"c:A", "c:B"}
