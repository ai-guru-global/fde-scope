# FDE Scope 商业化差距分析

> 调研日期：2026-09-27。基于全库代码与文档只读调研，每条结论附证据路径。
> 修复状态见各项末尾标注；路线图见 `docs/commercialization-roadmap.md`。

## 总判断

**这是"一个有真实引擎的 showroom"。**

- 引擎是真的：18 阶段状态机 + 10 个 gate 实时评估、连接器层、语料管线、runbook/移交包、eval——足以支撑真实交付。
- 展示层是 mock：`examples/seed_mock_engagements.py` 生成的十个"客户"engagement、reports、技能库案例全部是 illustrative 数据。
- 商业基础设施几乎为零：无鉴权、无多租户、无 license、无计费、无客户侧文档。

作为 **FDE 个人/团队自用工具或咨询交付加速器**，已接近可收费；作为**卖给企业的软件产品**，差距集中在安全边界、合规证据与商务闭环。

## 阻塞级差距（B 类：不解决过不了企业采购/安全评审）

### B1. Web 控制台零鉴权（最致命）

`fde_scope/web/app.py` 全部 36 条路由无任何认证授权：创建 engagement（app.py:107）、推进状态机（app.py:138）、文件上传（app.py:249）、skill 发布——任何能访问端口的人都能操作客户项目。默认绑 `127.0.0.1` 是唯一防线，`--host 0.0.0.0` 即失守；Form 端点无 CSRF 防护。全库无 APIKeyHeader/JWT/session。

**修复状态**：P0 已修复（2026-09-28），见 `docs/commercialization-roadmap.md`。

### B2. 无多租户/多用户/RBAC

`deploy/tenant_manager.py` 的 "tenant" 只是 AgentScope 部署配置名，不是 SaaS 租户隔离。Web/CLI 层所有 engagement 共享单一数据根（`fde_scope/paths.py`），无 user 模型、无 workspace 隔离、无 RBAC。

### B3. 本地 JSON 持久化，无并发与可靠性保障

所有状态在 `.fde_scope/engagements/*.json`（`fde_scope/web/deps.py:36-60`）。`fsutil.atomic_write_text` 防半写，但无锁（并发写互相覆盖）、无备份/恢复、无 schema 迁移机制；`paths.py` 的 CWD fallback 意味着启动目录不同就读到不同数据。

**修复状态**：P0 部分修复（2026-09-28）——已加进程内按 engagement 分锁；P1 补充归档/删除 API
（archive 走原子写，删除需客户名确认）支撑 GDPR 删除权；仍无数据库/备份/迁移机制，见 `docs/commercialization-roadmap.md`。

### B4. 审计名不副实

UI 宣称 gate 例外"进入审计日志"（`fde_scope/web/i18n.py:254`），实际只有 engagement JSON 内的 `gate_records`；无 append-only 审计日志、无操作者字段、整个 `fde_scope` 包零 `import logging`。制造/医药客户要的"谁、何时、改了什么"给不出。

**修复状态**：P1 已修复主体（2026-09-28）：操作者/理由/证据哈希/审计导出已具备——force advance
必填 reason，operator/reason 进审计事件；handoff 与证据附件记录 sha256+UTC 时间戳；
`GET /api/engagements/{eid}/audit`（+`?format=md`）按 engagement 导出审计轨迹。
操作者仍是自报字段（无认证用户体系，待 B2）；证据为文件哈希留存而非数字签名。见 `docs/commercialization-roadmap.md`。

### B5. 客户案例 100% mock + 真实公司名风险

`examples/seed_mock_engagements.py`（约 2300 行）自述 "illustrative"：十个 engagement 全部脚本构造，gate 时间戳手填回填，corpus 样本是 `"语料样本 #i"` 占位。指标（MAE 12.4、OEE +2.1pp）全是编的数字。对外演示使用真实公司名（华晨宝马、广汽、蒙牛等）存在商标/虚假背书风险。

