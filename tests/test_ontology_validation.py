"""SHACL-lite 校验器：每个错误码至少一正一反，import 合并与闭环词表。"""

from __future__ import annotations

import pytest

from fde_scope.ontology.models import (
    Concept,
    ConceptScheme,
    DataProperty,
    Individual,
    InstanceStore,
    Namespace,
    ObjectProperty,
    OntClass,
    OntologySchema,
)
from fde_scope.ontology.validation import resolve_imports, validate_schema, validate_store


def _minimal(id_: str = "t", version: str = "1.0.0") -> OntologySchema:
    return OntologySchema(
        id=id_,
        version=version,
        base_iri="https://example.com/o/",
        namespaces=[Namespace(prefix="t", iri="https://example.com/o/t#")],
        classes=[
            OntClass(curie="t:Thing", label="Thing"),
            OntClass(curie="t:Sub", label="Sub", sub_class_of=["t:Thing"]),
        ],
        object_properties=[ObjectProperty(curie="t:rel", label="rel", domain="t:Thing", range="t:Thing")],
        data_properties=[DataProperty(curie="t:slug", label="slug", domain="t:Thing")],
    )


def codes(report) -> set[str]:
    return {e.code for e in report.errors}


def test_valid_schema_passes() -> None:
    schema = _minimal()
    report = validate_schema(schema, loader={})
    assert report.ok, [e.model_dump() for e in report.errors]


def test_onto001_sub_class_of_cycle() -> None:
    schema = _minimal()
    schema.classes.append(OntClass(curie="t:A", label="A", sub_class_of=["t:B"]))
    schema.classes.append(OntClass(curie="t:B", label="B", sub_class_of=["t:A"]))
    assert "ONTO-001" in codes(validate_schema(schema, loader={}))


def test_onto002_sub_property_missing_and_inverse_cycle() -> None:
    schema = _minimal()
    schema.object_properties[0].inverse = "t:missing"  # 不存在
    schema.object_properties.append(
        ObjectProperty(curie="t:p2", label="p2", domain="t:Thing", range="t:Thing", sub_property_of="t:p2")
    )  # 自环
    report = validate_schema(schema, loader={})
    got = codes(report)
    assert "ONTO-002" in got


def test_onto012_broader_cycle() -> None:
    schema = _minimal()
    schema.concept_schemes.append(
        ConceptScheme(
            curie="t:Scheme",
            label="Scheme",
            concepts=[
                Concept(curie="t:CA", label="CA", broader=["t:CB"]),
                Concept(curie="t:CB", label="CB", broader=["t:CA"]),
            ],
        )
    )
    report = validate_schema(schema, loader={})
    assert "ONTO-012" in codes(report)


def test_onto012_acyclic_broader_passes() -> None:
    schema = _minimal()
    schema.concept_schemes.append(
        ConceptScheme(
            curie="t:Scheme",
            label="Scheme",
            concepts=[
                Concept(curie="t:P", label="P"),
                Concept(curie="t:C", label="C", broader=["t:P"]),
            ],
        )
    )
    report = validate_schema(schema, loader={})
    assert report.ok, [e.model_dump() for e in report.errors]


def test_onto010_undeclared_class_reference() -> None:
    schema = _minimal()
    schema.classes.append(OntClass(curie="t:Bad", label="Bad", sub_class_of=["t:Ghost"]))
    assert "ONTO-010" in codes(validate_schema(schema, loader={}))


def test_onto011_undeclared_property_reference() -> None:
    schema = _minimal()
    schema.object_properties.append(
        ObjectProperty(curie="t:p3", label="p3", domain="t:Thing", range="t:Thing", sub_property_of="t:ghost")
    )
    assert "ONTO-011" in codes(validate_schema(schema, loader={}))


def test_onto030_undeclared_prefix() -> None:
    schema = _minimal()
    schema.classes.append(OntClass(curie="x:Thing", label="X"))
    assert "ONTO-030" in codes(validate_schema(schema, loader={}))


def test_resolve_imports_merges_overlay_and_self_wins() -> None:
    core = _minimal(id_="core")
    overlay = OntologySchema(
        id="overlay",
        version="1.0.0",
        base_iri="https://example.com/o/",
        imports=["core"],
        namespaces=[Namespace(prefix="o", iri="https://example.com/o/o#")],
        classes=[OntClass(curie="o:Extra", label="Extra", sub_class_of=["t:Thing"])],
        data_properties=[DataProperty(curie="t:slug", label="slug overridden", domain="t:Thing")],
    )

    loader = {"core": core, "overlay": overlay}.get
    merged = resolve_imports(overlay, loader=loader)
    merged_curies = {c.curie for c in merged.classes}
    assert {"t:Thing", "t:Sub", "o:Extra"} <= merged_curies
    assert [p for p in merged.data_properties if p.curie == "t:slug"][0].label == "slug overridden"
    # overlay 引用 core 的类，在合并视图上校验通过
    assert validate_schema(overlay, loader=loader).ok


