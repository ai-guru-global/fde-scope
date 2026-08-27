"""Tests for the engagement SOP state machine + gates."""

from __future__ import annotations

import json

import pytest

from fde_scope.engagement import (
    AdvanceBlocked,
    Engagement,
    EngagementContext,
    Stakeholder,
    phases_for_profile,
)
from fde_scope.engagement.context import JournalEntry
from fde_scope.engagement.phases import phase_by_slug


def _ctx(profile="ticket", **kw) -> EngagementContext:
    base = {"id": "e1", "customer": "Acme", "profile": profile}
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


# -- gates are re-evaluated live (no permanent pass cache) --------------------
def _satisfied_success_criteria(eng: Engagement) -> None:
    eng.ctx.current_phase = "success_criteria"
    eng.ctx.success_criteria = ["intent_accuracy >= 0.9"]
    eng.ctx.stakeholders = [
        Stakeholder(name="A", role="VP", is_sponsor=True, success_metric="acc"),
        Stakeholder(name="B", role="Director", is_sponsor=True, success_metric="csat"),
    ]


def test_advance_reevaluates_gate_after_context_changes() -> None:
    eng = Engagement(_ctx())
    _satisfied_success_criteria(eng)
    assert eng.evaluate_gate("success_criteria").passed  # pass record now exists
    # context breaks *after* the pass — advance must re-evaluate and refuse
    eng.ctx.success_criteria = []
    with pytest.raises(AdvanceBlocked):
        eng.advance()
    assert eng.ctx.current_phase == "success_criteria"  # did not move


def test_can_advance_is_live_not_cached() -> None:
    eng = Engagement(_ctx())
    _satisfied_success_criteria(eng)
    assert eng.can_advance() is True
    eng.ctx.stakeholders = []  # sponsors gone → gate must fail again
    assert eng.can_advance() is False


# -- multi-gate phases (bug: 4 industrial gates were registered but unwired) ---
def test_industrial_gates_attached_to_phases() -> None:
    assert phase_by_slug("connect").gates == ("air_gap",)
    assert phase_by_slug("deploy").gates == ("fat_sat", "functional_safety", "conformity")
    assert phase_by_slug("slo_sla").gates == ("slo", "shift_handover")
    # primary-gate back-compat property
    assert phase_by_slug("deploy").gate == "fat_sat"
    assert phase_by_slug("qualification").gate is None


def test_multi_gate_phase_blocks_on_any_failure() -> None:
    eng = Engagement(_ctx(profile="manufacturing"))
    eng.ctx.current_phase = "deploy"
    # FAT/SAT satisfied, but no hazard analysis → functional_safety must block
    eng.ctx.assets["fat"] = {"passed": True, "signed_off_by": "integrator"}
    eng.ctx.assets["sat"] = {"passed": True, "signed_off_by": "client"}
    with pytest.raises(AdvanceBlocked) as exc:
        eng.advance()
    assert any("危险分析" in b for b in exc.value.result.blockers)
    # the passing fat_sat gate was still evaluated and recorded
    assert eng.ctx.gate_records["fat_sat"].passed is True


def test_ticket_profile_not_blocked_by_industrial_gates() -> None:
    # connect carries air_gap, but it is industrial_only → ticket advances freely
    eng = Engagement(_ctx())
    eng.ctx.current_phase = "connect"
    assert eng.advance().slug == "corpus"


# -- rollback must stay inside the profile's visible phases --------------------
def test_rollback_to_invisible_phase_raises() -> None:
    eng = Engagement(_ctx())  # ticket profile
    eng.ctx.current_phase = "corpus"
    with pytest.raises(ValueError, match="not visible"):
        eng.rollback("site_survey")  # industrial-only phase


def test_rollback_to_industrial_phase_ok_for_manufacturing() -> None:
    eng = Engagement(_ctx(profile="manufacturing"))
    eng.ctx.current_phase = "corpus"
    eng.rollback("site_survey")
    assert eng.ctx.current_phase == "site_survey"
    assert eng.is_complete is False


# -- unknown gate slugs fail loudly ---------------------------------------------
def test_evaluate_gate_unknown_slug_raises() -> None:
    eng = Engagement(_ctx())
    with pytest.raises(KeyError):
        eng.evaluate_gate("fatt_sat")  # typo must not "pass" silently


# -- journal（现场记录） -----------------------------------------------------------
def test_journal_entry_defaults() -> None:
    e = JournalEntry(kind="research", note="现场调研")
    assert e.id.startswith("jn-")
    assert e.ts  # ISO timestamp auto-generated
    assert e.skill_id is None


def test_context_journal_roundtrip() -> None:
    ctx = EngagementContext(id="e1", customer="Acme")
    ctx.journal.append(JournalEntry(kind="optimization", note="调优：降低误报"))
    ctx2 = EngagementContext.model_validate(ctx.model_dump())
    assert len(ctx2.journal) == 1
    assert ctx2.journal[0].kind == "optimization"
    assert ctx2.journal[0].note == "调优：降低误报"


def test_legacy_context_json_without_journal_loads(tmp_path) -> None:
    p = tmp_path / "legacy.json"
    p.write_text(json.dumps({"id": "e-old", "customer": "OldCo"}), encoding="utf-8")
    ctx = EngagementContext.load(p)
    assert ctx.journal == []


def test_save_is_atomic_keeps_previous_version_on_failure(tmp_path, monkeypatch) -> None:
    """A failed write leaves the previous complete JSON in place — never a
    truncated mix (architecture risk R4 / action A3)."""
    import fde_scope.fsutil as fsutil

    ctx = EngagementContext(id="e-atomic", customer="Acme")
    target = tmp_path / "eng" / "e-atomic.json"
    ctx.save(target)
    old = target.read_text(encoding="utf-8")

    def _boom(src: str, dst: str) -> None:
        raise OSError("simulated crash mid-replace")

    monkeypatch.setattr(fsutil.os, "replace", _boom)
    with pytest.raises(OSError):
        ctx.save(target)
    # previous version intact; no .tmp-* residue left behind
    assert target.read_text(encoding="utf-8") == old
    assert list((tmp_path / "eng").glob(".tmp-*")) == []


def test_save_roundtrip_after_atomic_write(tmp_path) -> None:
    ctx = EngagementContext(id="e2", customer="Acme")
    target = tmp_path / "nested" / "dir" / "e.json"
    assert ctx.save(target) == target
    ctx.customer = "Acme 2"
    ctx.save(target)
    assert EngagementContext.load(target).customer == "Acme 2"
