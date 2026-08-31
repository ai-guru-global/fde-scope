"""本体数据模型：TBox（OntologySchema）+ ABox（InstanceStore）。

CURIE 纪律：所有跨元素引用一律 ``prefix:local``，前缀必须在 schema 的
namespaces 表中声明（校验 ONTO-030）。TBox 含 SKOS 概念体系
（ConceptScheme/Concept），用于分类法（skills 四类、corpus 类目）。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

DataRange = Literal["string", "integer", "number", "boolean", "datetime", "iri"]

# 数据范围 → JSON-LD / xsd 映射（规格 §6）
XSD_MAP: dict[str, str] = {
    "string": "xsd:string",
    "integer": "xsd:integer",
    "number": "xsd:double",
    "boolean": "xsd:boolean",
    "datetime": "xsd:dateTime",
    "iri": "@id",
}


def parse_curie(curie: str) -> tuple[str, str]:
    """``prefix:local`` → (prefix, local)；非法 CURIE 抛 ValueError。"""
    prefix, sep, local = curie.partition(":")
    if not sep or not prefix or not local or ":" in local:
        raise ValueError(f"invalid CURIE: {curie!r}")
    return prefix, local


class Namespace(BaseModel):
    prefix: str
    iri: str


class OntClass(BaseModel):
    curie: str
    label: str
    label_zh: str | None = None
    comment: str | None = None
    sub_class_of: list[str] = Field(default_factory=list)
    deprecated: bool = False


class ObjectProperty(BaseModel):
    curie: str
    label: str
    domain: str
    range: str  # noqa: A003 — 本体术语，保持 domain/range 命名
    inverse: str | None = None
    sub_property_of: str | None = None


class DataProperty(BaseModel):
    curie: str
    label: str
    domain: str
    range: DataRange = "string"  # noqa: A003


class Concept(BaseModel):
    curie: str
    label: str
    label_zh: str | None = None
    broader: list[str] = Field(default_factory=list)  # skos:broader
    match_keywords: list[str] = Field(default_factory=list)  # P2 规则抽取用，不进 JSON-LD
    deprecated: bool = False


class ConceptScheme(BaseModel):
    curie: str
    label: str
    label_zh: str | None = None
    concepts: list[Concept] = Field(default_factory=list)


class OntologySchema(BaseModel):
    id: str
    version: str
    base_iri: str
    imports: list[str] = Field(default_factory=list)  # 依赖的 TBox id（overlay 机制）
    namespaces: list[Namespace] = Field(default_factory=list)
    classes: list[OntClass] = Field(default_factory=list)
    object_properties: list[ObjectProperty] = Field(default_factory=list)
    data_properties: list[DataProperty] = Field(default_factory=list)
    concept_schemes: list[ConceptScheme] = Field(default_factory=list)

    def ns_iri(self, prefix: str) -> str | None:
        for ns in self.namespaces:
            if ns.prefix == prefix:
                return ns.iri
        return None

    def expand(self, curie: str) -> str:
        """CURIE → 绝对 IRI；前缀未声明抛 ValueError。"""
        prefix, local = parse_curie(curie)
        iri = self.ns_iri(prefix)
        if iri is None:
            raise ValueError(f"undeclared prefix: {prefix!r} (curie {curie!r})")
        return iri + local


class Individual(BaseModel):
    curie: str
    types: list[str] = Field(default_factory=list)
    object_assertions: dict[str, list[str]] = Field(default_factory=dict)
    data_assertions: dict[str, list[Any]] = Field(default_factory=dict)


class InstanceStore(BaseModel):
    id: str
    ontology_ref: str  # "<schema-id>@<version>"
    namespace: str | None = None
    individuals: list[Individual] = Field(default_factory=list)
