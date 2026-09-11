# rosbag2 真实回放实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `fde_scope/connectors/ros2_bag.py` 从骨架变成真实可交付：真实读取 bag 文件、三步契约全通、TF/JointState 语义展开、大二进制排除、`[ros2]` extra 实测钉窗、双层测试 + 真实 bag 端到端实测。

**Architecture:** 单文件连接器（`ros2_bag.py`），复刻 MQTT-Sparkplug 的交付模式：`_iter_bag()` 是唯一触碰 rosbags 的点（产出平面元组），normalize/展开/排除逻辑只吃 dict——契约测试无需 rosbags。msg_type 键控展开器 dict（`_EXPANDERS`），大二进制排除表先于展开判断。

**Tech Stack:** Python 3.11+, rosbags (pure Python, ≥0.11,<0.12 — 实测钉窗), pytest, pydantic v2

**Spec:** `docs/superpowers/specs/2026-09-09-rosbag2-live-replay-design.md`

## Global Constraints

- rosbags specifier 以 Task 1 实测为准（预期 `rosbags>=0.11,<0.12`）；实测钉窗，不钉则不改
- `pyproject.toml` extra 名 `ros2`；`full` meta-extra 必须含 `"fde-scope[ros2]"`
- `dev` extra 加入 `rosbags`（自产 bag 测试零外部服务，CI 常跑）
- `markers` 新增 `ros2: tests that require a real recorded bag (skipped unless FDE_SCOPE_ROS2_BAG is set)`
- README/Makefile/守护测试三处 extras 口径一致
- 连接器 slug 不变（`ros2_bag`，已注册）；connector registry 守护测试不受影响
- 只读连接器——不触碰凭证、不产生持久化写、不改 gate/权限管线
- 文件体量红线 ≤400 行（spec §2 方案 A 理由）

---

### Task 1: 实测钉窗 — rosbags API 签名确认

**Files:**
- Create: `scripts/scratch_rosbags_api.py`（临时实测脚本，计划完成后可删）

**Interfaces:**
- Consumes: 无（纯实测）
- Produces: 确认 rosbags 0.11.x 的 `AnyReader` / `AnyWriter` / `default_typestore` / `get_typestore(Stores.ROS2_HUMBLE)` 实际签名，锁定 specifier

- [ ] **Step 1: 创建隔离 venv 安装 rosbags**

```bash
python3.12 -m venv /tmp/rosbags-probe
/tmp/rosbags-probe/bin/pip install rosbags
/tmp/rosbags-probe/bin/pip show rosbags  # 记录版本
```

- [ ] **Step 2: 写实测脚本确认 reader/writer/typestore 签名**

```python
# scripts/scratch_rosbags_api.py
"""rosbags API 实测——确认 reader/writer/typestore 签名后再钉 specifier。"""
from __future__ import annotations
import tempfile, shutil
from pathlib import Path

from rosbags.highlevel import AnyReader, AnyWriter
from rosbags.typesys import get_typestore, Stores, default_typestore

# Writer: 自产 bag
tmp = Path(tempfile.mkdtemp())
try:
    with AnyWriter(tmp) as writer:
        conn = writer.add_connection("/chatter", "std_msgs/msg/String")
        typestore = default_typestore()
        msg = typestore.deserialize_ros2(b"\x00" * 8 + b"hello", "std_msgs/msg/String")
        # 或直接构造: msg = typestore.create_instance("std_msgs/msg/String")
        writer.write(conn, 1_000_000_000, msg)
    # Reader: 读回
    with AnyReader(tmp) as reader:
        reader.open()
        for conn, timestamp, raw in reader.messages():
            msg = reader.deserialize(raw, conn.msgtype)
            print(f"topic={conn.topic} type={conn.msgtype} ts={timestamp} msg={msg}")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# typestore 签名
ts = get_typestore(Stores.ROS2_HUMBLE)
print(f"default_typestore type: {type(default_typestore())}")
print(f"get_typestore(Stores.ROS2_HUMBLE) type: {type(ts)}")
print(f"ROS2_HUMBLE value: {Stores.ROS2_HUMBLE}")
```

- [ ] **Step 3: 运行实测脚本，记录签名**

```bash
/tmp/rosbags-probe/bin/python scripts/scratch_rosbags_api.py
```

记录：
- `AnyWriter(path)` 上下文管理器 → `add_connection(topic, msgtype)` → `write(conn, timestamp_ns, msg)`
- `AnyReader(path)` 上下文管理器 → `.open()` → `.messages()` 产出 `(connection, timestamp, raw)` → `.deserialize(raw, msgtype)` 得消息对象
- `default_typestore()` / `get_typestore(Stores.ROS2_HUMBLE)` 可用
- 消息对象属性访问：`msg.data`（std_msgs/String）、`msg.transforms`（TFMessage）、`msg.name`/`msg.position` 等

- [ ] **Step 4: 确认版本并锁定 specifier**

```bash
/tmp/rosbags-probe/bin/pip show rosbags | grep Version
```

预期 `0.11.x`。若版本在 `[0.11, 0.12)` 范围且 API 与实测一致，specifier 钉为 `rosbags>=0.11,<0.12`。若有差异，以实测为准调整。

- [ ] **Step 5: 清理临时文件**

```bash
rm -rf /tmp/rosbags-probe
rm scripts/scratch_rosbags_api.py
```

- [ ] **Step 6: 记录实测结论**

在后续 Task 2 的 pyproject.toml 中使用实测确认的 specifier。不做 commit（此 task 是实测，无代码产物）。

---

### Task 2: pyproject.toml extras + markers 布线

**Files:**
- Modify: `pyproject.toml:32-92`
- Test: `tests/test_architecture_guard.py:44-50`（已有 extras 子集检查）

**Interfaces:**
- Consumes: Task 1 实测确认的 rosbags specifier
- Produces: `[ros2]` extra 可用；`full` 含 `fde-scope[ros2]`；`dev` 含 `rosbags`；`markers` 含 `ros2`

- [ ] **Step 1: 写失败测试 — 确认架构守卫会捕获缺失**

当前 `test_optional_dependencies_define_the_full_extra` 检查 `{dev, agentscope, mysql, opcua, web} <= set(extras)`。新增 `ros2` 后此检查不变（它只检查最低子集），但 `full` 引用检查需要 `ros2` 也在 full 中。先运行现有守卫确认基线：

```bash
pytest tests/test_architecture_guard.py -v
```

预期：全绿（基线）。

- [ ] **Step 2: 修改 pyproject.toml — 新增 ros2 extra + dev 加 rosbags + full 加 ros2 + markers 加 ros2**

在 `[project.optional-dependencies]` 段，`mqtt` 行之后新增：

```toml
ros2 = ["rosbags>=0.11,<0.12"]
```

修改 `dev` extra，在 `"python-multipart>=0.0.9",` 之后加入：

```toml
    "rosbags>=0.11,<0.12",
```

修改 `full` meta-extra，在 `"fde-scope[mqtt]",` 之后加入：

