# FDE Scope 用户指南（客户侧）

> 面向客户现场的运维/业务用户。不需要会 Python，也不需要理解 FDE 方法论细节。
> 命令行参数与 Web API 均以代码为准核对；技术术语保留英文原词。
> 配套文档：[`api-reference.md`](api-reference.md)（REST API 参考）、
> [`onboarding-customer.md`](onboarding-customer.md)（现场部署与验收）。

## 这是什么

FDE Scope 是一个**驻场项目管理工作台**：它把一次「AI 落地客户现场」的完整过程
——从第一次现场勘察、数据接入、语料锻造、上线部署，到最后的运维移交与客户签字
——固化成一条 18 阶段的流水线，每一阶段有明确的产出物；关键阶段出口处设有
**gate（门禁）**，条件不满足就不放行，且所有操作留审计痕迹。

类比：它像装修工程里的「工序验收单系统」——水电没验收，就不允许封墙。

## 安装

需要 **Python ≥ 3.11**。

```bash
pip install -e "."          # 核心功能（无 LLM、无额外依赖）
pip install -e ".[web]"     # + Web 控制台（FastAPI/uvicorn）
pip install -e ".[dev]"     # + 测试工具
pip install -e ".[full]"    # 全部 extras（含 agentscope 与各工业连接器驱动）
```

安装后得到 `fde-scope` 命令（等价于 `python -m fde_scope.cli`）。

## 5 分钟跑通第一个 engagement

以仓库自带的 `examples/quickstart_csv/` 演示数据为例（客服工单场景）：

```bash
# 1. 预览数据源（连接 CSV，查看 schema 与样本）
fde-scope connect --type csv --source examples/quickstart_csv/sample_tickets.csv
# 预期：打印字段表格（field/type/nullable/PII?），并提示样本已写入 samples/preview.json

# 2. 创建 engagement（profile=ticket，客服场景）
fde-scope engage init --customer "示例客户" --profile ticket
# 预期：✅ Engagement eng-示例客户-ticket created；phase: qualification · zone: pre_engagement

# 3. 推进 SOP 阶段（前一阶段无 gate 时直接放行）
fde-scope engage advance eng-示例客户-ticket
# 预期：✅ Advanced → ... ；若被 gate 拦截则红色打印 ❌ ADVANCE BLOCKED 及 blockers 清单

# 4. 随时查看状态
fde-scope engage status eng-示例客户-ticket
# 预期：customer / profile / current_phase / zone / gate 状态 / gate_records 表

# 5. 语料锻造（脱敏 → 去重 → 质量门 → 覆盖度 → 报告）
fde-scope corpus --input examples/quickstart_csv/sample_tickets.csv --out reports/corpus_report.html
# 预期：✅ PII entities masked / Dropped / Corpus forged 计数；报告写入 reports/

# 6. 或者打开 Web 控制台，在浏览器里做同样的事
fde-scope web    # → http://127.0.0.1:8080
```

制造业场景把 `--profile ticket` 换成 `manufacturing`，可跑的样本见
`examples/quickstart_manufacturing/station_samples.jsonl`（配合 `fde-scope kpi <id> --samples …`）。

## 核心概念一页纸

- **Engagement（驻场项目）**：一次完整的客户现场交付，是系统里所有数据、阶段、
  审计的归属单位。类比：一个装修工程单号。
- **18 阶段 / 4 Zone**：SOP 分四个 zone——Zone A 立项勘察（4 阶段）、
  Zone B 构建（6 阶段）、Zone C 运营化（5 阶段）、Zone D 交接退场（3 阶段）。
  `ticket` profile 跑 15 个阶段，`manufacturing` 跑全部 18 个。
  类比：毛坯 → 硬装 → 软装 → 竣工验收。
- **Gate（门禁）**：挂在阶段出口的可执行检查（如「双 sponsor 确认成功标准」
  「FAT/SAT 签字齐全」）。每次推进都**实时重评**，以前的通过记录不作数；
  有 blocker 就拒绝推进。类比：每个隐蔽工程节点的验收签字。
- **Profile（场景档案）**：`ticket`（客服工单）与 `manufacturing`（制造业/机器人）
  两个模板，决定可用的连接器、KPI 目录和适用哪些 gate。
- **语料锻造（Corpus Forge）**：把原始数据（CSV 等）变成可审计的训练/评估语料：
  PII 脱敏 → 去重 → 质量门 → 覆盖度分析 → 针对缺口合成 → HTML 报告。
  类比：把散料清洗、分拣、补齐后入库。
