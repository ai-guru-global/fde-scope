"""Layer 1 — the data-connector kit.

The FDE's first task on site is to get the data in. Source systems vary wildly
(ticketing, CRM, ERP, raw CSV dumps), so every source is wrapped behind the
same :class:`DataConnector` three-step contract: discover → sample → stream.

This layer has zero AgentScope dependency.
"""

from .base import Batch, DataConnector, register
from .schema import Schema, SchemaField

__all__ = ["DataConnector", "Batch", "Schema", "SchemaField", "register"]
