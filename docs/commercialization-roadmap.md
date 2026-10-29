# FDE Scope 商业化路线图

> 配套文档：`docs/commercialization-gap-analysis.md`（差距证据全表）。
> 每个阶段独立可交付；完成后回到差距分析文档标注修复状态。

## P0 — 安全底线 ✅（2026-09-28 完成）

目标：堵住企业安全评审第一关（差距 B1/B3/B4）。

- [x] Web 层 API token 认证：`FDE_SCOPE_API_TOKEN` 设置后所有路由要求
  `Authorization: Bearer` / `X-API-Key`；未设置只对回环请求放开；`/api/health` 除外
  （新增 `fde_scope/web/auth.py`）
- [x] 2026-10-06 收紧默认值：认证关闭不再随 `FDE_SCOPE_ALLOW_REMOTE=1` 一起生效——
  CLI 要求非回环绑定同时有 token（缺则 exit 2），中间件逐请求按 `scope["server"]`
  （连接被 accept 时落在哪个地址）兜底，未设 token 且从非回环地址到达 → 403。
  绕过 CLI 直接 `uvicorn`/`gunicorn` 启动同样受这层保护；回归见
  `tests/test_web_auth.py`（22 项），行为说明见 `docs/user-guide.md` FAQ 7/8 与
  `docs/api-reference.md` 认证节
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
- [x] MES ISA-95 / Historian（2026-09-28 完成，均照 zammad/salesforce 惯例的三态模式）：
  - MES：`GET {base}/api/v1/work-orders`（offset 分页，endpoint 可覆盖），Bearer 认证，
    `order_id→id`、`product→category`、`status→state`、`description→content`；
    env `FDE_SCOPE_MES_BASE_URL` / `FDE_SCOPE_MES_API_TOKEN`；`tests/test_mes_connector.py`（22 项）
  - Historian：默认 `GET {base}/api/v1/samples?tag=X`（按 tag + offset 分页），
    endpoint 含 `{tag}` 占位符时走 PI Web API 风格；quality 异常渲染为 content
    （时序数据的语义载体）；env `FDE_SCOPE_HISTORIAN_BASE_URL` / `FDE_SCOPE_HISTORIAN_API_TOKEN`；
    `tests/test_historian_connector.py`（21 项）
  - 注意：两者按常见 MES/Historian REST 约定建模，具体客户现场用 options.endpoint 适配
- [ ] 用真实连接器跑通一个 POC，替换 `seed_mock_engagements.py` 的至少一个案例

## P4 — 商业形态

- [x] 许可模式决策：双许可（开源核心 + 企业版功能开关）——已选定并实现
- [x] license 模块（2026-09-28 完成）：`fde_scope/license.py` 离线许可——key 格式
  `base64url(payload).base64url(hmac_sha256)`，签名密钥走 `FDE_SCOPE_LICENSE_SECRET`
  （不设则 fail closed 所有 key 无效）；key 从 `FDE_SCOPE_LICENSE_KEY` 或
  `.fde_scope/license.key` 读；tier：community / pro / enterprise（pro=+审计导出/证据留存/
  LLM 合成，enterprise=+deploy serve/多租户预留），payload 显式 features 与 tier 表取并集；
  过期降级 community + WARNING（不锁死用户）；`hmac.compare_digest` 常数时间比对；
  CLI `fde-scope license`（查看）/ `fde-scope license-issue`（签发交付工具）；
  web 门控：audit/export 与 evidence 上传要求 pro+（无 key → 402 明确文案）；
  `tests/test_license.py`（25 项）。docstring 注明：诚实防君子机制，非 DRM
- [x] mock 数据更名/显著免责声明（去真实公司名）（2026-09-28 完成：十个 engagement 全部改为虚构公司名 aurora/atlas/southbay/northern/swift/adnova/teaverse/horizon/riverbend/whitelake，README/GTM/reports/ 同步，种子脚本头部加显著免责声明）
- [x] GTM 站（2026-09-28 完成）：三档定价区块（Community 免费 / Pro 占位价¥4,800/席位/月
  标注"以商务洽谈为准" / Enterprise 面议）、联系区块（mailto + GitHub Issues）、导航锚点、
  页脚 NOTICE 链接 + "演示数据均为虚构"声明；中英双语经 `i18n_split.py` 同步（+11 条映射）。
  未做：转化追踪（无分析后端，纯静态站定位保留）
- [x] 客户侧文档：最终用户手册、API 参考（OpenAPI 导出）、onboarding 指南（2026-09-28 完成：`docs/user-guide.md` 用户手册、`docs/api-reference.md` 路由级 API 参考（逐条对照 `web/app.py` + `web/guided_api.py`，OpenAPI 导出本身未做）、`docs/onboarding-customer.md` 现场部署/安全基线/接入决策树/验收模板；README 文档区已索引）
- [x] 第三方依赖 license 审计 + NOTICE 文件（2026-09-28 完成：根目录 `NOTICE` + `docs/license-audit.md` + `tests/test_third_party_licenses.py` 守护；发现 mysql-connector-python GPLv2+FOSS 例外、asyncua LGPLv3+、paho-mqtt EPL-2.0/BSD 双许可，均为 optional extra）
- [x] 法务：真实公司名 mock 清理（见差距 B5，2026-09-28 修复）

