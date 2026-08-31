"""SHACL-lite 校验器：返回 ValidationReport，绝不抛异常中断主流程。

错误码契约（规格 §8）：
- ONTO-001  sub_class_of 层级含环
- ONTO-002  sub_property_of / inverse 引用图含环
- ONTO-012  skos:broader 概念引用图含环
- ONTO-010  引用了未声明的类（sub_class_of / domain / range / rdf:type，封闭词表）
- ONTO-011  引用了未声明的属性或概念（断言 / sub_property_of / inverse / skos:broader）
- ONTO-020  对象/数据断言违反属性 domain/range
- ONTO-021  对象断言指向不存在的个体
- ONTO-030  CURIE 非法或前缀未声明
- ONTO-040  store 的 ontology_ref 与 TBox id/version 不匹配

相对规格 §8 的偏差：未声明的 sub_property_of / inverse 目标统一归 ONTO-011
（未声明词汇引用），ONTO-002 仅保留环检测。

overlay 的校验在 resolve_imports 的合并视图上做；import 成环/缺依赖是装配
错误，resolve_imports 以 ValueError 报告（不属于数据校验报告的范畴）。
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, Field

from .models import (
    ConceptScheme,
    DataProperty,
    Individual,
    InstanceStore,
    Namespace,
    ObjectProperty,
    OntClass,
    OntologySchema,
    parse_curie,
)

Loader = Callable[[str], OntologySchema | None]


class ValidationIssue(BaseModel):
    code: str
    subject: str
    message: str


class ValidationReport(BaseModel):
    ok: bool = True
    errors: list[ValidationIssue] = Field(default_factory=list)

    def add(self, code: str, subject: str, message: str) -> None:
        self.ok = False
        self.errors.append(ValidationIssue(code=code, subject=subject, message=message))


def resolve_imports(schema: OntologySchema, loader: Loader) -> OntologySchema:
    """按 imports 深度优先合并出校验视图；后访问者（自身）声明优先。"""
    merged_ns: dict[str, str] = {}
    classes: dict[str, OntClass] = {}
    obj_props: dict[str, ObjectProperty] = {}
    data_props: dict[str, DataProperty] = {}
    schemes: dict[str, ConceptScheme] = {}

    def visit(cur: OntologySchema, visiting: set[str]) -> None:
        if cur.id in visiting:
            chain = " -> ".join([*visiting, cur.id])
            raise ValueError(f"circular import: {chain}")
        visiting = {*visiting, cur.id}
        for dep_id in cur.imports:
            dep = loader(dep_id)
            if dep is None:
                raise ValueError(f"unknown import: {dep_id!r} (required by {cur.id!r})")
            visit(dep, visiting)
        for ns in cur.namespaces:
            merged_ns[ns.prefix] = ns.iri
        for c in cur.classes:
            classes[c.curie] = c
        for op in cur.object_properties:
            obj_props[op.curie] = op
        for dp in cur.data_properties:
            data_props[dp.curie] = dp
        for s in cur.concept_schemes:
            schemes[s.curie] = s

    visit(schema, set())
    return OntologySchema(
        id=schema.id,
        version=schema.version,
        base_iri=schema.base_iri,
        imports=schema.imports,
        namespaces=[Namespace(prefix=p, iri=i) for p, i in merged_ns.items()],
        classes=list(classes.values()),
        object_properties=list(obj_props.values()),
        data_properties=list(data_props.values()),
        concept_schemes=list(schemes.values()),
    )


def _class_parents(merged: OntologySchema) -> dict[str, set[str]]:
    return {c.curie: set(c.sub_class_of) for c in merged.classes}


def _ancestors(curie: str, parents: dict[str, set[str]]) -> set[str]:
    seen: set[str] = set()
    stack = list(parents.get(curie, ()))
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(parents.get(cur, ()))
    return seen


def _is_a(type_curie: str, expected: str, parents: dict[str, set[str]]) -> bool:
    return type_curie == expected or expected in _ancestors(type_curie, parents)


def validate_schema(schema: OntologySchema, loader: Loader) -> ValidationReport:
    report = ValidationReport()
    merged = resolve_imports(schema, loader)
    class_curies = {c.curie for c in merged.classes}
    obj_prop_curies = {p.curie for p in merged.object_properties}

    def check_curie(curie: str, subject: str, kind: str) -> bool:
        try:
            prefix, _ = parse_curie(curie)
        except ValueError:
            report.add("ONTO-030", subject, f"malformed CURIE {curie!r} ({kind})")
            return False
        if merged.ns_iri(prefix) is None:
            report.add("ONTO-030", subject, f"undeclared prefix {prefix!r} in {curie!r} ({kind})")
            return False
        return True

    def check_class_ref(target: str, subject: str, kind: str) -> None:
        if not check_curie(target, subject, kind):
            return
        if target not in class_curies:
            report.add("ONTO-010", subject, f"{kind} {target!r} is not a declared class")

    for c in merged.classes:
        check_curie(c.curie, c.curie, "class curie")
        for parent in c.sub_class_of:
            check_class_ref(parent, c.curie, "sub_class_of")

    for op in merged.object_properties:
        check_curie(op.curie, op.curie, "property curie")
        check_class_ref(op.domain, op.curie, "domain")
        check_class_ref(op.range, op.curie, "range")
        if op.sub_property_of is not None and op.sub_property_of not in obj_prop_curies:
            report.add(
                "ONTO-011",
                op.curie,
                f"sub_property_of target {op.sub_property_of!r} is not a declared object property",
            )
        if op.inverse is not None and op.inverse not in obj_prop_curies:
            report.add(
                "ONTO-011", op.curie, f"inverse target {op.inverse!r} is not a declared object property"
            )
    for dp in merged.data_properties:
        check_curie(dp.curie, dp.curie, "property curie")
        check_class_ref(dp.domain, dp.curie, "domain")

    # ONTO-001：sub_class_of 环（DFS 回到起点）
    parents = _class_parents(merged)
    for start in parents:
        seen: set[str] = set()
        stack = [*parents[start]]
        while stack:
            cur = stack.pop()
            if cur == start:
                report.add("ONTO-001", start, "sub_class_of hierarchy contains a cycle")
                break
            if cur in seen or cur not in parents:
                continue
            seen.add(cur)
            stack.extend(parents[cur])

    # ONTO-002：sub_property_of / inverse 环
    prop_links = {p.curie: {t for t in (p.sub_property_of, p.inverse) if t} for p in merged.object_properties}
    for start, links in prop_links.items():
        seen = set()
        stack = [*links]
        while stack:
            cur = stack.pop()
            if cur == start:
                report.add("ONTO-002", start, "sub_property_of/inverse graph contains a cycle")
                break
            if cur in seen or cur not in prop_links:
                continue
            seen.add(cur)
            stack.extend(prop_links[cur])

    # SKOS 概念体系：broader 目标封闭词表
    concept_curies = {con.curie for s in merged.concept_schemes for con in s.concepts}
    for s in merged.concept_schemes:
        check_curie(s.curie, s.curie, "concept scheme curie")
        for con in s.concepts:
            check_curie(con.curie, con.curie, "concept curie")
            for b in con.broader:
                if b not in concept_curies:
                    report.add(
                        "ONTO-011",
                        con.curie,
                        f"skos:broader target {b!r} is not a declared concept",
                    )

    # ONTO-012：skos:broader 概念环（沿父方向 DFS 回到起点；跨 scheme 合并）
    broader_map: dict[str, set[str]] = {}
    for s in merged.concept_schemes:
        for con in s.concepts:
            broader_map.setdefault(con.curie, set()).update(con.broader)
    for start, links in broader_map.items():
        seen = set()
        stack = [*links]
        while stack:
            cur = stack.pop()
            if cur == start:
                report.add("ONTO-012", start, "skos:broader concept graph contains a cycle")
                break
            if cur in seen or cur not in broader_map:
                continue
            seen.add(cur)
            stack.extend(broader_map[cur])
    return report


_LITERAL_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "datetime": lambda v: isinstance(v, str),
    "iri": lambda v: isinstance(v, str),
}


def validate_store(store: InstanceStore, loader: Loader) -> ValidationReport:
    """ABox 校验：先解析 ontology_ref（ONTO-040），再在合并视图上查断言。"""
    report = ValidationReport()
    ref_id, sep, ref_ver = store.ontology_ref.partition("@")
    schema = loader(ref_id) if sep else None
    if schema is None:
        report.add(
            "ONTO-040", store.id, f"ontology_ref {store.ontology_ref!r} does not resolve to a known schema"
        )
        return report
    if ref_ver != schema.version:
        report.add(
            "ONTO-040",
            store.id,
            f"store targets {store.ontology_ref!r} but schema is {schema.id}@{schema.version}",
        )
        return report

    merged = resolve_imports(schema, loader)
    class_curies = {c.curie for c in merged.classes}
    obj_props = {p.curie: p for p in merged.object_properties}
    data_props = {p.curie: p for p in merged.data_properties}
    parents = _class_parents(merged)
    individuals = {i.curie: i for i in store.individuals}

    def check_property_curie(prop: str, subject: str) -> bool:
        try:
            prefix, _ = parse_curie(prop)
        except ValueError:
            report.add("ONTO-030", subject, f"malformed property CURIE {prop!r}")
            return False
        if merged.ns_iri(prefix) is None:
            report.add("ONTO-030", subject, f"undeclared prefix {prefix!r} in property {prop!r}")
            return False
        return True

    for ind in store.individuals:
        for t in ind.types:
            try:
                prefix, _ = parse_curie(t)
            except ValueError:
                report.add("ONTO-030", ind.curie, f"malformed type CURIE {t!r}")
                continue
            if merged.ns_iri(prefix) is None:
                report.add("ONTO-030", ind.curie, f"undeclared prefix {prefix!r} in type {t!r}")
                continue
            if t not in class_curies:
                report.add("ONTO-010", ind.curie, f"type {t!r} is not a declared class")

        def domain_ok(individual: Individual, expected: str, subject: str, side: str) -> None:
            if not individual.types:
                return  # 无类型个体不做 is-a 判定（类型封闭性已由 ONTO-010 覆盖）
            if not any(_is_a(t, expected, parents) for t in individual.types):
                report.add(
                    "ONTO-020", subject, f"{side}: types {individual.types} do not satisfy {expected!r}"
                )

        for prop, targets in ind.object_assertions.items():
            if not check_property_curie(prop, ind.curie):
                continue
            op = obj_props.get(prop)
            if op is None:
                report.add("ONTO-011", ind.curie, f"object assertion uses undeclared property {prop!r}")
                continue
            domain_ok(ind, op.domain, ind.curie, f"domain of {prop}")
            for target in targets:
                target_ind = individuals.get(target)
                if target_ind is None:
                    report.add("ONTO-021", ind.curie, f"{prop} target {target!r} does not exist in store")
                    continue
                if not target_ind.types:
                    report.add(
                        "ONTO-020",
                        ind.curie,
                        f"{prop} target {target!r} has no declared type (range {op.range!r} unverifiable)",
                    )
                else:
                    domain_ok(target_ind, op.range, ind.curie, f"range of {prop} (target {target})")

        for prop, values in ind.data_assertions.items():
            if not check_property_curie(prop, ind.curie):
                continue
            dp = data_props.get(prop)
            if dp is None:
                report.add("ONTO-011", ind.curie, f"data assertion uses undeclared property {prop!r}")
                continue
            domain_ok(ind, dp.domain, ind.curie, f"domain of {prop}")
            for value in values:
                if not _LITERAL_CHECKS[dp.range](value):
                    report.add(
                        "ONTO-020", ind.curie, f"{prop} value {value!r} does not match range {dp.range!r}"
                    )
    return report
