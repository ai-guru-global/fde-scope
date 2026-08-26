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


def test_validate_export_rejects_missing_id(tmp_path) -> None:
    from fde_scope.config import TenantConfig
    from fde_scope.integrations.qwenpaw_exporter import QwenPawExporter
    from fde_scope.integrations.validator import validate_export

    tenant = TenantConfig(id="acme", name="Acme", agents=[{"name": "a1", "role": "r1"}])
    QwenPawExporter().export(tenant, tmp_path)
    # 篡改：删掉 profile 的 name → 校验必须报错
    cfg = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    del cfg["agents"]["profiles"]["a1"]["name"]
    (tmp_path / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    report = validate_export(tmp_path)
    assert report["valid"] is False
    assert any("name" in e for e in report["errors"])


def test_validate_export_rejects_bad_agent_id(tmp_path) -> None:
    from fde_scope.config import TenantConfig
    from fde_scope.integrations.qwenpaw_exporter import QwenPawExporter
    from fde_scope.integrations.validator import validate_export

    tenant = TenantConfig(id="acme", name="Acme", agents=[{"name": "a1", "role": "r1"}])
    QwenPawExporter().export(tenant, tmp_path)
    cfg = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    cfg["agents"]["profiles"]["bad id!"] = dict(cfg["agents"]["profiles"]["a1"], id="bad id!")
    (tmp_path / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    report = validate_export(tmp_path)
    assert report["valid"] is False


def test_validate_export_rejects_missing_skill_frontmatter(tmp_path) -> None:
    from fde_scope.config import TenantConfig
    from fde_scope.integrations.qwenpaw_exporter import QwenPawExporter
    from fde_scope.integrations.validator import validate_export
    from fde_scope.skills.models import SkillRecord

    tenant = TenantConfig(id="acme", name="Acme", agents=[{"name": "a1", "role": "r1"}])
    skills = [
        SkillRecord(
            id="sk-1",
            title="技巧",
            category="research",
            body_md="body",
            source="manual",
            status="published",
            version=1,
        )
    ]
    QwenPawExporter().export(tenant, tmp_path, skills=skills)
    # 目录名由 exporters._slugify 决定，用 glob 定位实际 SKILL.md
    skill_mds = list((tmp_path / "skills").glob("*/SKILL.md"))
    assert skill_mds
    skill_mds[0].write_text("no frontmatter", encoding="utf-8")
    report = validate_export(tmp_path)
    assert report["valid"] is False


def test_validate_export_short_circuits_on_traversal_id(tmp_path) -> None:
    """穿越型 agent id 只报规则错误，不得探测目录外路径。"""
    from fde_scope.integrations.validator import validate_export

    (tmp_path / "config.json").write_text(
        json.dumps(
            {"agents": {"profiles": {"../../probe": {"id": "../../probe", "name": "x", "enabled": True}}}}
        ),
        encoding="utf-8",
    )
    report = validate_export(tmp_path)
    assert report["valid"] is False
    assert any("violates QwenPaw id rules" in e for e in report["errors"])
    assert not any("workspaces/../" in e for e in report["errors"])


def test_validate_export_rejects_malformed_structure(tmp_path) -> None:
    """结构畸形 JSON 应报错而非抛 AttributeError。"""
    from fde_scope.integrations.validator import validate_export

    (tmp_path / "config.json").write_text(
        json.dumps({"agents": {"profiles": {"x": ["notadict"]}}}), encoding="utf-8"
    )
    report = validate_export(tmp_path)
    assert report["valid"] is False
    assert any("not an object" in e for e in report["errors"])


def test_validate_export_rejects_non_object_root_and_agents(tmp_path) -> None:
    """config.json 根非对象 / agents 段缺失都返回错误报告而非异常。"""
    from fde_scope.integrations.validator import validate_export

    (tmp_path / "config.json").write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    report = validate_export(tmp_path)
    assert report["valid"] is False and "root is not an object" in report["errors"][0]

    (tmp_path / "config.json").write_text(json.dumps({"agents": "nope"}), encoding="utf-8")
    report = validate_export(tmp_path)
    assert report["valid"] is False and "agents section" in report["errors"][0]

    (tmp_path / "config.json").write_text(json.dumps({"agents": {}}), encoding="utf-8")
    report = validate_export(tmp_path)
    assert report["valid"] is False and "agents.profiles" in report["errors"][0]


def test_validate_export_checks_active_agent(tmp_path) -> None:
    """active_agent 必须指向存在的 profile。"""
    from fde_scope.config import TenantConfig
    from fde_scope.integrations.qwenpaw_exporter import QwenPawExporter
    from fde_scope.integrations.validator import validate_export

    tenant = TenantConfig(id="acme", name="Acme", agents=[{"name": "a1", "role": "r1"}])
    QwenPawExporter().export(tenant, tmp_path)
    cfg = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    cfg["agents"]["active_agent"] = "ghost"
    (tmp_path / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    report = validate_export(tmp_path)
    assert report["valid"] is False
    assert any("active_agent" in e for e in report["errors"])


def test_validate_export_rejects_persona_traversal(tmp_path) -> None:
    """system_prompt_files 含 .. 时报错，不得探测目录外路径。"""
    from fde_scope.integrations.validator import validate_export

    ws = tmp_path / "workspaces" / "a1"
    ws.mkdir(parents=True)
    (tmp_path / "config.json").write_text(
        json.dumps({"agents": {"profiles": {"a1": {"id": "a1", "name": "a1", "enabled": True}}}}),
        encoding="utf-8",
    )
    (ws / "agent.json").write_text(
        json.dumps({"id": "a1", "name": "a1", "system_prompt_files": ["../../probe.md"]}),
        encoding="utf-8",
    )
    report = validate_export(tmp_path)
    assert report["valid"] is False
    assert any("not a relative file" in e for e in report["errors"])


def test_qwenpaw_export_includes_corpus(tmp_path) -> None:
    """corpus_report 写出 corpus.json（collection/total/real/synthetic）。"""
    from types import SimpleNamespace

    from fde_scope.config import TenantConfig
    from fde_scope.integrations.qwenpaw_exporter import QwenPawExporter

    tenant = TenantConfig(id="acme", name="Acme", agents=[{"name": "a1", "role": "r1"}])
    corpus = SimpleNamespace(total=10, real=8, synthetic=2)
    QwenPawExporter().export(tenant, tmp_path, corpus_report=corpus)
    data = json.loads((tmp_path / "corpus.json").read_text(encoding="utf-8"))
    assert data == {"collection": "corpus_acme", "total": 10, "real": 8, "synthetic": 2}