**修复状态**：✅ 已修复（2026-09-28，P4）——十个 engagement 全部更名为明显虚构的公司
（aurora-motors 奥罗拉汽车 / atlas-auto-alliance 亚特联汽车 / southbay-motors 南湾汽车 /
northern-auto 北疆汽车 / swift-ride 迅捷出行 / adnova 星澜科技 / teaverse 茶语万象 /
horizon-auto 宏途汽车 / riverbend-spirits 河湾酒业 / whitelake-dairy 白湖乳业），engagement id、
`reports/*` 生成物、README/GTM/PRODUCT/tests/web UI 引用全部同步；种子脚本头部加了显著
中英双语免责声明（"全部为虚构数据，与任何真实公司无关；仅用于产品演示"）；真实人物名
（罗永浩、邓丽君）一并替换；mock engagement 与技能库已重新播种。

## 重要差距（C 类：影响交付可信度与可维护性）

### C1. 宣称的连接器中 4 个是 stub

`connectors/salesforce.py:49,53`、`mes_isa95.py:113,129`、`historian.py:54,58` 全是 TODO 占位（只读 JSONL 文件），README Roadmap 自己承认。企业 POC 接真实系统是必经环节，此前 40% 连接器不可用。

**修复状态**：P3 已修复（2026-09-28）——四个 stub 连接器全部升级为真实 HTTP/REST 实现
（Zammad `/api/v1/tickets` + Token；Salesforce SOQL `query` + Bearer 只读；
MES work-orders REST；Historian 时序 samples REST）。统一三态模式：env 配置 →
真实 API，本地 `.jsonl` → 离线回放，未配置 → 空结果 + WARNING。MES/Historian 端点
按常见 REST 约定建模，客户现场用 `options.endpoint` 适配。见 `docs/commercialization-roadmap.md`。

### C2. 核心卖点"自改进飞轮"未闭环

`flywheel/retrain_scheduler.py:63` 明写 `"submitted (stub — no training backend wired)"`；飞轮引擎是 "rule-based v0"（`engine.py:3`）。线上 drift 检测无实现（mock 里的 PSI 告警是编的）。

**修复状态**：P5 已修复主体（2026-09-28）——新增 `fde_scope/flywheel/backends.py`
`TrainingBackend` Protocol + `HTTPTrainingBackend`（webhook 式训练服务，env 配置）
+ `NoopBackend`（如实标注），scheduler 走工厂不再有 "stub" 误导字样；
`tests/test_training_backend.py`（28 项）。未做：真实训练流水线本身（属于客户基础设施集成）。

### C3. `deploy --serve` 端到端未实测

README Roadmap 明确未勾选。依赖 Redis + 可达模型 + `.[agentscope]` extra；AgentScope 2.0 无 `Agent.stop` 的缺口使运行期稳定性未经生产验证。

**修复状态**：✅ 已修复（2026-09-28）——`deploy/e2e/` 验证基建（fake_model.py +
docker-compose.e2e.yml + smoke_test.sh）已本机实测 PASS（agentscope 2.0.8）；
发现真实缺口 `agentscope[service]` 不含 redis Python 包，已在 e2e README 前置条件标注。

### C4. 零可观测性

无结构化日志、无 metrics/tracing（sentry/prometheus/otel 零命中），只有 `/api/health` 返回静态 dict；`_all_engagements` 遇坏文件静默跳过（deps.py:59）。客户现场出问题没有排障抓手。

**修复状态**：P2 已修复（2026-09-28）：新增 `fde_scope/logutil.py`（`fde_scope.*` 命名空间 +
幂等 `configure_logging()`，`FDE_SCOPE_LOG_LEVEL` 控制级别，CLI/web 启动接线），关键路径
（engagement advance/rollback、corpus forge、deploy plan、connector 失败、audit 写失败）打点；
`/api/health` 返回真实检查（data_root/reports_dir 可写、LLM 已配置与否、engagements 计数，
degraded 仍 200）。metrics/tracing 未做，留待后续。

### C5. LLM 单一供应商 + 合规皮毛

只接 MiMo Token Plan（`fde_scope/llm.py`，urllib 手写 client，非标准 `api-key` 头），无 provider 抽象。PII 脱敏仅 4 条中国手机号/身份证正则（`config.py` PIIRules），无数据保留策略、无删除权支持，engagement JSON 明文存干系人姓名电话——对要过 GDPR/EU AI Act 审查的制造客户（恰恰是目标客群）是硬伤。

