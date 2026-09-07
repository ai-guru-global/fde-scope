# MQTT-Sparkplug Live Broker IO Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the MQTT-Sparkplug connector's live-broker path real and shippable: declared `mqtt` extra, bounded stream termination, env-var auth, stage-aware cleanup, two-layer tests (fake paho + gated real broker), and one local real-broker verification run.

**Architecture:** All production changes stay inside `fde_scope/connectors/mqtt_sparkplug.py` (private helpers `_apply_auth` / `_make_on_message`, hardened `_collect_live`, bounded `_stream_live`, new `max_messages` option). Tests follow the repo's established opcua/mysql two-layer pattern: a fake `paho.mqtt.client` module injected into `sys.modules` for CI, plus one `@pytest.mark.mqtt` smoke test gated by `FDE_SCOPE_MQTT_URL`. Spec: `docs/superpowers/specs/2026-09-07-mqtt-sparkplug-live-design.md`.

**Tech Stack:** Python 3.12, paho-mqtt 2.x (VERSION2 callback API), pytest, ruff. No new production dependencies beyond the declared extra.

**Conventions for every task:**
- Run tests with `.venv/bin/python -m pytest` (repo standard, see AGENTS.md).
- Do not touch `fde_scope/engagement/`, `deploy/permission_builder.py`, `deploy/toolkit.py`, or the AgentScope window (AGENTS.md dangerous zones).
- JSONL replay behavior must not change: the 13 pre-existing tests in `tests/test_mqtt_connector.py` stay green throughout.

---

### Task 1: Fake paho test double + env auth (`_apply_auth`)

**Files:**
- Modify: `tests/test_mqtt_connector.py` (fake module classes, fixture, 3 new tests)
- Modify: `fde_scope/connectors/mqtt_sparkplug.py` (`_apply_auth` + one call site)

- [ ] **Step 1: Extend the test file imports**

In `tests/test_mqtt_connector.py`, replace the import block:

```python
from __future__ import annotations

import json
import os
import sys
import threading
import types
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from fde_scope.connectors.mqtt_sparkplug import MqttSparkplugConnector
```

- [ ] **Step 2: Add the fake paho module classes and fixture**

Append this block after the existing fixtures (before the first test):

```python
# ---------------------------------------------------------------------------
# Fake paho.mqtt.client — the surface the connector actually uses
# ---------------------------------------------------------------------------
class _FakeMqttMessage:
    """Mirror paho's MQTTMessage — only the attributes _normalize reads."""

    def __init__(self, topic: str, payload: bytes, qos: int = 0, retain: bool = False):
        self.topic = topic
        self.payload = payload
        self.qos = qos
        self.retain = retain


class _FakeMqttClient:
    """Mirror paho.mqtt.client.Client — records calls for assertions.

    ``loop_start`` replays the configured outbox through ``on_message`` on
    a real thread, so both the collect (list.append) and stream (queue.put)
    callbacks are exercised against real concurrency.
    """

    def __init__(
        self,
        callback_api_version: int,  # noqa: ARG002 — mirror paho signature
        outbox: list[_FakeMqttMessage] | None = None,
        *,
        fail_connect: bool = False,
        fail_subscribe: bool = False,
    ) -> None:
        self._outbox = outbox or []
        self._fail_connect = fail_connect
        self._fail_subscribe = fail_subscribe
        self.on_message: Any = None
        self.calls: list[str] = []
        self.subscribed: list[str] = []
        self.username_pw_args: tuple[str, str | None] | None = None
        self.tls_enabled = False
        self.connected = False
        self.loop_stopped = False
        self.disconnected = False
        self._thread: threading.Thread | None = None

    def username_pw_set(self, username: str, password: str | None = None) -> None:
        self.calls.append("username_pw_set")
        self.username_pw_args = (username, password)

    def tls_set(self) -> None:
        self.calls.append("tls_set")
        self.tls_enabled = True

    def connect(self, host: str, port: int, keepalive: int) -> None:  # noqa: ARG002
        self.calls.append("connect")
        if self._fail_connect:
            raise ConnectionRefusedError(f"[Errno 61] connect to {host}:{port} refused")
        self.connected = True

    def subscribe(self, topic: str) -> None:
        self.calls.append("subscribe")
        if self._fail_subscribe:
            raise RuntimeError(f"subscribe refused: {topic}")
        self.subscribed.append(topic)

    def loop_start(self) -> None:
        self.calls.append("loop_start")

        def _replay() -> None:
            for msg in self._outbox:
                if self.on_message is not None:
                    self.on_message(self, None, msg)

        self._thread = threading.Thread(target=_replay, daemon=True)
        self._thread.start()

    def loop_stop(self) -> None:
        self.calls.append("loop_stop")
        self.loop_stopped = True
        if self._thread is not None:
            self._thread.join(timeout=5)

    def disconnect(self) -> None:
        self.calls.append("disconnect")
        self.disconnected = True


class _FakeMqttModule(types.ModuleType):
    """Module stand-in for ``paho.mqtt.client``."""

    def __init__(self) -> None:
        super().__init__("paho.mqtt.client")
        self.outbox: list[_FakeMqttMessage] = []
        self.fail_connect = False
        self.fail_subscribe = False
        self.created: list[_FakeMqttClient] = []
        self.CallbackAPIVersion = types.SimpleNamespace(VERSION2=2)

    def Client(self, callback_api_version: int) -> _FakeMqttClient:  # noqa: N802
        c = _FakeMqttClient(
            callback_api_version,
            outbox=self.outbox,
            fail_connect=self.fail_connect,
            fail_subscribe=self.fail_subscribe,
        )
        self.created.append(c)
        return c


@pytest.fixture
def fake_paho_module() -> Iterator[_FakeMqttModule]:
    """Install a fake ``paho.mqtt.client`` (+ parent packages) in sys.modules.

    Tests configure behavior by mutating the yielded module (outbox,
    fail_connect, ...) before calling the connector.
    """
    paho = types.ModuleType("paho")
    mqtt_pkg = types.ModuleType("paho.mqtt")
    client_mod = _FakeMqttModule()
    paho.mqtt = mqtt_pkg  # type: ignore[attr-defined]
    mqtt_pkg.client = client_mod  # type: ignore[attr-defined]
    sys.modules["paho"] = paho
    sys.modules["paho.mqtt"] = mqtt_pkg
    sys.modules["paho.mqtt.client"] = client_mod
    try:
        yield client_mod
    finally:
        for name in ("paho", "paho.mqtt", "paho.mqtt.client"):
            sys.modules.pop(name, None)


def _live_msg(topic: str, payload: dict[str, Any]) -> _FakeMqttMessage:
    """Build one fake wire message (payload JSON-encoded like a real broker)."""
    return _FakeMqttMessage(topic=topic, payload=json.dumps(payload).encode("utf-8"))
```

