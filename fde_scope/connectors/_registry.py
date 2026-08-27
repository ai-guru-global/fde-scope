"""Connector registry.

Connectors register themselves via :func:`fde_scope.connectors.base.register`.
The registry is populated lazily through :func:`load_all`, which imports each
concrete module on demand — a missing optional dependency therefore only
breaks the connector that needs it, never the core.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import DataConnector

_REGISTRY: dict[str, type[DataConnector]] = {}

# type slug -> module path within fde_scope.connectors
_MODULE_BY_TYPE: dict[str, str] = {
    # ticket / SaaS
    "csv": "csv_fallback",
    "zammad": "zammad",
    "salesforce": "salesforce",
    "mysql": "mysql_generic",
    # documents (AgentScope rag parsers, imported lazily)
    "documents": "documents",
    # manufacturing / industrial
    "opcua": "opcua",
    "mqtt_sparkplug": "mqtt_sparkplug",
    "ros2_bag": "ros2_bag",
    "mes": "mes_isa95",
    "historian": "historian",
}


def register(slug: str, connector_cls: type[DataConnector]) -> None:
    _REGISTRY[slug] = connector_cls


def get_registry() -> dict[str, type[DataConnector]]:
    """Return the populated registry, importing all built-in connectors."""
    load_all()
    return dict(_REGISTRY)


def load_all() -> None:
    """Import every built-in connector module so they self-register."""
    from importlib import import_module

    for slug, mod in _MODULE_BY_TYPE.items():
        if slug not in _REGISTRY:
            try:
                import_module(f"fde_scope.connectors.{mod}")
            except Exception:  # noqa: BLE001 — optional deps may be missing
                # A connector that can't import (e.g. missing mysql driver)
                # must not poison the whole registry.
                continue


def get(slug: str):
    """Resolve a connector class by slug, importing on demand."""
    if slug not in _REGISTRY:
        mod = _MODULE_BY_TYPE.get(slug)
        if mod is None:
            raise KeyError(f"Unknown connector type: {slug!r}")
        from importlib import import_module

        import_module(f"fde_scope.connectors.{mod}")
    return _REGISTRY[slug]
