"""Mermaid 概念模型图导出：继承/关联/成员，确定性。"""

from __future__ import annotations

from fde_scope.ontology.diagram import schema_to_mermaid
from fde_scope.ontology.models import DataProperty, ObjectProperty, OntClass, OntologySchema


def _schema() -> OntologySchema:
    return OntologySchema(
        id="t",
        version="1.0.0",
        base_iri="https://example.com/o/",
        classes=[
            OntClass(curie="t:Thing", label="Thing", label_zh="东西"),
            OntClass(curie="t:Sub", label="Sub", label_zh="子类", sub_class_of=["t:Thing"]),
        ],
        object_properties=[ObjectProperty(curie="t:rel", label="rel", domain="t:Sub", range="t:Thing")],
        data_properties=[DataProperty(curie="t:slug", label="slug", domain="t:Sub", range="integer")],
    )


def test_mermaid_contains_all_structure() -> None:
    text = schema_to_mermaid(_schema())
    assert text.startswith("classDiagram")
    assert 'class Sub["Sub·子类"]' in text  # 双语显示名
    assert "Thing <|-- Sub" in text  # 继承边
    assert "Sub --> Thing : rel" in text  # 对象属性关联
    assert "Sub : +slug(integer)" in text  # 数据属性成员


def test_mermaid_is_deterministic() -> None:
    assert schema_to_mermaid(_schema()) == schema_to_mermaid(_schema())