- [ ] **Step 3: Write the failing auth tests**

Append to the end of the file:

```python
# ---------------------------------------------------------------------------
# Live broker path — mocked paho (fake module via sys.modules)
# ---------------------------------------------------------------------------
def test_live_collect_applies_env_auth(
    fake_paho_module: _FakeMqttModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both env vars set → username_pw_set('u','p') called BEFORE connect."""
    fake_paho_module.outbox = [
        _live_msg("spBv1.0/plant1/DBIRTH/edge01/cobot-01", {"metric": "joint_temp", "value": 72.5}),
    ]
    monkeypatch.setenv("FDE_SCOPE_MQTT_USERNAME", "svc-fde")
    monkeypatch.setenv("FDE_SCOPE_MQTT_PASSWORD", "s3cret")

    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=1)
    rows = conn.extract_sample(5)

    client = fake_paho_module.created[0]
    assert client.username_pw_args == ("svc-fde", "s3cret")
    assert client.calls.index("username_pw_set") < client.calls.index("connect")
    assert rows, "expected the replayed message to come back as a row"


def test_live_collect_username_only(
    fake_paho_module: _FakeMqttModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FDE_SCOPE_MQTT_USERNAME", "svc-fde")
    monkeypatch.delenv("FDE_SCOPE_MQTT_PASSWORD", raising=False)

    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=1)
    conn.extract_sample(5)

    client = fake_paho_module.created[0]
    assert client.username_pw_args == ("svc-fde", None)


def test_live_collect_password_only_ignored(
    fake_paho_module: _FakeMqttModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """paho has no password-only API → a lone password must not be applied."""
    monkeypatch.delenv("FDE_SCOPE_MQTT_USERNAME", raising=False)
    monkeypatch.setenv("FDE_SCOPE_MQTT_PASSWORD", "s3cret")

    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=1)
    conn.extract_sample(5)

    client = fake_paho_module.created[0]
    assert client.username_pw_args is None
    assert "username_pw_set" not in client.calls


def test_live_collect_no_env_no_auth(
    fake_paho_module: _FakeMqttModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FDE_SCOPE_MQTT_USERNAME", raising=False)
    monkeypatch.delenv("FDE_SCOPE_MQTT_PASSWORD", raising=False)

    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=1)
    conn.extract_sample(5)

    client = fake_paho_module.created[0]
    assert client.username_pw_args is None
    assert "username_pw_set" not in client.calls
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_mqtt_connector.py -k live_collect -v`
Expected: 2 FAIL — `test_live_collect_applies_env_auth` and `test_live_collect_username_only` (`username_pw_args is None`, production never calls `username_pw_set`). The other 2 (`password_only_ignored`, `no_env_no_auth`) already PASS on current code — they are negative locks. (The pre-existing 13 tests stay green.)

- [ ] **Step 5: Implement `_apply_auth` and call it in `_collect_live`**

In `fde_scope/connectors/mqtt_sparkplug.py`, add `os` to the stdlib imports at the top (after `import json` / `import re`, keeping alphabetical order):

```python
import json
import os
import re
```

Add the new private method right after `_ensure_driver` (before the `# -- payload parsing` section):

