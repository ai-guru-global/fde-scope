"""JSON-LD 1.1 导出：schema 与 instance store（规格 §9）。

确定性：返回 dict 的键序稳定，序列化统一用
``json.dumps(..., ensure_ascii=False, indent=2, sort_keys=True)``。
双语 label 走 JSON-LD language map（@context 中 rdfs:label/skos:prefLabel
声明为 @container: @language）。match_keywords 等操作性元数据不进 JSON-LD。
"""

from __future__ import annotations

from typing import Any

from .models import XSD_MAP, InstanceStore, OntologySchema, parse_curie

_STANDARD: dict[str, str] = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "dcterms": "http://purl.org/dc/terms/",
}


def _context(schema: OntologySchema) -> dict[str, Any]:
    ctx: dict[str, Any] = {ns.prefix: ns.iri for ns in schema.namespaces}
    for prefix, iri in _STANDARD.items():
        ctx.setdefault(prefix, iri)
    # rdfs 前缀项声明为带 @container 的 term definition（双语 label 的 language
    # map 挂在 rdfs 前缀上；@prefix: true 保持 rdfs:* 紧凑形式的展开）。
    ctx["rdfs"] = {
        "@id": "http://www.w3.org/2000/01/rdf-schema#",
        "@prefix": True,
        "@container": "@language",
    }
    ctx["skos:prefLabel"] = {
        "@id": "http://www.w3.org/2004/02/skos/core#prefLabel",
        "@container": "@language",
    }
    ctx["rdfs:comment"] = {"@id": "http://www.w3.org/2000/01/rdf-schema#comment"}
    return ctx


def _expand(schema: OntologySchema, curie: str) -> str:
    prefix, local = parse_curie(curie)
    iri = schema.ns_iri(prefix) or _STANDARD.get(prefix)
    if iri is None:
        raise ValueError(f"undeclared prefix: {prefix!r} (curie {curie!r})")
    return iri + local


def _labels(label: str, label_zh: str | None) -> dict[str, str]:
    labels = {"en": label}
    if label_zh:
        labels["zh"] = label_zh
    return labels


def schema_to_jsonld(schema: OntologySchema) -> dict[str, Any]:
    graph: list[dict[str, Any]] = []
    for c in schema.classes:
        node: dict[str, Any] = {
            "@id": _expand(schema, c.curie),
            "@type": "rdfs:Class",
            "rdfs:label": _labels(c.label, c.label_zh),
        }
        if c.comment:
            node["rdfs:comment"] = c.comment
        if c.sub_class_of:
            node["rdfs:subClassOf"] = [{"@id": _expand(schema, parent)} for parent in c.sub_class_of]
        if c.deprecated:
            node["owl:deprecated"] = True
        graph.append(node)
    for p in schema.object_properties:
        node = {
            "@id": _expand(schema, p.curie),
            "@type": "rdf:Property",
            "rdfs:label": _labels(p.label, None),
            "rdfs:domain": {"@id": _expand(schema, p.domain)},
            "rdfs:range": {"@id": _expand(schema, p.range)},
        }
        if p.inverse:
            node["owl:inverseOf"] = {"@id": _expand(schema, p.inverse)}
        if p.sub_property_of:
            node["rdfs:subPropertyOf"] = {"@id": _expand(schema, p.sub_property_of)}
        graph.append(node)
    for p in schema.data_properties:
        graph.append(
            {
                "@id": _expand(schema, p.curie),
                "@type": "rdf:Property",
                "rdfs:label": _labels(p.label, None),
                "rdfs:domain": {"@id": _expand(schema, p.domain)},
                "rdfs:range": {"@id": _expand(schema, XSD_MAP[p.range])},
            }
        )
    for scheme in schema.concept_schemes:
        graph.append(
            {
                "@id": _expand(schema, scheme.curie),
                "@type": "skos:ConceptScheme",
                "rdfs:label": _labels(scheme.label, scheme.label_zh),
            }
        )
        for con in scheme.concepts:
            cnode: dict[str, Any] = {
                "@id": _expand(schema, con.curie),
                "@type": "skos:Concept",
                "skos:prefLabel": _labels(con.label, con.label_zh),
                "skos:inScheme": {"@id": _expand(schema, scheme.curie)},
            }
            if con.broader:
                cnode["skos:broader"] = [{"@id": _expand(schema, b)} for b in con.broader]
            if con.deprecated:
                cnode["owl:deprecated"] = True
            graph.append(cnode)
    return {
        "@context": _context(schema),
        "@id": f"{schema.base_iri}{schema.id}/{schema.version}",
        "@type": "owl:Ontology",
        "owl:versionInfo": schema.version,
        "@graph": graph,
    }


def store_to_jsonld(store: InstanceStore, schema: OntologySchema) -> dict[str, Any]:
    """ABox 导出：CURIE 全部展开为绝对 IRI（个体/类型/属性键/对象目标）。"""
    graph: list[dict[str, Any]] = []
    for ind in store.individuals:
        node: dict[str, Any] = {"@id": _expand(schema, ind.curie)}
        if ind.types:
            node["@type"] = [_expand(schema, t) for t in ind.types]
        for prop, targets in ind.object_assertions.items():
            node[_expand(schema, prop)] = [{"@id": _expand(schema, t)} for t in targets]
        for prop, values in ind.data_assertions.items():
            node[_expand(schema, prop)] = list(values)
        graph.append(node)
    return {
        "@context": _context(schema),
        "@id": f"{schema.base_iri}stores/{store.id}",
        "rdfs:label": store.id,
        "@graph": graph,
    }