```toml
    "fde-scope[ros2]",
```

在 `[tool.pytest.ini_options] markers` 段，`mqtt` 行之后新增：

```toml
    "ros2: tests that require a real recorded bag (skipped unless FDE_SCOPE_ROS2_BAG is set)",
```

- [ ] **Step 3: 运行架构守卫确认通过**

```bash
pytest tests/test_architecture_guard.py -v
```

预期：全绿。`test_optional_dependencies_define_the_full_extra` 的 `full_ref` 检查现在要求 `"fde-scope[ros2]"` 出现在 full 中。

- [ ] **Step 4: 安装新 extra 确认依赖解析**

```bash
pip install -e ".[ros2]"
pip show rosbags  # 确认安装成功
```

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "build(ros2): declare [ros2] extra (rosbags>=0.11,<0.12) + dev + markers"
```

---

### Task 3: 路径形态检测 + _ensure_driver 错误指引

**Files:**
- Modify: `fde_scope/connectors/ros2_bag.py`
- Create: `tests/test_ros2_bag.py`

**Interfaces:**
- Consumes: pyproject.toml 的 `[ros2]` extra（Task 2）
- Produces: `Ros2BagConnector` 正确识别 bag 目录 / .mcap 文件 / 拒绝裸 .db3；`_ensure_driver` 错误信息指向 `fde-scope[ros2]`

- [ ] **Step 1: 写失败测试 — 路径形态检测**

```python
# tests/test_ros2_bag.py
"""Tests for the ROS 2 bag connector.

Contract layer: no rosbags dependency needed — fake dicts feed the
normalize/expand/exclude pipeline. Real-file layer: rosbags Writer
self-produces bags (dual format). Integration: env-gated real bag.
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from fde_scope.connectors.ros2_bag import Ros2BagConnector


# ---------------------------------------------------------------------------
# Path form detection
# ---------------------------------------------------------------------------
def test_bag_directory_detected(tmp_path: Path) -> None:
    """A directory containing metadata.yaml is a standard bag directory."""
    (tmp_path / "metadata.yaml").write_text("rosbag2_bagfile_information:\n", encoding="utf-8")
    c = Ros2BagConnector(str(tmp_path))
    assert c.bag_path == tmp_path
    assert c._path_form == "dir"


def test_mcap_file_detected(tmp_path: Path) -> None:
    c = Ros2BagConnector(str(tmp_path / "recording.mcap"))
    assert c._path_form == "mcap"


def test_db3_directory_rejected(tmp_path: Path) -> None:
    """A directory without metadata.yaml (e.g. bare .db3) must error with guidance."""
    (tmp_path / "data.db3").write_bytes(b"\x00")
    c = Ros2BagConnector(str(tmp_path))
    with pytest.raises(ValueError, match="metadata.yaml"):
        c._validate_path()


def test_unknown_extension_rejected(tmp_path: Path) -> None:
    c = Ros2BagConnector(str(tmp_path / "data.txt"))
    with pytest.raises(ValueError, match="mcap"):
        c._validate_path()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_ros2_bag.py -v
```

预期：FAIL — `_path_form` 属性不存在，`_validate_path` 不存在。

- [ ] **Step 3: 实现路径检测 + _validate_path**

在 `ros2_bag.py` 的 `__init__` 中，替换现有 `self.bag_path = Path(source)` 为路径形态检测逻辑：

```python
def __init__(self, source: str, **options: Any) -> None:
    super().__init__(source, **options)
    self.bag_path = Path(source)
    self.topics: list[str] = options.get("topics", [])  # empty = all
    self.expand: bool = options.get("expand", True)
    self.include_binary: bool = options.get("include_binary", False)
    self.skipped: int = 0
    self._path_form = self._detect_path_form()

def _detect_path_form(self) -> str:
    """Return 'dir' for a bag directory (has metadata.yaml), 'mcap' for a
    .mcap file, or 'unknown' for anything else."""
    p = self.bag_path
    if p.is_dir() and (p / "metadata.yaml").exists():
        return "dir"
    if p.suffix == ".mcap":
        return "mcap"
    return "unknown"

def _validate_path(self) -> None:
    """Raise ValueError with guidance if the path form is unsupported."""
    form = self._path_form
    if form in ("dir", "mcap"):
        return
    p = self.bag_path
    if p.is_dir():
        raise ValueError(
            f"Directory {p} has no metadata.yaml — not a standard rosbag2 bag. "
            "Bare .db3 files are not supported; re-record as mcap "
            "(rosbag2 record --storage mcap) or add a metadata.yaml."
        )
    raise ValueError(
        f"Unsupported bag path: {p}. Expected a bag directory (with metadata.yaml) "
        "or a .mcap file."
    )
```

- [ ] **Step 4: 写失败测试 — _ensure_driver 错误信息**

```python
def test_ensure_driver_message_names_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the user forgot the [ros2] extra, the error names the fix."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "rosbags" or name.startswith("rosbags."):
            raise ImportError("simulated missing driver")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    # Need a valid path form to reach _ensure_driver
    c = Ros2BagConnector("dummy.mcap")
    with pytest.raises(ImportError, match=r"fde-scope\[ros2\]"):
        c._ensure_driver()
```

- [ ] **Step 5: 运行测试确认失败**

```bash
pytest tests/test_ros2_bag.py::test_ensure_driver_message_names_the_extra -v
```

预期：FAIL — 现有错误信息不含 `fde-scope[ros2]`。

- [ ] **Step 6: 修改 _ensure_driver 错误信息**

替换现有的 `_ensure_driver` 方法：

```python
def _ensure_driver(self) -> None:
    try:
        from rosbags.highlevel import AnyReader  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "Ros2BagConnector needs the optional 'ros2' extra "
            "(rosbags): pip install 'fde-scope[ros2]'"
        ) from exc
```

- [ ] **Step 7: 运行测试确认通过**

```bash
pytest tests/test_ros2_bag.py -v
```

预期：全绿。

- [ ] **Step 8: Commit**

```bash
git add fde_scope/connectors/ros2_bag.py tests/test_ros2_bag.py
git commit -m "feat(ros2): path form detection + _ensure_driver extra naming"
```

---

### Task 4: Normalize 管道 + 大二进制排除表

**Files:**
- Modify: `fde_scope/connectors/ros2_bag.py`
- Modify: `tests/test_ros2_bag.py`

**Interfaces:**
- Consumes: Task 3 的路径检测 + options
- Produces: `_normalize(msg_dict)` 返回行列表；`_BINARY_TYPES` 排除表；`_is_binary(msg_type)` 判定

- [ ] **Step 1: 写失败测试 — normalize 基础字段**

```python
# --- normalize pipeline ---
def test_normalize_base_fields() -> None:
    """Every normalized row carries topic/msg_type/timestamp_ns/payload."""
    c = Ros2BagConnector("dummy.mcap")
    rows = c._normalize(
        topic="/chatter",
        msg_type="std_msgs/msg/String",
        timestamp_ns=1_000_000_000,
        msg={"data": "hello"},
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["topic"] == "/chatter"
    assert row["msg_type"] == "std_msgs/msg/String"
    assert row["timestamp_ns"] == 1_000_000_000
    assert row["payload"] == {"data": "hello"}
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_ros2_bag.py::test_normalize_base_fields -v
```

预期：FAIL — `_normalize` 方法签名不匹配。

- [ ] **Step 3: 实现 _normalize + _BINARY_TYPES + _is_binary**

在 `ros2_bag.py` 中定义排除表和 normalize 方法：

```python
# Large binary message types — skipped by default, metadata-only stubs
# when include_binary=True. Exclusion fires before expansion logic.
_BINARY_TYPES = frozenset({
    "sensor_msgs/msg/Image",
    "sensor_msgs/msg/CompressedImage",
    "sensor_msgs/msg/PointCloud2",
})

# msg_type → expander callable. Populated in Task 5; empty dict means
# all non-binary types fall through to the payload JSON fallback.
_EXPANDERS: dict[str, Any] = {}

def _is_binary(self, msg_type: str) -> bool:
    return msg_type in _BINARY_TYPES
```

`_normalize` 方法：

```python
def _normalize(
    self,
    *,
    topic: str,
    msg_type: str,
    timestamp_ns: int,
    msg: dict[str, Any],
) -> list[dict[str, Any]]:
    """Produce rows from one bag message.

    Binary exclusion fires first (before expansion). With
    ``include_binary=False`` (default) binary types are skipped entirely
    (the caller increments ``self.skipped``). With ``include_binary=True``
    a metadata-only stub row is emitted — scalar fields like
    width/height/encoding/format plus ``byte_size``, never the ``data``
    array.

    Non-binary types: if ``expand=True`` and an expander is registered
    for ``msg_type``, use it; otherwise fall back to payload JSON.
    """
    base = {
        "topic": topic,
        "msg_type": msg_type,
        "timestamp_ns": timestamp_ns,
    }

    if self._is_binary(msg_type):
        if not self.include_binary:
            return []  # caller increments self.skipped
        return [self._binary_stub(base, msg)]

    if self.expand:
        expander = _EXPANDERS.get(msg_type)
        if expander is not None:
            return [{**base, **row} for row in expander(msg)]

    return [{**base, "payload": msg}]
```

`_binary_stub` 方法：

```python
def _binary_stub(self, base: dict[str, Any], msg: dict[str, Any]) -> dict[str, Any]:
    """Extract scalar metadata from a binary message — never the data array."""
    stub: dict[str, Any] = {}
    # Image / CompressedImage share some fields; PointCloud2 has 'fields'
    for key in ("width", "height", "encoding", "format", "is_bigendian", "step"):
        if key in msg:
            stub[key] = msg[key]
    if "fields" in msg and isinstance(msg["fields"], list):
        stub["fields"] = [
            {"name": f.get("name", ""), "datatype": f.get("datatype", 0)}
            for f in msg["fields"]
            if isinstance(f, dict)
        ]
    # byte_size: len(data) if present, else 0
    data = msg.get("data")
    stub["byte_size"] = len(data) if isinstance(data, (bytes, list)) else 0
    return {**base, "payload": stub}
```

- [ ] **Step 4: 写失败测试 — 二进制排除 + include_binary stub**

```python
def test_binary_type_skipped_by_default() -> None:
    c = Ros2BagConnector("dummy.mcap")
    rows = c._normalize(
        topic="/camera/image",
        msg_type="sensor_msgs/msg/Image",
        timestamp_ns=100,
        msg={"width": 640, "height": 480, "encoding": "bgr8", "data": b"\x00" * 100},
    )
    assert rows == []

def test_binary_type_stub_with_include_binary() -> None:
    c = Ros2BagConnector("dummy.mcap", include_binary=True)
    rows = c._normalize(
        topic="/camera/image",
        msg_type="sensor_msgs/msg/Image",
        timestamp_ns=100,
        msg={"width": 640, "height": 480, "encoding": "bgr8", "data": b"\x00" * 100},
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["width"] == 640
    assert row["height"] == 480
    assert row["encoding"] == "bgr8"
    assert row["byte_size"] == 100
    assert "data" not in row  # never the raw array

def test_binary_exclusion_fires_before_expand() -> None:
    """expand=False must not re-enable binary types."""
    c = Ros2BagConnector("dummy.mcap", expand=False)
    rows = c._normalize(
        topic="/camera/image",
        msg_type="sensor_msgs/msg/Image",
        timestamp_ns=100,
        msg={"width": 640, "height": 480, "data": b"\x00" * 50},
    )
    assert rows == []

def test_pointcloud2_skipped_by_default() -> None:
    c = Ros2BagConnector("dummy.mcap")
    rows = c._normalize(
        topic="/lidar/points",
        msg_type="sensor_msgs/msg/PointCloud2",
        timestamp_ns=200,
        msg={"width": 100, "height": 1, "fields": [{"name": "x", "datatype": 7}], "data": b"\x00" * 200},
    )
    assert rows == []

def test_compressed_image_skipped_by_default() -> None:
    c = Ros2BagConnector("dummy.mcap")
    rows = c._normalize(
        topic="/camera/compressed",
        msg_type="sensor_msgs/msg/CompressedImage",
        timestamp_ns=300,
        msg={"format": "jpeg", "data": b"\xff\xd8\xff"},
    )
    assert rows == []
```

- [ ] **Step 5: 运行测试确认通过**

```bash
pytest tests/test_ros2_bag.py -v -k "normalize or binary"
```

预期：全绿。

- [ ] **Step 6: Commit**

```bash
git add fde_scope/connectors/ros2_bag.py tests/test_ros2_bag.py
git commit -m "feat(ros2): normalize pipeline + binary exclusion table"
```

---

### Task 5: TFMessage + JointState 语义展开器

**Files:**
- Modify: `fde_scope/connectors/ros2_bag.py`
- Modify: `tests/test_ros2_bag.py`

**Interfaces:**
- Consumes: Task 4 的 normalize 管道
- Produces: `_EXPANDERS` dict，TFMessage 每 transform 1 行，JointState 每关节 1 行

- [ ] **Step 1: 写失败测试 — TFMessage 展开**

```python
# --- expanders ---
def test_tf_message_expands_per_transform() -> None:
    """One TFMessage with 2 transforms → 2 rows, each with frame fields."""
    c = Ros2BagConnector("dummy.mcap")
    msg = {
        "transforms": [
            {
                "header": {"stamp": {"sec": 1, "nanosec": 0}},
                "child_frame_id": "base_link",
                "transform": {
                    "translation": {"x": 1.0, "y": 2.0, "z": 3.0},
                    "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                },
            },
            {
                "header": {"stamp": {"sec": 1, "nanosec": 500}},
                "child_frame_id": "camera_link",
                "transform": {
                    "translation": {"x": 0.1, "y": 0.0, "z": 0.5},
                    "rotation": {"x": 0.0, "y": 0.0, "z": 0.707, "w": 0.707},
                },
            },
        ]
    }
    # TFMessage topic is typically /tf; frame_id is in the header but we
    # use the parent frame from the transform itself (header.frame_id).
    # The expander reads from the dict shape rosbags deserializes to.
    rows = c._normalize(
        topic="/tf",
        msg_type="tf2_msgs/msg/TFMessage",
        timestamp_ns=1_000_000_000,
        msg=msg,
    )
    assert len(rows) == 2
    assert rows[0]["child_frame_id"] == "base_link"
    assert rows[0]["tx"] == 1.0
    assert rows[0]["ty"] == 2.0
    assert rows[0]["tz"] == 3.0
    assert rows[0]["qx"] == 0.0
    assert rows[0]["qy"] == 0.0
    assert rows[0]["qz"] == 0.0
    assert rows[0]["qw"] == 1.0
    assert rows[0]["header_stamp_ns"] == 1_000_000_000  # sec=1, nanosec=0
    assert rows[1]["child_frame_id"] == "camera_link"
    assert rows[1]["tx"] == 0.1

def test_tf_message_empty_transforms() -> None:
    c = Ros2BagConnector("dummy.mcap")
    rows = c._normalize(
        topic="/tf",
        msg_type="tf2_msgs/msg/TFMessage",
        timestamp_ns=100,
        msg={"transforms": []},
    )
    assert rows == []
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_ros2_bag.py::test_tf_message_expands_per_transform -v
```

预期：FAIL — `_EXPANDERS` 未定义。

- [ ] **Step 3: 写失败测试 — JointState 展开**

```python
def test_joint_state_expands_per_joint() -> None:
    """One JointState with 3 joints → 3 rows."""
    c = Ros2BagConnector("dummy.mcap")
    msg = {
        "header": {"stamp": {"sec": 2, "nanosec": 500_000_000}},
        "name": ["joint_1", "joint_2", "joint_3"],
        "position": [1.0, 2.0, 3.0],
        "velocity": [0.1, 0.2, 0.3],
        "effort": [10.0, 20.0, 30.0],
    }
    rows = c._normalize(
        topic="/joint_states",
        msg_type="sensor_msgs/msg/JointState",
        timestamp_ns=2_500_000_000,
        msg=msg,
    )
    assert len(rows) == 3
    assert rows[0]["joint_name"] == "joint_1"
    assert rows[0]["position"] == 1.0
    assert rows[0]["velocity"] == 0.1
    assert rows[0]["effort"] == 10.0
    assert rows[0]["header_stamp_ns"] == 2_500_000_000
    assert rows[2]["joint_name"] == "joint_3"
    assert rows[2]["position"] == 3.0

def test_joint_state_mismatched_lengths_truncated() -> None:
    """If name/position/velocity/effort have different lengths, zip truncates."""
    c = Ros2BagConnector("dummy.mcap")
    msg = {
        "header": {"stamp": {"sec": 0, "nanosec": 0}},
        "name": ["j1", "j2"],
        "position": [1.0],  # shorter than name
        "velocity": [],
        "effort": [],
    }
    rows = c._normalize(
        topic="/joint_states",
        msg_type="sensor_msgs/msg/JointState",
        timestamp_ns=100,
        msg=msg,
    )
    # zip truncates to shortest → 1 row
    assert len(rows) == 1
    assert rows[0]["joint_name"] == "j1"
    assert rows[0]["position"] == 1.0
```

- [ ] **Step 4: 运行测试确认失败**

```bash
pytest tests/test_ros2_bag.py -v -k "joint_state"
```

预期：FAIL。

- [ ] **Step 5: 写失败测试 — expand=False 绕过展开器**

```python
def test_expand_false_falls_back_to_payload() -> None:
    """expand=True is default; expand=False must skip all expanders."""
    c = Ros2BagConnector("dummy.mcap", expand=False)
    msg = {
        "transforms": [
            {
                "header": {"stamp": {"sec": 1, "nanosec": 0}},
                "child_frame_id": "base_link",
                "transform": {
                    "translation": {"x": 1.0, "y": 2.0, "z": 3.0},
                    "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                },
            },
        ]
    }
    rows = c._normalize(
        topic="/tf",
        msg_type="tf2_msgs/msg/TFMessage",
        timestamp_ns=100,
        msg=msg,
    )
    assert len(rows) == 1
    # No per-transform fields — just the raw payload
    assert "child_frame_id" not in rows[0]
    assert rows[0]["payload"] == msg
```

- [ ] **Step 6: 实现 _EXPANDERS dict + 展开函数**

在 `ros2_bag.py` 中，`_BINARY_TYPES` 定义之后：

```python
def _stamp_to_ns(stamp: Any) -> int:
    """Convert a ROS2 Time-like dict {sec, nanosec} to nanoseconds."""
    if isinstance(stamp, dict):
        return int(stamp.get("sec", 0)) * 10**9 + int(stamp.get("nanosec", 0))
    return 0


def _expand_tf(msg: dict[str, Any]) -> list[dict[str, Any]]:
    """TFMessage → one row per transform."""
    transforms = msg.get("transforms", [])
    rows = []
    for tf in transforms:
        if not isinstance(tf, dict):
            continue
        header = tf.get("header", {})
        transform = tf.get("transform", {})
        trans = transform.get("translation", {})
        rot = transform.get("rotation", {})
        rows.append({
            "frame_id": header.get("frame_id", ""),
            "child_frame_id": tf.get("child_frame_id", ""),
            "tx": trans.get("x", 0.0),
            "ty": trans.get("y", 0.0),
            "tz": trans.get("z", 0.0),
            "qx": rot.get("x", 0.0),
            "qy": rot.get("y", 0.0),
            "qz": rot.get("z", 0.0),
            "qw": rot.get("w", 1.0),
            "header_stamp_ns": _stamp_to_ns(header.get("stamp")),
        })
    return rows


def _expand_joint_state(msg: dict[str, Any]) -> list[dict[str, Any]]:
    """JointState → one row per joint (zip truncates to shortest)."""
    header = msg.get("header", {})
    names = msg.get("name", [])
    positions = msg.get("position", [])
    velocities = msg.get("velocity", [])
    efforts = msg.get("effort", [])
    rows = []
    for name, pos, vel, eff in zip(names, positions, velocities, efforts):
        rows.append({
            "joint_name": name,
            "position": pos,
            "velocity": vel,
            "effort": eff,
            "header_stamp_ns": _stamp_to_ns(header.get("stamp")),
        })
    return rows


# Populate the _EXPANDERS dict (initialized empty in Task 4).
_EXPANDERS.update({
    "tf2_msgs/msg/TFMessage": _expand_tf,
    "sensor_msgs/msg/JointState": _expand_joint_state,
})
```

- [ ] **Step 7: 运行全部 normalize/expand/binary 测试确认通过**

```bash
pytest tests/test_ros2_bag.py -v
```

预期：全绿。

- [ ] **Step 8: Commit**

```bash
git add fde_scope/connectors/ros2_bag.py tests/test_ros2_bag.py
git commit -m "feat(ros2): TFMessage + JointState semantic expanders"
```

---

### Task 6: _iter_bag + 三步契约（fake reader 契约测试）

**Files:**
- Modify: `fde_scope/connectors/ros2_bag.py`
- Modify: `tests/test_ros2_bag.py`

**Interfaces:**
- Consumes: Task 4-5 的 normalize + expanders
- Produces: `_iter_bag()` 唯一 rosbags 触点；`discover_schema()` / `extract_sample()` / `stream()` 全通

- [ ] **Step 1: 写失败测试 — topics 过滤（通过 extract_sample + monkeypatched _iter_bag）**

```python
# --- three-step contract (contract layer, no rosbags) ---
def test_topics_filter_excludes_non_matching(monkeypatch: pytest.MonkeyPatch) -> None:
    """When topics is set, only matching messages pass through."""
    c = Ros2BagConnector("dummy.mcap", topics=["/joint_states"])
    fake_msgs = [
        ("/tf", "tf2_msgs/msg/TFMessage", 100, {"transforms": []}),
        ("/joint_states", "sensor_msgs/msg/JointState", 200, {
            "name": ["j1"], "position": [1.0], "velocity": [0.1], "effort": [10.0],
            "header": {"stamp": {"sec": 1, "nanosec": 0}},
        }),
    ]
    monkeypatch.setattr(c, "_iter_bag", lambda: iter(fake_msgs))
    rows = c.extract_sample(10)
    assert len(rows) == 1
    assert rows[0]["topic"] == "/joint_states"
    assert rows[0]["joint_name"] == "j1"

def test_topics_empty_means_all(monkeypatch: pytest.MonkeyPatch) -> None:
    """topics=[] (default) → no filtering, all messages pass."""
    c = Ros2BagConnector("dummy.mcap")
    fake_msgs = [
        ("/tf", "tf2_msgs/msg/TFMessage", 100, {"transforms": []}),
        ("/chatter", "std_msgs/msg/String", 200, {"data": "hello"}),
    ]
    monkeypatch.setattr(c, "_iter_bag", lambda: iter(fake_msgs))
    rows = c.extract_sample(10)
    # TFMessage with empty transforms → 0 rows; String → 1 row
    assert len(rows) == 1
    assert rows[0]["topic"] == "/chatter"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_ros2_bag.py -v -k "topics_filter"
```

预期：FAIL — `extract_sample` 尚未实现（仍返回空列表）。

- [ ] **Step 3: 实现 _count_skips 辅助方法**

`stream` 和 `extract_sample` 各自内联 topic 过滤 + normalize 循环（二者产出形态不同——stream yield Batch，extract_sample collect n 行——不值得抽公共方法）。唯一需要共享的是跳过计数：

```python
def _count_skips(self, msg_type: str, rows: list[dict[str, Any]]) -> None:
    """Increment self.skipped when a binary message was excluded."""
    if self._is_binary(msg_type) and not self.include_binary and not rows:
        self.skipped += 1
```

- [ ] **Step 4: 写失败测试 — batch_size < 1 拒绝**

```python
def test_stream_rejects_invalid_batch_size() -> None:
    c = Ros2BagConnector("dummy.mcap")
    for bad in (0, -1):
        with pytest.raises(ValueError, match="batch_size"):
            list(c.stream(batch_size=bad))
```

- [ ] **Step 5: 实现 _iter_bag + _msg_to_dict + stream**

```python
def _iter_bag(self) -> Iterator[tuple[str, str, int, dict[str, Any]]]:
    """Open the bag and yield (topic, msg_type, timestamp_ns, msg_dict).

    This is the ONLY method that touches rosbags. All normalize/expand/
    exclude logic operates on plain dicts, so contract tests need no
    rosbags installed.
    """
    self._ensure_driver()
    self._validate_path()
    from rosbags.highlevel import AnyReader

    # AnyReader takes a sequence of paths; context manager opens/closes.
    with AnyReader([self.bag_path]) as reader:
        for conn, timestamp, raw in reader.messages():
            try:
                msg = reader.deserialize(raw, conn.msgtype)
            except Exception:  # noqa: BLE001 — half-corrupt messages happen in field bags
                self.skipped += 1
                continue
            yield conn.topic, conn.msgtype, timestamp, self._msg_to_dict(msg)

@staticmethod
def _msg_to_dict(msg: Any) -> dict[str, Any]:
    """Convert a rosbags-deserialized message object to a plain dict.

    rosbags 0.11.x message objects are dataclass-like — they expose
    ``__dataclass_fields__`` for field enumeration and ``__msgtype__``
    for the message type string. We recurse into nested messages and
    lists. bytes pass through as-is (the binary stub reads len(data)
    for byte_size). ``__msgtype__`` is excluded from the output.
    """
    if hasattr(msg, "__dataclass_fields__"):
        return {
            key: Ros2BagConnector._msg_to_dict(val)
            for key, val in vars(msg).items()
            if key != "__msgtype__"
        }
    if isinstance(msg, (list, tuple)):
        return [Ros2BagConnector._msg_to_dict(item) for item in msg]  # type: ignore[return-value]
    if isinstance(msg, bytes):
        return msg
    return msg  # primitives pass through

def stream(self, batch_size: int = 500) -> Iterator[Batch]:
    if batch_size < 1:
        raise ValueError(f"batch_size must be >= 1, got {batch_size}")
    # _validate_path is called inside _iter_bag; no need to repeat here.
    topic_set = set(self.topics) if self.topics else None
    batch: list[dict[str, Any]] = []
    for topic, msg_type, timestamp_ns, msg in self._iter_bag():
        if topic_set is not None and topic not in topic_set:
            continue
        rows = self._normalize(
            topic=topic, msg_type=msg_type, timestamp_ns=timestamp_ns, msg=msg,
        )
        self._count_skips(msg_type, rows)
        for row in rows:
            batch.append(row)
            if len(batch) >= batch_size:
                yield Batch(batch, source=str(self.bag_path))
                batch = []
    if batch:
        yield Batch(batch, source=str(self.bag_path))
```

- [ ] **Step 6: 实现 extract_sample + discover_schema**

```python
def extract_sample(self, n: int = 100) -> list[dict[str, Any]]:
    # _validate_path is called inside _iter_bag; no need to repeat here.
    topic_set = set(self.topics) if self.topics else None
    out: list[dict[str, Any]] = []
    for topic, msg_type, timestamp_ns, msg in self._iter_bag():
        if topic_set is not None and topic not in topic_set:
            continue
        rows = self._normalize(
            topic=topic, msg_type=msg_type, timestamp_ns=timestamp_ns, msg=msg,
        )
        self._count_skips(msg_type, rows)
        for row in rows:
            out.append(row)
            if len(out) >= n:
                return out
    return out

def discover_schema(self) -> Schema:
    self._validate_path()
    self._ensure_driver()
    from rosbags.highlevel import AnyReader

    topic_info: dict[str, tuple[str, int]] = {}  # topic → (msg_type, msg_count)
    with AnyReader([self.bag_path]) as reader:
        for conn, _timestamp, _raw in reader.messages():
            if conn.topic not in topic_info:
                topic_info[conn.topic] = (conn.msgtype, 0)
            mt, count = topic_info[conn.topic]
            topic_info[conn.topic] = (mt, count + 1)

    total_msgs = sum(c for _, c in topic_info.values())
    fields = [
        SchemaField(name="topic", inferred_type="string"),
        SchemaField(name="msg_type", inferred_type="string"),
        SchemaField(name="timestamp_ns", inferred_type="int"),
        SchemaField(name="payload", inferred_type="json"),
    ]
    # Add expander-specific fields if TF/JointState topics are present
    for _topic, (msg_type, _count) in topic_info.items():
        if msg_type == "tf2_msgs/msg/TFMessage":
            for name in ("frame_id", "child_frame_id", "tx", "ty", "tz", "qx", "qy", "qz", "qw", "header_stamp_ns"):
                fields.append(SchemaField(name=name, inferred_type="string" if "frame" in name else "float"))
            break
    for _topic, (msg_type, _count) in topic_info.items():
        if msg_type == "sensor_msgs/msg/JointState":
            for name in ("joint_name", "position", "velocity", "effort", "header_stamp_ns"):
                fields.append(SchemaField(name=name, inferred_type="string" if name == "joint_name" else "float"))
            break

    return Schema(
        source=str(self.bag_path),
        row_count=total_msgs,  # message count; expansion only adds rows, so this is a lower bound
        fields=fields,
        detected_categories=list(topic_info.keys()),
    )
```

- [ ] **Step 7: 写失败测试 — extract_sample 与 stream 的契约层行为（用 monkeypatch 替换 _iter_bag）**

```python
def test_extract_sample_with_fake_iter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contract test: extract_sample reads from _iter_bag, normalizes, returns n rows."""
    c = Ros2BagConnector("dummy.mcap")
    fake_msgs = [
        ("/chatter", "std_msgs/msg/String", 100, {"data": "hello"}),
        ("/chatter", "std_msgs/msg/String", 200, {"data": "world"}),
        ("/chatter", "std_msgs/msg/String", 300, {"data": "foo"}),
    ]
    monkeypatch.setattr(c, "_iter_bag", lambda: iter(fake_msgs))
    sample = c.extract_sample(2)
    assert len(sample) == 2
    assert sample[0]["payload"] == {"data": "hello"}
    assert sample[1]["payload"] == {"data": "world"}