```python
    # -- auth -------------------------------------------------------------------
    def _apply_auth(self, client: Any) -> None:
        """Apply broker credentials from the environment, if configured.

        Invariant (AGENTS.md #3): credentials live in env vars only — they
        are read at connect time and never persisted. paho's
        ``username_pw_set`` requires a username, so a password without a
        username cannot be expressed and is ignored.
        """
        username = os.environ.get("FDE_SCOPE_MQTT_USERNAME")
        password = os.environ.get("FDE_SCOPE_MQTT_PASSWORD")
        if username is not None:
            client.username_pw_set(username, password)
```

In `_collect_live`, insert the auth call between the TLS block and `client.on_message = ...`:

```python
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if use_tls:
            client.tls_set()
        self._apply_auth(client)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_mqtt_connector.py -v`
Expected: all PASS (13 pre-existing + 4 new).

- [ ] **Step 7: Commit**

```bash
git add tests/test_mqtt_connector.py fde_scope/connectors/mqtt_sparkplug.py
git commit -m "feat(mqtt): env-var broker auth via _apply_auth (FDE_SCOPE_MQTT_USERNAME/PASSWORD)"
```

---

### Task 2: `_collect_live` hardening (stage-aware cleanup, truncation, TLS, failure paths)

**Files:**
- Modify: `tests/test_mqtt_connector.py` (5 new tests)
- Modify: `fde_scope/connectors/mqtt_sparkplug.py` (rewrite `_collect_live`)

- [ ] **Step 1: Write the failing tests**

Append to the end of `tests/test_mqtt_connector.py`:

```python
def test_live_collect_normalizes_and_cleans_up(fake_paho_module: _FakeMqttModule) -> None:
    """Rows come out normalized; loop and socket are always torn down."""
    fake_paho_module.outbox = [
        _live_msg("spBv1.0/plant1/DBIRTH/edge01/cobot-01", {"metric": "joint_temp", "value": 72.5}),
        _live_msg("spBv1.0/plant1/DDATA/edge01/cobot-01", {"metrics": [{"name": "grip_force", "value": 35}]}),
    ]

    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=1)
    rows = conn.extract_sample(10)

    assert [r["metric_name"] for r in rows] == ["joint_temp", "grip_force"]
    assert rows[0]["device_id"] == "cobot-01"
    assert rows[0]["value"] == 72.5
    assert rows[0]["timestamp"]  # live path stamps receive time
    client = fake_paho_module.created[0]
    assert client.subscribed == ["spBv1.0/#"]
    assert client.tls_enabled is False  # plain mqtt:// → no TLS
    assert client.loop_stopped is True
    assert client.disconnected is True


def test_live_collect_truncates_at_n(fake_paho_module: _FakeMqttModule) -> None:
    """Callback thread may out-run the poll loop → truncate to n."""
    fake_paho_module.outbox = [
        _live_msg("spBv1.0/plant1/DDATA/edge01/cobot-01", {"metric": f"m{i}", "value": i})
        for i in range(5)
    ]

    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=1)
    rows = conn.extract_sample(2)

    assert len(rows) == 2


def test_live_collect_timeout_returns_empty(fake_paho_module: _FakeMqttModule) -> None:
    """Silent broker → [] after timeout_seconds, no hang."""
    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=1)
    assert conn.extract_sample(5) == []
    client = fake_paho_module.created[0]
    assert client.disconnected is True


def test_live_collect_connect_failure_propagates_without_cleanup(
    fake_paho_module: _FakeMqttModule,
) -> None:
    """Refused connect → error propagates; nothing to clean up is touched."""
    fake_paho_module.fail_connect = True

    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=1)
    with pytest.raises(ConnectionRefusedError):
        conn.extract_sample(5)

    client = fake_paho_module.created[0]
    assert client.connected is False
    assert client.loop_stopped is False
    assert client.disconnected is False


def test_live_collect_subscribe_failure_still_disconnects(
    fake_paho_module: _FakeMqttModule,
) -> None:
    """Connected but subscribe failed → socket must still be disconnected."""
    fake_paho_module.fail_subscribe = True

    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=1)
    with pytest.raises(RuntimeError, match="subscribe"):
        conn.extract_sample(5)

    client = fake_paho_module.created[0]
    assert client.connected is True
    assert client.loop_stopped is False  # loop never started
    assert client.disconnected is True


def test_live_collect_mqtts_enables_tls(fake_paho_module: _FakeMqttModule) -> None:
    fake_paho_module.outbox = [
        _live_msg("spBv1.0/plant1/DBIRTH/edge01/cobot-01", {"metric": "t", "value": 1}),
    ]

    conn = MqttSparkplugConnector("mqtts://broker.local:8883", timeout_seconds=1)
    conn.extract_sample(1)

    client = fake_paho_module.created[0]
    assert client.tls_enabled is True
```

- [ ] **Step 2: Run tests to verify the failure-path test fails**

