"""Lightweight schema model describing a connector's discovered data shape.

A connector's job is to turn *whatever* a customer gives the FDE (Zammad API,
Salesforce, MySQL, a CSV dump) into a uniform list of dicts. Before pulling
the full corpus, the FDE inspects the :class:`Schema` to sanity-check the
data — this is the "look before you load" step that distinguishes a one-shot
script from a reusable connector kit.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SchemaField(BaseModel):
    """A single column / field discovered in the source data."""

    name: str
    inferred_type: str = "string"  # string | int | float | bool | datetime | json
    nullable: bool = True
    sample_values: list[Any] = Field(default_factory=list)
    pii_candidate: bool = Field(
        default=False,
        description="Heuristic flag: does this field likely hold PII (name/email/phone)?",
    )


class Schema(BaseModel):
    """The discovered shape of a data source.

    Returned by :meth:`DataConnector.discover_schema`. The ``row_count`` is
    best-effort (``None`` when unknown until a full stream).
    """

    source: str
    fields: list[SchemaField] = Field(default_factory=list)
    row_count: int | None = None
    detected_categories: list[str] = Field(default_factory=list)
    detected_channels: list[str] = Field(default_factory=list)

    def field_names(self) -> list[str]:
        return [f.name for f in self.fields]

    def get(self, name: str) -> SchemaField | None:
        for f in self.fields:
            if f.name == name:
                return f
        return None
