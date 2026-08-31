"""JSON-LD 导出：结构、双语 language map、确定性、CURIE 展开。"""

from __future__ import annotations

import json

import pytest

from fde_scope.ontology.jsonld import schema_to_jsonld, store_to_jsonld
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


def _schema() -> OntologySchema:
    return OntologySchema(
        id="t",
        version="1.0.0",
        base_iri="https://example.com/o/",
        namespaces=[Namespace(prefix="t", iri="https://example.com/o/t#")],
        classes=[
            OntClass(curie="t:Thing", label="Thing", label_zh="东西"),
            OntClass(curie="t:Sub", label="Sub", sub_class_of=["t:Thing"]),
        ],
        object_properties=[ObjectProperty(curie="t:rel", label="rel", domain="t:Thing", range="t:Thing")],
        data_properties=[DataProperty(curie="t:slug", label="slug", domain="t:Thing")],
        concept_schemes=[
            ConceptScheme(
                curie="t:CatScheme",
                label="Categories",
                concepts=[Concept(curie="t:cat-a", label="a", broader=[])],
            )
        ],
    )


def test_schema_export_structure() -> None:
    doc = schema_to_jsonld(_schema())
    assert doc["@type"] == "owl:Ontology"
    assert doc["owl:versionInfo"] == "1.0.0"
    assert doc["@id"] == "https://example.com/o/t/1.0.0"
    ctx = doc["@context"]
    assert ctx["t"] == "https://example.com/o/t#"
    assert ctx["rdfs"]["@container"] == "@language"  # 双语 label 走 language map
    nodes = {n["@id"]: n for n in doc["@graph"]}
    thing = nodes["https://example.com/o/t#Thing"]
    assert thing["@type"] == "rdfs:Class"
    assert thing["rdfs:label"] == {"en": "Thing", "zh": "东西"}
    assert nodes["https://example.com/o/t#Sub"]["rdfs:subClassOf"] == [
        {"@id": "https://example.com/o/t#Thing"}
    ]
    assert nodes["https://example.com/o/t#rel"]["rdfs:range"] == {"@id": "https://example.com/o/t#Thing"}
    assert nodes["https://example.com/o/t#slug"]["rdfs:range"] == {
        "@id": "http://www.w3.org/2001/XMLSchema#string"
    }
    cat = nodes["https://example.com/o/t#cat-a"]
    assert cat["@type"] == "skos:Concept"
    assert cat["skos:inScheme"] == {"@id": "https://example.com/o/t#CatScheme"}


def test_schema_export_deterministic() -> None:
    a = json.dumps(schema_to_jsonld(_schema()), sort_keys=True, ensure_ascii=False)
    b = json.dumps(schema_to_jsonld(_schema()), sort_keys=True, ensure_ascii=False)
    assert a == b


def test_store_export_expands_curies_and_literals() -> None:
    schema = _schema()
    store = InstanceStore(
        id="s",
        ontology_ref="t@1.0.0",
        individuals=[
            Individual(
                curie="t:one",
                types=["t:Sub"],
                object_assertions={"t:rel": ["t:one"]},
                data_assertions={"t:slug": ["hello", 1]},
            )
        ],
    )
    doc = store_to_jsonld(store, schema)
    assert doc["@id"] == "https://example.com/o/stores/s"
    (node,) = doc["@graph"]
    assert node["@id"] == "https://example.com/o/t#one"
    assert node["@type"] == ["https://example.com/o/t#Sub"]
    assert node["https://example.com/o/t#rel"] == [{"@id": "https://example.com/o/t#one"}]
    assert node["https://example.com/o/t#slug"] == ["hello", 1]


def test_store_export_undeclared_prefix_raises() -> None:
    store = InstanceStore(
        id="s",
        ontology_ref="t@1.0.0",
        individuals=[Individual(curie="x:one", types=["t:Thing"])],
    )
    with pytest.raises(ValueError, match="undeclared prefix"):
        store_to_jsonld(store, _schema())
