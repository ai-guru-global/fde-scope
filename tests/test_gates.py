"""Tests for the industrial + zone gates."""

from __future__ import annotations

import pytest

from fde_scope.engagement import Engagement, EngagementContext, SafetyPosture, SiteInfo
from fde_scope.engagement.engagement import _default_gate_registry


def _eng(profile="manufacturing", **kw) -> Engagement:
    ctx = EngagementContext(id="m1", customer="Aurora Motors", profile=profile, **kw)
    return Engagement(ctx)


# -- functional safety -------------------------------------------------------
def test_functional_safety_blocks_on_low_pl() -> None:
    eng = _eng(safety=SafetyPosture(required_plr="d", achieved_pl="b", hazard_analysis_done=True))
    result = eng.evaluate_gate("functional_safety")
    assert not result.passed
    assert any("ISO 13849" in b for b in result.blockers)


def test_functional_safety_blocks_on_missing_hazard_analysis() -> None:
    eng = _eng(safety=SafetyPosture(required_plr="d", achieved_pl="d"))
    result = eng.evaluate_gate("functional_safety")
    assert not result.passed
    assert any("危险分析" in b for b in result.blockers)


def test_functional_safety_passes_when_met() -> None:
    eng = _eng(
        safety=SafetyPosture(
            required_plr="d", achieved_pl="e", iso10218_assessed=True, hazard_analysis_done=True
        )
    )
    result = eng.evaluate_gate("functional_safety")
    assert result.passed


def test_functional_safety_warns_on_missing_sil_achievement() -> None:
    eng = _eng(safety=SafetyPosture(sil_required=2, hazard_analysis_done=True))
    result = eng.evaluate_gate("functional_safety")
    assert result.passed  # warning, not blocker
    assert any("SIL" in w for w in result.warnings)


def test_functional_safety_warns_on_unrecognized_pl() -> None:
    # "PL_D" is not a valid PL token — it must not be silently ranked 0
    eng = _eng(safety=SafetyPosture(required_plr="PL_D", achieved_pl="d", hazard_analysis_done=True))
    result = eng.evaluate_gate("functional_safety")
    assert result.passed  # warning, not blocker
    assert any("无法识别" in w and "PL_D" in w for w in result.warnings)


# -- gates don't apply to ticket profile -------------------------------------
def test_industrial_gates_skip_for_ticket() -> None:
    eng = _eng(profile="ticket")
    result = eng.evaluate_gate("functional_safety")
    assert result.passed
    assert result.notes  # "not applicable"


def test_not_applicable_gate_result_is_recorded() -> None:
    # status().gate_passed reads gate_records only — a skipped gate must still
    # leave a passing record, or multi-gate phases (slo_sla) report a false ❌.
    eng = _eng(profile="ticket")
    result = eng.evaluate_gate("shift_handover")
    assert result.passed
    rec = eng.ctx.gate_records["shift_handover"]
    assert rec.passed


def test_gate_passed_true_for_ticket_at_slo_sla() -> None:
    from fde_scope.engagement import SLOSpec

    eng = _eng(
        profile="ticket",
        current_phase="slo_sla",
        slos=[SLOSpec(name="availability", target="99.5%")],
    )
    for slug in ("slo", "shift_handover"):
        assert eng.evaluate_gate(slug).passed
    assert eng.status()["gate_passed"] is True


# -- FAT/SAT -----------------------------------------------------------------
def test_fat_sat_blocks_without_records() -> None:
    eng = _eng()
    result = eng.evaluate_gate("fat_sat")
    assert not result.passed
    assert any("FAT" in b for b in result.blockers)


def test_fat_sat_passes_with_signed_records() -> None:
    eng = _eng()
    eng.ctx.assets["fat"] = {"passed": True, "signed_off_by": "integrator"}
    eng.ctx.assets["sat"] = {"passed": True, "signed_off_by": "client"}
    result = eng.evaluate_gate("fat_sat")
    assert result.passed


# -- conformity --------------------------------------------------------------
def test_conformity_blocks_high_risk_without_ce() -> None:
    eng = _eng(safety=SafetyPosture(eu_ai_act_high_risk=True, hazard_analysis_done=True))
    result = eng.evaluate_gate("conformity")
    assert not result.passed
    assert any("CE" in b for b in result.blockers)


# -- works council -----------------------------------------------------------
def test_works_council_blocks_when_represented_and_no_approval() -> None:
    eng = _eng(site=SiteInfo(works_council_represented=True))
    result = eng.evaluate_gate("works_council")
    assert not result.passed


def test_works_council_skips_when_not_represented() -> None:
    eng = _eng(site=SiteInfo(works_council_represented=False))
    result = eng.evaluate_gate("works_council")
    assert result.passed


# -- air gap -----------------------------------------------------------------
def test_air_gap_blocks_when_egress_allowed() -> None:
    eng = _eng(site=SiteInfo(air_gapped=True))
    eng.ctx.assets["air_gap_plan"] = {
        "edge_hardware": "NVIDIA edge",
        "offline_model_update": "usb courier",
        "telemetry_egress_allowed": True,
        "local_storage": "local ssd",
    }
    result = eng.evaluate_gate("air_gap")
    assert not result.passed
    assert any("遥测" in b or "telemetry" in b.lower() for b in result.blockers)


