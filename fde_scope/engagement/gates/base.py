"""Gate base class — the SOP's phase-gate contract.

Every gate is a callable ``check(context) -> GateResult``. A gate returns
*blockers* (hard stops — the engagement cannot advance past the phase) and
*warnings* (advisory). This is what turns the SOP from a checklist into an
enforced engineering process.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ..context import EngagementContext


def asset_record(assets: Mapping[str, Any], key: str) -> tuple[dict[str, Any], str | None]:
    """Read ``assets[key]`` as a mapping, failing closed on a readable blocker.

    ``ctx.assets`` is free-form ``dict[str, Any]``: ``POST
    /api/engagements/{id}/context`` merges ``body["assets"]`` with no schema,
    and the console lets an operator type anything. So a gate can be handed
    ``"fat": "done"`` or ``"air_gap_plan": []`` — and ``.get()`` on that raises
    :class:`AttributeError`, which escapes ``Engagement.advance`` as a 500
    after the phase's earlier gates were already evaluated and recorded. A
    record the gate cannot interpret is a *failed* gate, never a passing one.

    Returns ``(record, blocker)``: an empty dict and no blocker when the key
    is absent or empty — whether "not recorded yet" blocks is the gate's own
    domain call — and the offending shape described in ``blocker`` when the
    value is not a mapping. The blocker names ``assets.<key>``, which is what
    the operator has to fix.
    """
    value = assets.get(key)
    if value is None:
        return {}, None
    if isinstance(value, Mapping):
        return dict(value), None
    return {}, f"assets.{key} 记录无法判定：期望键值对（对象），实际为 {type(value).__name__}"


@dataclass
class GateResult:
    """Outcome of a gate check."""

    slug: str
    passed: bool
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def merge(self, other: GateResult) -> GateResult:
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