Run: `.venv/bin/python -m pytest tests/test_mqtt_connector.py -k "live_collect" -v`
Expected: `test_live_collect_subscribe_failure_still_disconnects` FAIL (`disconnected is False` — current code has no try/finally, so cleanup never runs) and `test_live_collect_truncates_at_n` racy-but-usually-FAIL (callback thread appends all 5 rows before the poll loop checks). The other 4 PASS (characterization locks).

- [ ] **Step 3: Rewrite `_collect_live`**

Replace the entire `_collect_live` method in `fde_scope/connectors/mqtt_sparkplug.py` with:

```python
    def _collect_live(self, n: int) -> list[dict[str, Any]]:  # pragma: no cover — needs broker
        """Connect, subscribe, collect up to ``n`` rows, disconnect.

        Cleanup is stage-aware: an unconnected client is not disconnected
        and a never-started loop is not stopped (paho's behavior on those
        calls against an unestablished session is not something we rely
        on). Errors propagate honestly — no silent empty-data fallback.
        """
        self._ensure_driver()
        import paho.mqtt.client as mqtt

        out: list[dict[str, Any]] = []
        host, port, use_tls = self._connection_params()
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if use_tls:
            client.tls_set()
        self._apply_auth(client)
        connected = False
        loop_running = False
        try:
            client.connect(host, port, 60)
            connected = True
            client.subscribe(self.topic_filter)
            client.loop_start()
            loop_running = True
            import time

            deadline = time.time() + self.timeout_seconds
            while len(out) < n and time.time() < deadline:
                time.sleep(0.05)
        finally:
            if loop_running:
                client.loop_stop()
            if connected:
                client.disconnect()
        # The callback thread can out-run the poll loop's final check.
        return out[:n]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_mqtt_connector.py -v`
Expected: all PASS (17 pre-existing+new from Task 1 + 6 new = 23 total).

- [ ] **Step 5: Commit**

```bash
git add tests/test_mqtt_connector.py fde_scope/connectors/mqtt_sparkplug.py
git commit -m "fix(mqtt): stage-aware cleanup + [:n] truncation in live collect path"
```

---

### Task 3: Bounded `_stream_live` (`max_messages` + silence deadline + tail batch)

**Files:**
- Modify: `tests/test_mqtt_connector.py` (4 new tests)
- Modify: `fde_scope/connectors/mqtt_sparkplug.py` (`__init__` option, rewrite `_stream_live`)

- [ ] **Step 1: Write the failing tests**

Append to the end of `tests/test_mqtt_connector.py`:

```python
# ---------------------------------------------------------------------------
# Live stream — bounded termination (the hang fix)
# ---------------------------------------------------------------------------
def test_stream_live_bounded_terminates(fake_paho_module: _FakeMqttModule) -> None:
    """max_messages=3 + batch_size=2 → [2, 1] batches, generator ends."""
    fake_paho_module.outbox = [
        _live_msg("spBv1.0/plant1/DBIRTH/edge01/cobot-01", {"metric": "joint_temp", "value": 72.5}),
        _live_msg("spBv1.0/plant1/DDATA/edge01/cobot-01", {"metric": "grip_force", "value": 35}),
        _live_msg("spBv1.0/plant1/DDATA/edge01/cobot-01", {"metric": "cycle_count", "value": 1042}),
    ]

    conn = MqttSparkplugConnector(
        "mqtt://localhost:1883", timeout_seconds=2, max_messages=3
    )
    batches = list(conn.stream(batch_size=2))

    assert [len(b) for b in batches] == [2, 1]
    assert batches[0].source == "mqtt://localhost:1883"
    client = fake_paho_module.created[0]
    assert client.loop_stopped is True
    assert client.disconnected is True


def test_stream_live_silence_terminates(fake_paho_module: _FakeMqttModule) -> None:
    """Silent broker → generator exits after timeout_seconds (no hang)."""
    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=1)
    assert list(conn.stream(batch_size=5)) == []
    client = fake_paho_module.created[0]
    assert client.loop_stopped is True
    assert client.disconnected is True


def test_stream_live_counts_messages_not_rows(fake_paho_module: _FakeMqttModule) -> None:
    """One multi-metric message is ONE message for max_messages purposes."""
    fake_paho_module.outbox = [
        _live_msg(
            "spBv1.0/plant1/DDATA/edge01/cobot-01",
            {
                "metrics": [
                    {"name": "grip_force", "value": 35},
                    {"name": "joint_temp", "value": 72.5},
                    {"name": "cycle_count", "value": 1042},
                ]
            },
        ),
    ]

    conn = MqttSparkplugConnector(
        "mqtt://localhost:1883", timeout_seconds=2, max_messages=1
    )
    batches = list(conn.stream(batch_size=10))

    # 1 message → 3 rows, all in the single tail batch.
    assert [len(b) for b in batches] == [3]


def test_stream_live_default_max_messages_is_bounded(
    fake_paho_module: _FakeMqttModule,
) -> None:
    """Default max_messages=1000: a small outbox still terminates on silence."""
    fake_paho_module.outbox = [
        _live_msg("spBv1.0/plant1/DDATA/edge01/cobot-01", {"metric": "m", "value": 1}),
    ]

    conn = MqttSparkplugConnector("mqtt://localhost:1883", timeout_seconds=1)
    batches = list(conn.stream(batch_size=10))

    assert [len(b) for b in batches] == [1]
```