- **技能库（Skills）**：现场经验沉淀为可复用的方法论卡片
  （research / implementation / optimization / methodology 四类），
  生命周期 draft → published → archived，可导出给 Agent 使用。
  类比：老师傅的「作业要领本」，越积越厚。

## 常用操作清单

| 操作 | 命令 |
|---|---|
| 创建项目 | `fde-scope engage init --customer "客户名" --profile ticket` |
| 查看状态 | `fde-scope engage status <id>` |
| 推进阶段 | `fde-scope engage advance <id>` |
| 回退阶段 | `fde-scope engage rollback <id> --to <phase-slug>` |
| 查看 gate | `fde-scope gate check <id>`（`--gate <slug>` 指定某个 gate） |
| gate 列表 | `fde-scope gate list --profile manufacturing` |
| 现场记录 | `fde-scope engage journal <id> --kind research --note "…"` |
| 移交包 | `fde-scope handoff <id> --accept`（生成 runbook + 移交包） |
| 技能沉淀 | `fde-scope skill add / list / review / publish / export` |

### 处理 gate 拦截

`advance` 被拦截时会打印 blockers 清单（如「sponsor 不足 2 人」）。正常做法是
补齐条件（通过 Web 控制台 Context tab 或 `POST /api/engagements/{eid}/context`
更新现场信息）后再次 advance。

确有例外时可强制推进：

```bash
# CLI
fde-scope engage advance <id> --force

# Web API（force 必须带非空 reason，否则 422）
curl -X POST http://127.0.0.1:8080/api/engagements/<id>/advance \
  -H "X-API-Key: $FDE_SCOPE_API_TOKEN" \
  -F force=true -F reason="客户要求先上线灰度，FAT 补签中" -F operator="张三"
```

注意：**force 只是豁免拦截，gate 照常评估并记录**——例外会留在审计日志里，
不会混同于干净通过。被拦截时系统还会自动生成一条 gate_hint 技能草稿，
可用 `fde-scope skill review` 查看完善。

### 导出审计

```bash
curl "http://127.0.0.1:8080/api/engagements/<id>/audit" -H "X-API-Key: $FDE_SCOPE_API_TOKEN"
curl "http://127.0.0.1:8080/api/engagements/<id>/audit/export" -H "X-API-Key: $FDE_SCOPE_API_TOKEN"
# 后者生成 reports/audit_<id>.md
```

### 附加证据（FAT/SAT 签字扫描件等）

```bash
curl -X POST http://127.0.0.1:8080/api/engagements/<id>/evidence \
  -H "X-API-Key: $FDE_SCOPE_API_TOKEN" \
  -F name="FAT签字页.pdf" -F operator="张三" -F file=@/path/to/FAT签字页.pdf
```

文件 sha256 + UTC 时间戳写入审计日志。**注意：这是文件证据留存，不是数字签名**
（无 PKI 验真，电子签集成暂未支持，见路线图 P5）。

### 归档 / 删除

```bash
# 归档：移入 .fde_scope/archive/，不再出现在列表
curl -X POST http://127.0.0.1:8080/api/engagements/<id>/archive -H "X-API-Key: $FDE_SCOPE_API_TOKEN"

# 删除（GDPR 删除权）：confirm 必须与客户名完全一致；审计日志保留
curl -X DELETE http://127.0.0.1:8080/api/engagements/<id> \
  -H "X-API-Key: $FDE_SCOPE_API_TOKEN" -F "confirm=客户名"
```

## env 配置速查表

所有凭据**只走环境变量**，绝不写入配置文件/报告/日志。

