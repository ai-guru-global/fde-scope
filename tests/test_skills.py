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