def test_air_gap_passes_when_clean() -> None:
    eng = _eng(site=SiteInfo(air_gapped=True))
    eng.ctx.assets["air_gap_plan"] = {
        "edge_hardware": "NVIDIA edge",
        "offline_model_update": "usb courier",
        "telemetry_egress_allowed": False,
    }
    result = eng.evaluate_gate("air_gap")
    assert result.passed


# -- shift handover ----------------------------------------------------------
def test_shift_handover_blocks_multi_shift_without_integration() -> None:
    eng = _eng(site=SiteInfo(shift_count=3))
    result = eng.evaluate_gate("shift_handover")
    assert not result.passed


def test_shift_handover_skips_single_shift() -> None:
    eng = _eng(site=SiteInfo(shift_count=1))
    result = eng.evaluate_gate("shift_handover")
    assert result.passed


# -- handoff -----------------------------------------------------------------
def test_handoff_gate_blocks_without_package() -> None:
    eng = _eng()
    result = eng.evaluate_gate("handoff_signoff")
    assert not result.passed


def test_handoff_gate_blocks_until_customer_accepts() -> None:
    # docstring contract: "Block disengagement until the handoff package is accepted"
    eng = _eng()
    eng.ctx.assets["handoff_package"] = {
        "runbook": "r.md",
        "eval_report": "e.html",
        "slo_definition": [{"name": "availability"}],
        "training_material": "t.md",
        "customer_accepted": False,
    }
    result = eng.evaluate_gate("handoff_signoff")
    assert not result.passed
    assert any("接受" in b for b in result.blockers)

    eng.ctx.assets["handoff_package"]["customer_accepted"] = True
    assert eng.evaluate_gate("handoff_signoff").passed


# -- SLO template --------------------------------------------------------------
def test_slo_template_error_budget_arithmetic() -> None:
    # 99.5% availability over 14d → 14 × 24h × 0.5% = 1.68h error budget
    from fde_scope.engagement.operationalization import build_slo_template

    availability = next(s for s in build_slo_template() if s["name"] == "availability")
    assert availability["error_budget"] == "1.68h / 14d"


# -- malformed asset records: fail closed, never crash -------------------------
# ctx.assets is free-form dict[str, Any] fed straight from client JSON (POST
# …/context merges it with no per-key schema), so a gate can be handed
# "fat": "done". Each gate read it with .get(), which raised AttributeError out
# of Engagement.advance — mid-phase, after the earlier gates had already been
# recorded — and surfaced as a 500 in the web layer.
_MALFORMED = [
    ("fat_sat", "fat", {}),
    ("air_gap", "air_gap_plan", {"air_gapped": True}),
    ("shift_handover", "shift_handover", {"shift_count": 3}),
    ("works_council", "works_council_approval", {"works_council_represented": True}),
]


@pytest.mark.parametrize("slug,key,site_flags", _MALFORMED)
@pytest.mark.parametrize("shape", ["done", 42, 3.5, ["gpu"], True])
def test_malformed_asset_yields_a_blocker_not_a_crash(slug, key, site_flags, shape) -> None:
    eng = _eng(site=SiteInfo(**site_flags))
    eng.ctx.assets[key] = shape
    result = eng.evaluate_gate(slug)
    assert not result.passed
    assert any(f"assets.{key}" in b and shape.__class__.__name__ in b for b in result.blockers)


def test_missing_asset_is_still_the_gates_own_blocker() -> None:
    """None and {} are absent-shaped, not malformed: the gate's domain wording
    must survive, with no format complaint on top."""
    for shape in (None, {}):
        eng = _eng()
        if shape is not None:
            eng.ctx.assets["fat"] = shape
        result = eng.evaluate_gate("fat_sat")
        assert not result.passed
        assert any("未执行或未记录" in b for b in result.blockers)
        assert not any("assets.fat" in b for b in result.blockers)


def test_valid_mapping_record_still_passes() -> None:
    """Failing closed on shapes must not tighten the bar for real records —
    including Mapping types a caller may hand over that are not dict."""
    from types import MappingProxyType

    eng = _eng()
    eng.ctx.assets["fat"] = MappingProxyType({"passed": True, "signed_off_by": "integrator"})
    eng.ctx.assets["sat"] = {"passed": True, "signed_off_by": "client"}
    assert eng.evaluate_gate("fat_sat").passed


def test_advance_reports_bad_asset_and_still_sweeps_the_phase() -> None:
    """deploy runs fat_sat → functional_safety → conformity. A crash in the
    first used to abort the sweep and leave the rest with no record; a bad
    asset must block while every gate of the phase is still evaluated."""
    from fde_scope.engagement.engagement import AdvanceBlocked

    eng = _eng(current_phase="deploy")
    eng.ctx.assets["fat"] = "signed off by email"
    with pytest.raises(AdvanceBlocked) as exc:
        eng.advance()
    assert "assets.fat" in str(exc.value)
    assert eng.ctx.current_phase == "deploy"
    assert {"fat_sat", "functional_safety", "conformity"} <= set(eng.ctx.gate_records)


def test_all_gates_registered() -> None:
    reg = _default_gate_registry()
    for slug in [
        "site_survey",
        "success_criteria",
        "fat_sat",
        "functional_safety",
        "conformity",
        "works_council",
        "air_gap",
        "shift_handover",
        "slo",
        "handoff_signoff",
    ]:
        assert slug in reg
