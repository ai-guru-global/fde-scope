"""Guided-mode domain layer: catalog map, deliverables, blocker advice, guided_view."""

from __future__ import annotations

from pathlib import Path

import pytest

from fde_scope.engagement.catalog_map import CATALOG_BY_PHASE, CATALOG_BY_ZONE, pages_for_phase
from fde_scope.engagement.context import EngagementContext, Stakeholder
from fde_scope.engagement.engagement import _default_gate_registry
from fde_scope.engagement.guided import (
    BLOCKER_ADVICE,
    PHASE_DELIVERABLES,
    guided_view,
    llm_draft_context,
    next_steps_for,
)
from fde_scope.engagement.phases import PHASES, Zone

_CATALOG_ROOT = Path(__file__).resolve().parents[1] / "docs" / "skills-catalog"

_PHASE_SLUGS = {p.slug for p in PHASES}
_GATE_SLUGS = set(_default_gate_registry())


def test_phase_deliverables_cover_every_phase() -> None:
    assert set(PHASE_DELIVERABLES) == _PHASE_SLUGS
    assert all(
        isinstance(v, list) and v and all(isinstance(x, str) for x in v) for v in PHASE_DELIVERABLES.values()
    )


def test_catalog_map_covers_every_phase() -> None:
    assert set(CATALOG_BY_PHASE) == _PHASE_SLUGS
    assert set(CATALOG_BY_ZONE) == set(Zone)


def test_catalog_routes_point_at_real_pages() -> None:
    if not _CATALOG_ROOT.is_dir():  # installed-wheel checkout without docs/
        pytest.skip("docs/skills-catalog not present")
    for routes in [*CATALOG_BY_PHASE.values(), *CATALOG_BY_ZONE.values()]:
        for route in routes:
            assert (_CATALOG_ROOT / f"{route}.md").exists(), f"missing catalog page: {route}"


def test_blocker_advice_covers_every_gate() -> None:
    assert set(BLOCKER_ADVICE) == _GATE_SLUGS
    for rules in BLOCKER_ADVICE.values():
        for needle, advice, target in rules:
            assert needle and advice and target


def test_pages_for_phase_local_and_github() -> None:
    gh = pages_for_phase("qualification", local=False)
    local = pages_for_phase("qualification", local=True)
    assert gh and len(gh) == len(local)
    assert all(p["url"].startswith("https://github.com/") and p["url"].endswith(".md") for p in gh)
    assert all(p["url"].startswith("/catalog/index.html#/") for p in local)
    assert all(p["url_en"].startswith("/catalog/en/index.html#/") for p in local)


def test_guided_view_empty_ticket_ctx() -> None:
    ctx = EngagementContext(id="eng-x", customer="Acme", profile="ticket")
    view = guided_view(ctx)
    assert view["phase"]["slug"] == "qualification"
    assert view["phase"]["progress"] == "1/15"
    assert view["phase"]["description"]
    assert view["deliverables"]  # qualification checklist exists
    assert view["gates"] == {}  # qualification carries no gate
    assert view["plan"] is None
    assert isinstance(view["llm_available"], bool)
    assert view["catalog_pages"]


def test_guided_view_industrial_progress_and_gates() -> None:
    ctx = EngagementContext(
        id="eng-m", customer="BMW", profile="manufacturing", current_phase="success_criteria"
    )
    view = guided_view(ctx)
    assert view["phase"]["progress"] == "4/18"
    gate = view["gates"]["success_criteria"]
    assert gate["passed"] is False
    assert gate["blockers"]
    # every blocker is translated into an actionable next step
    assert len(gate["next_steps"]) == len(gate["blockers"]) + len(gate["warnings"])
    for step in gate["next_steps"]:
        assert isinstance(step["advice"], str) and step["advice"]
        assert isinstance(step["target"], str) and step["target"]


def test_guided_view_is_read_only() -> None:
    """Guidance must never write gate records or touch the state machine."""
    ctx = EngagementContext(id="eng-ro", customer="Acme", profile="ticket", current_phase="success_criteria")
    before = ctx.model_dump()
    guided_view(ctx)
    assert ctx.model_dump() == before


