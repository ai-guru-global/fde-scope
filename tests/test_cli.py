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
