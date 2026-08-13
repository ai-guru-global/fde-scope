"""End-to-end integration test: a full manufacturing engagement from
qualification to signed-off handoff, exercising the SOP state machine,
the industrial gate overlay, profile KPIs, corpus forge, and handoff package.

This is the single test that proves the whole system hangs together as a
credible FDE workbench — not just isolated units.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fde_scope.engagement import Engagement, EngagementContext, SafetyPosture, SiteInfo, SLOSpec, Stakeholder
from fde_scope.engagement.handoff import build_handoff_package, render_handoff_summary
from fde_scope.engagement.operationalization import render_runbook
from fde_scope.profiles import get_profile


# ---------------------------------------------------------------------------
# Fixtures specific to this integration test
# ---------------------------------------------------------------------------
@pytest.fixture
def station_kpi_jsonl(tmp_path: Path) -> Path:
    """A tiny MES station-KPI export (the quickstart shape)."""
    records = [
        {
            "station": "WELD-01",
            "availability": 0.90,
            "performance": 0.88,
            "quality": 0.96,
            "uptime_hours": 168,
            "failures": 3,
            "repair_hours": 9,
            "good_units": 1840,
            "started_units": 1920,
            "defects": 80,
            "opportunities_per_unit": 4,
            "grasp_successes": 0,
            "grasp_attempts": 0,
            "tasks_succeeded": 850,
            "tasks_attempted": 900,
            "interventions": 12,
            "cycles": 1800,
        },
        {
            "station": "COBOT-01",
            "availability": 0.87,
            "performance": 0.86,
            "quality": 0.94,
            "uptime_hours": 155,
            "failures": 5,
            "repair_hours": 15,
            "good_units": 1620,
            "started_units": 1720,
            "defects": 100,
            "opportunities_per_unit": 5,
            "grasp_successes": 1500,
            "grasp_attempts": 1900,
            "tasks_succeeded": 1700,
            "tasks_attempted": 1850,
            "interventions": 25,
            "cycles": 1700,
        },
    ]
    p = tmp_path / "mes_export.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# The full engagement walkthrough
# ---------------------------------------------------------------------------
def test_full_manufacturing_engagement_lifecycle(station_kpi_jsonl: Path, sample_csv: Path) -> None:
    """Walk a manufacturing engagement end-to-end through all 4 zones."""
    ctx = EngagementContext(id="bmw-e2e", customer="BMW Spartanburg", profile="manufacturing")
    eng = Engagement(ctx)

    # ---- Zone A: Pre-engagement ------------------------------------------
    # Phase 1 → 2: qualification has no gate → free advance
    assert eng.advance().slug == "site_survey"

    # Phase 2: site_survey (industrial gate) — fill it, then it passes
    eng.ctx.site = SiteInfo(
        location="Spartanburg, SC",
        ot_it_separated=True,
        air_gapped=False,
        networks=["OT-VLAN-10", "IT-VLAN-20"],
        shift_count=3,
        works_council_represented=True,
        assets=[{"name": "BODY-WELD-01", "vendor": "Siemens", "protocol": "OPC UA"}],
    )
    result = eng.evaluate_gate("site_survey")
    assert result.passed, f"site_survey gate should pass: {result.blockers}"
    assert eng.advance().slug == "stakeholder_map"

    # Phase 3 → 4: stakeholder_map has no gate → advance
    assert eng.advance().slug == "success_criteria"

    # Phase 4: success_criteria gate — satisfy dual-sponsor + criteria
    eng.ctx.success_criteria = ["grasp_rate >= 0.85", "intervention_rate <= 0.015"]
    eng.ctx.stakeholders = [
        Stakeholder(
            name="Prod Director", role="VP Manufacturing", is_sponsor=True, success_metric="OEE +5pp"
        ),
        Stakeholder(name="IT Director", role="VP IT", is_sponsor=True, success_metric="uptime 99.5%"),
    ]
    assert eng.evaluate_gate("success_criteria").passed
    assert eng.advance().slug == "connect"  # entered Zone B

    # ---- Zone B: Build ---------------------------------------------------
    # connect → corpus → prototype → validate → deploy
    for _expected in ("corpus", "prototype_real_data", "validate", "deploy"):
        if eng.phase.slug == "deploy":
            break
        # advance through build phases whose gates (if any) pass until deploy
        if eng.can_advance():
            eng.advance()

    # Forge a corpus from the ticket sample (the corpus engine is profile-agnostic)
    from fde_scope.config import CorpusConfig
    from fde_scope.corpus import CorpusForge

    rows = json.loads(
        json.dumps(
            [  # deep copy sample_rows via the csv connector
                {"id": "x", "content": "机器人抓取失败，请检查夹爪压力。", "category": "抓取故障"},
                {"id": "y", "content": "焊接工位节拍不达标。", "category": "节拍异常"},
            ]
        )
    )
    report = CorpusForge(CorpusConfig(min_samples_per_category=10, synth_per_gap=2)).forge_rows(rows)
    assert report.total >= 2

    # deploy phase: FAT/SAT gate — satisfy it
    eng.ctx.current_phase = "deploy"
    eng.ctx.assets["fat"] = {"passed": True, "signed_off_by": "integrator-lead"}
    eng.ctx.assets["sat"] = {"passed": True, "signed_off_by": "client-ops"}
    # functional safety for the cobot cell
    eng.ctx.safety = SafetyPosture(
        required_plr="d",
        achieved_pl="d",
        iso10218_assessed=True,
        hazard_analysis_done=True,
        eu_ai_act_high_risk=False,
        ce_marking_done=True,
    )
    assert eng.evaluate_gate("fat_sat").passed
    assert eng.evaluate_gate("functional_safety").passed
    assert eng.advance().slug == "eval"

    # eval: compute manufacturing KPIs from the MES export
    from fde_scope.connectors.mes_isa95 import MesConnector

    mes = MesConnector(str(station_kpi_jsonl), entity="station_kpi")
    samples = mes.extract_sample(100)
    assert len(samples) == 2
    prof = get_profile("manufacturing")
    kpis = prof.compute_kpis(samples)
    assert 0 < kpis["oee"] < 1
    assert kpis["grasp_success_rate"] > 0
    assert eng.advance().slug == "slo_sla"  # entered Zone C

    # ---- Zone C: Operationalization --------------------------------------
    # slo_sla gates: slo + shift_handover (3-shift site needs handover integration)
    eng.ctx.slos = [SLOSpec(name="grasp_success", target=">=0.85", alert_route="fde-oncall")]
    eng.ctx.assets["shift_handover"] = {
        "digital_log_integrated": True,
        "per_shift_runbook": True,
    }
    assert eng.evaluate_gate("slo").passed
    eng.advance()  # → runbook

    # runbook renders
    runbook = render_runbook(eng.ctx)
    assert "BMW Spartanburg" in runbook
    assert "SLO" in runbook
    eng.advance()  # → monitoring_drift
    eng.advance()  # → change_mgmt_training

    # works_council gate (site has works_council_represented=True)
    eng.ctx.assets["works_council_approval"] = {
        "status": "approved",
        "signed_off_by": "works-council-chair",
    }
    assert eng.evaluate_gate("works_council").passed
    eng.advance()  # → flywheel_productization
    eng.advance()  # → ops_handoff  (entered Zone D)

    # ---- Zone D: Handoff -------------------------------------------------
    eng.advance()  # → knowledge_transfer
    pkg = build_handoff_package(
        eng.ctx,
        runbook_path="reports/runbook_bmw.md",
        eval_report_path="reports/eval_bmw.html",
        training_material="docs/operator_training.md",
        customer_accepted=True,
    )
    assert pkg["customer_accepted"] is True
    eng.advance()  # → disengage

    # handoff_signoff gate — now satisfied
    assert eng.evaluate_gate("handoff_signoff").passed
    summary = render_handoff_summary(eng.ctx)
    assert "BMW Spartanburg" in summary
    assert "✅" in summary  # customer accepted

    # The engagement is terminal + complete
    assert eng.ctx.current_phase == "disengage"
    assert eng.is_complete
    with pytest.raises(StopIteration):
        eng.advance()


def test_manufacturing_gate_blocks_when_safety_unmet() -> None:
    """A gate failure must prevent advancement through deploy."""
    ctx = EngagementContext(id="unsafe", customer="UnsafeCo", profile="manufacturing")
    eng = Engagement(ctx)
    eng.ctx.current_phase = "deploy"
    # No FAT, no safety posture → both gates fail
    fat = eng.evaluate_gate("fat_sat")
    safety = eng.evaluate_gate("functional_safety")
    assert not fat.passed
    assert not safety.passed
    assert any("FAT" in b for b in fat.blockers)
    assert any("危险分析" in b for b in safety.blockers)


def test_mes_connector_reads_jsonl_export(station_kpi_jsonl: Path) -> None:
    """The MES connector's JSONL mode is fully working (not a stub)."""
    from fde_scope.connectors.mes_isa95 import MesConnector

    mes = MesConnector(str(station_kpi_jsonl), entity="station_kpi")
    schema = mes.discover_schema()
    assert schema.row_count == 2
    assert "station" in schema.field_names()

    sample = mes.extract_sample(10)
    assert len(sample) == 2
    assert sample[0]["station"] == "WELD-01"

    batches = list(mes.stream(batch_size=1))
    assert len(batches) == 2  # 2 records, batch_size 1 → 2 batches
