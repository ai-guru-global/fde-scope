"""Tests for the skills subsystem (models / store / service / exporters)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from fde_scope.skills.models import (
    SkillCategory,
    SkillDraft,
    SkillRecord,
    SkillSource,
    SkillStatus,
)


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------


def test_skill_draft_defaults():
    draft = SkillDraft(
        title="OPC UA 连接踩坑",
        category=SkillCategory.IMPLEMENTATION,
        tags=["opcua"],
        body_md="# 步骤\n1. ...",
    )
    assert draft.source == SkillSource.MANUAL
    assert draft.applies_to == []
    assert draft.phase_slug is None
    assert draft.gate_slug is None
    # SkillDraft 不持有 status；由 SkillRecord 生成时默认 draft
    assert SkillRecord(**draft.model_dump()).status == SkillStatus.DRAFT


def test_skill_record_generates_id_and_timestamps():
    rec = SkillRecord(
        title="t", category=SkillCategory.RESEARCH, tags=[], body_md="b",
    )
    assert rec.id.startswith("skill-")
    assert rec.version == 1
    assert rec.export_formats == []
    assert rec.status == SkillStatus.DRAFT


def test_skill_category_enum_values():
    assert SkillCategory.RESEARCH.value == "research"
    assert SkillCategory.IMPLEMENTATION.value == "implementation"
    assert SkillCategory.OPTIMIZATION.value == "optimization"
    assert SkillCategory.METHODOLOGY.value == "methodology"


def test_title_required():
    with pytest.raises(ValidationError):
        SkillDraft(category=SkillCategory.RESEARCH, tags=[], body_md="b")


def test_touch_bumps_version_and_updated_at():
    rec = SkillRecord(title="t", category=SkillCategory.RESEARCH, tags=[], body_md="b")
    old = rec.updated_at
    rec.touch()
    assert rec.version == 2
    assert rec.updated_at >= old


# ---------------------------------------------------------------------------
# store
# ---------------------------------------------------------------------------


def _rec(title="t", **kw) -> SkillRecord:
    kw.setdefault("category", SkillCategory.METHODOLOGY)
    kw.setdefault("tags", [])
    kw.setdefault("body_md", "# body")
    return SkillRecord(title=title, **kw)


def test_store_roundtrip(tmp_path):
    from fde_scope.skills.store import SkillStore

    store = SkillStore(tmp_path / "skills")
    rec = _rec(title="OPC UA 踩坑")
    store.save(rec)
    loaded = store.load(rec.id)
    assert loaded == rec
    assert (tmp_path / "skills" / rec.id / "skill.md").read_text() == "# body"
    assert (tmp_path / "skills" / rec.id / "meta.json").exists()


def test_store_index_and_rebuild(tmp_path):
    from fde_scope.skills.store import SkillStore

    store = SkillStore(tmp_path / "skills")
    a, b = _rec(title="A"), _rec(title="B", category=SkillCategory.RESEARCH)
    store.save(a)
    store.save(b)
    assert len(store.index_entries()) == 2
    # 模拟索引损坏：重建必须从目录恢复
    (tmp_path / "skills" / "index.json").write_text("{broken")
    store.rebuild_index()
    assert len(store.index_entries()) == 2


def test_store_load_missing_and_corrupt(tmp_path):
    from fde_scope.skills.store import SkillStore

    store = SkillStore(tmp_path / "skills")
    assert store.load("skill-nope") is None
    d = tmp_path / "skills" / "skill-bad"
    d.mkdir(parents=True)
    (d / "meta.json").write_text("{bad json")
    assert store.load("skill-bad") is None  # 损坏条目跳过，不抛异常


def test_store_delete(tmp_path):
    from fde_scope.skills.store import SkillStore

    store = SkillStore(tmp_path / "skills")
    rec = _rec()
    store.save(rec)
    store.delete(rec.id)
    assert store.load(rec.id) is None
    assert len(store.index_entries()) == 0


def test_store_load_all_skips_corrupt(tmp_path):
    from fde_scope.skills.store import SkillStore

    store = SkillStore(tmp_path / "skills")
    store.save(_rec(title="OK"))
    d = tmp_path / "skills" / "skill-bad"
    d.mkdir(parents=True)
    (d / "meta.json").write_text("not json")
    assert len(store.load_all()) == 1


# ---------------------------------------------------------------------------
# service
# ---------------------------------------------------------------------------


@pytest.fixture()
def service(tmp_path):
    from fde_scope.skills.service import SkillService
    from fde_scope.skills.store import SkillStore

    return SkillService(SkillStore(tmp_path / "skills"))


def test_service_create_and_get(service):
    rec = service.create(SkillDraft(title="T", category=SkillCategory.RESEARCH, tags=["a"], body_md="b"))
    assert rec.status == SkillStatus.DRAFT
    assert service.get(rec.id).title == "T"


def test_service_publish_archive_lifecycle(service):
    rec = service.create(SkillDraft(title="T", category=SkillCategory.RESEARCH))
    service.publish(rec.id)
    assert service.get(rec.id).status == SkillStatus.PUBLISHED
    service.archive(rec.id)
    assert service.get(rec.id).status == SkillStatus.ARCHIVED


def test_service_publish_requires_draft(service):
    rec = service.create(SkillDraft(title="T", category=SkillCategory.RESEARCH))
    service.publish(rec.id)
    with pytest.raises(ValueError):
        service.publish(rec.id)  # 已发布不能再 publish


def test_service_update_bumps_version(service):
    from fde_scope.skills.models import SkillPatch

    rec = service.create(SkillDraft(title="T", category=SkillCategory.RESEARCH))
    updated = service.update(rec.id, SkillPatch(title="T2", tags=["x"]))
    assert updated.title == "T2"
    assert updated.tags == ["x"]
    assert updated.version == 2


def test_service_search_filters(service):
    service.create(
        SkillDraft(title="OPC UA 连接", category=SkillCategory.IMPLEMENTATION,
                   tags=["opcua"], phase_slug="deploy", applies_to=["manufacturing"])
    )
    service.create(SkillDraft(title="工单分类", category=SkillCategory.RESEARCH,
                              tags=["ticket"], applies_to=["ticket"]))
    service.create(SkillDraft(title="工会评审", category=SkillCategory.METHODOLOGY,
                              tags=["gate"], gate_slug="works_council", applies_to=["ticket"]))
    assert len(service.search("opc")) == 1
    assert len(service.search(status=SkillStatus.DRAFT)) == 3
    assert len(service.search(category=SkillCategory.RESEARCH)) == 1
    assert len(service.search(profile="ticket")) == 2
    assert len(service.search(gate_slug="works_council")) == 1
    assert len(service.search(phase_slug="deploy")) == 1
    assert len(service.search(tags=["opcua", "ticket"])) == 2  # 任一标签命中


def test_service_list_drafts_only(service):
    a = service.create(SkillDraft(title="A", category=SkillCategory.RESEARCH))
    b = service.create(SkillDraft(title="B", category=SkillCategory.RESEARCH))
    service.publish(a.id)
    assert [r.id for r in service.list_drafts()] == [b.id]


def test_service_get_missing_raises(service):
    with pytest.raises(KeyError):
        service.get("skill-nope")
