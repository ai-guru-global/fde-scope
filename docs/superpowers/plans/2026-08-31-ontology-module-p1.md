# Ontology 模块 P1（核心）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 fde-scope 的本体语义层 P1：TBox/ABox 模型、SHACL-lite 校验器、JSON-LD 导出、内置 FDE 基础本体 + ISA-95 工业 overlay、CLI 与 Web 只读路由、文档。

**Architecture:** 新建零依赖包 `fde_scope/ontology/`（pydantic v2 + pyyaml + 标准库，无 agentscope）；内置本体为包内只读 YAML 数据文件，用户 schema/store 在 `.fde_scope/ontology/{schemas,stores}` 工作区，全部写入走 `fsutil.atomic_write_text`。规格：`docs/superpowers/specs/2026-08-31-ontology-module-design.md`。

**Tech Stack:** Python ≥3.11、pydantic v2、pyyaml、typer + rich（CLI）、FastAPI（web）、pytest。

**范围说明：** 规格含 P1/P2/P3 三期。P2（corpus 集成）与 P3（skills 集成）在 P1 落地后**另出计划**（其集成点依赖 P1 实际 API），本计划只覆盖 P1。

**执行前检查（Pre-flight）：** 工作区存在与本计划无关的未提交改动（`fde_scope/web/app.py`、`docs/architecture.md`、`README.md` 等）。Task 8 会修改 `web/app.py`、Task 9 会修改 `docs/architecture.md`——提交这些文件会把既有未提交改动一并带上。执行前先与用户确认处置方式（先提交/先分离/一并带上）。

---

## File Structure（P1 全量）

```
fde_scope/ontology/
├── __init__.py        # 包导出（Task 1 建，Task 4/5 补导出）
├── models.py          # TBox/ABox 模型 + CURIE 工具（Task 1）
├── validation.py      # SHACL-lite 校验器（Task 2/3）
├── jsonld.py          # JSON-LD 1.1 导出（Task 4）
├── store.py           # 内置 schema + 工作区存储（Task 5）
└── data/
    ├── fde_core.yaml      # FDE 基础 TBox（Task 6）
    └── mfg_overlay.yaml   # ISA-95 overlay，imports fde-core（Task 6）
fde_scope/paths.py                 # +ontology_dir()（Task 1）
fde_scope/cli.py                   # +ontology 子应用（Task 7）
fde_scope/web/app.py               # +3 只读 GET 路由（Task 8）
tests/test_ontology_models.py      # Task 1
tests/test_ontology_validation.py  # Task 2/3
tests/test_ontology_jsonld.py      # Task 4
tests/test_ontology_store.py       # Task 5/6
tests/test_ontology_cli.py         # Task 7
tests/test_ontology_web.py         # Task 8
docs/ontology.md                   # Task 9
docs/architecture.md               # Task 9（增补一节）
```

---

### Task 1: 包骨架 + TBox/ABox 模型

**Files:**
- Create: `fde_scope/ontology/__init__.py`
- Create: `fde_scope/ontology/models.py`
- Modify: `fde_scope/paths.py`（追加 `ontology_dir`）
- Test: `tests/test_ontology_models.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_ontology_models.py`：

```python
"""ontology models：CURIE 解析/展开、模型 round-trip、字段约束。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fde_scope.ontology.models import (
    DataProperty,
    Individual,
    InstanceStore,
    Namespace,
    ObjectProperty,
    OntClass,
    OntologySchema,
    XSD_MAP,
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
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_ontology_models.py -q`
Expected: FAIL（`ModuleNotFoundError: fde_scope.ontology`）

- [ ] **Step 3: 实现**

创建 `fde_scope/ontology/__init__.py`：

```python
"""本体语义层（TBox/ABox + SHACL-lite 校验 + JSON-LD 导出）。

零新依赖：pydantic + pyyaml + 标准库；不导入 agentscope（零配置可跑）。
"""

from .jsonld import schema_to_jsonld, store_to_jsonld
from .models import (
    Concept,
    ConceptScheme,
    DataProperty,
    Individual,
    InstanceStore,
    Namespace,
    ObjectProperty,
    OntClass,
    OntologySchema,
    XSD_MAP,
    parse_curie,
)
from .store import OntologyStore
from .validation import (
    ValidationIssue,
    ValidationReport,
    resolve_imports,
    validate_schema,
    validate_store,
)

__all__ = [
    "Concept",
    "ConceptScheme",
    "DataProperty",
    "Individual",
    "InstanceStore",
    "Namespace",
    "ObjectProperty",
    "OntClass",
    "OntologySchema",
    "OntologyStore",
    "ValidationIssue",
    "ValidationReport",
    "XSD_MAP",
    "parse_curie",
    "resolve_imports",
    "schema_to_jsonld",
    "store_to_jsonld",
    "validate_schema",
    "validate_store",
]
```

创建 `fde_scope/ontology/models.py`：

```python
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
```

修改 `fde_scope/paths.py`，在 `skills_export_dir` 之后追加：

```python
def ontology_dir(create: bool = False) -> Path:
    """``<root>/.fde_scope/ontology`` — schemas/ + stores/（本体语义层）。"""
    return _under_root("ontology", create=create)
```

注意：`__init__.py` 引用的 `jsonld.py` / `store.py` / `validation.py` 在后续 Task 才创建——本 Task 先创建**空占位**会导致导入错误。因此本 Task 的 `__init__.py` 只写文档字符串，导出语句随 Task 2/4/5 分步补全：

```python
"""本体语义层（TBox/ABox + SHACL-lite 校验 + JSON-LD 导出）。

零新依赖：pydantic + pyyaml + 标准库；不导入 agentscope（零配置可跑）。
"""
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_ontology_models.py -q`
Expected: 6 passed

- [ ] **Step 5: 提交**

```bash
git add fde_scope/ontology/__init__.py fde_scope/ontology/models.py fde_scope/paths.py tests/test_ontology_models.py
git commit -m "feat(ontology): TBox/ABox pydantic models + CURIE discipline + paths.ontology_dir"
```

---

### Task 2: SHACL-lite 校验器 — schema 级 + import 合并

**Files:**
- Create: `fde_scope/ontology/validation.py`
- Modify: `fde_scope/ontology/__init__.py`（补 validation 导出）
- Test: `tests/test_ontology_validation.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_ontology_validation.py`（本 Task 用到的部分；Task 3 在同文件追加 store 级测试）：

```python
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
        object_properties=[
            ObjectProperty(curie="t:rel", label="rel", domain="t:Thing", range="t:Thing")
        ],
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
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_ontology_validation.py -q`
Expected: FAIL（`ModuleNotFoundError: fde_scope.ontology.validation`）

- [ ] **Step 3: 实现 validation.py（schema 部分）**

