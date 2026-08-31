"""SkillRecord ↔ SKOS 概念桥接：检索时动态推导，不持久化（P3）。

纯函数、无 IO。category 概念以 schema 声明了 SkillCategoryScheme 为前提；
tag 必须是 schema 概念表中已声明的 CURIE —— 未声明的 tag（哪怕形如
CURIE）一律忽略，不给检索引入幽灵节点。expand_concept 独立实现
（不走 corpus 的 ConceptExtractor），避免为技能检索引入 corpus 依赖。
"""

from __future__ import annotations

from ..skills.models import SkillRecord
from .models import OntologySchema

# 对齐 fde_scope/skills/models.py 的 SkillCategory 四枚举值
CATEGORY_CONCEPT = {
    "research": "fde:cat-research",
    "implementation": "fde:cat-implementation",
    "optimization": "fde:cat-optimization",
    "methodology": "fde:cat-methodology",
}

_SKILL_CATEGORY_SCHEME = "fde:SkillCategoryScheme"


def _declared(schema: OntologySchema) -> set[str]:
    return {c.curie for s in schema.concept_schemes for c in s.concepts}


def _children(schema: OntologySchema) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for scheme in schema.concept_schemes:
        for c in scheme.concepts:
            for b in c.broader:
                out.setdefault(b, set()).add(c.curie)
    return out


def skill_concepts(record: SkillRecord, schema: OntologySchema) -> list[str]:
    """category 概念（需 schema 声明 SkillCategoryScheme）+ 已声明 tag CURIE。

    去重、稳定序：category 概念在前，tag 按声明顺序随后。
    """
    out: list[str] = []
    has_scheme = any(s.curie == _SKILL_CATEGORY_SCHEME for s in schema.concept_schemes)
    if has_scheme:
        cat = CATEGORY_CONCEPT.get(record.category.value)
        if cat is not None and cat not in out:
            out.append(cat)
    declared = _declared(schema)
    for tag in record.tags:
        if tag in declared and tag not in out:
            out.append(tag)
    return out


def expand_concept(curie: str, schema: OntologySchema) -> set[str]:
    """自身 + 全部 narrower 后代的闭包；未知 CURIE 返回仅含自身。"""
    children = _children(schema)
    out = {curie}
    frontier = [curie]
    while frontier:
        cur = frontier.pop()
        for child in children.get(cur, ()):
            if child not in out:
                out.add(child)
                frontier.append(child)
    return out
