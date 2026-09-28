"""Tests for the zero-dependency fake model used by the ``deploy --serve`` e2e smoke."""

from __future__ import annotations

import importlib.util
import json
import threading
import urllib.request
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parent.parent / "deploy" / "e2e" / "fake_model.py"
_spec = importlib.util.spec_from_file_location("fde_e2e_fake_model", _MODULE_PATH)
fake_model = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fake_model)


@pytest.fixture()
def server():
    srv = fake_model.create_server(port=0)  # ephemeral port
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield srv
    srv.shutdown()
    srv.server_close()
    thread.join(timeout=5)


def _post_chat(port: int, payload: dict) -> dict:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def test_chat_completions_response_shape(server) -> None:
    port = server.server_address[1]
    body = _post_chat(
        port,
        {
            "model": "fde-fake-model",
            "messages": [{"role": "user", "content": "ping"}],
        },
    )
    assert body["object"] == "chat.completion"
    assert body["model"] == "fde-fake-model"
    assert body["choices"][0]["message"]["role"] == "assistant"
    assert body["choices"][0]["message"]["content"] == fake_model.FIXED_REPLY
    assert body["choices"][0]["finish_reason"] == "stop"
    assert body["usage"]["total_tokens"] > 0
    assert server.stats["chat_completions"] == 1


def test_chat_completions_streaming(server) -> None:
    port = server.server_address[1]
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions",
        data=json.dumps(
            {
                "model": "fde-fake-model",
                "messages": [{"role": "user", "content": "ping"}],
                "stream": True,
                "stream_options": {"include_usage": True},
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.headers["Content-Type"] == "text/event-stream"
        raw = resp.read().decode("utf-8")
    frames = [json.loads(line[5:]) for line in raw.splitlines() if line.startswith("data: {")]
    assert frames[0]["object"] == "chat.completion.chunk"
    assert frames[0]["choices"][0]["delta"]["content"] == fake_model.FIXED_REPLY
    assert frames[-1]["usage"]["total_tokens"] > 0
    assert raw.rstrip().endswith("data: [DONE]")


def test_stats_and_unknown_routes(server) -> None:
    port = server.server_address[1]
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=5) as resp:
        assert json.loads(resp.read())["status"] == "ok"
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/_stats", timeout=5) as resp:
        assert json.loads(resp.read()) == {"chat_completions": 0}
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/nope", timeout=5)
    assert excinfo.value.code == 404
