# MQTT-Sparkplug 真实 broker IO 设计（fde-scope）

> 日期：2026-09-07 · 状态：已批准（用户确认）
> 目标：把 `fde_scope/connectors/mqtt_sparkplug.py` 的 live broker 路径从
> "写了但没测"变成真实可交付：声明 extra、修复挂起 bug、补认证、两层测试
> 全覆盖，并在本机用真实 broker 实测一次。

## 1. 背景与范围

MQTT-Sparkplug connector 目前有两种模式：JSONL capture 回放（零依赖、已测、
green）与 live broker 订阅（`paho-mqtt`，`pragma: no cover`、未测）。live 路径
存在四个缺口：

- `paho-mqtt` 没有声明为 extra（`pyproject.toml` 无 `mqtt`），安装方式不可发现；
- `_stream_live` 的 `while True` + `queue.Empty: continue` 永不终止——对
  corpus forge 是挂起风险（`opcua`/`mysql` 的 stream 都是有界批次）；
- 无法认证（很多现场 broker 要求用户名/密码）；
- `connect`/`subscribe` 失败时没有 finally 清理，回调线程可能残留。

**范围**：仅真实 broker IO（连接/订阅/采集/认证）。Sparkplug B protobuf
解码不做，留在 roadmap（现有 JSON payload 路径继续工作）。不引入重连策略、
不引入 client_factory DI、不触碰权限管线（read-only connector，
AGENTS.md 危险区零接触）。

**凭证不变量**：认证信息只从环境变量读取
（`FDE_SCOPE_MQTT_USERNAME` / `FDE_SCOPE_MQTT_PASSWORD`），
不落入 manifest/report/日志（AGENTS.md #3）。

## 2. 方案选择记录

| 方案 | 结论 |
|---|---|
| A. 仿 opcua/mysql 两层测试：把 fake paho 模块塞进 `sys.modules`，不改公共面 | **采纳**：零新增依赖即可在 CI 全量覆盖 live 路径；与既有测试风格一致 |
| B. 引入 `client_factory` 可注入参数 | 否决：为测试改公共 API，YAGNI；A 已达成同样覆盖 |
| C. 只写 `@pytest.mark.mqtt` 门控真实测试 | 否决：CI 上跑不到，live 路径依旧裸奔 |

## 3. 生产代码改动（全部在 `mqtt_sparkplug.py`）

1. **`_ensure_driver` 错误信息** → `pip install 'fde-scope[mqtt]'`
   （与 opcua/mysql 的 extra 命名对齐）。
2. **`_apply_auth(client)`**（新私有方法）：读
   `FDE_SCOPE_MQTT_USERNAME` / `FDE_SCOPE_MQTT_PASSWORD`，
   各自仅在设置时应用（`username_pw_set`）。`_collect_live` 与
   `_stream_live` 在 connect 前调用。
3. **`_collect_live` 加固**：connect/subscribe/loop_start 包在 try 中，
   失败路径同样保证 `loop_stop` + `disconnect`，然后原样 re-raise
   （诚实传播，不做静默空数据回退）。
4. **`_stream_live` 修复（核心）**：新增 option `max_messages`
   （默认 `1000`，有界；`0` = 不设上限）。终止条件取先到者：
   累计收到 `max_messages` 条消息（按消息计，非 normalize 后的行），
   或连续 `timeout_seconds` 无新消息。两个条件都先产出尾部未满批次再退出；
   finally 保证清理。
5. **回调收敛**：两个几乎相同的 `on_message` 合并为 `_make_on_message`
   私有助手（collect 版 append 列表，stream 版 put 队列）。
6. **`import time` 上移**到模块顶部（当前 inline 在函数体内）。

`max_messages` 通过 `options.get("max_messages", 1000)` 进入 `__init__`，
与 `timeout_seconds` 等 option 同风格。

## 4. 交付面改动

- `pyproject.toml`：
  - 新增 extra `mqtt = ["paho-mqtt>=2.0,<3"]`（live 路径已用 VERSION2
    callback API，下限 2.0）；
  - `full` meta-extra 加入 `"fde-scope[mqtt]"`；
  - `[tool.pytest.ini_options] markers` 新增
    `mqtt: tests that require a real MQTT broker (skipped unless FDE_SCOPE_MQTT_URL is set)`。
- `README.md`：connectors 表格行标注 live 模式已可用（extra 名）；roadmap
  `- [ ] MQTT-Sparkplug 真实 broker IO（paho-mqtt）` 勾选。

架构守卫（`tests/test_architecture_guard.py` 的 extras 子集检查与
`.[full]` 一致性检查）不受影响，跑一遍确认。

## 5. 测试（两层，仿 opcua/mysql 模式）

**Mocked 层**（`tests/test_mqtt_connector.py` 扩展，monkeypatch 把
`paho.mqtt.client` 的 fake 模块塞进 `sys.modules`，`_FakeMqttClient`
只实现被用到的面：`CallbackAPIVersion` / `tls_set` / `username_pw_set` /
`connect` / `subscribe` / `loop_start` / `loop_stop` / `disconnect` /
`on_message` 可赋值）：

- `extract_sample` live 模式：注入 2 条消息 → 返回 normalize 后的行；
  结束后 `disconnect` 被调用；
- 截断：发 5 条、`n=3` → 只返回 3 行；
- `stream` 有界终止：`max_messages=3` + batch_size 2 → 两个批次
  （2+1 尾批），生成器自然结束不挂起；
- `stream` 消息不足：1 条 + batch_size 5 → 单条尾批；
- 认证：设置 env → `username_pw_set("u","p")` 被调用；只设其一 → 只应用
  那一个；都没设 → 不调用；
- TLS：`mqtts://` → `tls_set()` 被调用（`mqtt://` 不调）；
- driver 缺失：ImportError 信息含 `fde-scope[mqtt]`；
- connect 抛错 → 异常原样传播，finally 清理路径自身不崩；
- `timeout_seconds` 生效（collect）：fake 不投递消息、时间到 → 返回
  `[]` 正常退出；
- `timeout_seconds` 生效（stream）：无消息、`timeout_seconds` 到 →
  生成器退出不挂起（静默终止路径）。

**真实层**（`@pytest.mark.mqtt`，默认 skip）：

- gated by `FDE_SCOPE_MQTT_URL`（如 `mqtt://localhost:1883`）；
- 冒烟：`extract_sample(10)` 连真实 broker、订阅、收到 ≥1 行即过。

**本机实测（交付前一次性）**：`brew install mosquitto` → 起 broker 于
localhost:1883 → `mosquitto_pub` 发几条 Sparkplug B 风格 JSON 消息 →
`FDE_SCOPE_MQTT_URL=mqtt://localhost:1883 pytest -m mqtt` green → 停 broker。
（用户已批准本机安装与运行。）

## 6. 错误处理原则

- live 模式不做"失败返回空列表"的静默回退——错误原样抛给 FDE，
  由 FDE 决定改凭证/换主题/放弃；
- 所有资源（回调线程、socket）在 finally 中清理，异常路径不泄漏；
- JSONL 回放路径行为不变（现有 13 个测试全部保持 green）。

## 7. 明确不做

- Sparkplug B protobuf 解码（roadmap）；
- 自动重连 / 指数退避（现场由 supervisor 或未来 flywheel 负责）；
- `client_factory` 注入（方案 B 否决）；
- 写操作 / publish（connector 契约是 read-only 数据面）。