### 开源/商业边界决策（2026-10-06 提出，⚠️ 未定，需维护者拍板）

公开前的实测基线：`pyproject.toml` 声明 `license = { text = "MIT" }`，根目录有真
MIT `LICENSE`（署名 Allen Galler）与 `NOTICE`，两者**都已进入发行件**
（wheel `fde_scope-0.1.0.dist-info/licenses/`、sdist 顶层，2026-10-06 `python -m build` 实测）。
本轮未改动任何许可证文本，也未新增 CLA。

矛盾点在于上面第 85 行「双许可（开源核心 + 企业版功能开关）」这条已选定的形态，
与「整个包 MIT」不兼容：**MIT 授予任何人再分发与商用权，因此同一个 MIT 发行件里的
功能开关不构成商业边界**。`fde_scope/license.py:3` 自己也这么承认——docstring 原句
`This is an *honesty mechanism, not DRM*`，`SECURITY.md` 进一步把它列为"商业档位，不是安全控制"。
现状能守住的只有**信任与升级服务**（离线签发、无在线校验），守不住代码复制。
单机版与多用户企业版两条路都要走，就必须先把边界放到正确的那一层：

| 方案 | 边界落在哪 | 代价 | 适合什么 |
|---|---|---|---|
| A 维持 MIT，企业能力另发一个包 | 仓库/发行件（`fde-scope` MIT + `fde-scope-enterprise` 专有） | 需要维护私有仓库与共享内部层的版本同步 | 真正想卖多用户/RBAC/SSO，且接受"核心可被自由 fork" |
| B 核心改 Apache-2.0 | 许可证文本 | 需要全部贡献者同意再授权；工业侧 OEM/集成商更认这个（含明示专利授权） | 目标是被客户采购方接受，而非防止 fork |
| C 核心 Apache-2.0 + 企业层 ELv2/BUSL | 分层许可证 | 需明确"哪些目录属于企业层"，且改许可证要复测 `NOTICE`/第三方 license 守护 `tests/test_third_party_licenses.py` | 与 A 同类，但企业层与核心同仓 |

推荐：**A 或 C**，因为 P5 的多租户/RBAC/SSO 一旦落地必然是与核心不同代码路径的能力，
放在同一个 MIT 包里只会让第 85 行的宣称与实际可执行的权利不一致。
B 可单独执行且与 A/C 不冲突（核心换 Apache-2.0 不改变企业层的授权问题）。

需要澄清的一点（实测，非推测）：**客户可见文本目前并没有宣称这个排他边界**——
`grep -rn "开源核心" README.md GTM/index.html` 无命中，该表述只存在于本文件第 85 行与
`docs/commercialization-gap-analysis.md:145` 两份内部规划文档。所以公开前必改的是
**这两份文档里的一句话**（写成"MIT 开源 + 付费服务/另发的企业包"这类当前许可证
真正支持的表述），而不是先改许可证。若维持第 85 行现状直接 public，等于把一份
内部未自洽的形态描述公开在仓库里。

## P5 — 规模化

- [x] 存储后端抽象 + SQLite（2026-09-28 完成）：`fde_scope/storage.py` `StorageBackend`
  Protocol + `FileStorage`（默认，JSON 原子写行为零变化）+ `SQLiteStorage`（stdlib sqlite3
  零新依赖，WAL，事务写，`FDE_SCOPE_STORAGE=file|sqlite` 切换）；web 层全生命周期走后端；
  CLI `fde-scope storage-migrate --to sqlite` 单向迁移；`tests/test_storage.py`（15 项，
  含 8 线程并发写不丢）。**PostgreSQL 与 schema 迁移框架未做**——SQLite 已解并发与可靠性，
  PG 留待多租户落地时一起上
- [x] 飞轮再训练后端接线（2026-09-28 完成）：`fde_scope/flywheel/backends.py`
  `TrainingBackend` Protocol + `HTTPTrainingBackend`（通用 webhook 式训练服务，
  `FDE_SCOPE_TRAINING_URL`/`FDE_SCOPE_TRAINING_TOKEN`，Bearer 认证，token 不进日志/异常）
  + `NoopBackend`（如实标注 backend=noop，不再写"stub"误导）；scheduler 走工厂+可注入；
  `tests/test_training_backend.py`（28 项）
- [x] `deploy --serve` 端到端实测（2026-09-28 完成）：`deploy/e2e/` 验证基建——
  `fake_model.py`（stdlib OpenAI 兼容假模型）+ `docker-compose.e2e.yml`（redis）+
  `smoke_test.sh`（全自动：redis→fake model→隔离 FDE_SCOPE_HOME 起 serve→建 credential/
  agent/session→/chat/ 触发→断言 fake 收到调用）；**已本机实测 PASS（agentscope 2.0.8）**；
  发现真实缺口：`agentscope[service]` 不含 redis Python 包（已在 e2e README 前置条件标注）；
  `tests/test_deploy_e2e_fake_model.py`（3 项）
- [ ] 多租户/RBAC（user 模型、workspace 隔离）——依赖真实商业验证后启动
- [ ] SSO/LDAP——同上
- [ ] i18n 框架化（替代手工双份 HTML）
- [ ] 用真实连接器跑通一个 POC，替换 `seed_mock_engagements.py` 的至少一个案例
  （P3 遗留，连接器已全部就位）
