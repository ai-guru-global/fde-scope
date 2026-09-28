#!/usr/bin/env python3
"""Zero-dependency OpenAI-compatible fake model for ``deploy --serve`` e2e runs.

Stdlib ``http.server`` only — no third-party imports — so it runs with any
Python 3.11+ interpreter, inside or outside the project venv:

    python deploy/e2e/fake_model.py --port 19100

Endpoints:
    GET  /healthz                 liveness probe for the smoke script
    GET  /_stats                  {"chat_completions": N} — how many completion
                                  calls have been received (the smoke assertion)
    POST /v1/chat/completions     fixed completion; honours ``stream: true``
                                  with a minimal SSE stream

The server never calls out anywhere and the API key is not checked — it exists
only so a real client (AgentScope's OpenAIChatModel) has a reachable endpoint
to talk to.
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

FIXED_REPLY = "fde-scope e2e fake model reply"


def _completion_body(model: str) -> dict[str, Any]:
    return {
        "id": "chatcmpl-fde-fake",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": FIXED_REPLY},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


def _stream_chunks(model: str, include_usage: bool) -> list[dict[str, Any]]:
    base = {
        "id": "chatcmpl-fde-fake",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
    }
    chunks = [
        {
            **base,
            "choices": [
                {
                    "index": 0,
                    "delta": {"role": "assistant", "content": FIXED_REPLY},
                    "finish_reason": None,
                }
            ],
        },
        {**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
    ]
    if include_usage:
        chunks.append(
            {
                **base,
                "choices": [],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
        )
    return chunks


class _Handler(BaseHTTPRequestHandler):
    server_version = "FdeFakeModel/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:  # silence per-request logs
        pass

    def _send_json(self, body: dict[str, Any], status: int = 200) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802 — http.server naming
        if self.path == "/healthz":
            self._send_json({"status": "ok"})
        elif self.path == "/_stats":
            with self.server.lock:  # type: ignore[attr-defined]
                self._send_json(dict(self.server.stats))  # type: ignore[attr-defined]
        else:
            self._send_json({"error": "not found"}, status=404)

    def do_POST(self) -> None:  # noqa: N802 — http.server naming
        if self.path != "/v1/chat/completions":
            self._send_json({"error": "not found"}, status=404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            request = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._send_json({"error": "invalid JSON"}, status=400)
            return
        with self.server.lock:  # type: ignore[attr-defined]
            self.server.stats["chat_completions"] += 1  # type: ignore[attr-defined]
        model = str(request.get("model") or "fde-fake-model")
        stream = bool(request.get("stream"))
        if not stream:
            self._send_json(_completion_body(model))
            return
        include_usage = bool((request.get("stream_options") or {}).get("include_usage"))
        lines = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in _stream_chunks(model, include_usage))
        payload = (lines + "data: [DONE]\n\n").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def create_server(host: str = "127.0.0.1", port: int = 19100) -> ThreadingHTTPServer:
    """Build the fake-model server (not yet serving — call ``serve_forever``)."""
    server = ThreadingHTTPServer((host, port), _Handler)
    server.lock = threading.Lock()  # type: ignore[attr-defined]
    server.stats = {"chat_completions": 0}  # type: ignore[attr-defined]
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=19100)
    args = parser.parse_args()
    server = create_server(args.host, args.port)
    print(f"fake model ready on http://{args.host}:{args.port}/v1", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
