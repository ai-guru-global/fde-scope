"""技能导出器：SkillRecord → AgentScope / QwenPaw 兼容 SKILL.md。

格式约定来自官方文档检索（2026-08-25）：AgentScope 2.0 教程
task_agent_skill.html 与 QwenPaw CONTRIBUTING_zh.md 均遵循 Anthropic
Agent Skills 规范：目录含 SKILL.md（YAML frontmatter + Markdown 指令），
frontmatter 必填 name + description；QwenPaw 额外支持可选 metadata。
两格式同源，共用一个渲染器。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..ontology.skills_bridge import skill_concepts
from .models import SkillRecord

if TYPE_CHECKING:
    from ..ontology.models import OntologySchema


@dataclass
class ExportFile:
    """一个导出产物文件（相对路径 + 内容）。"""

    name: str
    content: str


def _slugify(title: str) -> str:
    """标题 → 目录名：小写、非字母数字/中文转连字符、截断 60 字符。

    保留 CJK（现场技能标题多为中文；纯符号标题退化为 "skill"）。
    """
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", title.lower()).strip("-")
    return s[:60] or "skill"


def _frontmatter(record: SkillRecord, ontology: OntologySchema | None = None) -> str:
    """按官方格式生成 frontmatter（name/description 必填，QwenPaw 兼容）。

    ontology 提供且技能解析出概念时，追加可选 ``concepts:`` 行（官方规范的
    附加元数据；无概念则不写行）。
    """
    fm = f"---\nname: {_slugify(record.title)}\ndescription: {record.title}"
    if ontology is not None:
        concepts = skill_concepts(record, ontology)
        if concepts:
            fm += f"\nconcepts: {', '.join(concepts)}"
    return fm + "\n---\n"


def export_skill(record: SkillRecord, fmt: str, ontology: OntologySchema | None = None) -> list[ExportFile]:
    """导出单条技能为指定格式；fmt 仅支持 agentscope / qwenpaw。"""
    if fmt not in ("agentscope", "qwenpaw"):
        raise ValueError(f"unsupported export format: {fmt!r}")
    name = _slugify(record.title)
    content = _frontmatter(record, ontology) + "\n" + record.body_md
    return [ExportFile(name=f"{name}/SKILL.md", content=content)]


def export_many(
    records: list[SkillRecord], fmt: str, ontology: OntologySchema | None = None
) -> list[ExportFile]:
    """批量导出（与单条同构，逐个目录条目）。"""
    files: list[ExportFile] = []
    for rec in records:
        files.extend(export_skill(rec, fmt, ontology))
    return files
