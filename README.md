# FDE Scope

> **The complete on-site operating system for a Forward Deployed Engineer.**
> From first gemba walk to signed-off handoff — across software/SaaS *and*
> embodied-robotics / manufacturing. Built on [AgentScope 2.0](https://github.com/agentscope-ai/agentscope).

[![CI](https://github.com/ai-guru-global/fde-scope/actions/workflows/ci.yml/badge.svg)](https://github.com/ai-guru-global/fde-scope/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/ai-guru-global/fde-scope/graph/badge.svg)](https://codecov.io/gh/ai-guru-global/fde-scope)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Code style: formatter](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

FDE is 2026's hottest AI role (OpenAI, Anthropic, Google, Palantir all build FDE
teams; listings up ~7× YoY). But every FDE shows up to a customer site and
rebuilds the same workflow from scratch — and most teams only model the "build"
half, skipping the pre-engagement, operationalization, and handoff zones that
actually decide whether the engagement produces value.

**FDE Scope codifies the *full* FDE standard operating procedure** — 4 zones,
18 phases — into an executable, gate-enforced state machine, with a parallel
**industrial overlay** (FAT/SAT, functional safety, CE/EU-AI-Act, works council,
air-gap, shift handover) for manufacturing/robotics deployments.

```
Zone A · Pre-engagement  →  Zone B · Build  →  Zone C · Operationalization  →  Zone D · Handoff
 qualification               connect             slo / on-call                   ops handoff
 site survey (🏭)            corpus              runbook                         knowledge transfer
 stakeholder map             prototype-real      monitoring / drift              disengage (signed off)
 success criteria            deploy (🏭 FAT/SAT) change-mgmt (🏭 works council)
                             eval                flywheel → productize
```

It is **not** an agent application — it's an FDE's workbench: a CLI, a Web UI,
and a Python library that turns the SOP from a checklist into enforced engineering.

---

## ✨ What makes it different

1. **Full SOP, not just "5 steps".** The naive connect→corpus→deploy→eval→flywheel
   model covers only the Build zone. FDE Scope adds the 4 pre-engagement phases,
   5 operationalization phases, and 3 handoff phases that most teams skip — and
   enforces them with phase gates. The `manufacturing` profile runs the full
   18 phases; the `ticket` profile runs the 15 SaaS-relevant ones. See
   [`docs/fde_sop_full.md`](docs/fde_sop_full.md).
2. **A real industrial overlay.** Manufacturing/robotics engagements hit gates
   that SaaS never does: FAT/SAT acceptance, functional safety
   (ISO 13849 / IEC 61508 / ISO 10218), CE/EU-AI-Act conformity, German works-council
   co-determination (BetrVG §87), air-gapped deployment, shift handover. Each is
   an executable `Gate.check()` — it blocks advancement when blockers are present.
3. **Scenario profiles.** `ticket` (customer service) and `manufacturing`
   (embodied-robotics factory) share one engine but differ in connectors, KPIs,
   and which gates apply. Manufacturing reports real production KPIs: OEE, MTBF/
   MTTR, FPY/DPMO, grasp success rate, collision/intervention rate.
4. **Built on real AgentScope 2.0.** The runtime layer maps to the *actual* 2.0.5
   API — not the fictional `HarnessAgent`/`SequentialPipeline`/`EventSystem.on`
   that appear in many design docs. See
   [`docs/agentscope_api_mapping.md`](docs/agentscope_api_mapping.md).
5. **Zero-config runnable.** The core data + engagement layers have **no**
   AgentScope dependency — no LLM key, no Docker. `pip install -e ".[dev]"` and
   `pytest` is green. The Web UI is one extra.
6. **A real workbench, not a mock.** Ship with `examples/seed_mock_engagements.py`
   to demo the console with six realistic Alibaba-Cloud-style enterprise
   engagements (EV/factory, ride-hailing, retail-tea-chain, outbound-SaaS …),
   each with engine-generated gate records, runbooks and corpus reports — see
   [Mock demo data](#-mock-demo-data).

---

## 🚀 Quick start

```bash
# install (core + dev + web; no agentscope/docker/api-key needed)
pip install -e ".[dev]"

# ── Scenario 1: customer-service tickets (the original) ──
fde-scope connect --type csv --source examples/quickstart_csv/sample_tickets.csv
fde-scope corpus --input examples/quickstart_csv/sample_tickets.csv --out reports/corpus_report.html

# ── Scenario 2: embodied-robotics factory (the new one) ──
fde-scope profiles                                    # see ticket + manufacturing
fde-scope engage init --customer "BMW Spartanburg" --profile manufacturing
fde-scope kpi <engagement-id> --samples examples/quickstart_manufacturing/station_samples.jsonl
fde-scope gate list --profile manufacturing           # 10 gates, 7 industrial-only

# ── Walk the full 18-phase SOP with gate enforcement ──
fde-scope engage advance <id>          # gate fails → refuses, shows blockers
fde-scope engage status <id>           # phase / zone / gate state / progress
fde-scope handoff <id> --accept        # Zone D: assemble the handoff package

# ── Or do it all in the browser ──
fde-scope web                          # → http://127.0.0.1:8080
```

### Web UI

```bash
pip install -e ".[web]"
fde-scope web                          # --host 127.0.0.1 --port 8080 --reload
```

A single-page engagement console — no build step, backed by JSON APIs:

- **Engagement dashboard** — list / create engagements, advance through the
  18-phase SOP (gates block in red when unmet), roll back, inspect blockers.
- **Gate inspector** — evaluate any gate live against an engagement
  (`/api/engagements/{eid}/gates`) with blocker/warning breakdown.
- **Context tab** — six structured cards per engagement: site survey, stakeholder
  map (with SPONSOR badges), success criteria, SLOs, functional-safety posture,
  and artifacts (runbook / corpus report / eval metrics / drift monitoring).
- **Corpus forge** — upload a CSV (≤ 10 MiB) and forge an auditable corpus report.
- **KPI explorer** — compute profile-specific KPIs over a sample set.
- **Report browser** — `/reports/` serves generated runbooks and corpus HTML.

---

## 🧪 Mock demo data

```bash
pip install -e ".[dev]"
python examples/seed_mock_engagements.py   # idempotent; re-run to re-seed
fde-scope web                              # open the console, pick any engagement
```

Seeds `.fde_scope/engagements/` with six realistic engagements based on real
Alibaba Cloud enterprise customers. Every gate record is produced by the engine
itself (`Engagement.evaluate_gate`), so the console's gate panels and the
engagement context are always self-consistent. Each engagement also writes a
rendered runbook (`reports/<slug>-runbook.md`) and corpus report
(`reports/<slug>-corpus.html`) with real train/eval/test splits.

| Customer | Profile | Phase | Story |
|---|---|---|---|
| 古茗 (tea-chain) | ticket | 15/15 disengage | Full handoff package, customer accepted |
| 一汽-大众 (automaker) | manufacturing | 11/18 runbook | 9/9 industrial gates passed (3 shifts + works council + PL d/SIL 2 + HAZOP) |
| 广汽 (automaker) | manufacturing | 9/18 deploy | FAT/SAT + functional safety + conformity genuinely BLOCKED → advance refused |
| 一汽 (automaker) | ticket | 13/15 flywheel | Productization flywheel running |
| 曹操出行 (ride-hailing) | ticket | 8/15 prototype | Real-data prototyping, SLO defined |
| 易点天下 (outbound SaaS) | ticket | 3/15 success_criteria | Single-sponsor blocker — the Sponsor Collapse anti-pattern |

---

## 🏗 Architecture

| Layer | Module | Role | agentscope? |
|---|---|---|---|
| **SOP** | `engagement/` | 18-phase state machine + 10 enforceable gates + handoff | ❌ |
| **Profiles** | `profiles/` | Scenario selector (ticket / manufacturing) | ❌ |
| 1 | `connectors/` | CSV★, Zammad, Salesforce, MySQL + OPC UA, MQTT-Sparkplug, ROS2, MES, Historian | ❌ |
| 2 | `corpus/` | PII scrub, dedup, quality gate, coverage, synthesis, report | ❌ |
| 3 | `deploy/` | DockerWorkspace + PermissionEngine + KnowledgeBase assembly | ✅ lazy |
| 4 | `eval/` | Ticket metrics + manufacturing KPIs (OEE/MTBF/FPY/…) + bad-case miner | ❌ |
| 5 | `flywheel/` | Concept→real event mapping + collectors + retrain scheduler | ✅ lazy |
| **Web** | `web/` | FastAPI engagement console (single-page, JSON APIs) | ❌ |

### The 10 phase gates

| Gate | Applies | Checks |
|---|---|---|
| `site_survey` | 🏭 | Site location required; empty assets / multi-shift without networks → warning |
| `success_criteria` | 🏢 | Written criteria + **≥ 2 sponsors**; sponsor without a success metric → warning |
| `fat_sat` | 🏭 | FAT **and** SAT both passed, each signed off |
| `functional_safety` | 🏭 | Achieved PL/SIL ≥ required; ISO 10218 assessed; **hazard analysis mandatory** (blocker) |
| `conformity` | 🏭 | EU-AI-Act high-risk ⇒ CE marking + technical construction file + hazard analysis |
| `works_council` | 🏭 | Works-council approval signed off when representatives exist |
| `air_gap` | 🏭 | Offline deployment posture settled at connect time (not phone-home) |
| `shift_handover` | 🏭 | Multi-shift sites need digital handover log + per-shift runbook |
| `slo` | 🏢 | SLO/SLA + error budget + alert route (missing route → warning) |
| `handoff_signoff` | 🏢 | Handoff package: runbook + eval report + SLO + training material, customer accepted |

Gates are executable code, not checklists: `Engagement(ctx).evaluate_gate(slug)`
returns `(passed, blockers, warnings)` and blocks `advance` until clean
(`--force` records the result without blocking). See
[`docs/architecture.md`](docs/architecture.md) and
[`docs/fde_sop_full.md`](docs/fde_sop_full.md).

---

## 🛠 CLI reference

```
connect   [Layer 1] Connect to a data source and preview schema + samples
corpus    [Layer 2] Forge a raw sample into an auditable, gap-aware corpus
deploy    [Layer 3] Assemble (and optionally start) a multi-tenant agent (multi-agent via --agent)
eval      [Layer 4] Run the FDE benchmark over a test set
flywheel  [Layer 5] Start (or replay into) the data flywheel
handoff   [Zone D]  Assemble the handoff / knowledge-transfer package
kpi       Profile-specific KPIs over a sample set
profiles  List available deployment scenario profiles
web       Launch the Web UI (workbench + skills + engagement console)
engage    [SOP] init / status / advance / rollback / journal / list
gate      [SOP] list (per profile) / check (per engagement)
skill     [Skills] 技能/方法论沉淀库（add / list / show / edit / publish / archive / review / export）
qwenpaw   [QwenPaw] Export / validate QwenPaw-compatible bundles (agents + skills + corpus)
```

---

## 🤖 多 Agent 拓扑（AgentScope 2.0）

`tenant_config.yaml` 的 `agents` 段（或 CLI `--agent name:role[:model]`）声明一个
tenant 的多个 Agent。`fde-scope deploy` 为每个 spec 组装真实的
`agentscope.agent.Agent`（模型从 `spec.model` wiring，缺失留运行时注入），
manifest 携带完整 `agents` 段与 `subagent_templates`。

多 Agent 交互走 AgentScope 2.0 官方机制：`agentscope.app.SubAgentTemplate`
蓝图（`create_app(custom_subagent_templates=...)`），leader agent 通过
`AgentCreate` / `TeamSay` 协调子 Agent。真实 app 服务（storage + message_bus +
workspace_manager）需要独立后端，本期交付蓝图导出 + 拓扑声明（spec §4.3 降级条款），
不虚构 API。生命周期：2.0 无 `Agent.stop`，`TenantDeployer.stop()` 关闭
workspace/engine 句柄并标记 manifest。

---

## 🐾 QwenPaw 集成

`fde-scope qwenpaw export --tenant acme --agent "researcher:调研员" --out qwenpaw-out`
把 tenant 的 agent 拓扑导出为 QwenPaw 兼容产物（`config.json` 的 `agents.profiles`
多 Agent 声明 + `workspaces/{agent_id}/agent.json` + `AGENTS.md` persona +
published 技能包 + corpus 说明），`qwenpaw validate --out ...` 按官方规则校验
（必填字段 / agent id 规则 / SKILL.md frontmatter）。ACP 适配：`AcpEndpoint`
基类把 FDE 能力暴露为 QwenPaw ACP runner（`delegate_external_agent`）。
详见 [`docs/qwenpaw_integration.md`](docs/qwenpaw_integration.md)。

---

## 💡 Skill 沉淀（Skills / Methodology capture）

FDE 在现场的每一步（调研、实施、调优、方法论）都可以沉淀为可复用的技能，跨 engagement、跨客户复用。技能存为文件库 `.fde_scope/skills/`（每个技能一个目录：`skill.md` + `meta.json`），随项目携带，零数据库依赖。

**三种沉淀入口：**

| 入口 | 触发方式 | 说明 |
|---|---|---|
| 手动 | `fde-scope skill add` | 随时沉淀，四类分类（research / implementation / optimization / methodology）+ 标签 |
| gate 阻塞提示 | `engage advance` / `gate check` 失败时自动 | 生成预填草稿（gate_hint），`skill review` 完善 |
| 操作自动捕获 | `engage advance` 成功 / `gate check` 通过时自动 | 轻量记录（auto_capture），`skill review` 完善 |

**生命周期：** draft → published → archived。`skill review` 审阅草稿队列 → `skill publish` → 可检索、可导出。

**导出给 Agent：** 支持 AgentScope 2.0 与 QwenPaw 两种格式（Anthropic Agent Skills 规范：`<skill-name>/SKILL.md`，frontmatter 含 `name` + `description`）。AgentScope 侧经 ``Toolkit(skills_or_loaders=[...])``（部署装配的 `AgentSpec.toolkit.skills_dirs`）注册进真实 Toolkit；QwenPaw 侧放入 `customized_skills` 目录自动发现。

```bash
fde-scope skill add --title "OPC UA 连接踩坑" --category implementation --tags opcua --body "# 步骤..."
fde-scope skill review                  # 审阅自动捕获/gate 提示产生的草稿队列
fde-scope skill publish <skill-id>
fde-scope skill list --category implementation --tag opcua
fde-scope skill export <skill-id> --format qwenpaw --out exports/   # 或 --format agentscope
```

Web UI 暴露完整的 skills API：`GET/POST /api/skills`、`GET/PATCH /api/skills/{id}`、`POST /api/skills/{id}/publish|archive|export`、`GET /api/skills/drafts`。

---

## 🖥️ FDE 工作台（Workbench + 现场记录）

`fde-scope web` 打开的单页控制台现在是一个跨项目工作台：

- **工作台首页**（`/console`）：全局统计条（进行中项目 / 阶段分布 / 待审草稿 / 技能总数）、
  跨项目矩阵（客户/阶段/zone/门禁/最近更新，点击进入详情）、最近沉淀技能；
- **技能库页**（`/console#skills`）：搜索 + 分类/状态筛选 + 技能卡片 +
  新建技能表单 + 草稿审阅队列（一键发布/编辑）；
- **现场记录**（详情页 tab）：`research / implementation / optimization` 三类记录，
  任意一条可一键“沉淀为技能”（kind → category 自动映射、关联来源 engagement）。

CLI 等价入口：`fde-scope engage journal <id> --kind research --note "..." [--link-skill <sid>]`。

---

## 🤖 LLM 接入（可选）

核心层零 LLM、零额外依赖：语料合成、质量评分、eval 回复、runbook 生成全部默认走确定性规则路径，只有设置了环境变量才启用 MiMo Token Plan（OpenAI 兼容协议，标准库 `urllib` 直连，无新依赖）。

```bash
# Token Plan 凭据（tp- 前缀，与按量付费 sk- 不通用）
export FDE_SCOPE_MIMO_API_KEY="tp-..."
# 可选：默认已是 https://token-plan-cn.xiaomimimo.com/v1 与 mimo-v2.5-pro
export FDE_SCOPE_MIMO_BASE_URL="https://token-plan-cn.xiaomimimo.com/v1"
export FDE_SCOPE_MIMO_MODEL="mimo-v2.5-pro"
```

所有 LLM 入口都是**失败自动回退规则路径**——网络错误、坏 JSON、无 key 都不会中断流水线：

| 入口 | 启用方式 | 效果 |
|---|---|---|
| 语料合成 | `fde-scope corpus --input … --llm` | 每个缺口类别由 LLM 生成真实感样本（参考种子风格，JSON 输出） |
| 质量评分 | 同上（合成后自动） | LLM 对样本打 1-5 质量分，规则分兜底 |
| Eval 基准 | `fde-scope eval --agent mimo --test-set …` | 用 MiMo 充当被评测的客服 Agent（`MiMoReplyFn`） |
| 部署清单 | `fde-scope deploy --tenant …` | manifest 携带 `llm` 段（provider/model/base_url） |
| Runbook | `fde-scope handoff <id> --llm` | 按客户/profile/阶段/SLO 生成 runbook，失败回退模板 |
| Web 控制台 | 自动 | `/api/forge` 有 key 即启用 LLM 合成，无需配置 |

`FDE_SCOPE_MIMO_API_KEY` 未设置时：`corpus --llm` / `eval --agent mimo` / `handoff --llm` 会明确报错（exit 2）提示配置，其余命令静默走规则模式。**凭据只经环境变量传递，请勿写入任何 git 文件。**

协议细节、六个接入点的回退语义、成本模型、测试策略与多 provider 扩展指南见
[`docs/llm_integration.md`](docs/llm_integration.md)；LLM 路径的加固记录与评审案例库见
[`docs/code_review_checklist.md`](docs/code_review_checklist.md)。

---

## 🧪 Tests

```bash
pip install -e ".[dev]"
pytest                 # 400 passed, 3 skipped — core + engagement + gates + skills + web + integrations + LLM mock + PawApp,
                       # no agentscope/mysql/opcua/LLM-key/QwenPaw needed (skips are integration-only);
                       # real-AgentScope runtime tests live under the `agentscope` marker (CI runs them in a dedicated job)
pytest -m agentscope   # 仅真库运行时测试（需 pip install -e ".[agentscope]"）
pytest --cov=fde_scope --cov-report=term-missing   # ~89% coverage
```

CI (GitHub Actions) runs the same suite on Python 3.11 + 3.12 with ruff lint
(`check` + `format --check`), mypy, and an sdist/wheel build — see
[`.github/workflows/ci.yml`](.github/workflows/ci.yml).

---

## 📦 Installation

```bash
pip install -e "."                 # core only
pip install -e ".[dev]"            # + pytest + web test client
pip install -e ".[web]"            # + FastAPI/uvicorn console
pip install -e ".[agentscope]"    # + real AgentScope 2.0 runtime layer
pip install -e ".[mysql]"          # + MySQL connector driver
pip install -e ".[opcua]"          # + OPC UA connector driver (asyncua)
pip install -e ".[full]"           # everything (dev + agentscope + mysql + opcua + web)
```

Requires **Python ≥ 3.11**. Entry point: `fde-scope` (or `python -m fde_scope.cli`).

---

## 📄 Documentation

- [`docs/fde_sop_full.md`](docs/fde_sop_full.md) — the 18-phase SOP, 12 anti-patterns, sources
- [`docs/manufacturing_scenario.md`](docs/manufacturing_scenario.md) — embodied-robotics factory end-to-end walkthrough
- [`docs/architecture.md`](docs/architecture.md) — layered design + data flow
- [`docs/skills.md`](docs/skills.md) — 技能沉淀系统：数据模型 / 生命周期 / 三种入口 / 双格式导出
- [`docs/llm_integration.md`](docs/llm_integration.md) — MiMo Token Plan integration: 6 touchpoints, fallback semantics, cost model, testing
- [`docs/qwenpaw_integration.md`](docs/qwenpaw_integration.md) — QwenPaw 集成：配置两层结构 / 导出与校验 / PawApp 桌面形态
- [`pawapp/README.md`](pawapp/README.md) — QwenPaw PawApp 安装/开发/API 契约
- [`docs/code_review_checklist.md`](docs/code_review_checklist.md) — repeatable review workflow + bug case library
- [`docs/agentscope_api_mapping.md`](docs/agentscope_api_mapping.md) — design-doc fiction vs. real 2.0.5 API
- [`docs/fde_playbook.md`](docs/fde_playbook.md) — on-site 72h playbook
- [`examples/README.md`](examples/README.md) — CSV cold-start walkthrough (quickstart data included)

---

## 🗺 Roadmap

- [x] OPC UA 真实工业 IO（asyncua 驱动，mock 测试覆盖）
- [x] Category-stratified train/eval/test split（`CorpusReport.splits`）
- [ ] MQTT-Sparkplug 真实 broker IO（paho-mqtt）
- [ ] rosbag2 真实回放（rosbags）
- [x] Real LLM corpus synthesis & quality scoring (drop-in behind existing signatures)
- [x] 小米 MiMo Token Plan 接入（`fde_scope/llm.py`，env 配置，失败回退规则）
- [x] Skill 沉淀库（四类分类 + 生命周期 + AgentScope/QwenPaw 双格式导出）
- [x] 多 Agent 拓扑（SubAgentTemplate 蓝图 + manifest agents 段）
- [x] QwenPaw 集成（qwenpaw export/validate + PawApp 桌面应用，真机验证通过）
- [ ] Real AgentScope agent startup (Docker workspace + model wiring)
- [ ] Full Zammad / Salesforce / MES / Historian HTTP/SQL implementations
- [ ] AgentScope Studio (npm `@agentscope/studio`) integration

---

## 📄 License

MIT.
