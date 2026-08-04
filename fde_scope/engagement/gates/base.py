"""Gate base class — the SOP's phase-gate contract.

Every gate is a callable ``check(context) -> GateResult``. A gate returns
*blockers* (hard stops — the engagement cannot advance past the phase) and
*warnings* (advisory). This is what turns the SOP from a checklist into an
enforced engineering process.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..context import EngagementContext


@dataclass
class GateResult:
    """Outcome of a gate check."""

    slug: str
    passed: bool
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def merge(self, other: "GateResult") -> "GateResult":
        return GateResult(
            slug=self.slug,
            passed=self.passed and other.passed,
            blockers=self.blockers + other.blockers,
            warnings=self.warnings + other.warnings,
            notes=self.notes + other.notes,
        )

    def summary(self) -> str:
        head = "✅ PASS" if self.passed else "❌ BLOCKED"
        lines = [f"{head} · gate={self.slug}"]
        for b in self.blockers:
            lines.append(f"  🚫 {b}")
        for w in self.warnings:
            lines.append(f"  ⚠️  {w}")
        return "\n".join(lines)


class Gate(ABC):
    """Base class for all engagement gates."""

    slug: str = "base"
    name: str = "Base Gate"
    industrial_only: bool = False

    @abstractmethod
    def check(self, ctx: EngagementContext) -> GateResult:
        """Evaluate the gate against the engagement context."""
        ...

    def applies(self, ctx: EngagementContext) -> bool:
        """Whether this gate is relevant to the current profile."""
        if self.industrial_only:
            return ctx.is_industrial
        return True
