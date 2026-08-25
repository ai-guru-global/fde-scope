"""Tests for the QwenPaw integration surface (spec §5.2 ACP placeholder)."""

from __future__ import annotations

import json

import pytest

from fde_scope.integrations.acp import AcpEndpoint


def test_acp_endpoint_is_abstract() -> None:
    with pytest.raises(TypeError):
        AcpEndpoint()  # type: ignore[abstract]


def test_acp_endpoint_runner_config_matches_qwenpaw_fields() -> None:
    class SopEngine(AcpEndpoint):
        name = "fde_sop"
        description = "FDE SOP state machine"
        acp_command = ["python", "-m", "fde_scope.acp_server"]
        acp_env = {"FDE_SCOPE_TENANT": "acme"}

        async def handle(self, payload: dict) -> dict:
            return {"ok": True}

    ep = SopEngine()
    cfg = ep.runner_config()
    # 字段名对齐 QwenPaw ACPConfig.ACPAgentConfig（官方源码 config.py）
    assert cfg["enabled"] is True
    assert cfg["command"] == "python"
    assert cfg["args"] == ["-m", "fde_scope.acp_server"]
    assert cfg["env"] == {"FDE_SCOPE_TENANT": "acme"}
    assert cfg["trusted"] is True
    assert cfg["tool_parse_mode"] == "call_title"


def test_qwenpaw_export_writes_full_bundle(tmp_path) -> None:
    from fde_scope.config import TenantConfig
    from fde_scope.integrations.qwenpaw_exporter import QwenPawExporter

    tenant = TenantConfig(
        id="acme",
        name="Acme",
        agents=[
            {"name": "researcher", "role": "调研员"},
            {"name": "coder", "role": "实施员", "system_prompt": "You code."},
        ],
    )
    ex = QwenPawExporter()
    bundle = ex.export(tenant, tmp_path)
    assert (tmp_path / "config.json").exists()
    assert (tmp_path / "workspaces" / "researcher" / "agent.json").exists()
    assert (tmp_path / "workspaces" / "coder" / "AGENTS.md").exists()
    assert "You code." in (tmp_path / "workspaces" / "coder" / "AGENTS.md").read_text(encoding="utf-8")
    # config.json 的 profiles 段对齐 QwenPaw 官方结构
    cfg = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    profiles = cfg["agents"]["profiles"]
    assert set(profiles) == {"researcher", "coder"}
    assert profiles["researcher"]["enabled"] is True
    assert cfg["agents"]["active_agent"] == "researcher"
    # agent.json 必填字段 + persona 引用
    aj = json.loads((tmp_path / "workspaces" / "coder" / "agent.json").read_text(encoding="utf-8"))
    assert aj["name"] == "coder"
    assert aj["system_prompt_files"] == ["AGENTS.md"]
    # 校验报告写出
    assert (tmp_path / "qwenpaw_validate.json").exists()
    assert bundle.report["valid"] is True


def test_qwenpaw_export_includes_skills_and_corpus(tmp_path) -> None:
    from fde_scope.config import TenantConfig
    from fde_scope.integrations.qwenpaw_exporter import QwenPawExporter
    from fde_scope.skills.models import SkillRecord

    tenant = TenantConfig(id="acme", name="Acme", agents=[{"name": "a1", "role": "r1"}])
    skills = [
        SkillRecord(
            id="sk-1",
            title="现场调研清单",
            category="research",
            body_md="## Checklist\n1. 首件确认",
            source="manual",
            status="published",
            version=1,
        )
    ]
    ex = QwenPawExporter()
    ex.export(tenant, tmp_path, skills=skills)
    # 目录名由 exporters._slugify 决定，此处只断言结构 + 内容
    skill_mds = list((tmp_path / "skills").glob("*/SKILL.md"))
    assert len(skill_mds) == 1
    assert "## Checklist" in skill_mds[0].read_text(encoding="utf-8")
