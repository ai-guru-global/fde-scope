"""技能服务层：CRUD、生命周期、检索、草稿队列。

检索规则：query 对 title/tags/body 大小写不敏感子串匹配；其余精确过滤；
tags 为"任一命中"；按 updated_at 倒序。过滤在内存中进行（文件库规模，
无需索引查询）。
"""

from __future__ import annotations

from .models import SkillCategory, SkillDraft, SkillPatch, SkillRecord, SkillStatus
from .store import SkillStore


class SkillService:
    """技能库的门面：所有业务规则集中在此。"""

    def __init__(self, store: SkillStore) -> None:
        self.store = store

    # -- CRUD ---------------------------------------------------------------
    def create(self, draft: SkillDraft) -> SkillRecord:
        rec = SkillRecord(**draft.model_dump())
        self.store.save(rec)
        return rec

    def get(self, skill_id: str) -> SkillRecord:
        rec = self.store.load(skill_id)
        if rec is None:
            raise KeyError(skill_id)
        return rec

    def update(self, skill_id: str, patch: SkillPatch) -> SkillRecord:
        rec = self.get(skill_id)
        for field, value in patch.model_dump(exclude_unset=True).items():
            setattr(rec, field, value)
        rec.touch()
        self.store.save(rec)
        return rec

    # -- 生命周期 ------------------------------------------------------------
    def publish(self, skill_id: str) -> SkillRecord:
        rec = self.get(skill_id)
        if rec.status != SkillStatus.DRAFT:
            raise ValueError(f"only drafts can be published: {rec.status.value}")
        rec.status = SkillStatus.PUBLISHED
        rec.touch()
        self.store.save(rec)
        return rec

    def archive(self, skill_id: str) -> SkillRecord:
        rec = self.get(skill_id)
        if rec.status == SkillStatus.ARCHIVED:
            raise ValueError("already archived")
        rec.status = SkillStatus.ARCHIVED
        rec.touch()
        self.store.save(rec)
        return rec

    # -- 检索 ---------------------------------------------------------------
    def search(
        self,
        query: str | None = None,
        *,
        category: SkillCategory | None = None,
        tags: list[str] | None = None,
        status: SkillStatus | None = None,
        phase_slug: str | None = None,
        gate_slug: str | None = None,
        profile: str | None = None,
        limit: int = 50,
    ) -> list[SkillRecord]:
        q = (query or "").strip().lower()
        tag_set = set(tags or [])
        results = []
        for rec in self.store.load_all():
            if category is not None and rec.category != category:
                continue
            if status is not None and rec.status != status:
                continue
            if phase_slug is not None and rec.phase_slug != phase_slug:
                continue
            if gate_slug is not None and rec.gate_slug != gate_slug:
                continue
            if profile is not None and profile not in rec.applies_to:
                continue
            if tag_set and not (tag_set & set(rec.tags)):
                continue
            if q and q not in (rec.title + " " + " ".join(rec.tags) + " " + rec.body_md).lower():
                continue
            results.append(rec)
        results.sort(key=lambda r: r.updated_at, reverse=True)
        return results[:limit]

    def list_drafts(self) -> list[SkillRecord]:
        return self.search(status=SkillStatus.DRAFT)

    # -- 上下文沉淀 -----------------------------------------------------------
    _ACTION_CATEGORIES = {
        "advance": SkillCategory.IMPLEMENTATION,
        "gate_pass": SkillCategory.METHODOLOGY,
        "kpi": SkillCategory.OPTIMIZATION,
    }

    def suggest_from_gate_block(
        self, engagement_id: str, gate_slug: str, blockers: list[str]
    ) -> SkillRecord:
        """gate 被阻塞时生成预填草稿（关键点提示）。"""
        summary = "; ".join(blockers[:3]) if blockers else "无"
        rec = SkillRecord(
            title=f"gate 被阻塞: {gate_slug} — {summary[:40]}",
            category=SkillCategory.METHODOLOGY,
            tags=[gate_slug, "gate-blocked"],
            body_md=(
                f"## 背景\n\n`{gate_slug}` 门禁在 engagement `{engagement_id}` 被阻塞。\n\n"
                f"## 阻塞项\n\n{summary}\n\n"
                "## 解法（待补充）\n\n- 步骤 1：…\n\n"
                "## 验收标准\n\n- …\n"
            ),
            gate_slug=gate_slug,
            source=SkillSource.GATE_HINT,
            source_engagement=engagement_id,
        )
        self.store.save(rec)
        return rec

    def capture_operation(
        self,
        *,
        action: str,
        engagement_id: str,
        phase_slug: str | None = None,
        detail: dict | None = None,
    ) -> SkillRecord | None:
        """操作自动捕获：记录一条轻量草稿；未知 action 返回 None。"""
        category = self._ACTION_CATEGORIES.get(action)
        if category is None:
            return None
        note = (detail or {}).get("note", "")
        body = (
            f"## 操作摘要\n\n`{action}` @ engagement `{engagement_id}`"
            + (f"（阶段 `{phase_slug}`）" if phase_slug else "")
            + (f"\n\n{note}" if note else "")
            + "\n\n## 可复用点（待补充）\n\n- …\n"
        )
        rec = SkillRecord(
            title=f"{action} 记录: {engagement_id}" + (f" @ {phase_slug}" if phase_slug else ""),
            category=category,
            tags=[action],
            body_md=body,
            phase_slug=phase_slug,
            source=SkillSource.AUTO_CAPTURE,
            source_engagement=engagement_id,
        )
        self.store.save(rec)
        return rec
