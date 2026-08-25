"""Tests for the skills subsystem (models / store / service / exporters)."""

from __future__ import annotations

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
        title="t",
        category=SkillCategory.RESEARCH,
        tags=[],
        body_md="b",
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
        SkillDraft(
            title="OPC UA 连接",
            category=SkillCategory.IMPLEMENTATION,
            tags=["opcua"],
            phase_slug="deploy",
            applies_to=["manufacturing"],
        )
    )
    service.create(
        SkillDraft(title="工单分类", category=SkillCategory.RESEARCH, tags=["ticket"], applies_to=["ticket"])
    )
    service.create(
        SkillDraft(
            title="工会评审",
            category=SkillCategory.METHODOLOGY,
            tags=["gate"],
            gate_slug="works_council",
            applies_to=["ticket"],
        )
    )
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


# ---------------------------------------------------------------------------
# context capture (gate hint + operation capture)
# ---------------------------------------------------------------------------


def test_suggest_from_gate_block(service):
    rec = service.suggest_from_gate_block("eng-x", "functional_safety", ["缺 hazard analysis", "PL/SIL 不足"])
    assert rec.source == SkillSource.GATE_HINT
    assert rec.gate_slug == "functional_safety"
    assert rec.source_engagement == "eng-x"
    assert "functional_safety" in rec.title
    assert "hazard analysis" in rec.body_md
    assert rec.status == SkillStatus.DRAFT
    assert rec.category == SkillCategory.METHODOLOGY


def test_suggest_from_gate_block_no_blockers(service):
    rec = service.suggest_from_gate_block("eng-x", "fat_sat", [])
    assert "无" in rec.body_md


def test_capture_operation_maps_category(service):
    r1 = service.capture_operation(action="advance", engagement_id="eng-x", phase_slug="deploy")
    assert r1 is not None and r1.category == SkillCategory.IMPLEMENTATION
    r2 = service.capture_operation(action="gate_pass", engagement_id="eng-x", phase_slug="deploy")
    assert r2 is not None and r2.category == SkillCategory.METHODOLOGY
    r3 = service.capture_operation(action="kpi", engagement_id="eng-x", phase_slug="flywheel")
    assert r3 is not None and r3.category == SkillCategory.OPTIMIZATION
    r4 = service.capture_operation(action="advance", engagement_id="eng-x")
    assert r4 is not None and r4.phase_slug is None
    # 未知 action 返回 None
    assert service.capture_operation(action="bogus", engagement_id="eng-x") is None


def test_capture_operation_sets_source_and_engagement(service):
    rec = service.capture_operation(action="advance", engagement_id="eng-y", phase_slug="deploy")
    assert rec is not None
    assert rec.source == SkillSource.AUTO_CAPTURE
    assert rec.source_engagement == "eng-y"
    assert "eng-y" in rec.title


# -- 导出器（Task 5） ----------------------------------------------------------


def test_export_agentscope_format():
    from fde_scope.skills.exporters import export_skill

    rec = _rec(title="OPC UA 排查", tags=["opcua"])
    files = export_skill(rec, "agentscope")
    assert len(files) == 1
    assert files[0].name == "opc-ua-排查/SKILL.md"  # 技能名 slug 化（保留中文，零依赖）
    assert "name:" in files[0].content and "description:" in files[0].content
    assert "# body" in files[0].content


def test_export_qwenpaw_format():
    from fde_scope.skills.exporters import export_skill

    files = export_skill(_rec(title="T"), "qwenpaw")
    assert files[0].name.endswith("SKILL.md")
    assert files[0].content  # 非空


def test_export_unknown_format_raises():
    from fde_scope.skills.exporters import export_skill

    with pytest.raises(ValueError):
        export_skill(_rec(), "bogus")


def test_export_many_produces_one_dir_per_skill():
    from fde_scope.skills.exporters import export_many

    files = export_many([_rec(title="A"), _rec(title="B")], "agentscope")
    assert len(files) == 2
    assert {f.name.split("/")[0] for f in files} == {"a", "b"}


def test_export_slug_falls_back_for_pure_symbols():
    from fde_scope.skills.exporters import export_skill

    files = export_skill(_rec(title="！！！"), "agentscope")
    assert files[0].name == "skill/SKILL.md"
