"""SHACL-lite 校验器：每个错误码至少一正一反，import 合并与闭环词表。"""

from __future__ import annotations

import pytest

from fde_scope.ontology.models import (
    DataProperty,
    Namespace,
    ObjectProperty,
    OntClass,
    OntologySchema,
)
from fde_scope.ontology.validation import resolve_imports, validate_schema


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
