"""Mermaid classDiagram 导出：TBox 概念模型图（步骤2 产出物的机器生成版）。

纯函数、确定性（全部排序）。导出的是**类级结构**：继承 + 对象属性关联 +
数据属性成员；概念体系（SKOS）不进类图。
"""

from __future__ import annotations

from .models import OntologySchema


def schema_to_mermaid(schema: OntologySchema) -> str:
    lines = ["classDiagram", "  direction TB"]
    labels: dict[str, str] = {}
    parents: list[tuple[str, str]] = []
    for c in schema.classes:
        labels[c.curie] = c.label_zh or c.label
        for parent in c.sub_class_of:
            parents.append((parent, c.curie))
    for curie in sorted(labels):
        lines.append(f'  class {curie.split(":")[-1]}["{curie.split(":")[-1]}·{labels[curie]}"]')
    for parent, child in sorted(parents):
        lines.append(f"  {parent.split(':')[-1]} <|-- {child.split(':')[-1]}")
    for p in sorted(schema.object_properties, key=lambda x: x.curie):
        lines.append(f"  {p.domain.split(':')[-1]} --> {p.range.split(':')[-1]} : {p.curie.split(':')[-1]}")
    for p in sorted(schema.data_properties, key=lambda x: x.curie):
        lines.append(f"  {p.domain.split(':')[-1]} : +{p.curie.split(':')[-1]}({p.range})")
    return "\n".join(lines) + "\n"