创建 `fde_scope/ontology/validation.py`：

```python
"""SHACL-lite 校验器：返回 ValidationReport，绝不抛异常中断主流程。

错误码契约（规格 §8）：
- ONTO-001  sub_class_of 层级含环
- ONTO-002  sub_property_of / inverse 引用含环或不存在
- ONTO-010  引用了未声明的类（sub_class_of / domain / range / rdf:type，封闭词表）
- ONTO-011  引用了未声明的属性或概念（断言 / sub_property_of / inverse / skos:broader）
- ONTO-020  对象/数据断言违反属性 domain/range
- ONTO-021  对象断言指向不存在的个体
- ONTO-030  CURIE 非法或前缀未声明
- ONTO-040  store 的 ontology_ref 与 TBox id/version 不匹配

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
            merged_ns.setdefault(ns.prefix, ns.iri)
        for c in cur.classes:
            classes.setdefault(c.curie, c)
        for p in cur.object_properties:
            obj_props.setdefault(p.curie, p)
        for p in cur.data_properties:
            data_props.setdefault(p.curie, p)
        for s in cur.concept_schemes:
            schemes.setdefault(s.curie, s)

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

    for p in merged.object_properties:
        check_curie(p.curie, p.curie, "property curie")
        check_class_ref(p.domain, p.curie, "domain")
        check_class_ref(p.range, p.curie, "range")
        if p.sub_property_of is not None and p.sub_property_of not in obj_prop_curies:
            report.add(
                "ONTO-002",
                p.curie,
                f"sub_property_of target {p.sub_property_of!r} is not a declared object property",
            )
        if p.inverse is not None and p.inverse not in obj_prop_curies:
            report.add(
                "ONTO-002", p.curie, f"inverse target {p.inverse!r} is not a declared object property"
            )
    for p in merged.data_properties:
        check_curie(p.curie, p.curie, "property curie")
        check_class_ref(p.domain, p.curie, "domain")

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
    prop_links = {
        p.curie: {t for t in (p.sub_property_of, p.inverse) if t} for p in merged.object_properties
    }
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
    return report
```

修改 `fde_scope/ontology/__init__.py`，追加：

```python
from .validation import (
    ValidationIssue,
    ValidationReport,
    resolve_imports,
    validate_schema,
)
```

并把 `"ValidationIssue"`, `"ValidationReport"`, `"resolve_imports"`, `"validate_schema"` 加入 `__all__`。

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_ontology_validation.py -q`
Expected: 9 passed

- [ ] **Step 5: 提交**

```bash
git add fde_scope/ontology/validation.py fde_scope/ontology/__init__.py tests/test_ontology_validation.py
git commit -m "feat(ontology): SHACL-lite schema validation + overlay import merge (ONTO-001/002/010/011/030)"
```

---

### Task 3: SHACL-lite 校验器 — store 级

**Files:**
- Modify: `fde_scope/ontology/validation.py`（追加 `validate_store`）
- Test: `tests/test_ontology_validation.py`（追加）

- [ ] **Step 1: 写失败测试**

在 `tests/test_ontology_validation.py` 末尾追加：

```python
from fde_scope.ontology.models import Individual, InstanceStore
from fde_scope.ontology.validation import validate_store


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
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_ontology_validation.py -q`
Expected: FAIL（`ImportError: cannot import name 'validate_store'`）

- [ ] **Step 3: 实现 validate_store**

在 `fde_scope/ontology/validation.py` 末尾追加：

```python
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
            p = obj_props.get(prop)
            if p is None:
                report.add("ONTO-011", ind.curie, f"object assertion uses undeclared property {prop!r}")
                continue
            domain_ok(ind, p.domain, ind.curie, f"domain of {prop}")
            for target in targets:
                target_ind = individuals.get(target)
                if target_ind is None:
                    report.add("ONTO-021", ind.curie, f"{prop} target {target!r} does not exist in store")
                    continue
                if not target_ind.types:
                    report.add(
                        "ONTO-020",
                        ind.curie,
                        f"{prop} target {target!r} has no declared type (range {p.range!r} unverifiable)",
                    )
                else:
                    domain_ok(target_ind, p.range, ind.curie, f"range of {prop} (target {target})")

        for prop, values in ind.data_assertions.items():
            if not check_property_curie(prop, ind.curie):
                continue
            p = data_props.get(prop)
            if p is None:
                report.add("ONTO-011", ind.curie, f"data assertion uses undeclared property {prop!r}")
                continue
            domain_ok(ind, p.domain, ind.curie, f"domain of {prop}")
            for value in values:
                if not _LITERAL_CHECKS[p.range](value):
                    report.add(
                        "ONTO-020", ind.curie, f"{prop} value {value!r} does not match range {p.range!r}"
                    )
    return report
```

同时把 `validate_store` 加入 `__init__.py` 的 validation 导入与 `__all__`。

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_ontology_validation.py -q`
Expected: 19 passed

- [ ] **Step 5: 提交**

```bash
git add fde_scope/ontology/validation.py fde_scope/ontology/__init__.py tests/test_ontology_validation.py
git commit -m "feat(ontology): ABox store validation with domain/range closure (ONTO-010/011/020/021/030/040)"
```

---

### Task 4: JSON-LD 1.1 导出

**Files:**
- Create: `fde_scope/ontology/jsonld.py`
- Modify: `fde_scope/ontology/__init__.py`（补 jsonld 导出）
- Test: `tests/test_ontology_jsonld.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_ontology_jsonld.py`：

```python
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
        object_properties=[
            ObjectProperty(curie="t:rel", label="rel", domain="t:Thing", range="t:Thing")
        ],
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
    assert nodes["https://example.com/o/t#slug"]["rdfs:range"] == {"@id": "http://www.w3.org/2001/XMLSchema#string"}
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
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_ontology_jsonld.py -q`
Expected: FAIL（`ModuleNotFoundError: fde_scope.ontology.jsonld`）

- [ ] **Step 3: 实现 jsonld.py**

创建 `fde_scope/ontology/jsonld.py`：

```python
"""JSON-LD 1.1 导出：schema 与 instance store（规格 §9）。

确定性：返回 dict 的键序稳定，序列化统一用
``json.dumps(..., ensure_ascii=False, indent=2, sort_keys=True)``。
双语 label 走 JSON-LD language map（@context 中 rdfs:label/skos:prefLabel
声明为 @container: @language）。match_keywords 等操作性元数据不进 JSON-LD。
"""

from __future__ import annotations

from typing import Any

from .models import ObjectProperty, OntologySchema, XSD_MAP, parse_curie

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
    ctx["rdfs:label"] = {"@id": "http://www.w3.org/2000/01/rdf-schema#label", "@container": "@language"}
    ctx["skos:prefLabel"] = {"@id": "http://www.w3.org/2004/02/skos/core#prefLabel", "@container": "@language"}
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


def store_to_jsonld(store, schema: OntologySchema) -> dict[str, Any]:
    """ABox 导出：CURIE 全部展开为绝对 IRI（个体/类型/属性键/对象目标）。"""
    from .models import InstanceStore  # 类型标注用（避免循环导入噪音）

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
```

