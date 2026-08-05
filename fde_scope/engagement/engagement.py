"""The engagement state machine — drives an FDE engagement through the SOP.

The state machine advances an :class:`EngagementContext` phase by phase.
Before leaving a phase whose ``gate`` is set, the gate must pass; otherwise
the advance is refused and the blockers are returned. This is the single
enforcement point that makes the SOP real.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .context import EngagementContext, GateRecord
from .gates.base import Gate, GateResult
from .phases import Phase, next_phase, phase_by_slug


class AdvanceBlocked(Exception):
    """Raised when an advance is refused because a gate failed."""

    def __init__(self, result: GateResult) -> None:
        self.result = result
        super().__init__(result.summary())


class Engagement:
    """An FDE engagement: a context + the phase state machine."""

    def __init__(self, ctx: EngagementContext, gates: dict[str, Gate] | None = None) -> None:
        self.ctx = ctx
        self.gates = gates or _default_gate_registry()

    # -- phase queries ----------------------------------------------------------
    @property
    def phase(self) -> Phase:
        return phase_by_slug(self.ctx.current_phase)

    @property
    def is_complete(self) -> bool:
        return next_phase(self.ctx.current_phase, self.ctx.is_industrial) is None

    # -- gate evaluation --------------------------------------------------------
    def evaluate_gate(self, slug: str) -> GateResult:
        """Run a gate and record its outcome on the context."""
        gate = self.gates.get(slug)
        if gate is None:
            return GateResult(slug=slug, passed=True, warnings=[f"no gate registered for {slug!r}"])
        if not gate.applies(self.ctx):
            return GateResult(slug=slug, passed=True, notes=[f"gate {slug!r} not applicable to profile"])
        result = gate.check(self.ctx)
        self.ctx.gate_records[slug] = GateRecord(
            slug=slug,
            passed=result.passed,
            blockers=result.blockers,
            warnings=result.warnings,
            checked_at=_now(),
        )
        return result

    def evaluate_phase_gate(self) -> GateResult | None:
        """Evaluate the gate (if any) attached to the current phase."""
        gate_slug = self.phase.gate
        if gate_slug is None:
            return None
        return self.evaluate_gate(gate_slug)

    # -- state transitions ------------------------------------------------------
    def can_advance(self) -> bool:
        """True if the current phase's gate (if any) has passed."""
        gate_slug = self.phase.gate
        if gate_slug is None:
            return True
        return self.ctx.gate_passed(gate_slug)

    def advance(self, force: bool = False) -> Phase:
        """Advance to the next phase, enforcing the current phase's gate.

        With ``force=True`` the gate is re-evaluated but blockers don't block;
        the result is still recorded. Use sparingly (override authority).
        """
        if self.is_complete:
            raise StopIteration("Engagement already at terminal phase (disengage).")
        gate_slug = self.phase.gate
        if gate_slug is not None and not self.ctx.gate_passed(gate_slug):
            result = self.evaluate_gate(gate_slug)
            if not result.passed and not force:
                raise AdvanceBlocked(result)
        nxt = next_phase(self.ctx.current_phase, self.ctx.is_industrial)
        if nxt is None:
            raise StopIteration("No next phase.")
        self.ctx.current_phase = nxt.slug
        return nxt

    def rollback(self, to_slug: str) -> Phase:
        """Roll the engagement back to an earlier phase."""
        target = phase_by_slug(to_slug)
        current_index = self.phase.index
        if target.index > current_index:
            raise ValueError(f"Cannot rollback forward: {to_slug} is after {self.ctx.current_phase}.")
        self.ctx.current_phase = to_slug
        return target

    # -- snapshots --------------------------------------------------------------
    def status(self) -> dict:
        nxt = next_phase(self.ctx.current_phase, self.ctx.is_industrial)
        gate_slug = self.phase.gate
        return {
            "engagement_id": self.ctx.id,
            "customer": self.ctx.customer,
            "profile": self.ctx.profile,
            "current_phase": self.ctx.current_phase,
            "current_zone": self.ctx.current_zone.value,
            "next_phase": nxt.slug if nxt else None,
            "is_complete": self.is_complete,
            "gate": gate_slug,
            "gate_passed": self.ctx.gate_passed(gate_slug) if gate_slug else None,
            "visible_phase_count": len(self.ctx.visible_phases),
            "gate_records": {k: v.model_dump() for k, v in self.ctx.gate_records.items()},
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Late import to avoid circular deps; the registry is built on first use.
def _default_gate_registry() -> dict[str, Gate]:
    from .gates.air_gap import AirGapGate
    from .gates.conformity import ConformityGate
    from .gates.fat_sat import FatSatGate
    from .gates.functional_safety import FunctionalSafetyGate
    from .gates.shift_handover import ShiftHandoverGate
    from .gates.works_council import WorksCouncilGate
    from .handoff import HandoffSignoffGate
    from .operationalization import SLOGate
    from .pre_engagement import SiteSurveyGate, SuccessCriteriaGate

    gates: list[Gate] = [
        SiteSurveyGate(),
        SuccessCriteriaGate(),
        FatSatGate(),
        FunctionalSafetyGate(),
        ConformityGate(),
        WorksCouncilGate(),
        AirGapGate(),
        ShiftHandoverGate(),
        SLOGate(),
        HandoffSignoffGate(),
    ]
    return {g.slug: g for g in gates}
