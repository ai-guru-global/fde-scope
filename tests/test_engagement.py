"""Tests for the engagement SOP state machine + gates."""

from __future__ import annotations

import pytest

from fde_scope.engagement import (
    AdvanceBlocked,
    Engagement,
    EngagementContext,
    SafetyPosture,
    SiteInfo,
    Stakeholder,
    phases_for_profile,
)


def _ctx(profile="ticket", **kw) -> EngagementContext:
    base = dict(id="e1", customer="Acme", profile=profile)
    base.update(kw)
    return EngagementContext(**base)


# -- phases ------------------------------------------------------------------
def test_ticket_profile_skips_industrial_phases() -> None:
    seq = phases_for_profile(is_industrial=False)
    slugs = [p.slug for p in seq]
    assert "qualification" in slugs
    assert "site_survey" not in slugs  # industrial-only
    assert "fat_sat" not in slugs
    assert "disengage" in slugs
    # ticket has fewer phases than manufacturing
    assert len(seq) < len(phases_for_profile(is_industrial=True))


def test_manufacturing_profile_has_all_18_phases() -> None:
    seq = phases_for_profile(is_industrial=True)
    assert len(seq) == 18
    assert seq[0].slug == "qualification"
    assert seq[-1].slug == "disengage"


# -- state machine -----------------------------------------------------------
def test_advance_through_no_gate_phases() -> None:
    eng = Engagement(_ctx())
    # qualification has no gate → advance free
    nxt = eng.advance()
    assert nxt.slug == "stakeholder_map"


def test_advance_blocked_by_success_criteria_gate() -> None:
    eng = Engagement(_ctx())
    # roll forward to success_criteria (phase 4) without sponsors/criteria
    eng.ctx.current_phase = "success_criteria"
    with pytest.raises(AdvanceBlocked) as exc:
        eng.advance()
    assert any("成功标准" in b for b in exc.value.result.blockers)
    assert any("sponsor" in b for b in exc.value.result.blockers)


def test_advance_passes_when_gate_satisfied() -> None:
    eng = Engagement(_ctx())
    eng.ctx.current_phase = "success_criteria"
    eng.ctx.success_criteria = ["intent_accuracy >= 0.9"]
    eng.ctx.stakeholders = [
        Stakeholder(name="A", role="VP", is_sponsor=True, success_metric="acc"),
        Stakeholder(name="B", role="Director", is_sponsor=True, success_metric="csat"),
    ]
    nxt = eng.advance()
    assert nxt.slug == "connect"


def test_force_advance_records_but_does_not_block() -> None:
    eng = Engagement(_ctx())
    eng.ctx.current_phase = "success_criteria"
    nxt = eng.advance(force=True)
    assert nxt.slug == "connect"
    # gate was still evaluated and recorded
    assert "success_criteria" in eng.ctx.gate_records
    assert eng.ctx.gate_records["success_criteria"].passed is False


def test_rollback() -> None:
    eng = Engagement(_ctx())
    eng.ctx.current_phase = "deploy"
    eng.rollback("connect")
    assert eng.ctx.current_phase == "connect"


def test_rollback_refuses_forward() -> None:
    eng = Engagement(_ctx())
    eng.ctx.current_phase = "connect"
    with pytest.raises(ValueError):
        eng.rollback("deploy")


def test_terminal_phase_advance_raises() -> None:
    eng = Engagement(_ctx())
    eng.ctx.current_phase = "disengage"
    with pytest.raises(StopIteration):
        eng.advance()


def test_status_snapshot() -> None:
    eng = Engagement(_ctx(profile="manufacturing"))
    st = eng.status()
    assert st["profile"] == "manufacturing"
    assert st["current_phase"] == "qualification"
    assert st["visible_phase_count"] == 18
    assert st["is_complete"] is False