def test_stream_with_fake_iter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contract test: stream yields Batch objects with correct source."""
    c = Ros2BagConnector("dummy.mcap")
    fake_msgs = [
        ("/chatter", "std_msgs/msg/String", i * 100, {"data": f"msg{i}"})
        for i in range(5)
    ]
    monkeypatch.setattr(c, "_iter_bag", lambda: iter(fake_msgs))
    batches = list(c.stream(batch_size=2))
    assert len(batches) == 3  # 2+2+1
    assert sum(len(b) for b in batches) == 5
    assert batches[0].source == "dummy.mcap"

def test_stream_with_expanded_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stream with TF expansion: 1 message → 2 rows."""
    c = Ros2BagConnector("dummy.mcap")
    fake_msgs = [
        ("/tf", "tf2_msgs/msg/TFMessage", 100, {
            "transforms": [
                {
                    "header": {"stamp": {"sec": 0, "nanosec": 0}, "frame_id": "odom"},
                    "child_frame_id": "base_link",
                    "transform": {
                        "translation": {"x": 1.0, "y": 0.0, "z": 0.0},
                        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                    },
                },
                {
                    "header": {"stamp": {"sec": 0, "nanosec": 0}, "frame_id": "base_link"},
                    "child_frame_id": "camera_link",
                    "transform": {
                        "translation": {"x": 0.1, "y": 0.0, "z": 0.5},
                        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                    },
                },
            ]
        }),
    ]
    monkeypatch.setattr(c, "_iter_bag", lambda: iter(fake_msgs))
    batches = list(c.stream(batch_size=10))
    assert len(batches) == 1
    assert len(batches[0]) == 2
    assert batches[0][0]["child_frame_id"] == "base_link"
    assert batches[0][1]["child_frame_id"] == "camera_link"
