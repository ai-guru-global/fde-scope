"""The data-connector contract.

Every connector (Zammad, Salesforce, MySQL, CSV, ...) implements the same
three-step surface so the FDE workflow is uniform regardless of where the
data physically lives:

    1. ``discover_schema()`` — look before you load (cheap)
    2. ``extract_sample(n)`` — eyeball data quality (cheap)
    3. ``stream(batch_size)`` — pull the full corpus (expensive)

Design note: this base is deliberately framework-agnostic. It yields plain
``dict`` rows, which the corpus engine consumes directly. None of this layer
imports AgentScope.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any

from .schema import Schema


class Batch(list):
    """A batch of rows plus lightweight provenance for the flywheel."""

    def __init__(self, rows: list[dict[str, Any]] | None = None, *, source: str = "") -> None:
        super().__init__(rows or [])
        self.source = source


class DataConnector(ABC):
    """FDE data-connector base class."""

    #: short slug used by the CLI (``--type csv``) and the registry
    type: str = "base"

    def __init__(self, source: str, **options: Any) -> None:
        self.source = source
        self.options = options

    # -- the three-step contract ------------------------------------------------
    @abstractmethod
    def discover_schema(self) -> Schema:
        """Auto-discover the customer's data shape. Should be cheap."""
        ...

    @abstractmethod
    def extract_sample(self, n: int = 100) -> list[dict[str, Any]]:
        """Pull a small sample so the FDE can judge data quality fast."""
        ...

    @abstractmethod
    def stream(self, batch_size: int = 500) -> Iterator[Batch]:
        """Stream the full dataset in batches. Yields :class:`Batch` objects."""
        ...

    # -- registry helpers --------------------------------------------------------
    @classmethod
    def registry(cls) -> dict[str, type["DataConnector"]]:
        """Return the connector registry, populated lazily.

        Importing concrete connectors is deferred so a missing optional dep
        (e.g. ``mysql-connector-python``) never breaks the core layer.
        """
        from . import _registry

        return _registry.get_registry()


def register(connector_cls: type[DataConnector]) -> type[DataConnector]:
    """Decorator: register a connector under its ``type`` slug."""
    from . import _registry

    _registry.register(connector_cls.type, connector_cls)
    return connector_cls
