# 客户现场 Onboarding 指南

> 面向交付方与客户方共同执行的首日/首周落地手册。
> 前置阅读：[`user-guide.md`](user-guide.md)（日常使用）、
> [`api-reference.md`](api-reference.md)（接口对接）。

## 1. 部署形态选择

| 形态 | 适用 | 前提 | 说明 |
|---|---|---|---|
| **单机桌面** | POC、单个工程师/客户经理使用 | Python ≥ 3.11；`pip install -e ".[web]"` | `fde-scope web` 默认绑 `127.0.0.1:8080`，无需认证即可用；macOS 另有双击即用的 DMG（同一控制台） |
| **内网服务器** | 客户团队多人共用、长期运行 | 一台内网 Linux/macOS 主机；Python ≥ 3.11 | **必须**先设 `FDE_SCOPE_API_TOKEN` 开启认证，再 `FDE_SCOPE_ALLOW_REMOTE=1 fde-scope web --host 0.0.0.0`；建议前面加反向代理做 HTTPS |
| **PawApp 插件** | 已部署 QwenPaw 桌面宿主的团队 | QwenPaw 宿主（私有软件） | 同一引擎、同一数据根的原生前端，18 条路由挂在 `/api/fde-scope` |

单机定位说明：当前版本**无多用户/RBAC**（见路线图 P5）。多人共用时以
「一台服务器 + 一个 token」为边界，操作者身份经 `operator` 字段自报进审计日志。

## 2. 安全基线清单（上线前逐项打勾）

- [ ] **设置 API token**：`export FDE_SCOPE_API_TOKEN="$(openssl rand -hex 32)"`。
      只放环境变量，不写进任何配置文件、脚本仓库或聊天记录。
- [ ] **仅受信网络暴露**：未设 token 前不要加 `FDE_SCOPE_ALLOW_REMOTE=1`；
      公网暴露暂不提供额外防护（HTTPS/SSO 见 P5）。
- [ ] **数据根目录权限**：确认数据根（`FDE_SCOPE_HOME` 或启动目录）下
      `.fde_scope/` 与 `reports/` 对运行账号可写、对无关账号不可读
      （`chmod 700` 级别；engagement JSON 明文含干系人姓名/电话）。
- [ ] **备份**：把 `.fde_scope/` + `reports/` 纳入每日备份
      （`tar czf fde-backup-$(date +%F).tgz .fde_scope/ reports/`），
      其中 `audit.jsonl` 是 append-only 审计轨迹，必须随备份保留。
- [ ] **审计保留策略**：删除 engagement（GDPR 删除权）不会删审计日志——
      这是有意设计，合规轨迹独立于客户数据生命周期；备份与保留策略要覆盖它。
- [ ] **日志级别**：生产用默认 `WARNING`；排障临时 `FDE_SCOPE_LOG_LEVEL=DEBUG`，
      排障后改回。凭据不会进日志，但 DEBUG 会输出 gate 评估细节。

## 3. 数据接入决策树

「客户能给什么」→ 对应连接器与 env 配置。所有连接器统一三态：
**env 齐配 → 真实 API；给本地 `.jsonl`/CSV → 离线回放；都没有 → 空结果 + WARNING**。

```
客户能提供什么？
├─ 一份导出的表格/工单 CSV
│   → CSV 连接器（零配置，冷启动首选）
│     fde-scope connect --type csv --source data/tickets.csv
│     Web 控制台 Corpus forge 直接上传（≤ 10 MiB）
├─ Zammad 工单系统
│   → export FDE_SCOPE_ZAMMAD_BASE_URL="https://support.example.com"
│     export FDE_SCOPE_ZAMMAD_API_TOKEN="..."
│     （GET /api/v1/tickets 分页拉取；缺一个变量即回退本地回放）
├─ Salesforce（CRM/Case）
│   → export FDE_SCOPE_SF_INSTANCE_URL="https://acme.my.salesforce.com"
│     export FDE_SCOPE_SF_ACCESS_TOKEN="..."   # 进程外获取的 access token，SOQL 只读
├─ MySQL 数据库
│   → pip install -e ".[mysql]"；--type mysql，--source 给 DSN
├─ MES（工单/质量/停机，ISA-95）
│   → export FDE_SCOPE_MES_BASE_URL=...  FDE_SCOPE_MES_API_TOKEN=...
│     （GET /api/v1/work-orders 约定；现场端点不同可用 options.endpoint 适配）
├─ Historian 时序库
│   → export FDE_SCOPE_HISTORIAN_BASE_URL=...  FDE_SCOPE_HISTORIAN_API_TOKEN=...
│     （GET /api/v1/samples?tag=X；支持 PI Web API 风格 {tag} 占位端点）
├─ PLC / 产线设备直读（OPC UA）
│   → pip install -e ".[opcua]"（asyncua 驱动）
├─ 设备遥测（MQTT-Sparkplug）
│   → pip install -e ".[mqtt]"（paho-mqtt，真 broker；也可 JSONL 回放）
├─ 机器人轨迹（ROS2 bag）
│   → pip install -e ".[ros2]"（rosbags 回放）
└─ 文档（PDF/Word/Excel/PPT）
    → documents 连接器；需 pip install -e ".[agentscope]"（延迟导入 agentscope.rag）
```

