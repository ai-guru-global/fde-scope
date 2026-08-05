"""Zammad (open-source ticketing) connector — HTTP skeleton.

STATUS: skeleton. The full Zammad REST integration (``/api/v1/tickets``,
pagination via ``page``/``per_page``, article expansion) is roadmap. The
contract surface is implemented so the FDE workflow is end-to-end testable
with a local mock; swapping in ``requests`` calls is a localized change.

Roadmap hook: replace the ``TODO`` blocks with real HTTP calls against
``{base_url}/api/v1/tickets/search`` using the provided API token.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from .base import Batch, DataConnector, register
from .schema import Schema, SchemaField


@register
class ZammadConnector(DataConnector):
    """Connect to a Zammad ticketing instance via its REST API."""

    connector_type = "zammad"

    def __init__(self, source: str, **options: Any) -> None:
        super().__init__(source, **options)
        # `source` is the base URL; `api_key` / `token` come in via options.
        self.base_url = source.rstrip("/")
        self.api_key = options.get("api_key") or options.get("token", "")

    def discover_schema(self) -> Schema:
        # TODO: GET {base_url}/api/v1/tickets?per_page=1 to infer fields.
        # Until the live integration lands, we expose Zammad's documented
        # ticket object shape so downstream code has a stable contract.
        return Schema(
            source=self.base_url,
            row_count=None,
            fields=[
                SchemaField(name="id", inferred_type="int"),
                SchemaField(name="number", inferred_type="string"),
                SchemaField(name="title", inferred_type="string"),
                SchemaField(name="note", inferred_type="string", pii_candidate=True),
                SchemaField(name="category", inferred_type="string"),
                SchemaField(name="state", inferred_type="string"),
                SchemaField(name="channel", inferred_type="string"),
                SchemaField(name="content", inferred_type="string"),
            ],
        )

    def extract_sample(self, n: int = 100) -> list[dict[str, Any]]:
        # TODO: GET {base_url}/api/v1/tickets/search?per_page={n}
        return []

    def stream(self, batch_size: int = 500) -> Iterator[Batch]:
        # TODO: paginate GET /api/v1/tickets, expand articles into `content`.
        return
        yield  # pragma: no cover — generator marker