- [ ] **Step 2: Run the bounded test under a watchdog to verify it hangs (the bug)**

The current `_stream_live` never terminates (`while True` + `Empty: continue`), so a plain pytest run would hang. Verify with a Python watchdog:

Run:
```bash
python3 - <<'PY'
import subprocess, sys
try:
    r = subprocess.run(
        [".venv/bin/python", "-m", "pytest",
         "tests/test_mqtt_connector.py::test_stream_live_bounded_terminates",
         "-x", "-q"], timeout=90)
    sys.exit(r.returncode)
except subprocess.TimeoutExpired:
    print("HUNG (90s) — expected: current _stream_live never terminates")
    sys.exit(1)
PY
```
Expected: exit code 1 with the `HUNG` message (pytest killed after 90s).

- [ ] **Step 3: Add the `max_messages` option in `__init__`**

In `fde_scope/connectors/mqtt_sparkplug.py`, extend the option block in `__init__`:

```python
        self.topic_filter = options.get("topic", "spBv1.0/#")
        self.sparkplug = options.get("sparkplug", True)
        self.timeout_seconds = options.get("timeout_seconds", 5)
        # Live-stream bound: stop after this many *messages* (0 = unbounded,
        # consumer closes the generator). Guards corpus forge against a
        # never-terminating subscription.
        self.max_messages = int(options.get("max_messages", 1000))
```

- [ ] **Step 4: Rewrite `_stream_live`**

Replace the entire `_stream_live` method with:

```python
    def _stream_live(self, batch_size: int) -> Iterator[Batch]:  # pragma: no cover — needs broker
        """Bounded live subscription; yields batches as they fill.

        Terminates on whichever limit hits first: ``max_messages`` messages
        received (0 = unbounded — the consumer closes the generator), or
        ``timeout_seconds`` of silence. A partially-filled tail batch is
        yielded before exit.
        """
        self._ensure_driver()
        import queue

        import paho.mqtt.client as mqtt

        q: queue.Queue = queue.Queue()
        messages: list[Any] = []  # one entry per wire message (not per row)
        host, port, use_tls = self._connection_params()
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if use_tls:
            client.tls_set()
        self._apply_auth(client)
        client.on_message = self._make_on_message(q.put, messages)
        connected = False
        loop_running = False
        try:
            client.connect(host, port, 60)
            connected = True
            client.subscribe(self.topic_filter)
            client.loop_start()
            loop_running = True
            import time

            deadline = time.time() + self.timeout_seconds
            batch: list[dict[str, Any]] = []
            while self.max_messages == 0 or len(messages) < self.max_messages:
                try:
                    rec = q.get(timeout=1.0)
                except queue.Empty:
                    if time.time() >= deadline:
                        break
                    continue
                batch.append(rec)
                deadline = time.time() + self.timeout_seconds
                if len(batch) >= batch_size:
                    yield Batch(batch, source=str(self.broker))
                    batch = []
            if batch:
                yield Batch(batch, source=str(self.broker))
        finally:
            if loop_running:
                client.loop_stop()
            if connected:
                client.disconnect()
```

