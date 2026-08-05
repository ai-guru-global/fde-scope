"""Zone A (Pre-engagement) gates + helpers.

Pre-engagement is the half of the SOP most teams skip — and the half that
determines whether the engagement produces real value or becomes an infinite
pilot. These gates enforce: a real site survey, a dual-sponsor stakeholder
map (the Sponsor Collapse anti-pattern), and contractual success criteria.
"""

from __future__ import annotations

from .context import EngagementContext
from .gates.base import Gate, GateResult


class SiteSurveyGate(Gate):
    """Industrial gemba walk — verify the site was actually surveyed."""

    slug = "site_survey"
    name = "Site Survey / Gemba Walk"
    industrial_only = True

    def check(self, ctx: EngagementContext) -> GateResult:
        blockers: list[str] = []
        warnings: list[str] = []
        site = ctx.site
        if not site.location:
            blockers.append("现场勘察缺失：location 未记录")
        if not site.assets:
            warnings.append("资产清单为空")
        if site.shift_count > 1 and not site.networks:
            warnings.append("多班次现场但未记录网络拓扑")
        return GateResult(slug=self.slug, passed=not blockers, blockers=blockers, warnings=warnings)


class SuccessCriteriaGate(Gate):
    """Contractual success criteria + dual sponsor (both zones)."""

    slug = "success_criteria"
    name = "Success Criteria & Dual Sponsor"

    def check(self, ctx: EngagementContext) -> GateResult:
        blockers: list[str] = []
        warnings: list[str] = []
        if not ctx.success_criteria:
            blockers.append("成功标准未定义——无法判定 done（无限 pilot 反模式）")
        sponsors = [s for s in ctx.stakeholders if s.is_sponsor]
        if len(sponsors) < 2:
            blockers.append(f"仅有 {len(sponsors)} 个 sponsor——要求 ≥2（防 Sponsor Collapse）")
        if not any(s.success_metric for s in sponsors):
            warnings.append("sponsor 未填写可度量的 success_metric")
        return GateResult(slug=self.slug, passed=not blockers, blockers=blockers, warnings=warnings)


# ---------------------------------------------------------------------------
# Pre-engagement generators (write structured artifacts into ctx.assets)
# ---------------------------------------------------------------------------
def build_site_survey_template() -> dict:
    """Seed a site-survey worksheet an FDE fills in on the gemba walk."""
    return {
        "location": "",
        "visit_date": "",
        "ot_it_separated": False,
        "air_gapped": False,
        "networks": [],
        "assets": [],  # {name, type, vendor, protocol, criticality}
        "shift_count": 1,
        "works_council_represented": False,
        "environmental": {"dust": False, "vibration": False, "temp_range": ""},
        "notes": "",
    }


def build_stakeholder_map_template() -> dict:
    return {
        "sponsors": [],  # [{name, role, success_metric, influence}]
        "naysayers": [],
        "operators": [],
        "it_ot_contacts": [],
    }


def build_success_criteria_template() -> dict:
    """Time-boxed SLAs (perspective.ai / FDE Academy consensus defaults)."""
    return {
        "time_to_first_integration_days": 14,
        "time_to_production_days": 90,
        "disengage_after_days": 120,
        "customer_engineering_counterpart_named": False,
        "measurable_outcomes": [],  # [{kpi, baseline, target}]
    }
