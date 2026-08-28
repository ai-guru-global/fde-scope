#!/usr/bin/env python3
"""FDE Scope.app launcher — double-click to run the Web workbench locally.

Behaviour (designed for a PyInstaller ``--windowed`` bundle, no terminal):
  1. Export the persistent user data dir as ``FDE_SCOPE_HOME``
     (``~/Documents/FDE Scope`` unless overridden) — engagement JSON, the
     skill library and reports live there, visible to the user; every
     entry point resolves them through fde_scope.paths (B1), so no chdir.
  2. Start the FastAPI workbench (uvicorn, in-process, 127.0.0.1 only).
  3. Wait for ``/api/health`` then open the browser at ``/console``.

Production guards:
  * single instance — a second double-click just re-opens the browser;
  * uncaught exceptions (main + worker threads) go to the rotating log file;
  * bundled ``build_info.json`` (version / git sha / timestamp) is logged on
    every start so support tickets can name the exact build.

The app object is passed to uvicorn directly (no import string, no reload,
no workers) — the frozen single-process pattern recommended by PyInstaller.
"""

from __future__ import annotations

import contextlib
import json
import os
import socket
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

DEFAULT_PORT = 8737
HOST = "127.0.0.1"
LOG_MAX_BYTES = 2_000_000


def _ensure_data_home() -> Path:
    """Resolve/create the data home and export it as ``FDE_SCOPE_HOME`` (B1).

    The app does NOT chdir anymore: every entry point resolves data
    locations through fde_scope.paths, which reads this env var first.
    """
    override = os.environ.get("FDE_SCOPE_HOME")
    path = Path(override).expanduser() if override else Path.home() / "Documents" / "FDE Scope"
    path.mkdir(parents=True, exist_ok=True)
    os.environ["FDE_SCOPE_HOME"] = str(path)
    return path


def _build_info() -> dict:
    """Read the provenance file injected next to the frozen executable."""
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    with contextlib.suppress(Exception):
        return json.loads((root / "build_info.json").read_text(encoding="utf-8"))
    return {}


def _rotate_log(path: Path) -> None:
    """Keep one .1 backup so a crash loop can't grow the log unbounded."""
    with contextlib.suppress(OSError):
        if path.exists() and path.stat().st_size > LOG_MAX_BYTES:
            path.replace(path.with_suffix(".log.1"))


def _pick_port() -> int:
    """Use DEFAULT_PORT when free; otherwise let the OS pick an ephemeral one."""
    wanted = int(os.environ.get("FDE_SCOPE_PORT") or DEFAULT_PORT)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((HOST, wanted))
            return sock.getsockname()[1]
        except OSError:
            pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return sock.getsockname()[1]


def _fetch_title(port: int) -> str:
    """Best-effort page-title fetch used to confirm the port owner is us."""
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/", timeout=1) as resp:  # noqa: S310
            return resp.read(4096).decode("utf-8", "ignore")
    except Exception:
        return ""


def _alert(title: str, message: str) -> None:
    """Best-effort GUI error dialog for a windowed app with no console."""
    with contextlib.suppress(Exception):
        subprocess.run(
            ["osascript", "-e", f'display dialog {message!r} with title {title!r} buttons {{"好"}}'],
            check=False,
            timeout=30,
        )


def _probe(port: int, timeout: float = 0.6) -> bool:
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://{HOST}:{port}/api/health", timeout=timeout) as resp:  # noqa: S310
            return resp.status == 200
    except Exception:
        return False


def _wait_healthy(port: int, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _probe(port):
            return True
        time.sleep(0.25)
    return False


def main() -> int:
    import logging
    import signal

    data = _ensure_data_home()

    log_file = data / "fde-scope-app.log"
    _rotate_log(log_file)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_file)],
    )
    log = logging.getLogger("fde_scope.app")

    def _hook(exc_type, exc, tb):  # noqa: ARG001
        log.error("uncaught:\n%s", "".join(traceback.format_exception(exc_type, exc, tb)))

    sys.excepthook = _hook
    threading.excepthook = lambda args: _hook(args.exc_type, args.exc_value, args.exc_traceback)

    info = _build_info()
    log.info(
        "starting fde-scope app version=%s git=%s built=%s arch=%s",
        info.get("version", "dev"),
        (info.get("git_sha") or "?")[:8],
        info.get("build_time", "?"),
        info.get("arch", "?"),
    )

    # Single instance: if a healthy workbench already owns the port, a second
    # double-click should just re-focus the browser, not spawn a new server.
    wanted = int(os.environ.get("FDE_SCOPE_PORT") or DEFAULT_PORT)
    if _probe(wanted) and "fde scope" in _fetch_title(wanted).lower():
        webbrowser.open(f"http://{HOST}:{wanted}/console")
        log.info("existing instance on port %s — re-opened browser", wanted)
        return 0

    try:
        import uvicorn

        from fde_scope.web.app import app
    except Exception as exc:  # pragma: no cover — bundle integrity guard
        log.exception("startup import failed")
        _alert("FDE Scope 启动失败", f"无法加载核心模块：{exc}\n详见 {log_file}")
        return 1

    port = _pick_port()
    server = uvicorn.Server(uvicorn.Config(app, host=HOST, port=port, log_level="info", access_log=False))

    # A windowed PyInstaller bundle has no Cocoa event loop, so macOS "Quit"
    # arrives as SIGTERM (pkill / force-quit) rather than an Apple event —
    # map it to uvicorn's graceful shutdown flag.
    def _stop(signum, frame):  # noqa: ARG001
        server.should_exit = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    threading.Thread(target=server.run, daemon=True).start()

    if _wait_healthy(port):
        webbrowser.open(f"http://{HOST}:{port}/console")
        log.info("workbench ready at http://%s:%s data=%s", HOST, port, data)
    else:
        log.error("server did not become healthy on port %s", port)
        _alert("FDE Scope 启动失败", f"服务未在端口 {port} 就绪，详见 {log_file}")
        return 1

    # Keep the process alive; exit cleanly when the server stops.
    try:
        while server.should_exit is False:
            time.sleep(1)
    except KeyboardInterrupt:
        server.should_exit = True
    return 0


if __name__ == "__main__":
    sys.exit(main())
