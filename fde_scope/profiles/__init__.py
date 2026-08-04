"""Scenario profiles — select connectors / KPIs / gates per deployment type.

The profile mechanism is what keeps FDE Scope scenario-agnostic at its core
while still being deeply credible in each vertical. Today: ticket (the
original customer-service scenario) and manufacturing (the embodied-robotics
factory scenario).
"""

from .base import Profile, all_profiles, get_profile, register

__all__ = ["Profile", "get_profile", "all_profiles", "register"]
