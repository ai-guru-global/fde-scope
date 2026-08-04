"""Engagement gates — enforced SOP phase gates.

Each gate is a small, focused, testable rule-engine that turns one SOP
checkpoint into code. Industrial gates are marked ``industrial_only`` and
auto-skip for software/SaaS profiles.
"""

from .base import Gate, GateResult

__all__ = ["Gate", "GateResult"]