| 变量 | 作用 | 备注 |
|---|---|---|
| `FDE_SCOPE_API_TOKEN` | Web API 认证 token | 设置后所有非白名单路由要求 `Authorization: Bearer` 或 `X-API-Key`；不设置则认证关闭（本地单机模式） |
| `FDE_SCOPE_ALLOW_REMOTE` | 允许绑定非回环地址 | 需显式设为 `1`，否则 `fde-scope web --host 0.0.0.0` 被拒绝 |
| `FDE_SCOPE_HOME` | 数据根目录 | 不设则按「CWD 含数据 → 应用目录 → CWD」解析 |
| `FDE_SCOPE_LOG_LEVEL` | 日志级别 | 默认 `WARNING`；`DEBUG` 可见 gate 评估细节 |
| `FDE_SCOPE_MIMO_API_KEY` | MiMo Token Plan 凭据 | `tp-` 前缀；可选 `FDE_SCOPE_MIMO_BASE_URL` / `FDE_SCOPE_MIMO_MODEL` |
| `FDE_SCOPE_LLM_BASE_URL` / `FDE_SCOPE_LLM_API_KEY` / `FDE_SCOPE_LLM_MODEL` | 任意 OpenAI 兼容端点（vLLM/DeepSeek/本地模型…） | 三个里 BASE_URL+API_KEY 齐配时优先于 MiMo；MODEL 缺省 `gpt-4o-mini` |
| `FDE_SCOPE_ZAMMAD_BASE_URL` / `FDE_SCOPE_ZAMMAD_API_TOKEN` | Zammad 工单连接器 | 两个都设才走真实 API，否则回退本地 `.jsonl` |
| `FDE_SCOPE_SF_INSTANCE_URL` / `FDE_SCOPE_SF_ACCESS_TOKEN` | Salesforce 连接器 | 同上，SOQL 只读 |
| `FDE_SCOPE_MES_BASE_URL` / `FDE_SCOPE_MES_API_TOKEN` | MES (ISA-95) 连接器 | 同上 |
| `FDE_SCOPE_HISTORIAN_BASE_URL` / `FDE_SCOPE_HISTORIAN_API_TOKEN` | Historian 连接器 | 同上 |

## 故障排查 FAQ

**1. `/api/health` 返回 `status: degraded` 怎么办？**
看 `checks` 里哪一项 `ok: false`：`data_root` 或 `reports_dir` 不可写通常是目录
权限问题（见下条）；`llm.configured: false` 不算故障，只表示未配 LLM。
degraded 时 HTTP 仍是 200（探活语义：进程活着，子系统可能不健康）。

**2. 没配 LLM 会怎样？**
一切照常。语料合成、质量评分、runbook 生成全部走确定性规则路径；
Web 控制台引导模式的 AI 起草自动回退为手动表单。只有显式要求 LLM 的命令
（`corpus --llm`、`eval --agent mimo`、`handoff --llm`）会在无 key 时明确报错退出
（exit 2）并提示配置方法。

**3. API token 忘了 / 要重置？**
token 只存在环境变量里，不落任何文件。直接换一个新值重启即可：

```bash
export FDE_SCOPE_API_TOKEN="新的随机长字符串"
fde-scope web
```

旧 token 立即失效。建议用 `openssl rand -hex 32` 生成。

**4. 数据存在哪里？**
数据根解析顺序：`FDE_SCOPE_HOME` > 含 `.fde_scope/` 的当前目录 > 当前目录。
其下：`.fde_scope/engagements/*.json`（项目状态）、`.fde_scope/skills/`（技能库）、
`.fde_scope/audit.jsonl`（审计日志，append-only）、`.fde_scope/evidence/<id>/`（证据附件）、
`.fde_scope/archive/`（归档）、`reports/`（runbook / 语料报告 / 审计导出）。

**5. 如何备份？**
备份整个数据根即可（零数据库，全是文件）：

```bash
tar czf fde-backup-$(date +%F).tgz .fde_scope/ reports/
```

`audit.jsonl` 是 append-only，备份它即可保留完整操作轨迹。

**6. 换目录启动后看不到之前的 engagement？**
数据根按当前工作目录解析（见第 4 条）。在原来的目录启动，或显式
`export FDE_SCOPE_HOME=/path/to/数据根` 固定位置（macOS App 就是这么做的）。

**7. 想绑定 `0.0.0.0` 给局域网用被拒绝？**
这是安全设计：先设 `FDE_SCOPE_API_TOKEN` 开启认证，再
`FDE_SCOPE_ALLOW_REMOTE=1 fde-scope web --host 0.0.0.0`。
仅建议在受信内网这么做；公网暴露暂不提供额外防护（HTTPS 终止、SSO 等见路线图 P5）。

**8. gate 被拦、看不懂 blocker 是什么意思？**
Web 控制台 engagement 详情页的「引导」tab 会把每个 blocker 翻译成
「下一步做什么」的白话清单，并给出当前阶段的产出物列表与技能手册深链；
无需 FDE 驻场也能自行补齐条件。

## 暂未支持（见商业化路线图 P5）

SSO/LDAP、多用户/RBAC、数字签名（现有的是文件 sha256 证据留存）、
PostgreSQL 后端与 schema 迁移、飞轮再训练后端（当前为 stub）、
`deploy --serve` 端到端生产验证。
