"""技能/方法论沉淀的数据模型。

混合形态：Markdown 正文（body_md）+ 结构化元数据（分类/标签/阶段绑定/溯源）。
独立于 engagement 引擎，跨项目复用。
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class SkillCategory(str, Enum):
    """沉淀内容的四类分类：调研 / 实施 / 调优 / 方法论。"""

    RESEARCH = "research"
    IMPLEMENTATION = "implementation"
    OPTIMIZATION = "optimization"
    METHODOLOGY = "methodology"


class SkillStatus(str, Enum):
    """生命周期：草稿 → 发布 → 归档。导出只作用于 published。"""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class SkillSource(str, Enum):
    """来源：手动 / gate 阻塞提示 / 操作自动捕获。"""

    MANUAL = "manual"
    GATE_HINT = "gate_hint"
    AUTO_CAPTURE = "auto_capture"


ExportFormat = Literal["agentscope", "qwenpaw"]


def _now() -> datetime:
    return datetime.now(UTC)


class SkillDraft(BaseModel):
    """创建技能的输入（id/status/version/时间戳由 SkillRecord 生成）。"""

    title: str = Field(min_length=1, max_length=80)
    category: SkillCategory
    tags: list[str] = Field(default_factory=list)
    body_md: str = ""
    phase_slug: str | None = None
    gate_slug: str | None = None
    applies_to: list[str] = Field(default_factory=list)
    source: SkillSource = SkillSource.MANUAL
    source_engagement: str | None = None


class SkillPatch(BaseModel):
    """编辑技能的输入；未提供的字段保持不变。"""

    title: str | None = Field(default=None, min_length=1, max_length=80)
    tags: list[str] | None = None
    body_md: str | None = None
    phase_slug: str | None = None
    gate_slug: str | None = None
    applies_to: list[str] | None = None


class SkillRecord(BaseModel):
    """一条技能记录（持久化为 meta.json + skill.md）。"""

    id: str = Field(default_factory=lambda: f"skill-{secrets.token_hex(4)}")
    title: str
    category: SkillCategory
    tags: list[str] = Field(default_factory=list)
    body_md: str = ""
    phase_slug: str | None = None
    gate_slug: str | None = None
    applies_to: list[str] = Field(default_factory=list)
    source: SkillSource = SkillSource.MANUAL
    source_engagement: str | None = None
    status: SkillStatus = SkillStatus.DRAFT
    version: int = 1
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    export_formats: list[str] = Field(default_factory=list)

    def touch(self) -> None:
        """内容变更后调用：版本 +1、更新时间刷新。"""
        self.version += 1
        self.updated_at = _now()