(Note: this references `_make_on_message`, which is extracted in Task 4. To keep this task green on its own, use a temporary inline callback instead — replace the `client.on_message = ...` line with:

```python
        def on_message(_c: Any, _d: Any, msg: Any) -> None:  # noqa: ANN001
            messages.append(msg)
            for row in self._normalize(
                {
                    "topic": msg.topic,
                    "payload": msg.payload.decode("utf-8", errors="replace"),
                    # No wire timestamp in plain MQTT — stamp receive time.
                    "timestamp": datetime.now(UTC).isoformat(),
                    "qos": msg.qos,
                    "retain": msg.retain,
                }
            ):
                q.put(row)
```

and keep everything else as shown. Task 4 then swaps it for `self._make_on_message(q.put, messages)`.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_mqtt_connector.py -v`
Expected: all PASS (23 + 4 = 27 total).

- [ ] **Step 6: Commit**

```bash
git add tests/test_mqtt_connector.py fde_scope/connectors/mqtt_sparkplug.py
git commit -m "fix(mqtt): bounded live stream — max_messages cap + silence deadline + tail batch"
```

---

### Task 4: Callback dedupe (`_make_on_message`) + hoist `import time`

**Files:**
- Modify: `fde_scope/connectors/mqtt_sparkplug.py` (refactor only — no behavior change)

- [ ] **Step 1: Hoist `import time` to module top**

In `fde_scope/connectors/mqtt_sparkplug.py`, the stdlib import block becomes:

```python
import asyncio
import json
import os
import re
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
```

(If `asyncio` is not in this module's imports, keep whatever exists and only add `time`, `os` (already added in Task 1), and extend the `collections.abc` import with `Callable`.)

- [ ] **Step 2: Add the `_make_on_message` helper**

Add after `_apply_auth`:

```python
    # -- shared live plumbing ----------------------------------------------------
    def _make_on_message(
        self,
        sink: Callable[[dict[str, Any]], None],
        message_log: list[Any] | None = None,
    ) -> Callable[..., None]:
        """Build a paho ``on_message`` callback over the shared normalize pipeline.

        Both live paths converge here; only the sink differs (list.append for
        collect, queue.put for stream). ``message_log`` records one entry per
        wire message — the stream path counts *messages*, not normalized rows.
        """

        def on_message(_client: Any, _userdata: Any, msg: Any) -> None:
            if message_log is not None:
                message_log.append(msg)
            for row in self._normalize(
                {
                    "topic": msg.topic,
                    "payload": msg.payload.decode("utf-8", errors="replace"),
                    # No wire timestamp in plain MQTT — stamp receive time.
                    "timestamp": datetime.now(UTC).isoformat(),
                    "qos": msg.qos,
                    "retain": msg.retain,
                }
            ):
                sink(row)

        return on_message
```

- [ ] **Step 3: Replace both inline callbacks**

In `_collect_live`, replace the inline `def on_message(...)` block and its assignment with:

```python
        client.on_message = self._make_on_message(out.append)
```

In `_stream_live`, replace the temporary inline callback from Task 3 with:

```python
        client.on_message = self._make_on_message(q.put, messages)
```

Then delete the now-duplicate inline `import time` lines inside `_collect_live` and `_stream_live` (module-level `time` is available).

- [ ] **Step 4: Run tests + lint to verify no behavior change**

Run: `.venv/bin/python -m pytest tests/test_mqtt_connector.py -q`
Expected: all 27 PASS.

Run: `.venv/bin/ruff check fde_scope/connectors/mqtt_sparkplug.py tests/test_mqtt_connector.py && .venv/bin/ruff format --check fde_scope/connectors/mqtt_sparkplug.py tests/test_mqtt_connector.py`
Expected: no errors (format clean).

- [ ] **Step 5: Commit**

```bash
git add fde_scope/connectors/mqtt_sparkplug.py
git commit -m "refactor(mqtt): converge live callbacks into _make_on_message, hoist time import"
```

---

### Task 5: Driver contract (extra-named error, fake-vs-real surface guard, gated real smoke)

**Files:**
- Modify: `tests/test_mqtt_connector.py` (2 new tests)
- Modify: `fde_scope/connectors/mqtt_sparkplug.py` (`_ensure_driver` message)

- [ ] **Step 1: Write the failing driver-message test and the surface guard**

Append to the end of `tests/test_mqtt_connector.py`:

```python
# ---------------------------------------------------------------------------
# Driver availability contract
# ---------------------------------------------------------------------------
def test_ensure_driver_message_names_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the user forgot the [mqtt] extra, the error names the fix."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "paho" or name.startswith("paho."):
            raise ImportError("simulated missing driver")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    conn = MqttSparkplugConnector("mqtt://localhost:1883")
    with pytest.raises(ImportError, match=r"fde-scope\[mqtt\]"):
        conn._ensure_driver()


def test_fake_surface_matches_real_paho_client() -> None:
    """Guard against the fake drifting from the real paho Client API.

    Skipped when paho-mqtt isn't installed (CI without the [mqtt] extra).
    """
    paho_client = pytest.importorskip("paho.mqtt.client")
    for name in (
        "username_pw_set",
        "tls_set",
        "connect",
        "subscribe",
        "loop_start",
        "loop_stop",
        "disconnect",
    ):
        assert hasattr(paho_client.Client, name), (
            f"paho Client.{name} missing — fake drifted from driver"
        )


# ---------------------------------------------------------------------------
# Real-broker integration test (opt-in via env var)
# ---------------------------------------------------------------------------
@pytest.mark.mqtt
def test_mqtt_real_broker_smoke() -> None:
    """End-to-end against a real broker. Skipped unless FDE_SCOPE_MQTT_URL
    is set (e.g. local mosquitto or a customer's broker). Publish at least
    one retained message before running, or run it while a publisher is live.
    """
    url = os.environ.get("FDE_SCOPE_MQTT_URL")
    if not url:
        pytest.skip("FDE_SCOPE_MQTT_URL not set; skipping real-broker integration test")
    pytest.importorskip("paho.mqtt.client")
    conn = MqttSparkplugConnector(url, timeout_seconds=10)
    sample = conn.extract_sample(10)
    assert sample, "no messages received; publish a test message first"
    assert sample[0]["topic"]
```

- [ ] **Step 2: Register the `mqtt` pytest marker in `pyproject.toml`**

This must land in the same task as the `@pytest.mark.mqtt` test to avoid a `PytestUnknownMarkWarning`. In `[tool.pytest.ini_options]`, add after the `opcua` marker line:

```toml
markers = [
    "agentscope: tests that import the optional agentscope extra (skipped if not installed)",
    "mysql: tests that require a real MySQL server (skipped unless FDE_SCOPE_MYSQL_DSN is set)",
    "opcua: tests that require a real OPC UA server (skipped unless FDE_SCOPE_OPCUA_URL is set)",
    "mqtt: tests that require a real MQTT broker (skipped unless FDE_SCOPE_MQTT_URL is set)",
]
```

- [ ] **Step 3: Run to verify the driver test fails**

Run: `.venv/bin/python -m pytest tests/test_mqtt_connector.py::test_ensure_driver_message_names_the_extra tests/test_mqtt_connector.py::test_fake_surface_matches_real_paho_client tests/test_mqtt_connector.py::test_mqtt_real_broker_smoke -v`
Expected: `test_ensure_driver_message_names_the_extra` FAIL (current message says `pip install paho-mqtt`, not `fde-scope[mqtt]`); `test_fake_surface_matches_real_paho_client` SKIPPED (paho not installed in venv yet); `test_mqtt_real_broker_smoke` SKIPPED (env var unset).

- [ ] **Step 4: Update `_ensure_driver`**

In `fde_scope/connectors/mqtt_sparkplug.py`, replace the `_ensure_driver` body:

```python
    # -- driver lazy import -----------------------------------------------------
    def _ensure_driver(self) -> None:
        try:
            import paho.mqtt.client  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "MqttSparkplugConnector live mode needs the optional 'mqtt' extra "
                "(paho-mqtt): pip install 'fde-scope[mqtt]'"
            ) from exc
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_mqtt_connector.py -q`
Expected: all PASS with 2 skips (surface guard + real smoke).

- [ ] **Step 6: Commit**

```bash
git add tests/test_mqtt_connector.py fde_scope/connectors/mqtt_sparkplug.py pyproject.toml
git commit -m "feat(mqtt): actionable driver error naming the [mqtt] extra + paho surface guard"
```

---

### Task 6: Packaging & docs wiring (pyproject extra/full, README install block, module docstring)

**Files:**
- Modify: `pyproject.toml`
- Modify: `fde_scope/connectors/mqtt_sparkplug.py` (module docstring only)
- Modify: `README.md` (install block)

- [ ] **Step 1: Declare the `mqtt` extra in `pyproject.toml`**

(The pytest marker was already added in Task 5 Step 2.) In `[project.optional-dependencies]`, after the `opcua` line, add:

```toml
opcua = ["asyncua>=1.0,<3"]
mqtt = ["paho-mqtt>=2.0,<3"]
web = ["fastapi>=0.110", "uvicorn[standard]>=0.27", "python-multipart>=0.0.9"]
```

Add to the `full` meta-extra (keep alphabetical order, after opcua):

```toml
full = [
    "fde-scope[dev]",
    "fde-scope[agentscope]",
    "fde-scope[mysql]",
    "fde-scope[opcua]",
    "fde-scope[mqtt]",
    "fde-scope[web]",
]
```

- [ ] **Step 2: Update the README install block**

In `README.md`, the install block (around line 598-606) becomes:

```bash
pip install -e "."                 # core only
pip install -e ".[dev]"            # + pytest + web test client
pip install -e ".[web]"            # + FastAPI/uvicorn console
pip install -e ".[agentscope]"    # + real AgentScope 2.0 runtime layer
pip install -e ".[mysql]"          # + MySQL connector driver
pip install -e ".[opcua]"          # + OPC UA connector driver (asyncua)
pip install -e ".[mqtt]"           # + MQTT-Sparkplug live broker driver (paho-mqtt)
pip install -e ".[full]"           # everything (dev + agentscope + mysql + opcua + mqtt + web)
```

- [ ] **Step 3: Update the module docstring in `mqtt_sparkplug.py`**

In the module docstring, extend mode 2's paragraph (after the "2. **Live broker subscription**" paragraph, before "Industry note:"):

```python
2. **Live broker subscription** (needs ``paho-mqtt``: ``pip install
   'fde-scope[mqtt]'``): connect to a real broker, subscribe, and collect
   messages. Plain-MQTT JSON payloads are parsed; native Sparkplug B
   protobuf decoding is roadmap (the payload schema is honored
   regardless, so downstream code is stable).

