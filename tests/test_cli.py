"""CLI smoke tests — every subcommand's --help and a dry-run end-to-end."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from fde_scope.cli import app

runner = CliRunner()


def test_top_help_lists_subcommands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("connect", "corpus", "deploy", "eval", "flywheel"):
        assert cmd in result.stdout


def test_connect_dry_run() -> None:
    result = runner.invoke(app, ["connect", "--type", "csv", "--source", "x.csv", "--dry-run"])
    assert result.exit_code == 0
    assert "DRY-RUN" in result.stdout


def test_connect_real_csv(sample_csv: Path) -> None:
    result = runner.invoke(app, ["connect", "--type", "csv", "--source", str(sample_csv)])
    assert result.exit_code == 0
    assert "退款" in result.stdout  # detected category


def test_corpus_forge_end_to_end(tmp_path: Path, sample_csv: Path) -> None:
    out = tmp_path / "report.html"
    result = runner.invoke(
        app,
        ["corpus", "--input", str(sample_csv), "--out", str(out)],
    )
    assert result.exit_code == 0, result.stdout
    assert "Corpus forged" in result.stdout
    assert out.exists()
    html = out.read_text(encoding="utf-8")
    assert "语料报告" in html


def test_deploy_dry_run() -> None:
    result = runner.invoke(app, ["deploy", "--tenant", "acme", "--dry-run"])
    assert result.exit_code == 0
    assert "corpus_acme" in result.stdout


def test_eval_runs(eval_cases_jsonl: Path) -> None:
    result = runner.invoke(app, ["eval", "--agent", "mock", "--test-set", str(eval_cases_jsonl)])
    assert result.exit_code == 0, result.stdout
    assert "Metrics" in result.stdout


def test_flywheel_replay(tmp_path: Path) -> None:
    events = [
        {"concept": "agent.human_override", "payload": {"id": "1", "ticket": "退款", "category": "退款"}},
        {"concept": "agent.low_confidence", "payload": {"id": "2", "ticket": "??", "category": "其他"}},
        {"concept": "agent.unknown", "payload": {}},
    ]
    ev_path = tmp_path / "events.json"
    ev_path.write_text(json.dumps(events, ensure_ascii=False), encoding="utf-8")
    result = runner.invoke(app, ["flywheel", "--agent", "acme", "--events", str(ev_path)])
    assert result.exit_code == 0, result.stdout
    assert "golden=1" in result.stdout


# ---------------------------------------------------------------------------
# regression tests
# ---------------------------------------------------------------------------
def test_corpus_json_written_next_to_out(tmp_path: Path, sample_csv: Path) -> None:
    """The JSON report must land in the --out directory, not hardcoded reports/."""
    out = tmp_path / "sub" / "report.html"
    result = runner.invoke(app, ["corpus", "--input", str(sample_csv), "--out", str(out)])
    assert result.exit_code == 0, result.stdout
    assert out.exists()
    assert (tmp_path / "sub" / "corpus_report.json").exists()


def test_eval_non_mock_agent_errors(eval_cases_jsonl: Path) -> None:
    """An unknown agent ID must fail loudly instead of silently using the mock."""
    result = runner.invoke(app, ["eval", "--agent", "acme-prod", "--test-set", str(eval_cases_jsonl)])
    assert result.exit_code == 2
    assert "Unknown agent" in result.stdout


def test_deploy_with_corpus_report(tmp_path: Path, sample_csv: Path) -> None:
    """--corpus loads the CorpusReport and passes it into the manifest."""
    out = tmp_path / "report.html"
    result = runner.invoke(app, ["corpus", "--input", str(sample_csv), "--out", str(out)])
    assert result.exit_code == 0, result.stdout
    corpus_json = tmp_path / "corpus_report.json"
    assert corpus_json.exists()

    result = runner.invoke(app, ["deploy", "--tenant", "acme", "--corpus", str(corpus_json), "--dry-run"])
    assert result.exit_code == 0, result.stdout
    assert '"corpus"' in result.stdout  # manifest carries the corpus summary


def test_deploy_with_missing_corpus_errors(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["deploy", "--tenant", "acme", "--corpus", str(tmp_path / "nope.json"), "--dry-run"]
    )
    assert result.exit_code == 2
    assert "Cannot load corpus report" in result.stdout


def test_engage_init_refuses_overwrite_without_force(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    args = ["engage", "init", "--customer", "Acme", "--profile", "ticket"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.stdout
    result = runner.invoke(app, args)
    assert result.exit_code == 2
    assert "already exists" in result.stdout
    # explicit --force still works
    result = runner.invoke(app, [*args, "--force"])
    assert result.exit_code == 0, result.stdout


def test_engage_rollback_unknown_phase_friendly_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["engage", "init", "--customer", "Acme", "--profile", "ticket"])
    assert result.exit_code == 0, result.stdout
    eid = "eng-acme-ticket"
    result = runner.invoke(app, ["engage", "advance", eid])
    assert result.exit_code == 0, result.stdout
    result = runner.invoke(app, ["engage", "rollback", eid, "--to", "no_such_phase"])
    assert result.exit_code == 2
    assert "Unknown phase" in result.stdout
    assert "Traceback" not in result.stdout


# ---------------------------------------------------------------------------
# skills（技能/方法论沉淀）
# ---------------------------------------------------------------------------
from fde_scope.skills.models import SkillStatus  # noqa: E402
from fde_scope.skills.store import SkillStore  # noqa: E402


def test_skill_add_publish_export(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app,
        [
            "skill",
            "add",
            "--title",
            "OPC UA 排查",
            "--category",
            "implementation",
            "--tags",
            "opcua",
            "--body",
            "# 步骤",
        ],
    )
    assert result.exit_code == 0, result.stdout
    store = SkillStore(tmp_path / ".fde_scope" / "skills")
    drafts = store.load_all()
    assert len(drafts) == 1
    assert drafts[0].status == SkillStatus.DRAFT
    sid = drafts[0].id
    assert runner.invoke(app, ["skill", "publish", sid]).exit_code == 0
    assert (
        runner.invoke(
            app, ["skill", "export", sid, "--format", "agentscope", "--out", str(tmp_path / "out")]
        ).exit_code
        == 0
    )
    assert (tmp_path / "out" / "opc-ua" / "SKILL.md").exists()


def test_skill_list_and_review(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["skill", "add", "--title", "T1", "--category", "research"])
    r = runner.invoke(app, ["skill", "list", "--category", "research"])
    assert r.exit_code == 0 and "T1" in r.stdout
    r2 = runner.invoke(app, ["skill", "review"])
    assert r2.exit_code == 0 and "T1" in r2.stdout


def test_skill_add_requires_category(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["skill", "add", "--title", "T"])
    assert r.exit_code != 0


# ---------------------------------------------------------------------------
# skills × engagement 钩子
# ---------------------------------------------------------------------------
from fde_scope.cli import _save_engagement  # noqa: E402
from fde_scope.engagement import Engagement, EngagementContext  # noqa: E402


def _plant_engagement(tmp_path: Path, *, profile: str = "manufacturing", phase: str = "site_survey") -> None:
    """构造并落盘一个 engagement（CLI 命令从文件加载）。"""
    ctx = EngagementContext(id="eng-t", customer="Acme", profile=profile)
    ctx.current_phase = phase
    _save_engagement(Engagement(ctx))


def test_advance_blocked_suggests_skill(tmp_path: Path, monkeypatch) -> None:
    """advance 被阻塞时生成 gate_hint 草稿。"""
    monkeypatch.chdir(tmp_path)
    _plant_engagement(tmp_path)  # site_survey 空 ctx 必然阻塞
    result = runner.invoke(app, ["engage", "advance", "eng-t"])
    assert result.exit_code == 1
    drafts = SkillStore(tmp_path / ".fde_scope" / "skills").load_all()
    assert any(r.source.value == "gate_hint" for r in drafts)


def test_gate_check_failure_suggests_skill(tmp_path: Path, monkeypatch) -> None:
    """gate check 失败时同样生成 gate_hint 草稿。"""
    monkeypatch.chdir(tmp_path)
    _plant_engagement(tmp_path)
    result = runner.invoke(app, ["gate", "check", "eng-t", "--gate", "site_survey"])
    assert result.exit_code == 1
    drafts = SkillStore(tmp_path / ".fde_scope" / "skills").load_all()
    assert any(r.source.value == "gate_hint" for r in drafts)


def test_advance_success_captures_operation(tmp_path: Path, monkeypatch) -> None:
    """advance 成功时自动捕获一条 implementation 草稿。"""
    monkeypatch.chdir(tmp_path)
    _plant_engagement(tmp_path, profile="ticket", phase="qualification")  # 无 gate
    result = runner.invoke(app, ["engage", "advance", "eng-t"])
    assert result.exit_code == 0, result.stdout
    drafts = SkillStore(tmp_path / ".fde_scope" / "skills").load_all()
    assert any(r.source.value == "auto_capture" and "advance" in r.tags for r in drafts)


# ---------------------------------------------------------------------------
# engage journal（现场记录）
# ---------------------------------------------------------------------------
def test_journal_append_view_and_link(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    _plant_engagement(tmp_path)
    # 先造一个技能供 --link-skill 校验
    r = runner.invoke(app, ["skill", "add", "--title", "现场技巧", "--category", "implementation"])
    assert r.exit_code == 0, r.stdout
    sid = SkillStore(tmp_path / ".fde_scope" / "skills").load_all()[0].id
    # 追加
    r2 = runner.invoke(
        app,
        ["engage", "journal", "eng-t", "--kind", "research", "--note", "产线A 调研完成", "--link-skill", sid],
    )
    assert r2.exit_code == 0, r2.stdout
    assert "产线A 调研完成" in r2.stdout
    # 查看
    r3 = runner.invoke(app, ["engage", "journal", "eng-t"])
    assert r3.exit_code == 0
    assert "产线A 调研完成" in r3.stdout
    assert sid in r3.stdout
    # 非法 kind
    r4 = runner.invoke(app, ["engage", "journal", "eng-t", "--kind", "oops", "--note", "x"])
    assert r4.exit_code == 2
    # 未知 skill
    r5 = runner.invoke(app, ["engage", "journal", "eng-t", "--note", "x", "--link-skill", "skill-nope"])
    assert r5.exit_code == 2
    # 不存在的 engagement
    r6 = runner.invoke(app, ["engage", "journal", "eng-nope"])
    assert r6.exit_code == 2


def test_deploy_manifest_lists_agents(tmp_path: Path, monkeypatch) -> None:
    """--agent 可重复声明多 Agent 拓扑，manifest 输出 agents 段。"""
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(
        app,
        [
            "deploy",
            "--tenant",
            "acme",
            "--name",
            "Acme",
            "--dry-run",
            "--agent",
            "researcher:调研员",
            "--agent",
            "coder:实施员:qwen-max",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert '"agents"' in r.stdout
    assert "researcher" in r.stdout and "coder" in r.stdout


def test_deploy_invalid_agent_spec_exits_2(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["deploy", "--tenant", "acme", "--dry-run", "--agent", "bad-spec"])
    assert r.exit_code == 2


def test_qwenpaw_export_and_validate(tmp_path: Path, monkeypatch) -> None:
    """qwenpaw export 产出可被 qwenpaw validate 验证通过。"""
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out"
    r = runner.invoke(
        app,
        [
            "qwenpaw",
            "export",
            "--tenant",
            "acme",
            "--name",
            "Acme",
            "--out",
            str(out),
            "--agent",
            "researcher:调研员",
            "--agent",
            "coder:实施员:qwen-max",
        ],
    )
    assert r.exit_code == 0, r.stdout
    assert (out / "config.json").exists()
    assert '"profiles"' in (out / "config.json").read_text(encoding="utf-8")
    r2 = runner.invoke(app, ["qwenpaw", "validate", "--out", str(out)])
    assert r2.exit_code == 0, r2.stdout
    assert "VALID" in r2.stdout


def test_qwenpaw_validate_reports_bad_bundle(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    (out / "config.json").write_text('{"agents": {"profiles": {}}}', encoding="utf-8")
    r = runner.invoke(app, ["qwenpaw", "validate", "--out", str(out)])
    assert r.exit_code == 1
    assert "profiles" in r.stdout
