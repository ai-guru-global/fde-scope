"""ontology models：CURIE 解析/展开、模型 round-trip、字段约束。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fde_scope.ontology.models import (
    XSD_MAP,
    DataProperty,
    Individual,
    InstanceStore,
    Namespace,
    ObjectProperty,
    OntClass,
    OntologySchema,
    parse_curie,
)


def _schema() -> OntologySchema:
    return OntologySchema(
        id="t",
        version="1.0.0",
        base_iri="https://example.com/o/",
        namespaces=[Namespace(prefix="t", iri="https://example.com/o/t#")],
        classes=[OntClass(curie="t:Thing", label="Thing")],
        object_properties=[
            ObjectProperty(curie="t:part_of", label="part of", domain="t:Thing", range="t:Thing")
        ],
        data_properties=[DataProperty(curie="t:slug", label="slug", domain="t:Thing")],
    )


def test_parse_curie_ok_and_invalid() -> None:
    assert parse_curie("fde:Phase") == ("fde", "Phase")
    with pytest.raises(ValueError):
        parse_curie("no-colon")
    with pytest.raises(ValueError):
        parse_curie(":empty-prefix")
    with pytest.raises(ValueError):
        parse_curie("empty-local:")
    with pytest.raises(ValueError):
        parse_curie("a:b:c")


def test_expand_resolves_and_rejects_undeclared() -> None:
    schema = _schema()
    assert schema.expand("t:Thing") == "https://example.com/o/t#Thing"
    with pytest.raises(ValueError):
        schema.expand("nope:Thing")


def test_schema_round_trip() -> None:
    schema = _schema()
    assert OntologySchema.model_validate(schema.model_dump(mode="json")) == schema


def test_store_defaults_and_round_trip() -> None:
    store = InstanceStore(id="demo", ontology_ref="t@1.0.0")
    assert store.individuals == []
    store.individuals.append(
        Individual(
            curie="t:one",
            types=["t:Thing"],
            object_assertions={"t:part_of": ["t:one"]},
            data_assertions={"t:slug": ["a"]},
        )
    )
    assert InstanceStore.model_validate(store.model_dump(mode="json")) == store


def test_data_property_range_is_closed_enum() -> None:
    with pytest.raises(ValidationError):
        DataProperty(curie="t:x", label="x", domain="t:Thing", range="float")
    assert XSD_MAP["number"] == "xsd:double"


def test_multi_inheritance_and_deprecated_allowed() -> None:
    c = OntClass(curie="t:Both", label="b", sub_class_of=["t:Thing", "t:Other"], deprecated=True)
    assert c.sub_class_of == ["t:Thing", "t:Other"]
    assert c.deprecated is True
