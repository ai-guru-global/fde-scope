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
