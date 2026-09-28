"""TBox 版本 diff：破坏性变更清单 + ABox 影响面（只读、纯函数、零依赖）。

"破坏性"判据（变更后 ONTO-020/010/011 可能拒绝既有断言，或 is-a 语义漂移）：
- D1  类/属性被移除（改名 = 移除 + 新增）
- D2  属性 domain/range 指向别的类
- D3  数据属性字面量范围变化（任何变化都按破坏处理：旧字面量可能失配 ONTO-020）
- D4  sub_class_of 收紧（失去父类 —— is-a 闭包变窄，旧数据靠该祖先链
      满足的 domain/range 断言可能违规）；新增父类是放宽，非破坏

非破坏（info）：新增类/属性；sub_class_of 放宽（超集）；inverse /
sub_property_of 变化（导航语义，不参与断言合法性判定）；deprecated 翻转。
概念体系（concept_schemes）不进 diff：SKOS 只服务检索/注解，不约束 ABox
断言合法性。ABox 影响面列出引用了 removed/changed 元素的个体（证据清单，
不做推断——那是校验器 ONTO-020 的事）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import InstanceStore, OntologySchema


@dataclass
class Change:
    kind: str  # D1-D4 / INFO
    subject: str
    detail: str


@dataclass
class SchemaDiff:
    from_version: str
    to_version: str
    breaking: list[Change] = field(default_factory=list)
    info: list[Change] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.breaking


def diff_schemas(old: OntologySchema, new: OntologySchema) -> SchemaDiff:
    diff = SchemaDiff(from_version=old.version, to_version=new.version)
    old_classes = {c.curie: c for c in old.classes}
    new_classes = {c.curie: c for c in new.classes}
    old_ops = {p.curie: p for p in old.object_properties}
    new_ops = {p.curie: p for p in new.object_properties}
    old_dps = {p.curie: p for p in old.data_properties}
    new_dps = {p.curie: p for p in new.data_properties}

    for curie in sorted(set(old_classes) - set(new_classes)):
        diff.breaking.append(Change("D1", curie, "class removed"))
    for curie in sorted(set(new_classes) - set(old_classes)):
        diff.info.append(Change("INFO", curie, "class added"))
    for curie in sorted(set(old_classes) & set(new_classes)):
        old_p, new_p = set(old_classes[curie].sub_class_of), set(new_classes[curie].sub_class_of)
        if not old_p <= new_p:
            # 失去父类 → is-a 闭包变窄，靠旧祖先链满足 domain 的断言可能违规
            diff.breaking.append(
                Change(
                    "D4",
                    curie,
                    f"sub_class_of tightened: {sorted(old_p)} -> {sorted(new_p)}",
                )
            )
        elif new_p != old_p:
            diff.info.append(
                Change("INFO", curie, f"sub_class_of widened: {sorted(old_p)} -> {sorted(new_p)}")
            )
        if old_classes[curie].deprecated != new_classes[curie].deprecated and new_classes[curie].deprecated:
            diff.info.append(Change("INFO", curie, "deprecated"))

    for curie in sorted(set(old_ops) - set(new_ops)):
        diff.breaking.append(Change("D1", curie, "object property removed"))
    for curie in sorted(set(new_ops) - set(old_ops)):
        diff.info.append(Change("INFO", curie, "object property added"))
    for curie in sorted(set(old_ops) & set(new_ops)):
        old_prop, new_prop = old_ops[curie], new_ops[curie]
        if (old_prop.domain, old_prop.range) != (new_prop.domain, new_prop.range):
            diff.breaking.append(
                Change(
                    "D2",
                    curie,
                    f"domain/range changed: ({old_prop.domain}, {old_prop.range})"
                    f" -> ({new_prop.domain}, {new_prop.range})",
                )
            )
        if old_prop.inverse != new_prop.inverse or old_prop.sub_property_of != new_prop.sub_property_of:
            diff.info.append(Change("INFO", curie, "inverse/sub_property_of changed"))

    for curie in sorted(set(old_dps) - set(new_dps)):
        diff.breaking.append(Change("D1", curie, "data property removed"))
    for curie in sorted(set(new_dps) - set(old_dps)):
        diff.info.append(Change("INFO", curie, "data property added"))
    for curie in sorted(set(old_dps) & set(new_dps)):
        old_prop, new_prop = old_dps[curie], new_dps[curie]
        if (old_prop.domain, old_prop.range) != (new_prop.domain, new_prop.range):
            diff.breaking.append(
                Change(
                    "D3" if old_prop.range != new_prop.range else "D2",
                    curie,
                    f"domain/range changed: ({old_prop.domain}, {old_prop.range})"
                    f" -> ({new_prop.domain}, {new_prop.range})",
                )
            )
    return diff


def store_impact(store: InstanceStore, diff: SchemaDiff) -> list[Change]:
    """引用了 removed/changed 元素的个体——迁移工作量证据，不是推断。"""
    suspect_props = {c.subject for c in [*diff.breaking, *diff.info] if c.kind != "INFO"}
    suspect_props |= {c.subject for c in diff.breaking if c.kind in ("D2", "D3")}
    suspect_classes = {c.subject for c in diff.breaking if c.kind in ("D1", "D4")}
    impact: list[Change] = []
    for ind in store.individuals:
        touched: list[str] = []
        if suspect_classes & set(ind.types):
            touched.append("type")
        for prop in ind.object_assertions:
            if prop in suspect_props:
                touched.append(f"object:{prop}")
        for prop in ind.data_assertions:
            if prop in suspect_props:
                touched.append(f"data:{prop}")
        if touched:
            impact.append(Change("IMPACT", ind.curie, ", ".join(sorted(touched))))
    return impact
