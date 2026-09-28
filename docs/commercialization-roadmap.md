# FDE Scope 商业化路线图

> 配套文档：`docs/commercialization-gap-analysis.md`（差距证据全表）。
> 每个阶段独立可交付；完成后回到差距分析文档标注修复状态。

## P0 — 安全底线 ✅（2026-09-28 完成）

目标：堵住企业安全评审第一关（差距 B1/B3/B4）。

- [x] Web 层 API token 认证：`FDE_SCOPE_API_TOKEN` 设置后所有路由要求
  `Authorization: Bearer` / `X-API-Key`；未设置保持本地单机现状；`/api/health` 除外
  （新增 `fde_scope/web/auth.py`）
- [x] 审计事件：advance / force advance / gate 评估 / skill 发布落审计日志
  （新增 `fde_scope/audit.py`，追加写 `.fde_scope/audit.jsonl`，凭据不进日志）
- [x] engagement load/save 进程内按 eid 加锁（`fde_scope/web/deps.py`）
- [x] 测试：`tests/test_web_auth.py`、`tests/test_audit.py`

## P1 — 审计与证据链 ✅（2026-09-28 完成主体）

- [x] gate 例外/force 推进记录操作者与理由：force advance 无 `reason` 直接 422；
  `reason`/`operator` 记入 `engagement.advance` 与 `engagement.gate_evaluate` 审计事件
- [x] 审计导出：`GET /api/engagements/{eid}/audit`（JSON 过滤，逐行流式读）+
  `?format=md` / `/audit/export` 生成 Markdown 报告到 reports/（PDF 未做，Markdown 已够合规审查）
- [x] 签字链：handoff 生成 runbook/移交包与 `accept=true` 验收时把文件 sha256+字节数+UTC
  时间戳写入 `handoff.package` / `handoff.accepted`；`POST/GET /api/engagements/{eid}/evidence`
  留存 FAT/SAT 签字扫描件等外部证据（sha256 入审计）。**注意：这是"文件证据留存"而非数字签名
  （无 PKI/签名验真），电子签集成留待后续**
- [x] 数据生命周期：`POST /api/engagements/{eid}/archive`（移入 .fde_scope/archive/）+
  `DELETE /api/engagements/{eid}`（需 `confirm=<customer名>` 精确匹配，删除 engagement 与证据目录，
  审计日志本身保留——删除权针对客户数据而非合规轨迹）
- [x] 测试：`tests/test_audit_chain.py`（14 项）

## P2 — 可观测性 + LLM 抽象 ✅（2026-09-28 完成）

- [x] 结构化日志贯穿包内（`fde_scope/logutil.py`：`get_logger` 统一 `fde_scope.*` 命名空间，
  `configure_logging()` 幂等装一个 StreamHandler，级别走 `FDE_SCOPE_LOG_LEVEL`，默认 WARNING；
  CLI 入口与 web app 启动均接线；engagement advance/rollback、corpus forge 起止、deploy plan、
  connector 导入失败/CSV 源缺失/MySQL 行数失败、audit 写失败等约 12 处打点，凭据不进日志）
- [x] 健康检查升级为真实状态（`/api/health` 返回 data_root 可写、reports_dir 可写、
  LLM 是否已配置（仅查 env，不发请求）、engagements 计数；任一项失败 status=degraded，
  HTTP 仍 200；路由保持免认证）
- [x] LLM provider 抽象：`LLMClient` Protocol + 共享 `_ChatCompletionsClient` 传输层；
  `OpenAICompatClient`（`FDE_SCOPE_LLM_BASE_URL/API_KEY/MODEL`，标准 Bearer 头，仍 urllib 零新依赖）；
  `get_llm_client()` 工厂（OpenAI 兼容 env 齐配 → OpenAICompat，否则 MiMo 默认）；
  所有调用方（web forge、guided、CLI `_maybe_llm`、PawApp、guided `_llm_available`）改走工厂；
  无网络单测覆盖请求头/body/错误路径与工厂选择矩阵
- [x] PII 规则扩展：新增 IPv4 与英文尊称人名（仅 `Mr./Ms./Mrs./Dr. Xxx` 显式称谓模式，
  规避英文散文误报）；邮箱/银行卡此前已有；每条规则带标签进 `[REDACTED](label)` 计数；
  误报控制有测试钉住（正常英文/中文段落零命中）

## P3 — 连接器补齐（支撑真实 POC）

- [x] Zammad HTTP API（ticket profile 主链路，优先级最高）——2026-09-28 完成：
  `GET {base_url}/api/v1/tickets`（`expand=true`，`limit`/`page` 分页），
  `Authorization: Token token=…` 认证，urllib 零新依赖，30s 超时；
  配置走 `FDE_SCOPE_ZAMMAD_BASE_URL` / `FDE_SCOPE_ZAMMAD_API_TOKEN`（options 可覆盖），
  部分配置 WARNING + 回退；`source` 为本地 `.jsonl` 时走离线回放模式；
  票据归一化到语料契约（group→category、state→state、note/title→content）；
  token 不进日志/异常；`tests/test_zammad_connector.py`（18 项）
- [x] Salesforce REST（2026-09-28 完成）：`/services/data/v59.0/query` SOQL 查询
  Case 对象（`Authorization: Bearer`，access token 直配，不引入 OAuth 换 token），
  `nextRecordsUrl` 分页，只读通道（非 SELECT 直接拒绝），归一化到语料契约
  （Origin→channel、Status→state、Description/Subject→content）；
  配置走 `FDE_SCOPE_SF_INSTANCE_URL` / `FDE_SCOPE_SF_ACCESS_TOKEN`，JSONL 回放兜底；
  token 不进日志/异常；`tests/test_salesforce_connector.py`（21 项）
- [ ] MES ISA-95 / Historian（SQL/OPC 历史库）
- [ ] 用真实连接器跑通一个 POC，替换 `seed_mock_engagements.py` 的至少一个案例

## P4 — 商业形态

- [ ] 许可模式决策：双许可（开源核心 + 企业版功能开关）vs 纯服务
- [ ] license 模块：license key 校验 + 功能开关 + seat 计数
- [ ] mock 数据更名/显著免责声明（去真实公司名）
- [ ] GTM 站：定价区块 + 联系/demo 表单 + 转化追踪
- [ ] 客户侧文档：最终用户手册、API 参考（OpenAPI 导出）、onboarding 指南
- [ ] 第三方依赖 license 审计 + NOTICE 文件
- [ ] 法务：真实公司名 mock 清理（见差距 B5）

## P5 — 规模化（视商业验证启动）

- [ ] 数据库后端（PostgreSQL）替代 JSON 文件，schema 迁移机制
- [ ] 多租户/RBAC（user 模型、workspace 隔离）
- [ ] SSO/LDAP
- [ ] 飞轮再训练后端接线（现在是 stub）
- [ ] `deploy --serve` 端到端实测
- [ ] i18n 框架化（替代手工双份 HTML）
