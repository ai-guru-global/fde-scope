"""Skills — FDE 技能/方法论沉淀库。

独立于 engagement 引擎：技能位于 .fde_scope/skills/ 文件库，跨项目复用。
CLI 通过事件钩子（gate 阻塞提示 / 操作捕获）向本模块产生草稿。
"""

from .models import (
    SkillCategory,
    SkillDraft,
    SkillPatch,
    SkillRecord,
    SkillSource,
    SkillStatus,
)
from .store import SkillStore

__all__ = [
    "SkillCategory",
    "SkillDraft",
    "SkillPatch",
    "SkillRecord",
    "SkillSource",
    "SkillStatus",
    "SkillStore",
]
