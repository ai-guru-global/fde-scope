"""The engagement state machine — drives an FDE engagement through the SOP.

The state machine advances an :class:`EngagementContext` phase by phase.
Before leaving a phase whose ``gates`` are set, every gate is re-evaluated
unconditionally (a previously recorded pass is never trusted — the context
may have changed since); if any gate fails, the advance is refused and the
blockers are returned. This is the single enforcement point that makes the
SOP real.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .context import EngagementContext, GateRecord
from .gates.base import Gate, GateResult
from .phases import Phase, next_phase, phase_by_slug, phases_for_profile


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
        """Run a gate and record its outcome on the context.

        Raises :class:`KeyError` for an unregistered slug — a typo'd gate
        name must fail loudly, never "pass" silently.
        """
        gate = self.gates.get(slug)
        if gate is None:
            raise KeyError(f"Unknown gate: {slug!r}")
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

    def evaluate_phase_gates(self) -> list[GateResult]:
        """Evaluate every gate attached to the current phase (empty if none)."""
        return [self.evaluate_gate(slug) for slug in self.phase.gates]

    # -- state transitions ------------------------------------------------------
    def can_advance(self) -> bool:
        """True if every gate of the current phase passes *right now*.

        Gates are re-evaluated live (outcomes are recorded); a stale pass
        record never counts, because the context may have changed since.
        """
        return all(r.passed for r in self.evaluate_phase_gates())

    def advance(self, force: bool = False) -> Phase:
        """Advance to the next phase, enforcing the current phase's gates.

        Every gate attached to the current phase is re-evaluated
        unconditionally — a previously recorded pass does not exempt the
        engagement from re-checking. With ``force=True`` the gates are
        still evaluated and recorded but blockers don't block. Use
        sparingly (override authority).
        """
        if self.is_complete:
            raise StopIteration("Engagement already at terminal phase (disengage).")
        failed = [r for r in self.evaluate_phase_gates() if not r.passed]
        if failed and not force:
            raise AdvanceBlocked(_merge_results(failed))
        nxt = next_phase(self.ctx.current_phase, self.ctx.is_industrial)
        if nxt is None:
            raise StopIteration("No next phase.")
        self.ctx.current_phase = nxt.slug
        return nxt

    def rollback(self, to_slug: str) -> Phase:
        """Roll the engagement back to an earlier phase.

        The target must be visible to the engagement's profile — rolling a
        non-industrial engagement back to an industrial-only phase would
        strand the state machine on a phase it cannot advance from and make
        ``is_complete`` report a false completion.
        """
        target = phase_by_slug(to_slug)
        visible = {p.slug for p in phases_for_profile(self.ctx.is_industrial)}
        if to_slug not in visible:
            raise ValueError(
                f"Cannot rollback to {to_slug!r}: phase not visible to profile {self.ctx.profile!r}."
            )
        current_index = self.phase.index
        if target.index > current_index:
            raise ValueError(f"Cannot rollback forward: {to_slug} is after {self.ctx.current_phase}.")
        self.ctx.current_phase = to_slug
        return target

    # -- snapshots --------------------------------------------------------------
    def status(self) -> dict:
        nxt = next_phase(self.ctx.current_phase, self.ctx.is_industrial)
        gate_slugs = list(self.phase.gates)
        return {
            "engagement_id": self.ctx.id,
            "customer": self.ctx.customer,
            "profile": self.ctx.profile,
            "current_phase": self.ctx.current_phase,
            "current_zone": self.ctx.current_zone.value,
            "next_phase": nxt.slug if nxt else None,
            "is_complete": self.is_complete,
            "gate": gate_slugs[0] if gate_slugs else None,  # primary gate (single-gate callers)
            "gates": gate_slugs,
            "gate_passed": all(self.ctx.gate_passed(s) for s in gate_slugs) if gate_slugs else None,
            "visible_phase_count": len(self.ctx.visible_phases),
            "gate_records": {k: v.model_dump() for k, v in self.ctx.gate_records.items()},
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _merge_results(results: list[GateResult]) -> GateResult:
    """Fold several gate results into one (for a multi-gate AdvanceBlocked)."""
    merged = results[0]
    for r in results[1:]:
        merged = merged.merge(r)
    return merged


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