def test_resolve_imports_unknown_dependency_raises() -> None:
    schema = _minimal()
    schema.imports = ["ghost"]
    with pytest.raises(ValueError, match="unknown import"):
        resolve_imports(schema, loader={}.get)


def test_resolve_imports_cycle_raises() -> None:
    a = _minimal(id_="a")
    a.imports = ["b"]
    b = _minimal(id_="b")
    b.imports = ["a"]
    loader = {"a": a, "b": b}.get
    with pytest.raises(ValueError, match="circular import"):
        resolve_imports(a, loader=loader)


def _store(schema_id: str = "t", version: str = "1.0.0") -> InstanceStore:
    return InstanceStore(id="s", ontology_ref=f"{schema_id}@{version}")


def test_store_valid_passes_with_subclass_domain() -> None:
    schema = _minimal()
    store = _store()
    store.individuals = [
        Individual(curie="t:sub1", types=["t:Sub"], data_assertions={"t:slug": ["x"]}),
        Individual(curie="t:thing1", types=["t:Thing"], object_assertions={"t:rel": ["t:sub1"]}),
    ]
    report = validate_store(store, loader={"t": schema}.get)
    assert report.ok, [e.model_dump() for e in report.errors]


def test_onto040_version_mismatch() -> None:
    schema = _minimal()
    store = _store(version="9.9.9")
    assert "ONTO-040" in codes(validate_store(store, loader={"t": schema}.get))


def test_onto040_unknown_schema() -> None:
    store = _store(schema_id="ghost")
    assert "ONTO-040" in codes(validate_store(store, loader={"t": _minimal()}.get))


def test_onto010_unknown_type() -> None:
    schema = _minimal()
    store = _store()
    store.individuals = [Individual(curie="t:x", types=["t:Ghost"])]
    assert "ONTO-010" in codes(validate_store(store, loader={"t": schema}.get))


def test_onto011_undeclared_assertion_property() -> None:
    schema = _minimal()
    store = _store()
    store.individuals = [Individual(curie="t:x", types=["t:Thing"], data_assertions={"t:nope": ["v"]})]
    assert "ONTO-011" in codes(validate_store(store, loader={"t": schema}.get))


def test_onto020_domain_violation() -> None:
    schema = _minimal()
    schema.classes.append(OntClass(curie="t:Other", label="Other"))
    store = _store()
    store.individuals = [
        Individual(curie="t:other1", types=["t:Other"], object_assertions={"t:rel": ["t:x"]}),
        Individual(curie="t:x", types=["t:Thing"]),
    ]
    # t:rel domain=t:Thing，但主体只有 t:Other 类型 → 违反
    assert "ONTO-020" in codes(validate_store(store, loader={"t": schema}.get))


def test_onto020_range_violation_and_missing_type() -> None:
    schema = _minimal()
    schema.classes.append(OntClass(curie="t:Other", label="Other"))
    store = _store()
    store.individuals = [
        Individual(curie="t:thing1", types=["t:Thing"], object_assertions={"t:rel": ["t:other1"]}),
        Individual(curie="t:other1", types=["t:Other"]),
    ]
    report = validate_store(store, loader={"t": schema}.get)
    assert "ONTO-020" in codes(report)  # range=t:Thing 但目标是 t:Other


def test_onto021_dangling_object_reference() -> None:
    schema = _minimal()
    store = _store()
    store.individuals = [
        Individual(curie="t:thing1", types=["t:Thing"], object_assertions={"t:rel": ["t:ghost"]})
    ]
    assert "ONTO-021" in codes(validate_store(store, loader={"t": schema}.get))


def test_onto020_literal_type_mismatch() -> None:
    schema = _minimal()
    store = _store()
    store.individuals = [
        Individual(curie="t:x", types=["t:Thing"], data_assertions={"t:count": ["not-a-number"]})
    ]
    schema.data_properties.append(
        DataProperty(curie="t:count", label="count", domain="t:Thing", range="integer")
    )
    assert "ONTO-020" in codes(validate_store(store, loader={"t": schema}.get))


def test_onto030_undeclared_prefix_in_assertion() -> None:
    schema = _minimal()
    store = _store()
    store.individuals = [Individual(curie="t:x", types=["t:Thing"], data_assertions={"nope:x": ["v"]})]
    assert "ONTO-030" in codes(validate_store(store, loader={"t": schema}.get))
