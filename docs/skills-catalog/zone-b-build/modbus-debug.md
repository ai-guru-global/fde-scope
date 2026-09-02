# modbus-debug

> 状态：📦 可安装 · registry 真名 `leokemp223/embed-ai-tool@modbus-debug`（与建档名一致；低装机社区件，主题在 registry 中独有）· 类型：工具 · FDE 位点：Zone B · connect（产线设备联调）
> 安装：`npx skills add leokemp223/embed-ai-tool@modbus-debug --directory ~/.qoder/skills -y` · 装机量：491（skills.sh，2026-08-31 实测；调研清单记 493，以 registry 实时为准）· 详情：https://skills.sh/leokemp223/embed-ai-tool/modbus-debug

## 能做什么
Modbus RTU（串口）与 Modbus TCP（网络）的寄存器级通信调试工具：读写 Holding Registers / Input Registers / Coils / Discrete Inputs 四类点位，从站扫描（`--scan`）确认总线在线状态，持续监控寄存器值变化。核心脚本 `scripts/modbus_tool.py`，依赖 pymodbus + pyserial；RTU 需给端口/波特率/从站地址（如 `COM42` + 115200），TCP 需给 host/port/从站地址。属 embed-ai-tool 套件（24 个嵌入式 skill）成员，与 `serial-monitor`（烧录后抓串口日志）互补。

## 何时使用
- 产线设备联调：PLC/网关/仪表的寄存器读写验证、点位表核对（station_samples 类产线数据接入前的现场验证）
- 通信异常定位：从站无响应、报非法功能码、地址越界时，区分是链路问题还是从站能力问题

**不用于**：MQTT 等消息总线接入（→ [mqtt-development](mqtt-development.md)——MQTT 是消息总线，本页是寄存器级工业协议）；固件烧录后的原始串口日志抓取（套件内 serial-monitor 的活）。

## 新人上手
- **触发**：对 agent 说"用 modbus-debug 读 2 号从站 40001 起的 10 个保持寄存器，TCP 连 192.168.1.10:502"
- **第一步**：装完后先跑 `python scripts/modbus_tool.py --detect` 探测链路与从站，再按需 `--read` / `--write` / `--scan`（monitor 模式盯寄存器变化）
- **常见坑**：`--write` 直接动产线设备——先 `--read` 核对点位表再写，Coil/寄存器写错会触发设备误动作，现场操作必须遵循客户安全规程
- **常见坑**：返回 "illegal function" 不一定是链路故障，多是从站不支持该功能码（如只读仪表拒绝写操作），换只读操作验证从站是否在线

## 最佳实践
- 装前门禁：低装机社区件（491，未达主流件量级），先用 [skill-criticagent](../cross-cutting/skill-criticagent.md) 评估，结论回写本页
- 节奏固定：`--scan` 确认从站在线 → `--read` 核对点位 → 才考虑 `--write`；读写全程留记录进交付日志
- 连接失败/无响应分层排查：物理链路（端口/波特率）→ 从站地址 → 功能码/地址范围，别一上来改代码
- 监控模式只观察不写入，适合交付前的稳定性确认

## 项目应用位点
- Zone B `connect`（数据接入）：产线设备 Modbus 点位联调与验证
- station_samples 产线数据样例的现场点位表核对
- 制造业客户 air-gap 现场的寄存器级排障

## 相关
[mqtt-development](mqtt-development.md) · [attach-db](attach-db.md) · [read-file](read-file.md)

同主题兄弟条目（未单独立页）：`zhinkgit/embeddedskills@can`（CAN 总线，556 装机）、`zhaoxuya520/reverse-skill@ot-ics`（OT/ICS 协议分析，488 装机），主题相邻可关注。
