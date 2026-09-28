"""TBox 版本 diff：D1-D4 破坏性判据 + ABox 影响面。"""

from __future__ import annotations

from fde_scope.ontology.diff import diff_schemas, store_impact
from fde_scope.ontology.models import (
    DataProperty,
    Individual,
    InstanceStore,
    ObjectProperty,
    OntClass,
    OntologySchema,
)


def _schema(**overrides) -> OntologySchema:
    base: dict = {
        "id": "t",
        "version": "1.0.0",
        "base_iri": "https://example.com/o/",
        "classes": [OntClass(curie="t:Thing", label="Thing")],
        "object_properties": [ObjectProperty(curie="t:rel", label="rel", domain="t:Thing", range="t:Thing")],
        "data_properties": [DataProperty(curie="t:slug", label="slug", domain="t:Thing")],
    }
    base.update(overrides)
    return OntologySchema(**base)


def test_added_only_is_not_breaking() -> None:
    new = _schema(
        version="1.1.0",
        classes=[
            OntClass(curie="t:Thing", label="Thing"),
            OntClass(curie="t:Sub", label="Sub", sub_class_of=["t:Thing"]),
        ],
        object_properties=[
            ObjectProperty(curie="t:rel", label="rel", domain="t:Thing", range="t:Thing"),
            ObjectProperty(curie="t:rel2", label="rel2", domain="t:Thing", range="t:Thing"),
        ],
    )
    diff = diff_schemas(_schema(), new)
    assert diff.ok
    assert [c.kind for c in diff.breaking] == []
    assert {c.subject for c in diff.info} == {"t:Sub", "t:rel2"}


def test_d1_removal_is_breaking() -> None:
    new = _schema(classes=[], object_properties=[], data_properties=[])
    diff = diff_schemas(_schema(), new)
    assert not diff.ok
    assert {(c.kind, c.subject) for c in diff.breaking} == {
        ("D1", "t:Thing"),
        ("D1", "t:rel"),
        ("D1", "t:slug"),
    }


def test_d2_domain_change_is_breaking() -> None:
    new = _schema(
        object_properties=[ObjectProperty(curie="t:rel", label="rel", domain="t:Other", range="t:Thing")],
        classes=[OntClass(curie="t:Thing", label="Thing"), OntClass(curie="t:Other", label="Other")],
    )
    diff = diff_schemas(_schema(), new)
    assert [(c.kind, c.subject) for c in diff.breaking] == [("D2", "t:rel")]


def test_d3_data_range_change_is_breaking() -> None:
    new = _schema(
        data_properties=[DataProperty(curie="t:slug", label="slug", domain="t:Thing", range="integer")]
    )
    diff = diff_schemas(_schema(), new)
    assert [(c.kind, c.subject) for c in diff.breaking] == [("D3", "t:slug")]


def test_d4_parent_tightening_breaks_but_widening_is_info() -> None:
    two = _schema(
        classes=[
            OntClass(curie="t:Thing", label="Thing"),
            OntClass(curie="t:A", label="A"),
            OntClass(curie="t:Sub", label="Sub", sub_class_of=["t:A", "t:Thing"]),
        ]
    )
    one = _schema(
        classes=[
            OntClass(curie="t:Thing", label="Thing"),
            OntClass(curie="t:A", label="A"),
            OntClass(curie="t:Sub", label="Sub", sub_class_of=["t:A"]),
        ]
    )
    tightened = diff_schemas(two, one)  # 丢了 t:Thing 父类 → 语义漂移
    assert [(c.kind, c.subject) for c in tightened.breaking] == [("D4", "t:Sub")]
    widened = diff_schemas(one, two)  # 加父类只会放宽 is-a → 非破坏
    assert widened.ok
    assert any(c.subject == "t:Sub" for c in widened.info)


def test_store_impact_lists_referencing_individuals() -> None:
    new = _schema(classes=[])
    store = InstanceStore(
        id="s",
        ontology_ref="t@1.0.0",
        individuals=[
            Individual(curie="t:hit", types=["t:Thing"], data_assertions={"t:slug": [1]}),
            Individual(curie="t:clean", types=[]),
        ],
    )
    impact = store_impact(store, diff_schemas(_schema(), new))
    subjects = {c.subject for c in impact}
    assert subjects == {"t:hit"}


def test_identical_schemas_no_changes() -> None:
    diff = diff_schemas(_schema(), _schema())
    assert diff.ok and not diff.info
