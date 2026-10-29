"""Tests for the engagement retrospective (SLA clock + timeline + gate stats)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fde_scope.engagement.context import EngagementContext, GateRecord, JournalEntry
from fde_scope.engagement.retrospective import (
    RetrospectiveReport,
    build_retrospective,
    render_markdown,
)

_D0 = datetime(2026, 1, 1, tzinfo=UTC)


def _ts(days: float) -> str:
    return (_D0 + timedelta(days=days)).isoformat()


def _ctx(**kw) -> EngagementContext:
    base = {"id": "e1", "customer": "Acme", "profile": "ticket"}
    base.update(kw)
    return EngagementContext(**base)


def _ev(action: str, days: float, **detail) -> dict:
    return {
        "ts": _ts(days),
        "actor": "local",
        "action": action,
        "detail": {"engagement_id": "e1", **detail},
    }


def _now(days: float) -> datetime:
    return _D0 + timedelta(days=days)


def _ticket_trail_events() -> list[dict]:
    return [
        _ev("engagement.create", 0),
        _ev("engagement.advance", 3, advanced=True),
        _ev("engagement.advance", 5, advanced=True),
        _ev("engagement.gate_evaluate", 6, gate="success_criteria", passed=False),
        _ev("engagement.gate_evaluate", 9, gate="success_criteria", passed=True),
        _ev("engagement.advance", 10, advanced=True),
        _ev("engagement.gate_evaluate", 11, gate="air_gap", passed=True),
        _ev("engagement.advance", 12, advanced=True),
        _ev("engagement.advance", 13, advanced=False),  # blocked — no move
    ]


def _trail_ctx() -> EngagementContext:
    ctx = _ctx()
    ctx.current_phase = "corpus"
    ctx.gate_records["success_criteria"] = GateRecord(slug="success_criteria", passed=True, checked_at=_ts(9))
    return ctx


# -- timeline replay ----------------------------------------------------------
def test_replay_builds_phase_timings_with_durations() -> None:
    report = build_retrospective(_trail_ctx(), _ticket_trail_events(), now=_now(40))
    by_slug = {p.slug: p for p in report.phases}
    assert by_slug["qualification"].visits == 1
    assert by_slug["qualification"].total_days == 3.0
    assert by_slug["stakeholder_map"].total_days == 2.0
    assert by_slug["success_criteria"].total_days == 5.0
    assert by_slug["connect"].total_days == 2.0
    assert by_slug["corpus"].current is True
    assert by_slug["corpus"].total_days == 28.0  # open visit counts enter→now (12→40)
    assert report.timeline_consistent is True
    assert report.elapsed_days == 40.0


def test_blocked_advances_count_but_do_not_move() -> None:
    report = build_retrospective(_trail_ctx(), _ticket_trail_events(), now=_now(40))
    assert report.advances_blocked == 1
    assert report.advances_ok == 4
    assert report.current_phase == "corpus"


def test_forced_advances_are_counted() -> None:
    events = _ticket_trail_events()
    events.append(_ev("engagement.advance", 14, advanced=True, force=True, reason="sponsor 压力"))
    report = build_retrospective(_trail_ctx(), _ticket_trail_events(), now=_now(40))
    assert report.advances_forced == 0  # base trail has no forced advance
    report2 = build_retrospective(_trail_ctx(), events, now=_now(40))
    assert report2.advances_forced == 1


def test_rollback_creates_second_visit() -> None:
    ctx = _trail_ctx()
    ctx.current_phase = "connect"
    events = _ticket_trail_events() + [
        _ev("engagement.rollback", 20, from_phase="corpus", to_phase="connect")
    ]
    report = build_retrospective(ctx, events, now=_now(40))
    assert report.rollbacks == 1
    by_slug = {p.slug: p for p in report.phases}
    assert by_slug["connect"].visits == 2
    assert by_slug["connect"].total_days == 22.0  # 2d first visit + open 20→40
    assert by_slug["connect"].current is True
    assert report.timeline_consistent is True


def test_replay_mismatch_flags_inconsistent_timeline() -> None:
    ctx = _trail_ctx()
    ctx.current_phase = "eval"  # audit trail says corpus
    report = build_retrospective(ctx, _ticket_trail_events(), now=_now(40))
    assert report.timeline_consistent is False


def test_industrial_replay_includes_site_survey() -> None:
    ctx = _ctx(profile="manufacturing")
    ctx.current_phase = "stakeholder_map"
    events = [
        _ev("engagement.create", 0),
        _ev("engagement.advance", 1, advanced=True),  # → site_survey
        _ev("engagement.advance", 4, advanced=True),  # → stakeholder_map
    ]
    report = build_retrospective(ctx, events, now=_now(10))
    slugs = [p.slug for p in report.phases]
    assert slugs == ["qualification", "site_survey", "stakeholder_map"]
    assert report.timeline_consistent is True


# -- SLA milestones -----------------------------------------------------------
def test_sla_met_on_time() -> None:
    report = build_retrospective(_trail_ctx(), _ticket_trail_events(), now=_now(40))
    m = next(x for x in report.sla if x.key == "first_integration")
    assert m.reached is True
    assert m.deadline_days == 14
    assert m.deadline_source == "defaults"
    assert m.status == "met"
    assert m.elapsed_days == 12.0


def test_sla_missed_when_reach_exceeds_deadline() -> None:
    ctx = _trail_ctx()
    ctx.assets["success_criteria_sla"] = {"time_to_first_integration_days": 10}
    report = build_retrospective(ctx, _ticket_trail_events(), now=_now(40))
    m = next(x for x in report.sla if x.key == "first_integration")
    assert m.deadline_days == 10
    assert m.deadline_source == "assets"
    assert m.status == "missed"


def test_sla_on_track_and_at_risk_before_reach() -> None:
    report = build_retrospective(_trail_ctx(), _ticket_trail_events(), now=_now(40))
    production = next(x for x in report.sla if x.key == "production")
    assert production.status == "on_track"  # 40d ≤ 0.8·90
    late = build_retrospective(_trail_ctx(), _ticket_trail_events(), now=_now(80))
    production_late = next(x for x in late.sla if x.key == "production")
    assert production_late.status == "at_risk"  # 72 < 80 ≤ 90
    missed = build_retrospective(_trail_ctx(), _ticket_trail_events(), now=_now(100))
    assert next(x for x in missed.sla if x.key == "production").status == "missed"


def test_sla_unknown_without_any_time_anchor() -> None:
    report = build_retrospective(_ctx(), [], now=_now(40))
    assert report.started_at is None
    assert all(m.status == "unknown" for m in report.sla)
    assert report.phases == []
    assert report.timeline_consistent is True  # replay trivially matches qualification


# -- gate stats ---------------------------------------------------------------
def test_gate_stats_first_pass_and_retries() -> None:
    report = build_retrospective(_trail_ctx(), _ticket_trail_events(), now=_now(40))
    sc = next(g for g in report.gates if g.slug == "success_criteria")
    assert sc.evaluations == 2
    assert sc.first_pass is False
    assert sc.passes == 1
    assert sc.latest_passed is True
    assert sc.source == "audit"
    air = next(g for g in report.gates if g.slug == "air_gap")
    assert air.first_pass is True
    assert report.gate_first_pass_rate == 0.5


def test_gate_stats_context_only_when_no_audit() -> None:
    ctx = _trail_ctx()
    report = build_retrospective(ctx, [], now=_now(40))
    sc = next(g for g in report.gates if g.slug == "success_criteria")
    assert sc.evaluations is None
    assert sc.first_pass is None
    assert sc.latest_passed is True
    assert sc.source == "context-only"
    assert report.gate_first_pass_rate is None


# -- start anchor & data sources ----------------------------------------------
def test_journal_fallback_anchor() -> None:
    ctx = _trail_ctx()
    ctx.journal = [
        JournalEntry(kind="research", note="n1", ts=_ts(2)),
        JournalEntry(kind="implementation", note="n2", ts=_ts(1)),
    ]
    report = build_retrospective(ctx, [], now=_now(40))
    assert report.started_at == _ts(1)
    assert report.start_source == "earliest-journal"
    assert report.journal_counts == {"research": 1, "implementation": 1}
    assert any("journal" in s for s in report.data_sources)


def test_data_sources_list_audit_when_present() -> None:
    report = build_retrospective(_trail_ctx(), _ticket_trail_events(), now=_now(40))
    assert report.audit_event_count == len(_ticket_trail_events())
    assert report.data_sources[0].startswith("audit.jsonl")


# -- markdown ------------------------------------------------------------------
def test_render_markdown_contains_sections_and_warning() -> None:
    ctx = _trail_ctx()
    ctx.current_phase = "eval"  # force inconsistency for the warning line
    report = build_retrospective(ctx, _ticket_trail_events(), now=_now(40))
    md = render_markdown(report)
    assert md.startswith("# 复盘报告 · e1（Acme）")
    assert "## SLA 里程碑" in md
    assert "## 阶段时间线" in md
    assert "## Gate 统计" in md
    assert "⚠️ 审计流重放终态与当前阶段不一致" in md


def test_complete_advance_is_not_counted_as_blocked() -> None:
    ctx = _trail_ctx()
    events = _ticket_trail_events() + [_ev("engagement.advance", 30, advanced=False, reason="complete")]
    report = build_retrospective(ctx, events, now=_now(40))
    assert report.advances_blocked == 1  # 只有那条真正的被拦推进


def test_report_is_json_serializable() -> None:
    report = build_retrospective(_trail_ctx(), _ticket_trail_events(), now=_now(40))
    assert isinstance(report, RetrospectiveReport)
    assert report.model_dump()["engagement_id"] == "e1"
