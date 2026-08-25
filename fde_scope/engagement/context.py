"""Engagement context — the shared state every phase and gate reads/writes.

This is the FDE's running notebook for one customer engagement: who the
sponsors are, what the site looks like, what the safety posture is, what
SLOs were agreed, which gates have passed. It persists to JSON so an
engagement survives across CLI invocations.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from .phases import Zone, phases_for_profile


class SafetyPosture(BaseModel):
    """Functional-safety facts the FunctionalSafetyGate and ConformityGate read.

    Industrial engagements fill these in during the site survey / safety
    assessment; the gates then check them against the standards.
    """

    # ISO 13849 — required vs achieved Performance Level (a..e)
    required_plr: str | None = None
    achieved_pl: str | None = None
    # IEC 61508 — required vs achieved Safety Integrity Level (1..4)
    sil_required: int | None = None
    sil_achieved: int | None = None
    # ISO 10218-1:2025 robot safety
    iso10218_assessed: bool = False
    # EU AI Act high-risk system?
    eu_ai_act_high_risk: bool = False
    ce_marking_done: bool = False
    # STPA / HAZOP lite
    hazard_analysis_done: bool = False
    risk_assessment_notes: str = ""


class SiteInfo(BaseModel):
    """Physical-site facts gathered during the site survey / Gemba walk."""

    location: str = ""
    ot_it_separated: bool = False
    air_gapped: bool = False
    networks: list[str] = Field(default_factory=list)
    assets: list[dict[str, Any]] = Field(default_factory=list)
    shift_count: int = 1
    works_council_represented: bool = False
    notes: str = ""


class Stakeholder(BaseModel):
    name: str
    role: str
    is_sponsor: bool = False
    success_metric: str = ""


class SLOSpec(BaseModel):
    name: str
    target: str
    error_budget: str = ""
    alert_route: str = ""
    window: str = "28d"


class GateRecord(BaseModel):
    """The persisted outcome of one gate check."""

    slug: str
    passed: bool
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checked_at: str = ""


class JournalEntry(BaseModel):
    """一条现场记录：调研 / 实施 / 调优（可选关联已沉淀技能）。"""

    id: str = Field(default_factory=lambda: f"jn-{secrets.token_hex(4)}")
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    kind: Literal["research", "implementation", "optimization"]
    note: str
    skill_id: str | None = None


class EngagementContext(BaseModel):
    """The full running state of one FDE engagement."""

    id: str
    customer: str
    profile: str = "ticket"  # ticket | manufacturing
    current_phase: str = "qualification"
    site: SiteInfo = Field(default_factory=SiteInfo)
    stakeholders: list[Stakeholder] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    safety: SafetyPosture = Field(default_factory=SafetyPosture)
    slos: list[SLOSpec] = Field(default_factory=list)
    journal: list[JournalEntry] = Field(default_factory=list)
    gate_records: dict[str, GateRecord] = Field(default_factory=dict)
    assets: dict[str, Any] = Field(default_factory=dict)  # free-form per-phase outputs

    @property
    def is_industrial(self) -> bool:
        return self.profile == "manufacturing"

    @property
    def visible_phases(self):
        return phases_for_profile(self.is_industrial)

    @property
    def current_zone(self) -> Zone:
        from .phases import phase_by_slug

        return phase_by_slug(self.current_phase).zone

    def gate_passed(self, slug: str) -> bool:
        rec = self.gate_records.get(slug)
        return bool(rec and rec.passed)

    # -- persistence ------------------------------------------------------------
    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return p

    @classmethod
    def load(cls, path: str | Path) -> EngagementContext:
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))