注意：`store_to_jsonld(store, ...)` 的参数类型标注直接写 `store: InstanceStore`（把顶部 `from .models import InstanceStore` 加入 import 块，删除函数体内的局部导入）。最终签名：`def store_to_jsonld(store: InstanceStore, schema: OntologySchema) -> dict[str, Any]:`。

修改 `fde_scope/ontology/__init__.py`：追加 `from .jsonld import schema_to_jsonld, store_to_jsonld`，并把两者加入 `__all__`。

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_ontology_jsonld.py tests/test_ontology_models.py -q`
Expected: 10 passed

- [ ] **Step 5: 提交**

```bash
git add fde_scope/ontology/jsonld.py fde_scope/ontology/__init__.py tests/test_ontology_jsonld.py
git commit -m "feat(ontology): deterministic JSON-LD 1.1 export for TBox and ABox"
```

---

### Task 5: OntologyStore（内置只读 schema + 工作区存储）

**Files:**
- Create: `fde_scope/ontology/store.py`
- Modify: `fde_scope/ontology/__init__.py`（补 OntologyStore 导出）
- Test: `tests/test_ontology_store.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_ontology_store.py`：

```python
"""OntologyStore：内置加载、工作区覆盖优先、原子写、宽容加载。"""

from __future__ import annotations

import os
from pathlib import Path

from fde_scope import paths
from fde_scope.ontology.models import Individual, InstanceStore, OntologySchema
from fde_scope.ontology.store import OntologyStore


def test_default_root_resolves_through_paths() -> None:
    store = OntologyStore()
    assert store.root == paths.ontology_dir()
    assert paths.ontology_dir() == Path(os.environ["FDE_SCOPE_HOME"]) / ".fde_scope" / "ontology"


def test_workspace_schema_round_trip(tmp_path: Path) -> None:
    store = OntologyStore(root=tmp_path)
    schema = OntologySchema(
        id="mine",
        version="0.1.0",
        base_iri="https://example.com/",
        namespaces=[],
    )
    store.save_schema(schema)
    loaded = store.load_schema("mine")
    assert loaded == schema
    assert (tmp_path / "schemas" / "mine.yaml").exists()


def test_workspace_store_round_trip(tmp_path: Path) -> None:
    store = OntologyStore(root=tmp_path)
    inst = InstanceStore(
        id="demo",
        ontology_ref="fde-core@1.0.0",
        individuals=[Individual(curie="ex:one", types=[])],
    )
    store.save_store(inst)
    assert store.load_store("demo") == inst


def test_load_missing_returns_none(tmp_path: Path) -> None:
    store = OntologyStore(root=tmp_path)
    assert store.load_schema("ghost") is None
    assert store.load_store("ghost") is None