**修复状态**：P2 部分修复（2026-09-28）：`LLMClient` Protocol + `OpenAICompatClient`
（`FDE_SCOPE_LLM_BASE_URL/API_KEY/MODEL`，标准 Bearer 头）+ `get_llm_client()` 工厂，
全部调用方改走工厂，MiMo 保持默认；PII 规则新增 IPv4 与尊称人名模式（误报控制有测试）。
未做：数据保留策略、engagement JSON 字段级加密；删除权已由 P1 的 DELETE API 覆盖。

## 商业闭环缺口

- **MIT 裸奔**（`pyproject.toml:11`）：无 license key、无 seat 限制、无功能开关——即便客户愿意付费也没有"付费形态"；竞争者可自由 fork 转售。无 NOTICE、无第三方依赖 license 审计（paho-mqtt 的 EPL/EDL 需注意）。**修复状态**：✅ 已修复（2026-09-28，P4）——`fde_scope/license.py` 离线许可（HMAC 签名、三档 tier、过期降级、web 门控 pro+、CLI 签发工具）；根目录 `NOTICE` + `docs/license-audit.md` + 守护测试。
- **GTM 站无商务触点**：全站 CTA 只有 GitHub/文档链接，无定价、无联系表单、无 demo 预约（`GTM/index.html`）；PRODUCT.md:41 明确"无真实商务联系渠道"。**修复状态**：✅ 已修复（2026-09-28，P4）——三档定价区块（Pro 占位价标注"以商务洽谈为准"）+ mailto 联系区块 + 导航锚点 + 虚构数据免责声明；转化追踪未做（纯静态站定位保留）。
- **企业采购标准件全缺**：SSO/LDAP、安全白皮书、SLA 支持体系。
- **客户侧文档为零**：无最终用户手册、无 API 参考、无 onboarding 指南（`fde_scope/engagement/guided.py` 刚开始补引导模式）。**修复状态**：✅ 已修复（2026-09-28，P4）——新增 `docs/user-guide.md` / `docs/api-reference.md` / `docs/onboarding-customer.md`，README 文档区已索引；OpenAPI 自动导出未做，留待后续。
- **分发形态不成熟**：macOS 默认 ad-hoc 签名（README.md:683）；Android 是 debug keystore 的 WebView 壳（`android/build.sh`）；PawApp 依赖私有宿主 QwenPaw。
- **i18n 是手工双份 HTML**（`web/i18n.py` 手工对照表），加功能要翻译两遍，无法扩展第三语言。

## 供应链/依赖风险

- **AgentScope 版本窗口** `>=2.0.4.post1,<3`（pyproject.toml:49）：逐版本实测钉住（好），但上游三个月内改过一次权限语义（2.0.5 read-only fast path），每次发版都需重测，是持续维护税。
- **正面**：除 serve 路径的 Redis 外零外部服务依赖；LLM 全路径有确定性规则兜底——部署形态本身是加分项。

## 部署形态完成度

| 形态 | 状态 |
|---|---|
| PyPI 包 | 可用，0.1.0 Alpha |
| Web 控制台 | 功能完整（36 路由）但无鉴权，单机定位 |
| macOS DMG | universal2 + CI release 齐，默认 ad-hoc 签名 |
| PawApp 插件 | 18 路由，依赖私有宿主，面窄 |
| Android | debug 签名 WebView 壳，玩具级 |
| GTM 落地页 | 静态 HTML，无后端/表单 |

## 最短商业化路径

1. **P0 安全底线**：Web 层认证 + 审计日志 + 并发锁（B1/B3/B4）。
2. **明确部署边界**：落地数据库做多用户版，或明确定位"单机版 + 企业内网部署"。
3. **真实案例**：补齐 1-2 个 stub 连接器，跑通一个真实客户 POC，替换 mock 数据。
4. **商业模式**：双许可（开源核心 + 企业版功能开关）是最自然的选择。
