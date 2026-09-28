"""Structured logging for the fde_scope package (commercialization P2).

One namespace: every module logs under ``fde_scope.<module>`` via
:func:`get_logger`. :func:`configure_logging` installs a single stderr
handler on the ``fde_scope`` root logger (time / level / logger name) and is
idempotent — entry points (CLI, web app, launcher) may each call it.

Level comes from ``FDE_SCOPE_LOG_LEVEL`` (default ``WARNING``). Red line
(AGENTS.md invariant 3): log messages must never carry env var values,
tokens or API keys — log identifiers and counts, never credentials.
"""

from __future__ import annotations

import logging
import os

PACKAGE_LOGGER = "fde_scope"
ENV_LOG_LEVEL = "FDE_SCOPE_LOG_LEVEL"
_DEFAULT_LEVEL = "WARNING"
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"

#: Marker attribute on the package logger so repeated calls are no-ops.
_MARKER = "_fde_scope_configured"


def get_logger(name: str) -> logging.Logger:
    """Return ``logging.getLogger("fde_scope." + name)``."""
    return logging.getLogger(f"{PACKAGE_LOGGER}.{name}")


def configure_logging(level: str | None = None) -> logging.Logger:
    """Attach one StreamHandler to the ``fde_scope`` root logger; idempotent.

    The package logger is configured rather than the process root logger so
    embedding apps (PawApp host, uvicorn) keep their own logging setup.
    """
    logger = logging.getLogger(PACKAGE_LOGGER)
    if getattr(logger, _MARKER, False):
        return logger
    resolved = (level or os.environ.get(ENV_LOG_LEVEL) or _DEFAULT_LEVEL).strip().upper()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, resolved, logging.WARNING))
    setattr(logger, _MARKER, True)
    return logger
