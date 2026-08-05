"""The engagement layer — FDE Scope's SOP state machine + enforced gates.

This is the top-level orchestration that turns the FDE's on-site standard
operating procedure from a checklist into an executable, gate-enforced
process. It spans the full 4-zone / 18-phase lifecycle, with an industrial
overlay (FAT/SAT, functional safety, CE/EU-AI-Act, works council, air-gap,
shift handover) for manufacturing/robotics profiles.

Public surface:
    - Engagement          the state machine (advance / rollback / status)
    - EngagementContext   the persisted engagement state
    - Gate / GateResult   the phase-gate contract
    - phases / Zone       the SOP phase model
"""

from .context import EngagementContext, GateRecord, SafetyPosture, SiteInfo, SLOSpec, Stakeholder
from .engagement import AdvanceBlocked, Engagement
from .gates.base import Gate, GateResult
from .handoff import build_handoff_package, render_handoff_summary
from .phases import PHASES, Phase, Zone, phases_for_profile

__all__ = [
    "AdvanceBlocked",
    "Engagement",
    "EngagementContext",
    "Gate",
    "GateResult",
    "GateRecord",
    "PHASES",
    "Phase",
    "SafetyPosture",
    "SLOSpec",
    "SiteInfo",
    "Stakeholder",
    "Zone",
    "build_handoff_package",
    "phases_for_profile",
    "render_handoff_summary",
]