profile 选择：客服/工单类用 `ticket`（CSV/Zammad/Salesforce/MySQL），
工厂/机器人类用 `manufacturing`（OPC UA/MQTT/ROS2/MES/Historian）。

## 4. LLM 配置决策树

LLM **完全可选**：不配则语料合成、质量评分、runbook、引导起草全部走确定性规则路径，
流水线不中断。要 AI 增强时按下图选：

```
想用 LLM 增强（合成补盲 / AI 起草 context / runbook 起草 / LLM 评测）？
├─ 可出公网，接受按 token 计费
│   → MiMo Token Plan（默认路径）
│     export FDE_SCOPE_MIMO_API_KEY="tp-..."     # tp- 前缀，与 sk- 按量 key 不通用
│     # 可选覆盖：FDE_SCOPE_MIMO_BASE_URL / FDE_SCOPE_MIMO_MODEL（默认 mimo-v2.5-pro）
├─ 企业已有 OpenAI 兼容端点（内部网关 / DeepSeek / vLLM / ollama 本地模型）
│   → export FDE_SCOPE_LLM_BASE_URL="http://localhost:11434/v1"
│     export FDE_SCOPE_LLM_API_KEY="sk-..."      # 本地模型可填任意非空值
│     export FDE_SCOPE_LLM_MODEL="qwen3:14b"     # 缺省 gpt-4o-mini
│     （与 MiMo 同时配置时优先走这里）
└─ 数据不能出内网且没有本地模型
    → 不配任何 LLM env，纯规则兜底——功能完整可用，仅「AI 起草/合成」为规则版
```

验证：`curl localhost:8080/api/health` 看 `checks.llm.configured`。
显式依赖 LLM 的命令（`corpus --llm` 等）未配置时会 exit 2 并提示，不会静默失败。

## 5. 验收标准模板（POC 成功判据）

在 engagement 的 success_criteria 阶段把下列判据契约化（Web Context tab 或
`POST /api/engagements/{eid}/context` 写入，`success_criteria` gate 要求
**≥ 2 名 sponsor** 且每条可度量）：

**KPI 目标（示例，按 profile 调整）**

- [ ] ticket：意图准确率 ≥ ___、首响时间 P95 < ___ 分钟、升级率 ≤ ___
- [ ] manufacturing：OEE 提升 ≥ ___pp、抓取成功率 ≥ ___、碰撞/干预率 ≤ ___%
      （基线参照：OEE 世界级 0.85；抓取率 DexNet 基准 ~0.80）

**流程完备性**

- [ ] 适用 gate 全部通过且无未说明的 force 例外（`GET /api/engagements/{eid}/gates`
      全绿；审计日志中每条 force advance 都有 reason + operator）
- [ ] 移交包齐全且客户验收：runbook + eval 报告 + SLO + 培训材料，
      `handoff` 已带 `accept=true` 执行并留 `handoff.accepted` 审计事件
- [ ] FAT/SAT 签字扫描件等证据已附加（`GET .../evidence` 非空，sha256 入审计）
- [ ] 审计可导出：`GET /api/engagements/{eid}/audit/export` 产出 Markdown 报告
- [ ] SLO 已定义且告警路由到位（`slo` gate 通过）

**运维就绪**

- [ ] 备份脚本已跑通一次并验证可恢复
- [ ] `/api/health` 全部 `ok: true`
- [ ] 运维方已完成知识转移（Zone D 阶段 17）并能独立执行常用操作清单
      （见 `docs/user-guide.md`）

## 6. 常见现场情况

- **Air-gapped（气隙）现场**：安装包与依赖 wheel 需离线带入；LLM 只能选本地
  OpenAI 兼容端点或不启用；`air_gap` gate 会在 connect 阶段校验离线部署姿态。
- **多班次工厂**：manufacturing profile 下 `shift_handover` gate 要求数字交接
  日志 + 每班次 runbook；提前与客户排班负责人对齐。
- **德国/欧盟客户**：`works_council`（BetrVG §87 工会共决）与 `conformity`
  （CE / EU AI Act）gate 默认启用；签字扫描件走 evidence API 留存。
