"""Structured logging plumbing (P2): get_logger namespacing + idempotent config."""

from __future__ import annotations

import logging

from fde_scope.logutil import configure_logging, get_logger


def _stash_root(monkeypatch) -> logging.Logger:
    """Undo a previous configure_logging so the test re-runs it cleanly."""
    root = logging.getLogger("fde_scope")
    monkeypatch.delattr(root, "_fde_scope_configured", raising=False)
    return root


def test_get_logger_namespaces_under_package() -> None:
    logger = get_logger("corpus.pipeline")
    assert logger.name == "fde_scope.corpus.pipeline"


def test_configure_logging_installs_one_handler_and_is_idempotent(monkeypatch) -> None:
    monkeypatch.setenv("FDE_SCOPE_LOG_LEVEL", "DEBUG")
    root = _stash_root(monkeypatch)
    before = len(root.handlers)
    first = configure_logging()
    assert first is root
    assert len(root.handlers) == before + 1
    assert root.level == logging.DEBUG
    configure_logging()  # second call must not stack another handler
    assert len(root.handlers) == before + 1


def test_configure_logging_defaults_to_warning(monkeypatch) -> None:
    monkeypatch.delenv("FDE_SCOPE_LOG_LEVEL", raising=False)
    root = _stash_root(monkeypatch)
    configure_logging()
    assert root.level == logging.WARNING


def test_module_loggers_share_the_package_namespace() -> None:
    from fde_scope import audit

    assert audit.logger.name == "fde_scope.audit"