Live-mode options: ``timeout_seconds`` (collect window / stream silence
deadline), ``max_messages`` (stream bound, default 1000, 0 = unbounded),
``topic`` (subscription filter). Broker credentials come from the
environment only: ``FDE_SCOPE_MQTT_USERNAME`` / ``FDE_SCOPE_MQTT_PASSWORD``.
```

- [ ] **Step 4: Run the architecture guards and full suite**

Run: `.venv/bin/python -m pytest tests/test_architecture_guard.py -q`
Expected: all PASS (extras subset check and `.[full]` doc agreement unaffected).

Run: `.venv/bin/python -m pytest -q`
Expected: full suite green; new skips: surface guard + real-broker smoke (both paho/env-gated).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml README.md fde_scope/connectors/mqtt_sparkplug.py
git commit -m "build(mqtt): declare [mqtt] extra (paho-mqtt>=2,<3), pytest marker, docs wiring"
```

---

### Task 7: Real-broker verification (local mosquitto) + roadmap checkbox

**Files:**
- Modify: `README.md` (roadmap line only)

No repo code changes in this task — this is the one-time real-broker proof (user pre-approved `brew install mosquitto` and a local broker run).

- [ ] **Step 1: Install the broker and the driver**

```bash
brew install mosquitto
.venv/bin/pip install 'paho-mqtt>=2.0,<3'
```