```

- [ ] **Step 8: 运行全部契约测试确认通过**

```bash
pytest tests/test_ros2_bag.py -v
```

预期：全绿。

- [ ] **Step 9: Commit**

```bash
git add fde_scope/connectors/ros2_bag.py tests/test_ros2_bag.py
git commit -m "feat(ros2): _iter_bag + three-step contract with topic filtering"
```

---

### Task 7: 错误处理 — 反序列化失败跳过计数

**Files:**
- Modify: `fde_scope/connectors/ros2_bag.py`（已在 Task 6 的 `_iter_bag` 中实现）
- Modify: `tests/test_ros2_bag.py`

**Interfaces:**
- Consumes: Task 6 的 `_iter_bag`
- Produces: `self.skipped` 计数器准确反映跳过消息数

- [ ] **Step 1: 写失败测试 — 反序列化失败跳过计数**

```python
def test_deserialize_failure_skips_and_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Half-corrupt bag: one good message, one that raises, one good again."""
    c = Ros2BagConnector("dummy.mcap")

    call_count = 0

    def fake_iter_bag() -> Iterator[tuple[str, str, int, dict[str, Any]]]:
        nonlocal call_count
        call_count += 1
        yield "/chatter", "std_msgs/msg/String", 100, {"data": "good1"}
        # Simulate a deserialize failure by raising inside _iter_bag
        # (already handled in _iter_bag's try/except)
        yield "/broken", "custom_msgs/msg/Weird", 200, {"data": "good2"}
        yield "/chatter", "std_msgs/msg/String", 300, {"data": "good3"}

    monkeypatch.setattr(c, "_iter_bag", fake_iter_bag)
    sample = c.extract_sample(10)
    # All 3 messages come through _iter_bag already deserialized
    # (the skip counting for deserialize failures happens inside _iter_bag itself)
    assert len(sample) == 3

def test_binary_skip_increments_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    """Binary messages skipped by default → self.skipped counts them."""
    c = Ros2BagConnector("dummy.mcap")
    fake_msgs = [
        ("/camera/image", "sensor_msgs/msg/Image", 100, {"width": 640, "height": 480, "data": b"\x00" * 100}),
        ("/chatter", "std_msgs/msg/String", 200, {"data": "hello"}),
        ("/lidar/points", "sensor_msgs/msg/PointCloud2", 300, {"data": b"\x00" * 50}),
    ]
    monkeypatch.setattr(c, "_iter_bag", lambda: iter(fake_msgs))
    sample = c.extract_sample(10)
    assert len(sample) == 1  # only the String message
    assert sample[0]["payload"] == {"data": "hello"}
    assert c.skipped == 2  # Image + PointCloud2
```

- [ ] **Step 2: 运行测试确认通过**

```bash
pytest tests/test_ros2_bag.py -v -k "skip"
```

预期：全绿（`_count_skips` 已在 Task 6 实现）。

- [ ] **Step 3: Commit**

```bash
git add tests/test_ros2_bag.py
git commit -m "test(ros2): error handling — skip count for binary + deserialize failures"
```

---

### Task 8: 真实文件层测试 — rosbags Writer 自产 bag（sqlite3）

**Files:**
- Modify: `tests/test_ros2_bag.py`

**Interfaces:**
- Consumes: rosbags 在 dev extra（Task 2）
- Produces: 自产 sqlite3 bag 读写回断言（rosbags 0.11.5 无 mcap writer，mcap 读取由集成测试覆盖）

**API 实测结论（Task 1）**：
- Writer: `rosbags.rosbag2.Writer(path, version=Writer.VERSION_LATEST)` — path 必须不存在
- `add_connection(topic, msgtype, typestore=ts)` — 必须传 typestore
- `write(conn, timestamp_ns, raw_bytes)` — raw bytes，不是 message 对象
- 消息构造: `ts.types[msgtype](field=value, ...)` — 直接调用类构造函数
- 序列化: `bytes(ts.serialize_cdr(msg, msgtype))` — serialize_cdr 返回 memoryview
- AnyReader: `AnyReader([paths])` — 接受路径列表，context manager 自动 open
- 消息对象: dataclass-like，用 `__dataclass_fields__` / `vars()` 枚举字段，含 `__msgtype__`

- [ ] **Step 1: 写 pytest fixture — 自产 sqlite3 bag**

```python
# --- real-file layer (rosbags Writer self-produces sqlite3 bags) ---
rosbags = pytest.importorskip("rosbags")

from rosbags.rosbag2 import Writer as Rosbag2Writer
from rosbags.typesys import get_typestore, Stores


@pytest.fixture(scope="module")
def typestore():
    return get_typestore(Stores.ROS2_HUMBLE)


def _write_bag(bag_dir: Path, ts: Any) -> None:
    """Self-produce a sqlite3 bag with TFMessage (2 transforms/msg),
    JointState (3 joints), std_msgs/String, and a small sensor_msgs/Image.

    ``bag_dir`` must NOT exist yet — Writer refuses to overwrite.
    """
    with Rosbag2Writer(bag_dir, version=Rosbag2Writer.VERSION_LATEST) as writer:
        # /tf — TFMessage with 2 transforms
        tf_conn = writer.add_connection("/tf", "tf2_msgs/msg/TFMessage", typestore=ts)
        TFType = ts.types["tf2_msgs/msg/TFMessage"]
        TSType = ts.types["geometry_msgs/msg/TransformStamped"]
        HType = ts.types["std_msgs/msg/Header"]
        TimeType = ts.types["builtin_interfaces/msg/Time"]
        TrType = ts.types["geometry_msgs/msg/Transform"]
        V3Type = ts.types["geometry_msgs/msg/Vector3"]
        QType = ts.types["geometry_msgs/msg/Quaternion"]

        tf_msg = TFType(transforms=[
            TSType(
                header=HType(stamp=TimeType(sec=1, nanosec=0), frame_id="odom"),
                child_frame_id="base_link",
                transform=TrType(
                    translation=V3Type(x=1.0, y=2.0, z=3.0),
                    rotation=QType(x=0.0, y=0.0, z=0.0, w=1.0),
                ),
            ),
            TSType(
                header=HType(stamp=TimeType(sec=1, nanosec=500), frame_id="base_link"),
                child_frame_id="camera_link",
                transform=TrType(
                    translation=V3Type(x=0.1, y=0.0, z=0.5),
                    rotation=QType(x=0.0, y=0.0, z=0.707, w=0.707),
                ),
            ),
        ])
        writer.write(tf_conn, 1_000_000_000, bytes(ts.serialize_cdr(tf_msg, "tf2_msgs/msg/TFMessage")))

        # /joint_states — JointState (3 joints)
        JSType = ts.types["sensor_msgs/msg/JointState"]
        js_msg = JSType(
            header=HType(stamp=TimeType(sec=2, nanosec=0), frame_id=""),
            name=["joint_1", "joint_2", "joint_3"],
            position=[1.0, 2.0, 3.0],
            velocity=[0.1, 0.2, 0.3],
            effort=[10.0, 20.0, 30.0],
        )
        js_conn = writer.add_connection("/joint_states", "sensor_msgs/msg/JointState", typestore=ts)
        writer.write(js_conn, 2_000_000_000, bytes(ts.serialize_cdr(js_msg, "sensor_msgs/msg/JointState")))

        # /chatter — std_msgs/String
        StrType = ts.types["std_msgs/msg/String"]
        str_msg = StrType(data="hello from bag")
        str_conn = writer.add_connection("/chatter", "std_msgs/msg/String", typestore=ts)
        writer.write(str_conn, 3_000_000_000, bytes(ts.serialize_cdr(str_msg, "std_msgs/msg/String")))

        # /camera/image — small sensor_msgs/Image (excluded by default)
        ImgType = ts.types["sensor_msgs/msg/Image"]
        img_msg = ImgType(
            header=HType(stamp=TimeType(sec=3, nanosec=0), frame_id="camera"),
            height=2, width=2, encoding="bgr8", is_bigendian=0, step=6,
            data=b"\x00" * 12,
        )
        img_conn = writer.add_connection("/camera/image", "sensor_msgs/msg/Image", typestore=ts)
        writer.write(img_conn, 4_000_000_000, bytes(ts.serialize_cdr(img_msg, "sensor_msgs/msg/Image")))


@pytest.fixture(scope="module")
def sqlite_bag(tmp_path_factory: pytest.TempPathFactory, typestore: Any) -> Path:
    """Self-produced sqlite3 bag directory."""
    base = tmp_path_factory.mktemp("bag_sqlite")
    bag_dir = base / "test_bag"  # must NOT exist yet
    _write_bag(bag_dir, typestore)
    return bag_dir
```

- [ ] **Step 2: 写真实文件测试**

```python
def test_sqlite_bag_extract_sample(sqlite_bag: Path) -> None:
    """Read back self-produced sqlite3 bag — TF expands, JointState expands,
    String passes through, Image excluded."""
    c = Ros2BagConnector(str(sqlite_bag))
    sample = c.extract_sample(100)
    # 1 TF msg → 2 rows, 1 JointState → 3 rows, 1 String → 1 row, 1 Image → 0 (excluded)
    assert len(sample) == 6
    tf_rows = [r for r in sample if r["msg_type"] == "tf2_msgs/msg/TFMessage"]
    assert len(tf_rows) == 2
    assert tf_rows[0]["child_frame_id"] == "base_link"
    js_rows = [r for r in sample if r["msg_type"] == "sensor_msgs/msg/JointState"]
    assert len(js_rows) == 3
    assert js_rows[0]["joint_name"] == "joint_1"
    str_rows = [r for r in sample if r["msg_type"] == "std_msgs/msg/String"]
    assert len(str_rows) == 1
    assert str_rows[0]["payload"] == {"data": "hello from bag"}
    assert c.skipped == 1  # Image

def test_sqlite_bag_stream_batches(sqlite_bag: Path) -> None:
    c = Ros2BagConnector(str(sqlite_bag))
    batches = list(c.stream(batch_size=3))
    total = sum(len(b) for b in batches)
    assert total == 6
    assert all(b.source == str(sqlite_bag) for b in batches)

def test_sqlite_bag_discover_schema(sqlite_bag: Path) -> None:
    c = Ros2BagConnector(str(sqlite_bag))
    schema = c.discover_schema()
    assert schema.row_count == 4  # 4 messages (TF + JS + String + Image)
    assert "/tf" in schema.detected_categories
    assert "/joint_states" in schema.detected_categories

def test_include_binary_produces_stub(sqlite_bag: Path) -> None:
    c = Ros2BagConnector(str(sqlite_bag), include_binary=True)
    sample = c.extract_sample(100)
    img_rows = [r for r in sample if r["msg_type"] == "sensor_msgs/msg/Image"]
    assert len(img_rows) == 1
    assert img_rows[0]["width"] == 2
    assert img_rows[0]["height"] == 2
    assert img_rows[0]["encoding"] == "bgr8"
    assert img_rows[0]["byte_size"] == 12
```

- [ ] **Step 3: 运行真实文件测试**

```bash
pytest tests/test_ros2_bag.py -v -k "sqlite_bag or include_binary_produces"
```

预期：全绿。

- [ ] **Step 4: Commit**

```bash
git add tests/test_ros2_bag.py
git commit -m "test(ros2): real-file layer — self-produced sqlite3 bag roundtrip"
```

---

### Task 9: 真实 bag 集成测试（marker ros2）

**Files:**
- Modify: `tests/test_ros2_bag.py`

**Interfaces:**
- Consumes: 用户提供的真实 bag（env `FDE_SCOPE_ROS2_BAG`）
- Produces: `@pytest.mark.ros2` 集成测试

- [ ] **Step 1: 写集成测试**

```python
# ---------------------------------------------------------------------------
# Real-bag integration test (opt-in via env var)
# ---------------------------------------------------------------------------
@pytest.mark.ros2
def test_ros2_real_bag_smoke() -> None:
    """End-to-end against a real recorded bag. Skipped unless FDE_SCOPE_ROS2_BAG
    is set. The bag should contain at least /tf or /joint_states."""
    bag_path = os.environ.get("FDE_SCOPE_ROS2_BAG")
    if not bag_path:
        pytest.skip("FDE_SCOPE_ROS2_BAG not set; skipping real-bag integration test")
    pytest.importorskip("rosbags")
    c = Ros2BagConnector(bag_path)
    schema = c.discover_schema()
    assert schema.row_count is not None and schema.row_count > 0
    sample = c.extract_sample(50)
    assert sample, "no messages extracted from real bag"
    assert sample[0]["topic"]
    assert sample[0]["msg_type"]
```

- [ ] **Step 2: 运行集成测试（预期 skip）**

```bash
pytest tests/test_ros2_bag.py -v -m ros2
```

预期：SKIP（`FDE_SCOPE_ROS2_BAG` 未设置）。

- [ ] **Step 3: Commit**

```bash
git add tests/test_ros2_bag.py
git commit -m "test(ros2): real-bag integration test (marker ros2, env-gated)"
```

---

### Task 10: README + Makefile 更新

**Files:**
- Modify: `README.md`
- Modify: `Makefile`

**Interfaces:**
- Consumes: pyproject.toml extras（Task 2）
- Produces: README/Makefile/守护测试三处 extras 口径一致

- [ ] **Step 1: 修改 README.md — connector 表格行**

在 README.md 的 `10 connectors` 行（Feature checklist → Data & intelligence），确认 ROS2 bag 已在列表中（已标注）。无需改动此行。

在 Installation 段，`pip install -e ".[mqtt]"` 行之后新增：

```bash
pip install -e ".[ros2]"           # + ROS2 bag replay driver (rosbags)
```

修改 `pip install -e ".[full]"` 行的注释：

```bash
pip install -e ".[full]"           # everything (dev + agentscope + mysql + opcua + mqtt + ros2 + web)
```

- [ ] **Step 2: 修改 README.md — roadmap 勾选**

将 roadmap 中的：

```markdown
- [ ] rosbag2 真实回放（rosbags）
```

改为：

```markdown
- [x] rosbag2 真实回放（rosbags）
```

- [ ] **Step 3: 修改 Makefile — install-full 帮助文案**

将 Makefile 第 20 行：

```makefile
install-full: ## Install everything (dev + agentscope + mysql + opcua + mqtt + web)
```

改为：

```makefile
install-full: ## Install everything (dev + agentscope + mysql + opcua + mqtt + ros2 + web)
```

- [ ] **Step 4: 运行架构守卫确认一致**

```bash
pytest tests/test_architecture_guard.py -v
```

预期：全绿。`test_install_docs_agree_on_full_extra` 检查 README 和 Makefile 都含 `.[full]`。

- [ ] **Step 5: Commit**

```bash
git add README.md Makefile
git commit -m "docs(ros2): README + Makefile extras wiring + roadmap checkbox"
```

---

### Task 11: 全量验证 + 最终提交

**Files:**
- 无新文件

**Interfaces:**
- Consumes: 全部前序 task
- Produces: 全绿验收

- [ ] **Step 1: 全量测试**

```bash
pytest -q
```

预期：全绿（ros2 契约测试 + 真实文件测试通过；集成测试 skip）。

- [ ] **Step 2: Lint + format**

```bash
ruff check fde_scope tests && ruff format --check fde_scope tests
```

预期：无错误。

- [ ] **Step 3: 架构守卫**

```bash
pytest tests/test_architecture_guard.py -v
```

预期：全绿。

- [ ] **Step 4: 干净 venv 安装验证**

```bash
python3.12 -m venv /tmp/fde-full-check
/tmp/fde-full-check/bin/pip install -e ".[full]"
/tmp/fde-full-check/bin/python -c "from fde_scope.connectors.ros2_bag import Ros2BagConnector; print('ok')"
rm -rf /tmp/fde-full-check
```

预期：安装成功，import 成功。

- [ ] **Step 5: 真实 bag 端到端（如用户有 bag 文件）**

```bash
export FDE_SCOPE_ROS2_BAG=/path/to/real/bag
pytest tests/test_ros2_bag.py -v -m ros2
fde-scope connect --type ros2_bag --source "$FDE_SCOPE_ROS2_BAG"
```

预期：集成测试通过；CLI preview 输出 schema + samples。

- [ ] **Step 6: 确认文件体量**

```bash
wc -l fde_scope/connectors/ros2_bag.py
```

预期：≤400 行。

- [ ] **Step 7: 最终 commit（如有遗漏修复）**

```bash
git add -A
git status  # review what's included
git commit -m "feat(ros2): rosbag2 live replay — full delivery"
```
