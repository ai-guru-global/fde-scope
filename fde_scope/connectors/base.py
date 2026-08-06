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
from typing import Any, ClassVar

from .schema import Schema


class Batch(list):
    """A batch of rows plus lightweight provenance for the flywheel."""

    def __init__(self, rows: list[dict[str, Any]] | None = None, *, source: str = "") -> None:
        super().__init__(rows or [])
        self.source = source


class DataConnector(ABC):
    """FDE data-connector base class."""

    #: short slug used by the CLI (``--type csv``) and the registry.
    #: Subclasses override this to identify themselves. ``ClassVar`` keeps
    #: mypy happy despite shadowing the ``type`` builtin inside the class body.
    type: ClassVar[str] = "base"
    #: Deprecated alias kept solely so out-of-tree subclasses written against
    #: the old name still register. Prefer ``type``.
    connector_type: ClassVar[str] = "base"

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
    def registry(cls) -> dict[str, type]:
        """Return the connector registry, populated lazily.

        Importing concrete connectors is deferred so a missing optional dep
        (e.g. ``mysql-connector-python``) never breaks the core layer.
        """
        from . import _registry

        return _registry.get_registry()


def register(connector_cls: type) -> type:
    """Decorator: register a connector under its ``type`` slug."""
    from . import _registry

    slug = getattr(connector_cls, "type", None) or getattr(connector_cls, "connector_type", None)
    if not slug:
        raise AttributeError(
            f"{connector_cls.__name__} must define a `type` class attribute to be registered"
        )
    _registry.register(slug, connector_cls)
    return connector_cls
