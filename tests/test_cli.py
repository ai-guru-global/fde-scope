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
