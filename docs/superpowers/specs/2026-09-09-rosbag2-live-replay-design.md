# rosbag2 真实回放设计（fde-scope）

> 日期：2026-09-09 · 状态：已批准（用户确认）
> 目标：把 `fde_scope/connectors/ros2_bag.py` 从骨架（`extract_sample` /
> `stream` 为 TODO）变成真实可交付：真实读取 bag 文件、三步契约全通、
> 标准消息类型语义展开、大二进制排除、两层测试，并钉入 `rosbags` 实测窗口。

## 1. 背景与范围

`Ros2BagConnector` 已注册（slug `ros2_bag`）但只有硬编码 schema 与两个
TODO 方法。骨架注释里列出的目标 topic（/tf、/joint_states、图像、抓取候选、
任务切换）是制造业/机器人 profile 的核心数据源——OPC UA、MQTT-Sparkplug
的真实 IO 已落地，ROS2 bag 是机器人侧最后一块。

驱动库事实（2026-09-09 查证）：[`rosbags`](https://ternaris.gitlab.io/rosbags/)
0.11.5（2026-08-19 发布），纯 Python、无第三方依赖、支持 Python ≥3.10，
自带 rosbag2 reader **和 writer**（零 ROS 安装）——writer 使「自产 bag 测试」
可行，比 MQTT 的真 broker 更省外部环境。

**范围**：bag 目录（`metadata.yaml` + `.db3`/`.mcap`）与裸 `.mcap` 文件的
真实读取；msg_type 键控语义展开；大二进制排除表；`[ros2]` extra 实测钉窗；
双层测试 + 交付时真实 bag 端到端实测。

**非目标**（防蔓延）：
- 实时 ROS2 DDS 订阅——bag 是离线制品，回放即读文件；
- `fde-scope bag` 新 CLI 子命令——`connect` 已能 preview schema + samples；
- web/pawapp 上传 bag——语料 forge 仍限 CSV ≤10 MiB；
- KPI 从 bag 直接计算——eval 层本期不动；
- 裸 `.db3`（无 metadata.yaml）——rosbags 不直接支持，报错指引转 mcap
  或补 metadata。

**不变量核对**：只读连接器——不触碰凭证（无网络认证）、不产生持久化写、
不改 gate/权限管线；connector registry 不新增 slug（守护测试的 registry
断言不变）。

## 2. 方案选择记录

| 方案 | 结论 |
|---|---|
| A. 单文件连接器 + msg_type 键控展开器 dict（复刻 MQTT 模式） | **采纳**：与已验收两轮的 opcua/mqtt 交付同构；单文件可控在 C1 红线（≤400 行）内；展开器将来膨胀再拆（接触即改善） |
| B. 拆 `connectors/ros2bag/` 子包（reader 适配层 + semantics/ 插件） | 否决：本期只有 2 个展开器 + 1 张排除表，结构先行 = YAGNI |
| C. A + `fde-scope bag inspect` 子命令 | 否决：新 surface 要 web/pawapp 三入口同步对齐，本期范围膨胀 |

用户确认的范围深度：**闭环 + 语义展开**（介于「纯 JSON 化」与「KPI 接线」之间）。
用户确认的验证标准：**自产 bag 常规测试 + 交付时真实录制 bag 端到端实测**
（对齐 MQTT 的「真 broker 实测」验收）。

## 3. 生产代码改动（全部在 `ros2_bag.py`）

1. **路径形态自适应**：`source` 为含 `metadata.yaml` 的目录（标准 bag）
   或 `.mcap` 单文件；二者皆非（含裸 `.db3`）→ 明确报错并给指引。
2. **`_ensure_driver` 错误信息** → `pip install 'fde-scope[ros2]'`
   （对齐 opcua/mysql/mqtt 的 extra 命名）。
3. **选项**（`options.get(...)` 风格）：
   - `topics: list[str]`（已有语义：空 = 全部）；
   - `expand: bool = True`——关闭后所有 msg_type 一律 payload JSON 兜底；
   - `include_binary: bool = False`——开启后大二进制类型输出元数据 stub 行。
4. **行形状**：所有行共有 `topic` / `msg_type` / `timestamp_ns`（bag 存储
   时间，ns 整数，JSON 安全）/ `payload`。展开器 dict（`msg_type → callable`，
   对齐 MQTT「一行一 metric」先例）：
   - `tf2_msgs/msg/TFMessage` → 每 transform 1 行：`frame_id`、
     `child_frame_id`、`tx/ty/tz`、`qx/qy/qz/qw`、`header_stamp_ns`；
   - `sensor_msgs/msg/JointState` → 每关节 1 行：`joint_name`、`position`、
     `velocity`、`effort`、`header_stamp_ns`；
   - 其他类型（含现场自定义 grasp/task 消息）→ payload JSON，msgdef
     内嵌即可解。
   行体量用 `topics` 过滤控制；`expand=False` 是全局逃生门。
5. **大二进制排除表**：`sensor_msgs/msg/Image`、
   `sensor_msgs/msg/CompressedImage`、`sensor_msgs/msg/PointCloud2`
   默认整条跳过（排除先于展开判断，`expand=False` 不影响排除）；
   `include_binary=True` 时输出**只含标量元数据**的行
   （width/height/encoding/format/fields + `byte_size`），绝不含 `data`
   数组。
6. **三步契约实现**：
   - `discover_schema()`：打开 bag 枚举 connections → 每 topic 的
     msg_type/msgcount、`row_count`（消息计数；展开只增行不减，故为下界）、
     展开字段并入 fields；
   - `extract_sample(n)`：前 n 行（展开后行计）；
   - `stream(batch_size)`：批次 yield（`Batch(source=bag 路径)`）；
     `batch_size < 1` → `ValueError`（MQTT 先例）。
7. **错误处理**：单条消息反序列化失败 → 跳过并计数
   （`self.skipped`），不炸整条流——现场 bag 常有半损坏消息；异常
   原样传播，不做静默空数据回退。
8. **IO/逻辑分离**：`_iter_bag()` 是唯一触碰 rosbags 的点，产出
   `(topic, msg_type, timestamp_ns, msg)` 平面元组；normalize/展开/排除
   逻辑只吃 dict——契约测试无需 rosbags。
9. **typestore**：rosbags 可用时构建默认 typestore 传入 reader，兼容
   内嵌 msgdef 与标准消息；**具体签名（`default_typestore` /
   `get_typestore(Stores.ROS2_HUMBLE)`）以实施第一步实测为准**。

## 4. 依赖与交付面改动

- **实施第一步（实测钉窗，对齐 agentscope B2/B5 文化）**：隔离 venv
  安装 rosbags，跑通「Writer 自产 bag → AnyReader 读回」scratch 脚本，
  确认 0.11.x 的 reader/writer/typestore 实际签名，再落 specifier
  （预期 `rosbags>=0.11,<0.12`，实测为准）。
- `pyproject.toml`：
  - 新增 extra `ros2 = ["rosbags>=0.11,<0.12"]`（以实测为准）；
  - `dev` extra 加入 `rosbags`（自产 bag 测试零外部服务，CI 常跑）；
  - `full` meta-extra 加入 `"fde-scope[ros2]"`；
  - `markers` 新增 `ros2: tests that require a real recorded bag (skipped unless FDE_SCOPE_ROS2_BAG is set)`。
- `README.md`：connector 表格行标注真实回放已可用（extra 名）；roadmap
  `- [ ] rosbag2 真实回放（rosbags）` 勾选；安装段加 `[ros2]`。
- `Makefile`：install-full 帮助文案提及 `ros2` extra（如有该行）。
- 架构守卫（extras 契约、`[full]` 一致性、registry）跑一遍确认。

## 5. 测试（双层 + 集成，仿 MQTT 模式）

**契约层**（不需要 rosbags，`tests/test_ros2_bag.py`）：注入假 reader /
dict 假消息，覆盖：normalize 基础字段、TF/JointState 展开计数与字段、
`expand=False` 兜底、排除表默认跳过、`include_binary` stub 行只含元数据、
`topics` 过滤、批次边界与 `batch_size<1`、反序列化失败跳过计数。

**真实文件层**（rosbags 在 dev extra，CI 永远跑；无则 skipif）：
fixture 用 rosbags Writer 自产 bag——TFMessage（2 transform/消息）、
JointState（3 关节）、`std_msgs/String`、小尺寸 `sensor_msgs/Image`
各一路；`.mcap` 与 sqlite3 两种存储格式各一份；经连接器读回断言
展开/排除/计数；`extract_sample` 与 `stream` 两路径都覆盖。

**真实 bag 集成层**：`@pytest.mark.ros2`，`FDE_SCOPE_ROS2_BAG` 指向
真实录制 bag 时才跑（未设置 skip）——交付实测入口。

## 6. 验收标准

1. 全量 `pytest` + `ruff check && ruff format --check` +
   `pytest tests/test_architecture_guard.py` 全绿；
2. 干净 venv `pip install -e ".[full]"` 成功；
3. 自产 bag 双格式（mcap/sqlite3）读写回断言全过（CI 内）；
4. 用户提供的真实 bag（含 /tf、/joint_states）端到端：
   `connect` preview → `corpus` 出报告（含 `--llm` 可选路径）；
5. README/Makefile/守护测试三处 extras 口径一致。

## 7. 参考实现先例

- `mqtt_sparkplug.py`：双模式 + normalize 管道 + `_ensure_driver`
  extra 指名 + 契约/真实两层测试（本轮直接复刻的结构模板）；
- `docs/superpowers/specs/2026-09-07-mqtt-sparkplug-live-design.md`：
  spec 结构与验收标准模板；
- `docs/architecture-model/remediation-plan.md` B2/B5：实测钉窗流程。