def test_corrupt_workspace_file_skipped(tmp_path: Path) -> None:
    store = OntologyStore(root=tmp_path)
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas" / "bad.yaml").write_text("{{{{not yaml", encoding="utf-8")
    assert store.load_schema("bad") is None


def test_list_precedence_workspace_over_builtin(tmp_path: Path) -> None:
    store = OntologyStore(root=tmp_path)
    entries = {e["id"]: e for e in store.list_schemas()}
    assert entries["fde-core"]["origin"] == "builtin"
    override = OntologySchema(id="fde-core", version="9.9.9", base_iri="https://example.com/")
    store.save_schema(override)
    entries = {e["id"]: e for e in store.list_schemas()}
    assert entries["fde-core"]["origin"] == "workspace"
    assert entries["fde-core"]["version"] == "9.9.9"
    assert store.load_schema("fde-core").version == "9.9.9"


def test_list_stores_empty(tmp_path: Path) -> None:
    assert OntologyStore(root=tmp_path).list_stores() == []
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_ontology_store.py -q`
Expected: FAIL（`ModuleNotFoundError: fde_scope.ontology.store`）
（`test_default_root_resolves_through_paths` 同时确认 `paths.ontology_dir` 已存在——Task 1 已实现。）

- [ ] **Step 3: 实现 store.py**

创建 `fde_scope/ontology/store.py`：

```python
"""本体文件存储：内置只读 schema（data/*.yaml）+ 工作区 schemas/stores。

风格与 skills store 一致：加载宽容（损坏条目跳过不炸），写入原子
（fsutil.atomic_write_text）。查找优先级：工作区 > 内置（用户可覆盖内置
schema，如 corpus_taxonomy 的现场扩展）。
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from .. import paths
from ..fsutil import atomic_write_text
from .models import InstanceStore, OntologySchema

_DATA_DIR = Path(__file__).parent / "data"


class OntologyStore:
    """内置 + 工作区本体的统一读写入口。"""

    def __init__(self, root: Path | str | None = None) -> None:
        # 默认经 fde_scope.paths 惰性解析（B1：不缓存 data-root 决策）
        self.root = Path(root) if root is not None else paths.ontology_dir()
        self.schemas_dir = self.root / "schemas"
        self.stores_dir = self.root / "stores"

    # -- 内置 ----------------------------------------------------------------
    def builtin_schemas(self) -> dict[str, OntologySchema]:
        out: dict[str, OntologySchema] = {}
        if not _DATA_DIR.is_dir():
            return out
        for p in sorted(_DATA_DIR.glob("*.yaml")):
            schema = self._parse_schema(p)
            if schema is not None:
                out.setdefault(schema.id, schema)
        return out

    # -- 读写 schema -----------------------------------------------------------
    def load_schema(self, schema_id: str) -> OntologySchema | None:
        p = self.schemas_dir / f"{schema_id}.yaml"
        if p.exists():
            return self._parse_schema(p)
        return self.builtin_schemas().get(schema_id)

    def save_schema(self, schema: OntologySchema) -> None:
        text = yaml.safe_dump(schema.model_dump(mode="json"), allow_unicode=True, sort_keys=False)
        atomic_write_text(self.schemas_dir / f"{schema.id}.yaml", text)

    def list_schemas(self) -> list[dict]:
        workspace: dict[str, dict] = {}
        if self.schemas_dir.is_dir():
            for p in sorted(self.schemas_dir.glob("*.yaml")):
                schema = self._parse_schema(p)
                if schema is not None:
                    workspace[schema.id] = self._schema_entry(schema, origin="workspace")
        builtin = {
            sid: self._schema_entry(s, origin="builtin")
            for sid, s in self.builtin_schemas().items()
            if sid not in workspace
        }
        return [*workspace.values(), *builtin.values()]

    # -- 读写 store ------------------------------------------------------------
    def load_store(self, store_id: str) -> InstanceStore | None:
        p = self.stores_dir / f"{store_id}.json"
        if not p.exists():
            return None
        try:
            return InstanceStore.model_validate(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return None

    def save_store(self, store: InstanceStore) -> None:
        text = json.dumps(store.model_dump(mode="json"), ensure_ascii=False, indent=2)
        atomic_write_text(self.stores_dir / f"{store.id}.json", text)

    def list_stores(self) -> list[dict]:
        entries: list[dict] = []
        if not self.stores_dir.is_dir():
            return entries
        for p in sorted(self.stores_dir.glob("*.json")):
            inst = self.load_store(p.stem)
            if inst is not None:
                entries.append(
                    {
                        "id": inst.id,
                        "ontology_ref": inst.ontology_ref,
                        "individuals": len(inst.individuals),
                    }
                )
        return entries

    # -- 内部 ----------------------------------------------------------------
    @staticmethod
    def _parse_schema(path: Path) -> OntologySchema | None:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            return OntologySchema.model_validate(data)
        except (OSError, ValueError, yaml.YAMLError):
            return None  # 损坏条目跳过，不让 CLI 炸

    @staticmethod
    def _schema_entry(schema: OntologySchema, *, origin: str) -> dict:
        return {
            "id": schema.id,
            "version": schema.version,
            "origin": origin,
            "imports": schema.imports,
            "classes": len(schema.classes),
            "object_properties": len(schema.object_properties),
            "data_properties": len(schema.data_properties),
            "concept_schemes": len(schema.concept_schemes),
        }
```

修改 `fde_scope/ontology/__init__.py`：追加 `from .store import OntologyStore`，把 `"OntologyStore"` 加入 `__all__`。

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_ontology_store.py -q`
Expected: 7 passed（`test_list_precedence_workspace_over_builtin` 依赖 Task 6 的 `fde-core` 数据文件——若此时报 builtin 缺失，先跳过该条断言不行：**把 Task 6 提前**，见下方顺序说明）

> **顺序说明：** 若 `test_list_precedence_workspace_over_builtin` 因 `fde-core` 尚未存在而失败，先完成 Task 6（数据文件）再回到本 Task Step 4。推荐执行顺序：Task 5 Step 1-3 → Task 6 全部 → Task 5 Step 4-5。

- [ ] **Step 5: 提交**

```bash
git add fde_scope/ontology/store.py fde_scope/ontology/__init__.py tests/test_ontology_store.py
git commit -m "feat(ontology): OntologyStore with builtin schemas, workspace override, atomic writes"
```

---

### Task 6: 内置本体数据文件（fde-core + mfg-overlay）+ 狗粮校验

**Files:**
- Create: `fde_scope/ontology/data/fde_core.yaml`
- Create: `fde_scope/ontology/data/mfg_overlay.yaml`
- Test: `tests/test_ontology_store.py`（追加狗粮测试）

- [ ] **Step 1: 写失败测试**

在 `tests/test_ontology_store.py` 末尾追加：

```python
from fde_scope.ontology.validation import resolve_imports, validate_schema


def test_builtin_schemas_present() -> None:
    schemas = OntologyStore().builtin_schemas()
    assert {"fde-core", "mfg-overlay"} <= set(schemas)


def test_builtin_schemas_self_validate() -> None:
    """狗粮：内置 TBox 必须通过自己的校验器。"""
    store = OntologyStore()
    for sid, schema in store.builtin_schemas().items():
        report = validate_schema(schema, loader=store.load_schema)
        assert report.ok, (sid, [e.model_dump() for e in report.errors])


def test_overlay_merges_core_on_validation() -> None:
    store = OntologyStore()
    overlay = store.load_schema("mfg-overlay")
    merged = resolve_imports(overlay, loader=store.load_schema)
    curies = {c.curie for c in merged.classes}
    assert "fde:Artifact" in curies  # 来自 fde-core
    assert "mfg:OEE" in curies  # overlay 自有
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_ontology_store.py -k builtin -q`
Expected: FAIL（`assert {"fde-core", "mfg-overlay"} <= set()`）

- [ ] **Step 3: 写 fde_core.yaml**

创建 `fde_scope/ontology/data/fde_core.yaml`：

```yaml
# FDE 基础本体（TBox）——建模项目现有领域概念，不发明新概念。
# 校验契约：本文件必须通过 fde_scope.ontology.validation.validate_schema（狗粮测试）。
id: fde-core
version: 1.0.0
base_iri: https://ai-guru-global.github.io/fde-scope/ontology/
imports: []
namespaces:
  - prefix: fde
    iri: https://ai-guru-global.github.io/fde-scope/ontology/core#
  - prefix: skos
    iri: http://www.w3.org/2004/02/skos/core#
  - prefix: dcterms
    iri: http://purl.org/dc/terms/
classes:
  # 顶层类
  - curie: fde:Engagement
    label: Engagement
    label_zh: FDE 交付项目
    comment: A customer engagement run by an FDE through the 18-phase SOP.
  - curie: fde:Skill
    label: Skill
    label_zh: 技能
  - curie: fde:DataSource
    label: Data Source
    label_zh: 数据源
  # 超类
  - curie: fde:Artifact
    label: Artifact
    label_zh: 交付工件
  - curie: fde:Component
    label: Component
    label_zh: 系统组件
  - curie: fde:ControlFlow
    label: Control Flow Element
    label_zh: 流程控制元素
  - curie: fde:Evaluable
    label: Evaluable
    label_zh: 可评估对象
  # ControlFlow 子类（对应 engagement/ 18 阶段状态机）
  - curie: fde:Zone
    label: Zone
    label_zh: 区段
    sub_class_of: [fde:ControlFlow]
  - curie: fde:Phase
    label: Phase
    label_zh: 阶段
    sub_class_of: [fde:ControlFlow]
  - curie: fde:Gate
    label: Gate
    label_zh: 门禁
    sub_class_of: [fde:ControlFlow]
  - curie: fde:GateResult
    label: Gate Result
    label_zh: 门禁结果
    sub_class_of: [fde:ControlFlow]
  # Artifact 子类
  - curie: fde:CorpusReport
    label: Corpus Report
    label_zh: 语料报告
    sub_class_of: [fde:Artifact]
  - curie: fde:EvalReport
    label: Eval Report
    label_zh: 评估报告
    sub_class_of: [fde:Artifact]
  - curie: fde:Runbook
    label: Runbook
    label_zh: 运维手册
    sub_class_of: [fde:Artifact]
  - curie: fde:HandoffPackage
    label: Handoff Package
    label_zh: 移交包
    sub_class_of: [fde:Artifact]
  # Component 子类（对应 deploy/ 多租户装配）
  - curie: fde:Connector
    label: Connector
    label_zh: 数据连接器
    sub_class_of: [fde:Component]
  - curie: fde:AgentSpec
    label: Agent Spec
    label_zh: Agent 规格
    sub_class_of: [fde:Component]
  - curie: fde:Workspace
    label: Workspace
    label_zh: 执行沙箱
    sub_class_of: [fde:Component]
  - curie: fde:Tenant
    label: Tenant
    label_zh: 租户
    sub_class_of: [fde:Component]
  # Metric（对应 eval/）
  - curie: fde:Metric
    label: Metric
    label_zh: 指标
    sub_class_of: [fde:Evaluable]
object_properties:
  - curie: fde:has_phase
    label: has phase
    label_zh: 包含阶段
    domain: fde:Engagement
    range: fde:Phase
  - curie: fde:has_zone
    label: has zone
    label_zh: 包含区段
    domain: fde:Engagement
    range: fde:Zone
  - curie: fde:guarded_by
    label: guarded by
    label_zh: 受门禁约束
    domain: fde:Phase
    range: fde:Gate
  - curie: fde:produces
    label: produces
    label_zh: 产出
    domain: fde:Phase
    range: fde:Artifact
  - curie: fde:connects_source
    label: connects source
    label_zh: 连接数据源
    domain: fde:Connector
    range: fde:DataSource
  - curie: fde:bound_to
    label: bound to
    label_zh: 绑定
    domain: fde:AgentSpec
    range: fde:Component
  - curie: fde:runs_in
    label: runs in
    label_zh: 运行于
    domain: fde:AgentSpec
    range: fde:Workspace
  - curie: fde:belongs_to
    label: belongs to
    label_zh: 隶属
    domain: fde:Component
    range: fde:Tenant
  - curie: fde:evaluates
    label: evaluates
    label_zh: 评估
    domain: fde:EvalReport
    range: fde:Evaluable
  - curie: fde:measures
    label: measures
    label_zh: 度量
    domain: fde:Metric
    range: fde:Engagement
  - curie: fde:captures_experience
    label: captures experience
    label_zh: 沉淀经验
    domain: fde:Skill
    range: fde:Phase
  - curie: fde:part_of
    label: part of
    label_zh: 属于（层级组装，工业 ISA-95 复用）
    domain: fde:Component
    range: fde:Component
data_properties:
  - curie: fde:slug
    label: slug
    domain: fde:ControlFlow
  - curie: fde:status
    label: status
    domain: fde:Engagement
  - curie: fde:display_name
    label: display name
    domain: fde:Component
  - curie: fde:phase_index
    label: phase index
    domain: fde:Phase
    range: integer
  - curie: fde:quality_score
    label: quality score
    domain: fde:Evaluable
    range: number
  - curie: fde:passed
    label: passed
    domain: fde:GateResult
    range: boolean
  - curie: dcterms:created
    label: created
    domain: fde:Engagement
    range: datetime
  - curie: dcterms:title
    label: title
    domain: fde:Artifact
concept_schemes:
  # 对齐 fde_scope/skills/models.py 的 SkillCategory 四类枚举
  - curie: fde:SkillCategoryScheme
    label: FDE Skill Categories
    label_zh: 技能四类分类
    concepts:
      - curie: fde:cat-research
        label: research
        label_zh: 调研
      - curie: fde:cat-implementation
        label: implementation
        label_zh: 实施
      - curie: fde:cat-optimization
        label: optimization
        label_zh: 调优
      - curie: fde:cat-methodology
        label: methodology
        label_zh: 方法论
```

- [ ] **Step 4: 写 mfg_overlay.yaml**

创建 `fde_scope/ontology/data/mfg_overlay.yaml`：

```yaml
# ISA-95 制造业 overlay——imports fde-core，建模企业层级 / 验收合规工件 / 工业 KPI。
# 对齐 profiles/manufacturing.py 与 eval/manufacturing_metrics.py。
id: mfg-overlay
version: 1.0.0
base_iri: https://ai-guru-global.github.io/fde-scope/ontology/
imports: [fde-core]
namespaces:
  - prefix: mfg
    iri: https://ai-guru-global.github.io/fde-scope/ontology/manufacturing#
  - prefix: fde
    iri: https://ai-guru-global.github.io/fde-scope/ontology/core#
classes:
  # ISA-95 企业层级（经 fde:part_of 组装）
  - curie: mfg:Enterprise
    label: Enterprise
    label_zh: 企业（ISA-95）
    sub_class_of: [fde:Component]
  - curie: mfg:Site
    label: Site
    label_zh: 工厂场地（ISA-95）
    sub_class_of: [fde:Component]
  - curie: mfg:Area
    label: Area
    label_zh: 区域（ISA-95）
    sub_class_of: [fde:Component]
  - curie: mfg:WorkCenter
    label: Work Center
    label_zh: 工作中心（ISA-95）
    sub_class_of: [fde:Component]
  - curie: mfg:WorkUnit
    label: Work Unit
    label_zh: 工作单元（ISA-95）
    sub_class_of: [fde:Component]
  - curie: mfg:Equipment
    label: Equipment
    label_zh: 设备
    sub_class_of: [fde:Component]
  - curie: mfg:Sensor
    label: Sensor
    label_zh: 传感器
    sub_class_of: [mfg:Equipment]
  # 验收 / 安全 / 合规工件（对应 manufacturing gate overlay）
  - curie: mfg:FATReport
    label: FAT Report
    label_zh: 工厂验收报告
    sub_class_of: [fde:Artifact]
  - curie: mfg:SATReport
    label: SAT Report
    label_zh: 现场验收报告
    sub_class_of: [fde:Artifact]
  - curie: mfg:SafetyAssessment
    label: Safety Assessment
    label_zh: 功能安全评估（ISO 13849 / IEC 61508）
    sub_class_of: [fde:Artifact]
  - curie: mfg:ConformityDeclaration
    label: Conformity Declaration
    label_zh: 合规声明（CE / EU AI Act）
    sub_class_of: [fde:Artifact]
  # 工业 KPI（对齐 eval/manufacturing_metrics.py）
  - curie: mfg:OEE
    label: OEE
    label_zh: 设备综合效率
    sub_class_of: [fde:Metric]
  - curie: mfg:MTBF
    label: MTBF
    label_zh: 平均故障间隔时间
    sub_class_of: [fde:Metric]
  - curie: mfg:FPY
    label: FPY
    label_zh: 一次合格率
    sub_class_of: [fde:Metric]
  - curie: mfg:DPMO
    label: DPMO
    label_zh: 每百万缺陷数
    sub_class_of: [fde:Metric]
object_properties:
  - curie: mfg:monitored_by
    label: monitored by
    label_zh: 被监测
    domain: mfg:Equipment
    range: mfg:Sensor
  - curie: mfg:hosts_equipment
    label: hosts equipment
    label_zh: 承载设备
    domain: mfg:WorkUnit
    range: mfg:Equipment
data_properties:
  - curie: mfg:pl_determined
    label: performance level determined
    label_zh: 已确定 PL 等级
    domain: mfg:SafetyAssessment
    range: boolean
```

- [ ] **Step 5: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_ontology_store.py tests/test_ontology_models.py tests/test_ontology_validation.py tests/test_ontology_jsonld.py -q`
Expected: 全部通过（狗粮测试确认两个内置 TBox 过校验、overlay 合并成功）

- [ ] **Step 6: 提交**

```bash
git add fde_scope/ontology/data/fde_core.yaml fde_scope/ontology/data/mfg_overlay.yaml tests/test_ontology_store.py
git commit -m "feat(ontology): builtin fde-core TBox + ISA-95 mfg overlay, dogfood-validated"
```

---

### Task 7: CLI 子应用（list / validate / check / export）

**Files:**
- Modify: `fde_scope/cli.py`（文件末尾追加 ontology 子应用）
- Test: `tests/test_ontology_cli.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_ontology_cli.py`：

```python
"""ontology CLI：list / validate / check / export 的 CliRunner 覆盖。"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from fde_scope.cli import app
from fde_scope.ontology.models import Individual, InstanceStore
from fde_scope.ontology.store import OntologyStore

runner = CliRunner()


def test_list_shows_builtin_schemas() -> None:
    result = runner.invoke(app, ["ontology", "list"])
    assert result.exit_code == 0, result.stdout
    assert "fde-core" in result.stdout
    assert "mfg-overlay" in result.stdout


def test_validate_builtin_schema_passes() -> None:
    result = runner.invoke(app, ["ontology", "validate", "fde-core"])
    assert result.exit_code == 0, result.stdout
    assert "VALID" in result.stdout


def test_validate_overlay_passes() -> None:
    result = runner.invoke(app, ["ontology", "validate", "mfg-overlay"])
    assert result.exit_code == 0, result.stdout


def test_validate_unknown_schema_exit_2() -> None:
    result = runner.invoke(app, ["ontology", "validate", "ghost"])
    assert result.exit_code == 2


def test_validate_broken_workspace_schema_exit_1(tmp_path: Path) -> None:
    store = OntologyStore()
    schema = store.load_schema("fde-core").model_copy(deep=True)
    schema.id = "broken"
    schema.classes[0].sub_class_of = ["fde:Ghost"]  # 引用未声明类 → ONTO-010
    store.save_schema(schema)
    result = runner.invoke(app, ["ontology", "validate", "broken"])
    assert result.exit_code == 1
    assert "ONTO-010" in result.stdout


def test_check_store_passes(tmp_path: Path) -> None:
    store = OntologyStore()
    core = store.load_schema("fde-core")
    store.save_store(
        InstanceStore(
            id="demo",
            ontology_ref="fde-core@1.0.0",
            individuals=[
                Individual(
                    curie="ex:phase-a",
                    types=["fde:Phase"],
                    data_assertions={"fde:slug": ["connect"], "fde:phase_index": [1]},
                ),
                Individual(curie="ex:eng", types=["fde:Engagement"], object_assertions={"fde:has_phase": ["ex:phase-a"]}),
            ],
        )
    )
    assert core is not None
    result = runner.invoke(app, ["ontology", "check", "demo"])
    assert result.exit_code == 0, result.stdout
    assert "VALID" in result.stdout


def test_check_store_version_mismatch_exit_1(tmp_path: Path) -> None:
    OntologyStore().save_store(InstanceStore(id="stale", ontology_ref="fde-core@9.9.9"))
    result = runner.invoke(app, ["ontology", "check", "stale"])
    assert result.exit_code == 1
    assert "ONTO-040" in result.stdout


def test_check_unknown_store_exit_2() -> None:
    result = runner.invoke(app, ["ontology", "check", "ghost"])
    assert result.exit_code == 2


def test_export_schema_to_stdout() -> None:
    result = runner.invoke(app, ["ontology", "export", "fde-core"])
    assert result.exit_code == 0, result.stdout
    assert '"@graph"' in result.stdout


def test_export_store_to_file(tmp_path: Path) -> None:
    OntologyStore().save_store(InstanceStore(id="empty", ontology_ref="fde-core@1.0.0"))
    out = tmp_path / "out.jsonld"
    result = runner.invoke(app, ["ontology", "export", "empty", "--out", str(out)])
    assert result.exit_code == 0, result.stdout
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["@context"]["fde"] == "https://ai-guru-global.github.io/fde-scope/ontology/core#"


def test_export_unsupported_format_exit_2() -> None:
    result = runner.invoke(app, ["ontology", "export", "fde-core", "--format", "turtle"])
    assert result.exit_code == 2
```

注意：`test_validate_broken_workspace_schema_exit_1` / `test_check_*` 依赖 conftest 的 `_isolated_data_root`（FDE_SCOPE_HOME → tmp_path），不会污染真实工作区。

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_ontology_cli.py -q`
Expected: FAIL（命令不存在，exit code 非 0 / "No such command"）

- [ ] **Step 3: 实现 CLI**

在 `fde_scope/cli.py` 文件末尾追加：

```python
# ---------------------------------------------------------------------------
# ontology（本体语义层：TBox/ABox 校验 + JSON-LD 导出）
# ---------------------------------------------------------------------------
ontology_app = typer.Typer(
    name="ontology", help="[Ontology] 本体 schema/实例库：校验与 JSON-LD 导出.", no_args_is_help=True
)
app.add_typer(ontology_app)


def _ontology_store():
    from .ontology.store import OntologyStore

    return OntologyStore()


def _print_report(prefix: str, report) -> None:
    from rich.table import Table

    if report.ok:
        console.print(f"✅ [green]VALID[/green] — {prefix}")
        return
    table = Table(title="Validation errors")
    table.add_column("code", style="red")
    table.add_column("subject")
    table.add_column("message")
    for e in report.errors:
        table.add_row(e.code, e.subject, e.message)
    console.print(table)
    console.print(f"❌ [red]INVALID[/red] — {len(report.errors)} error(s)")


@ontology_app.command("list")
def ontology_list() -> None:
    """[Ontology] 列出内置 + 工作区 schema 与实例库."""
    _banner("ontology list")
    store = _ontology_store()
    schemas = store.list_schemas()
    stores = store.list_stores()
    console.print(f"[bold]schemas[/bold] ({len(schemas)})")
    for s in schemas:
        console.print(
            f"  {s['id']}@{s['version']}  [{s['origin']}]  classes={s['classes']} "
            f"obj={s['object_properties']} data={s['data_properties']} schemes={s['concept_schemes']}"
        )
    console.print(f"[bold]stores[/bold] ({len(stores)})")
    for s in stores:
        console.print(f"  {s['id']}  ref={s['ontology_ref']}  individuals={s['individuals']}")
    if not schemas and not stores:
        console.print("  (empty)")


@ontology_app.command("validate")
def ontology_validate(
    schema_id: str = typer.Argument(..., help="Schema id，如 fde-core"),
) -> None:
    """[Ontology] 校验 TBox（含 overlay 的 import 合并视图）. exit 1 = 校验失败."""
    _banner(f"ontology validate · {schema_id}")
    store = _ontology_store()
    schema = store.load_schema(schema_id)
    if schema is None:
        console.print(f"[red]Unknown schema:[/red] {schema_id}")
        raise typer.Exit(2)
    from .ontology.validation import validate_schema

    report = validate_schema(schema, loader=store.load_schema)
    _print_report(f"{schema_id}@{schema.version}", report)
    if not report.ok:
        raise typer.Exit(1)


@ontology_app.command("check")
def ontology_check(
    store_id: str = typer.Argument(..., help="Instance store id"),
) -> None:
    """[Ontology] 校验 ABox 实例库（对 ontology_ref 指向的 TBox）. exit 1 = 校验失败."""
    _banner(f"ontology check · {store_id}")
    inst = _ontology_store().load_store(store_id)
    if inst is None:
        console.print(f"[red]Unknown store:[/red] {store_id}")
        raise typer.Exit(2)
    from .ontology.validation import validate_store

    report = validate_store(inst, loader=_ontology_store().load_schema)
    _print_report(f"{store_id} ({inst.ontology_ref})", report)
    if not report.ok:
        raise typer.Exit(1)


@ontology_app.command("export")
def ontology_export(
    target: str = typer.Argument(..., help="Schema 或 store id"),
    fmt: str = typer.Option("jsonld", "--format", help="输出格式（当前仅 jsonld）"),
    out: Path | None = typer.Option(None, "--out", "-o", help="写入文件（缺省打印到 stdout）"),
) -> None:
    """[Ontology] 导出 JSON-LD（schema 直接导出；store 联同其 TBox 上下文）."""
    _banner(f"ontology export · {target}")
    if fmt != "jsonld":
        console.print(f"[red]Unsupported format:[/red] {fmt} (only jsonld)")
        raise typer.Exit(2)
    store = _ontology_store()
    schema = store.load_schema(target)
    if schema is not None:
        from .ontology.jsonld import schema_to_jsonld

        doc = schema_to_jsonld(schema)
    else:
        inst = store.load_store(target)
        if inst is None:
            console.print(f"[red]Unknown target:[/red] {target}")
            raise typer.Exit(2)
        ref_id = inst.ontology_ref.split("@", 1)[0]
        ref_schema = store.load_schema(ref_id)
        if ref_schema is None:
            console.print(f"[red]Store references unknown schema:[/red] {inst.ontology_ref}")
            raise typer.Exit(2)
        from .ontology.jsonld import store_to_jsonld

        doc = store_to_jsonld(inst, ref_schema)
    text = json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True)
    if out is None:
        console.print(text)
    else:
        from .fsutil import atomic_write_text

        atomic_write_text(out, text + "\n")
        console.print(f"✅ Exported JSON-LD → [green]{out}[/green]")
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_ontology_cli.py -q`
Expected: 11 passed

- [ ] **Step 5: 手动冒烟**

Run: `.venv/bin/python -m fde_scope.cli ontology list && .venv/bin/python -m fde_scope.cli ontology validate mfg-overlay`
Expected: 列出两个内置 schema；mfg-overlay VALID。

- [ ] **Step 6: 提交**

```bash
git add fde_scope/cli.py tests/test_ontology_cli.py
git commit -m "feat(ontology): CLI sub-app (list/validate/check/export) with exit-code contract"
```

---

### Task 8: Web 只读路由

**Files:**
- Modify: `fde_scope/web/app.py`（追加 3 个 GET 路由，紧跟 skills 路由区块之后）
- Test: `tests/test_ontology_web.py`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_ontology_web.py`：

```python
"""ontology web 只读路由。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from fde_scope.web.app import app

client = TestClient(app)


def test_list_schemas_contains_builtin() -> None:
    resp = client.get("/api/ontology/schemas")
    assert resp.status_code == 200
    ids = {e["id"] for e in resp.json()}
    assert {"fde-core", "mfg-overlay"} <= ids


def test_schema_detail_and_404() -> None:
    resp = client.get("/api/ontology/schema/fde-core")
    assert resp.status_code == 200
    assert resp.json()["id"] == "fde-core"
    assert client.get("/api/ontology/schema/ghost").status_code == 404


def test_store_detail_and_404() -> None:
    assert client.get("/api/ontology/store/ghost").status_code == 404
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv/bin/python -m pytest tests/test_ontology_web.py -q`
Expected: FAIL（404）

- [ ] **Step 3: 实现路由**

在 `fde_scope/web/app.py` 的 skills 路由区块之后追加：

```python
# ---------------------------------------------------------------------------
# ontology（本体语义层：只读）
# ---------------------------------------------------------------------------
@app.get("/api/ontology/schemas")
def api_ontology_schemas() -> list[dict]:
    from ..ontology.store import OntologyStore

    return OntologyStore().list_schemas()


@app.get("/api/ontology/schema/{schema_id}")
def api_ontology_schema(schema_id: str) -> dict:
    from ..ontology.store import OntologyStore

    schema = OntologyStore().load_schema(schema_id)
    if schema is None:
        raise HTTPException(status_code=404, detail=f"unknown ontology schema: {schema_id}")
    return schema.model_dump()


@app.get("/api/ontology/store/{store_id}")
def api_ontology_store(store_id: str) -> dict:
    from ..ontology.store import OntologyStore

    store = OntologyStore().load_store(store_id)
    if store is None:
        raise HTTPException(status_code=404, detail=f"unknown ontology store: {store_id}")
    return store.model_dump()
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv/bin/python -m pytest tests/test_ontology_web.py -q`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add fde_scope/web/app.py tests/test_ontology_web.py
git commit -m "feat(ontology): read-only web routes for schemas and stores"
```

> **提交注意：** `web/app.py` 在工作区可能携带用户既有未提交改动——按 Pre-flight 约定处置后再提交。

---

### Task 9: 文档 + 全量回归

**Files:**
- Create: `docs/ontology.md`
- Modify: `docs/architecture.md`（横切模块清单 + 新设计小节）
- Test: 全量

- [ ] **Step 1: 写 docs/ontology.md**

创建 `docs/ontology.md`：

```markdown
# Ontology 语义层

> 把 FDE 领域概念（Phase/Gate/Connector/CorpusItem/Skill/KPI…）形式化为
> 机器可读本体：TBox（模式）+ ABox（实例），SKOS 分类法，JSON-LD 1.1 导出。
> 零新依赖：pydantic + pyyaml + 标准库；不导入 agentscope。

## 模块地图

| 文件 | 职责 |
|---|---|
| `fde_scope/ontology/models.py` | TBox/ABox 模型 + CURIE 工具 + xsd 类型映射 |
| `fde_scope/ontology/validation.py` | SHACL-lite 校验器（错误码 ONTO-xxx）+ overlay import 合并 |
| `fde_scope/ontology/jsonld.py` | 确定性 JSON-LD 1.1 导出（双语 label 走 language map） |
| `fde_scope/ontology/store.py` | 内置只读 schema + 工作区 schemas/stores（原子写） |
| `fde_scope/ontology/data/*.yaml` | 内置本体：`fde-core`（FDE 基础）+ `mfg-overlay`（ISA-95） |

## 存储布局

- 包内（只读）：`fde_scope/ontology/data/*.yaml`
- 工作区：`<data-root>/.fde_scope/ontology/schemas/<id>.yaml`、`stores/<id>.json`
- 查找优先级：工作区 > 内置（用户可覆盖内置 schema）

## 校验错误码

| 码 | 含义 |
|---|---|
| ONTO-001 | sub_class_of 层级含环 |
| ONTO-002 | sub_property_of / inverse 引用含环或不存在 |
| ONTO-010 | 引用未声明的类（sub_class_of / domain / range / rdf:type） |
| ONTO-011 | 引用未声明的属性或概念（断言 / sub_property_of / inverse / skos:broader） |
| ONTO-020 | 断言违反 domain/range（is-a 闭包判定）或字面量类型不符 |
| ONTO-021 | 对象断言指向不存在的个体 |
| ONTO-030 | CURIE 非法或前缀未声明 |
| ONTO-040 | store 的 ontology_ref 与 TBox id/version 不匹配 |

校验不阻断写入（存储层宽容），由 CLI/调用方决定是否 fail——记录与谓词分离。

## CLI

    fde-scope ontology list                      # 内置 + 工作区清单
    fde-scope ontology validate fde-core         # 校验 TBox（exit 1 = 失败）
    fde-scope ontology check <store-id>          # 校验 ABox（exit 1 = 失败）
    fde-scope ontology export fde-core -o out.jsonld   # JSON-LD 导出

## Web（只读）

    GET /api/ontology/schemas
    GET /api/ontology/schema/{id}
    GET /api/ontology/store/{id}

## 分期路线

- **P1（本期）**：核心 + 内置本体 + CLI/Web + 文档。
- **P2**：`corpus --ontology`——概念注解、概念级覆盖度（祖先合并）、定向合成。
- **P3**：skills SKOS 桥接——`skills search --concept` 经 broader/narrower 扩展。

## 作者指南（YAML）

schema 顶层字段：`id / version / base_iri / imports / namespaces / classes /
object_properties / data_properties / concept_schemes`。所有引用写 CURIE
（`fde:Phase`），前缀必须在 `namespaces` 声明。改内置本体 = 复制到工作区
schemas/ 同名覆盖，或在 `data/` 中以版本号演进（内置本体由狗粮测试锁定：
必须通过自己的校验器）。
```

- [ ] **Step 2: 增补 docs/architecture.md**

在“核心设计决策”小节 10 之后追加（编号顺延）：

```markdown
### 11. 本体语义层（ontology/）

`fde_scope/ontology/` 把领域概念形式化为 TBox（`OntologySchema`：类层级、
对象/数据属性、SKOS 概念体系、命名空间、版本）+ ABox（`InstanceStore`：
个体与属性断言），零新依赖（pydantic + pyyaml）。内置 `fde-core` 与
ISA-95 `mfg-overlay` 为包内只读 YAML（狗粮校验：内置本体必须通过自己的
SHACL-lite 校验器）；用户本体/实例库在 `.fde_scope/ontology/` 工作区
（工作区覆盖内置），全部写入走 `fsutil.atomic_write_text`。JSON-LD 1.1
导出保证互操作（`ontology export`）。校验返回错误码报告（ONTO-xxx）而非
异常——记录与谓词分离，与 gate 哲学一致。详见
[`ontology.md`](ontology.md)。
```

同时把分层代码块中的横切模块注释区追加一行（紧跟 skills 横切注释之后）：

```markdown
> **横切模块 `fde_scope/ontology/`（本体语义层）**：领域概念的形式化
> TBox/ABox + SKOS 分类法 + JSON-LD 导出；P2/P3 将接入 corpus 覆盖度与
> skills 检索。详见 [`ontology.md`](ontology.md)。
```

- [ ] **Step 3: 全量回归**

Run: `make test`
Expected: 全绿（405+ 现有测试零回归 + ontology 新测试）

Run: `.venv/bin/ruff check fde_scope tests && .venv/bin/ruff format --check fde_scope tests`
Expected: 干净（如有格式问题，`ruff format fde_scope/ontology tests/test_ontology_*.py` 修复后重跑）

- [ ] **Step 4: 提交**

```bash
git add docs/ontology.md docs/architecture.md
git commit -m "docs(ontology): module guide + architecture section for the semantic layer"
```

---

## Self-Review 记录

- **规格覆盖**：§5 模块结构 → Task 1-6；§6 模型 → Task 1；§7 内置本体 → Task 6；§8 校验 → Task 2/3；§9 导出 → Task 4；§10 CLI/Web → Task 7/8；§13 不变量 → 各任务（零 agentscope、原子写、不触碰 gate/权限）；§14 测试 → 各任务 + Task 9 全量回归；§15 验收 1-3、5 → P1 覆盖（验收 4 属 P2/P3，另出计划）。规格 §7 的 `corpus_taxonomy.yaml` 属 P2 交付物，不在本计划。
- **类型一致性**：`validate_store(store, loader)` 在 Task 3 定义、Task 7 CLI 调用一致；`store_to_jsonld(store, schema)` Task 4 定义、Task 7 调用一致；`OntologyStore.load_schema/list_schemas/load_store/save_store/list_stores` Task 5 定义、Task 7/8 调用一致；`paths.ontology_dir()` Task 1 定义、Task 5 使用一致。
- **占位符扫描**：无 TBD/TODO；Task 5 的执行顺序说明是显式指引（数据文件先行），非占位。
- **已知偏差（有意为之，记录于 validation.py docstring）**：ONTO-011 的解释统一为“未声明词汇引用（属性断言 / sub_property_of / inverse / skos:broader）”，覆盖规格中概念引用的归类；import 成环/缺依赖以 ValueError 报告（装配错误，不进数据校验报告）。