def test_next_steps_for_unknown_blocker_falls_back() -> None:
    from fde_scope.engagement.gates.base import GateResult

    result = GateResult(slug="slo", passed=False, blockers=["某种没见过的阻塞"])
    steps = next_steps_for("slo", result)
    assert len(steps) == 1
    assert "重新校验" in steps[0]["advice"]
    assert steps[0]["target"] == "tab:gates"


def test_next_steps_matches_by_substring() -> None:
    from fde_scope.engagement.gates.base import GateResult

    result = GateResult(
        slug="success_criteria",
        passed=False,
        blockers=["仅有 1 个 sponsor——要求 ≥2（防 Sponsor Collapse）"],
    )
    steps = next_steps_for("success_criteria", result)
    assert steps[0]["target"] == "context:stakeholders"
    assert "sponsor" in steps[0]["advice"].lower()


def test_guided_view_surfaces_plan_from_assets() -> None:
    ctx = EngagementContext(id="eng-p", customer="Acme", profile="ticket")
    ctx.assets["guided_plan"] = {"goal": "g", "items": []}
    view = guided_view(ctx)
    assert view["plan"] == {"goal": "g", "items": []}


def test_guided_view_stakeholder_pass_path() -> None:
    ctx = EngagementContext(
        id="eng-ok",
        customer="Acme",
        profile="ticket",
        current_phase="success_criteria",
        success_criteria=["首响 <8s"],
        stakeholders=[
            Stakeholder(name="A", role="CTO", is_sponsor=True, success_metric="首响 <8s"),
            Stakeholder(name="B", role="COO", is_sponsor=True, success_metric="坏例率 <10%"),
        ],
    )
    view = guided_view(ctx)
    gate = view["gates"]["success_criteria"]
    assert gate["passed"] is True
    assert gate["next_steps"] == []


# ---------------------------------------------------------------------------
# AI draft context（迭代 3）
# ---------------------------------------------------------------------------
class FakeLLM:
    def __init__(self, reply: str | None = None, *, error: bool = False, available: bool = True) -> None:
        self._reply = reply
        self._error = error
        self.available = available
        self.calls = 0

    def complete(self, prompt, **kwargs):  # noqa: ANN001, ANN201
        self.calls += 1
        if self._error:
            raise RuntimeError("boom")
        return self._reply


def _ctx(**kw) -> EngagementContext:
    defaults = {"id": "eng-t", "customer": "Acme", "profile": "ticket"}
    defaults.update(kw)
    return EngagementContext(**defaults)


_GOOD_DRAFT = (
    '{"site": {"location": "长春工厂", "shift_count": 3},'
    ' "stakeholders": [{"name": "张三", "role": "CTO", "is_sponsor": true, "success_metric": "首响<8s"},'
    '{"name": "李四", "role": "COO", "is_sponsor": true}],'
    ' "success_criteria": ["首响 <8s", "坏例率 <10%"],'
    ' "slos": [{"name": "availability", "target": "99.5%", "window": "14d"}]}'
)


def test_llm_draft_context_happy_path() -> None:
    draft, used = llm_draft_context(_ctx(), "描述", FakeLLM(_GOOD_DRAFT))
    assert used is True
    assert draft is not None
    assert draft["site"]["location"] == "长春工厂"
    assert len(draft["stakeholders"]) == 2
    assert draft["success_criteria"] == ["首响 <8s", "坏例率 <10%"]
    assert draft["slos"][0]["name"] == "availability"


def test_llm_draft_context_strips_fences_and_prose() -> None:
    fenced = "好的，结果如下：\n```json\n" + _GOOD_DRAFT + "\n```\n希望有帮助。"
    draft, used = llm_draft_context(_ctx(), "描述", FakeLLM(fenced))
    assert used is True and draft is not None


def test_llm_draft_context_bad_json_returns_none() -> None:
    assert llm_draft_context(_ctx(), "描述", FakeLLM("这不是 JSON")) == (None, False)


def test_llm_draft_context_partial_blocks_adopted() -> None:
    partial = (
        '{"site": "not-a-dict", "stakeholders": [{"name": "王五", "role": "CEO"}], "slos": [{"bad": 1}]}'
    )
    draft, used = llm_draft_context(_ctx(), "描述", FakeLLM(partial))
    assert used is True
    assert draft == {
        "stakeholders": [{"name": "王五", "role": "CEO", "is_sponsor": False, "success_metric": ""}]
    }