- [ ] **Step 2: Start a local broker with an explicit config**

mosquitto 2.x denies anonymous access by default when a config listener is present; make the intent explicit so the test is deterministic:

```bash
cat > /tmp/fde-mosquitto.conf <<'EOF'
listener 1883 127.0.0.1
allow_anonymous true
EOF
/opt/homebrew/sbin/mosquitto -c /tmp/fde-mosquitto.conf -d
```

(If `/opt/homebrew/sbin/mosquitto` doesn't exist, use `mosquitto -c /tmp/fde-mosquitto.conf -d`.)

Verify it is listening:

```bash
lsof -nP -iTCP:1883 -sTCP:LISTEN
```
Expected: one mosquitto process on 127.0.0.1:1883.

- [ ] **Step 3: Publish retained Sparkplug-style sample messages**

Retained (`-r`) so the messages survive until the test subscribes — order-independent:

```bash
mosquitto_pub -h 127.0.0.1 -t 'spBv1.0/plant1/DBIRTH/edge01/cobot-01' -r -m '{"metric":"joint_temp","value":72.5}'
mosquitto_pub -h 127.0.0.1 -t 'spBv1.0/plant1/DDATA/edge01/cobot-01' -r -m '{"metrics":[{"name":"grip_force","value":35},{"name":"cycle_count","value":1042}]}'
mosquitto_pub -h 127.0.0.1 -t 'spBv1.0/plant1/NDEATH/edge01' -r -m 'raw-bytes'
```

- [ ] **Step 4: Run the gated real-broker test**

```bash
FDE_SCOPE_MQTT_URL=mqtt://127.0.0.1:1883 .venv/bin/python -m pytest tests/test_mqtt_connector.py -m mqtt -v
```
Expected: `test_mqtt_real_broker_smoke PASSED` (receives the retained messages, extracts device `cobot-01` from the topic, parses the metric payloads).

- [ ] **Step 5: Exercise the connector end-to-end from Python (optional but recommended)**

```bash
FDE_SCOPE_MQTT_URL=mqtt://127.0.0.1:1883 .venv/bin/python - <<'PY'
from fde_scope.connectors.mqtt_sparkplug import MqttSparkplugConnector
conn = MqttSparkplugConnector("mqtt://127.0.0.1:1883", timeout_seconds=5, max_messages=10)
print("schema row_count:", conn.discover_schema().row_count)
for row in conn.extract_sample(10):
    print(row["device_id"], row["metric_name"], row["value"])
PY
```
Expected: schema row_count None (live), then rows for joint_temp / grip_force / cycle_count / raw with device ids cobot-01 / edge01.

- [ ] **Step 6: Stop the broker and clear retained state**

```bash
pkill -f 'mosquitto.*fde-mosquitto.conf'
```

- [ ] **Step 7: Flip the README roadmap checkbox**

In `README.md` line ~678, change:

```markdown
- [ ] MQTT-Sparkplug 真实 broker IO（paho-mqtt）
```
to (mirroring the OPC UA line's style):

```markdown
- [x] MQTT-Sparkplug 真实 broker IO（paho-mqtt 驱动，mock + 真 broker 测试）
```

- [ ] **Step 8: Final full verification + commit**

Run: `.venv/bin/python -m pytest -q`
Expected: full suite green (only the expected env-gated skips).

Run: `.venv/bin/ruff check fde_scope tests && .venv/bin/ruff format --check fde_scope tests`
Expected: clean.

```bash
git add README.md
git commit -m "docs(readme): mark MQTT-Sparkplug live broker IO done (verified against local mosquitto)"
```

---

## Verification checklist (maps to spec §5)

| Spec requirement | Task |
|---|---|
| `_ensure_driver` → `fde-scope[mqtt]` | Task 5 |
| `_apply_auth` env-only, username-gated | Task 1 |
| `_collect_live` stage-aware cleanup + `[:n]` + honest errors | Task 2 |
| `_stream_live` bounded (`max_messages` / silence / tail batch) | Task 3 |
| `_make_on_message` dedupe + `import time` hoist | Task 4 |
| pyproject extra/full + README install | Task 6 |
| `mqtt` pytest marker | Task 5 |
| Mocked layer: auth / normalize / truncate / TLS / failures / timeouts / stream bounds | Tasks 1-3 |
| Real layer `@pytest.mark.mqtt` + surface guard | Task 5 |
| Local mosquitto verification | Task 7 |
| Roadmap checkbox | Task 7 |
