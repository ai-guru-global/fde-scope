"""Profile base — selects connectors, eval metrics, and gates per scenario.

A profile bundles everything that differs between deployment scenarios:
which connectors are first-class, which KPIs the eval reports, and whether
the industrial gate overlay applies. This keeps the engagement layer
scenario-agnostic — it just asks the profile.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Profile(ABC):
    """A deployment scenario (ticket / manufacturing / future)."""

    slug: str
    name: str
    is_industrial: bool = False
    primary_connectors: list[str] = field(default_factory=list)
    kpi_catalogue: dict[str, str] = field(default_factory=dict)
    description: str = ""

    @abstractmethod
    def compute_kpis(self, samples: list[dict]) -> dict[str, float]:
        """Compute this profile's KPIs over a list of sample records."""
        ...


_REGISTRY: dict[str, Profile] = {}


def register(profile: Profile) -> Profile:
    _REGISTRY[profile.slug] = profile
    return profile


def get_profile(slug: str) -> Profile:
    from .manufacturing import ManufacturingProfile
    from .ticket import TicketProfile

    # Lazy-load built-ins so optional deps don't break the core.
    if "ticket" not in _REGISTRY:
        TicketProfile()
    if "manufacturing" not in _REGISTRY:
        ManufacturingProfile()
    if slug not in _REGISTRY:
        raise KeyError(f"Unknown profile: {slug!r}")
    return _REGISTRY[slug]


def all_profiles() -> dict[str, Profile]:
    from .manufacturing import ManufacturingProfile
    from .ticket import TicketProfile

    TicketProfile()
    ManufacturingProfile()
    return dict(_REGISTRY)
