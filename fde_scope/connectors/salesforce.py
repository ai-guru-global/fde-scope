"""Salesforce CRM connector — HTTP skeleton.

STATUS: skeleton. Real implementation will use SOQL queries against the
Salesforce REST API (``/services/data/vXX.X/queryAll``) with OAuth bearer
auth. The contract surface is in place so it is selectable from the CLI today.

Roadmap hook: SOQL ``SELECT Id, Subject, Description, Origin, Status FROM
Case`` maps cleanly onto the corpus engine's expected fields.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from .base import Batch, DataConnector, register
from .schema import Schema, SchemaField


@register
class SalesforceConnector(DataConnector):
    """Connect to Salesforce (Case object) via the REST API."""

    connector_type = "salesforce"

    def __init__(self, source: str, **options: Any) -> None:
        super().__init__(source, **options)
        self.instance_url = source.rstrip("/")
        self.access_token = options.get("access_token", "")
        self.api_version = options.get("api_version", "59.0")

    def discover_schema(self) -> Schema:
        return Schema(
            source=self.instance_url,
            row_count=None,
            fields=[
                SchemaField(name="id", inferred_type="string"),
                SchemaField(name="title", inferred_type="string"),  # Subject
                SchemaField(name="content", inferred_type="string"),  # Description
                SchemaField(name="category", inferred_type="string"),
                SchemaField(name="channel", inferred_type="string"),  # Origin
                SchemaField(name="state", inferred_type="string"),  # Status
            ],
        )

    def extract_sample(self, n: int = 100) -> list[dict[str, Any]]:
        # TODO: SOQL `SELECT ... FROM Case LIMIT {n}`
        return []

    def stream(self, batch_size: int = 500) -> Iterator[Batch]:
        # TODO: SOQL query + nextRecordsUrl pagination.
        return
        yield  # pragma: no cover
