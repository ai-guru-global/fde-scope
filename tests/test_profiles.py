"""Tests for profiles + manufacturing KPIs + handoff package."""

from __future__ import annotations

from fde_scope.engagement import EngagementContext
from fde_scope.engagement.handoff import build_handoff_package, render_handoff_summary
from fde_scope.profiles import all_profiles, get_profile
from fde_scope.eval.manufacturing_metrics import (
    collision_intervention_rate,
    dpmo,
    first_pass_yield,
    grasp_success_rate,
    mtbf,
    mttr,
    oee,
    task_completion_rate,
)


# -- profiles ----------------------------------------------------------------
def test_get_profile_ticket() -> None:
    p = get_profile("ticket")
    assert not p.is_industrial
    assert "csv" in p.primary_connectors


def test_get_profile_manufacturing() -> None:
    p = get_profile("manufacturing")
    assert p.is_industrial
    assert "opcua" in p.primary_connectors
    assert "oee" in p.kpi_catalogue


def test_unknown_profile_raises() -> None:
    import pytest

    with pytest.raises(KeyError):
        get_profile("space")


def test_all_profiles_lists_both() -> None:
    assert set(all_profiles()) >= {"ticket", "manufacturing"}


# -- KPI calculators ---------------------------------------------------------
def test_oee_world_class() -> None:
    # 0.90 * 0.95 * 0.99 = 0.84645 ≈ world-class
    assert 0.84 < oee(0.90, 0.95, 0.99) < 0.85


def test_oee_zero_when_any_zero() -> None:
    assert oee(0.0, 0.95, 0.99) == 0.0


def test_mtbf_and_mttr() -> None:
    assert mtbf(1000.0, 5) == 200.0
    assert mttr(20.0, 5) == 4.0


def test_first_pass_yield() -> None:
    assert first_pass_yield(95, 100) == 0.95


def test_dpmo_six_sigma_anchor() -> None:
    # 34 defects / (1M units * 1 opp) → 34 DPMO (not 3.4, but right formula)
    assert dpmo(34, 1_000_000, 1) == 34.0


def test_grasp_and_task_rates() -> None:
    assert grasp_success_rate(80, 100) == 0.80
    assert task_completion_rate(9, 10) == 0.90


def test_collision_rate() -> None:
    assert collision_intervention_rate(5, 1000) == 0.005


# -- profile KPI aggregation -------------------------------------------------
def test_manufacturing_profile_aggregates_samples() -> None:
    p = get_profile("manufacturing")
    samples = [
        {"availability": 0.90, "performance": 0.95, "quality": 0.99,
         "uptime_hours": 100, "failures": 2, "repair_hours": 4,
         "good_units": 95, "started_units": 100, "defects": 5,
         "opportunities_per_unit": 1,
         "grasp_successes": 80, "grasp_attempts": 100,
         "tasks_succeeded": 90, "tasks_attempted": 100,
         "interventions": 3, "cycles": 1000},
    ]
    kpis = p.compute_kpis(samples)
    assert 0 < kpis["oee"] < 1
    assert kpis["mtbf"] == 50.0
    assert kpis["grasp_success_rate"] == 0.80


def test_ticket_profile_aggregates() -> None:
    p = get_profile("ticket")
    samples = [
        {"intent_correct": True, "adopted": True, "escalated": False, "handle_time_seconds": 30},
        {"intent_correct": False, "adopted": False, "escalated": True, "handle_time_seconds": 60},
    ]
    kpis = p.compute_kpis(samples)
    assert kpis["intent_accuracy"] == 0.5
    assert kpis["escalation_rate"] == 0.5


# -- handoff -----------------------------------------------------------------
def test_handoff_package_builds_and_renders() -> None:
    ctx = EngagementContext(id="m1", customer="BMW", profile="manufacturing")
    pkg = build_handoff_package(ctx, runbook_path="r.md", eval_report_path="e.html",
                                customer_accepted=True)
    assert pkg["customer_accepted"] is True
    assert pkg["runbook"] == "r.md"
    summary = render_handoff_summary(ctx)
    assert "BMW" in summary