def test_llm_draft_context_drops_safety_block() -> None:
    """SafetyPosture is compliance sign-off data — never AI-draftable."""
    payload = '{"safety": {"ce_marking_done": true}, "success_criteria": ["x"]}'
    draft, used = llm_draft_context(_ctx(), "描述", FakeLLM(payload))
    assert used is True
    assert "safety" not in draft
    assert draft == {"success_criteria": ["x"]}


def test_llm_draft_context_llm_error_returns_none() -> None:
    assert llm_draft_context(_ctx(), "描述", FakeLLM(error=True)) == (None, False)


def test_llm_draft_context_unavailable_makes_no_call() -> None:
    fake = FakeLLM(_GOOD_DRAFT, available=False)
    assert llm_draft_context(_ctx(), "描述", fake) == (None, False)
    assert fake.calls == 0
    assert llm_draft_context(_ctx(), "描述", None) == (None, False)


def test_llm_draft_context_caps_list_lengths() -> None:
    import json

    payload = json.dumps({"success_criteria": [f"c{i}" for i in range(50)]})
    draft, used = llm_draft_context(_ctx(), "描述", FakeLLM(payload))
    assert used is True and len(draft["success_criteria"]) == 10


def test_context_field_guide_variants() -> None:
    from fde_scope.engagement.guided import context_field_guide

    ind = {b["block"] for b in context_field_guide(True)}
    tkt = {b["block"] for b in context_field_guide(False)}
    assert ind == {"site", "stakeholders", "success_criteria", "slos"}
    assert tkt == {"stakeholders", "success_criteria", "slos"}


# ---------------------------------------------------------------------------
# 目标拆解（迭代 4）
# ---------------------------------------------------------------------------
def test_rule_plan_covers_all_visible_phases() -> None:
    from fde_scope.engagement.guided import rule_plan

    for profile, expected in (("ticket", 15), ("manufacturing", 18)):
        plan = rule_plan(_ctx(profile=profile), "目标")
        slugs = {i["phase_slug"] for i in plan["items"]}
        assert len(slugs) == expected
        assert plan["used_llm"] is False
        ids = [i["id"] for i in plan["items"]]
        assert len(ids) == len(set(ids))  # server-generated, unique
        assert all(i["done"] is False and i["title"] for i in plan["items"])


def test_llm_goal_plan_overrides_and_drops_unknown_slugs() -> None:
    from fde_scope.engagement.guided import PHASE_DELIVERABLES, llm_goal_plan, rule_plan

    reply = '{"qualification": ["定制任务A", "定制任务B"], "bogus_slug": ["垃圾"]}'
    plan, used = llm_goal_plan(_ctx(profile="ticket"), "目标", FakeLLM(reply))
    assert used is True
    qual = [i["title"] for i in plan["items"] if i["phase_slug"] == "qualification"]
    assert qual == ["定制任务A", "定制任务B"]
    assert not any(i["phase_slug"] == "bogus_slug" for i in plan["items"])
    # untouched phases keep the rule skeleton
    skeleton = rule_plan(_ctx(profile="ticket"), "目标")
    for slug in ("corpus", "eval"):
        kept = [i["title"] for i in plan["items"] if i["phase_slug"] == slug]
        base = [i["title"] for i in skeleton["items"] if i["phase_slug"] == slug]
        assert kept == base
        assert kept[:1] == [PHASE_DELIVERABLES[slug][0]]


def test_llm_goal_plan_falls_back_to_rule_plan() -> None:
    from fde_scope.engagement.guided import llm_goal_plan

    plan, used = llm_goal_plan(_ctx(), "目标", FakeLLM("不是 JSON"))
    assert used is False and plan["items"]
    plan, used = llm_goal_plan(_ctx(), "目标", FakeLLM(error=True))
    assert used is False and plan["items"]
    plan, used = llm_goal_plan(_ctx(), "目标", FakeLLM(available=False))
    assert used is False and plan["items"]
