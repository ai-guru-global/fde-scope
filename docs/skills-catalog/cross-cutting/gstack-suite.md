# GStack 套件（53 件套 · YC CEO 的开发全流程工厂）

> 状态：✅ 已安装（Quest Marketplace 插件 `gstack` v1.58.5，作者 Garry Tan / Y Combinator，MIT）· 类型：套件档案 · FDE 位点：横切（Zone B 实施 ~ Zone D 交付）
> 本地路径：`~/.qoder/plugins/cache/qoder-marketplace/gstack/1.58.5` · 上游：https://github.com/garrytan/gstack
> 定位："我的开源软件工厂"——把 agent 变成一支虚拟工程团队（CEO/工程经理/设计师/评审/QA/安全官/发布工程师）
> ⚠️ 计数事实：**打包 53 个 skill，当前会话实际注册可调用 43 个**；未注册的 10 个（`spec`、`retro`、`qa-only`、`devex-review`、`design-shotgun`、`benchmark-models`、`ios-sync`、`open-gstack-browser`、`sync-gbrain`、`skillify`）需要时直接 Read 其 `SKILL.md` 按其流程执行。插件元数据里"23 个 skill"的说法是旧版本描述，已过时。

## 能做什么
全部以 slash-command 风格组织的 skill + 一个**快速 headless 浏览器**（自带 `bin/`，`/browse` 用它，不用其他浏览器 MCP）。按用途分八组：

| 组 | Skill | 干什么 |
|---|---|---|
| 意图→规格 | `spec` `office-hours` `autoplan` `plan-tune` | 模糊需求→可执行 spec；五阶段收敛；自动串行跑四类评审 |
| 多角色评审 | `plan-ceo-review` `plan-eng-review` `plan-design-review` `plan-devex-review` `review` `cso` | 产品/架构/设计/开发者体验四视角 + 代码评审 + 安全官（OWASP + STRIDE） |
| 设计与前端 | `design-consultation` `design-html` `design-review` `ios-design-review` `diagram` | 设计咨询、HTML 出稿、设计找 AI slop、图 |
| 浏览器与 QA | `browse` `qa` `qa-only` `scrape` `setup-browser-cookies` `open-gstack-browser` | 真浏览器打开预发/线上做 QA、抓取、cookie 复用 |
| 排障与稳定性 | `investigate` `health` `canary` `benchmark` `benchmark-models` | 根因排查、健康度、发布后金丝雀观察、性能与跨模型基准 |
| 安全护栏 | `careful` `guard` `freeze` `unfreeze` | 破坏性命令告警、目录级只读锁定（改代码前后夹住） |
| 发布与运维 | `ship` `land-and-deploy` `setup-deploy` `retro` `learn` | 检测 base 分支→跑测试→审 diff→bump VERSION→CHANGELOG→commit→push→PR；周复盘；项目学习记录管理 |
| 交付文档 | `document-generate` `document-release` `make-pdf` `landing-report` | 补文档、发布后同步文档、Markdown→出版级 PDF、落地页报告 |
| 上下文与协作 | `context-save` `context-restore` `pair-agent` `codex` `gstack-upgrade` | 跨会话上下文存取、结对、调用 Codex、自升级 |
| iOS/移动端 | `ios-qa` `ios-fix` `ios-clean` `ios-sync` | 真机 SwiftUI QA、自治修 bug、清理 DebugBridge 接线 |
| 代码检索基建 | `setup-gbrain` `sync-gbrain` `skillify` | gbrain 索引安装/同步；把成功的一次 `/scrape` 固化成常驻 browser-skill |

## 何时使用（按 FDE 阶段）
- Zone B：`spec` 收敛客户需求 → `plan-eng-review` 锁架构 → `careful`/`guard` 夹住改动范围 → `investigate` 排障
- Zone C：`health` + `canary` 做上线后观察；`cso` 做交付前 OWASP/STRIDE 审计（**给客户安全部门看的东西**）
- Zone D：`document-generate` / `document-release` / `make-pdf` 出交付物（本库已有三张单页：[document-generate](../zone-d-handoff/document-generate.md) · [document-release](../zone-d-handoff/document-release.md) · [make-pdf](../zone-d-handoff/make-pdf.md)）
- 需要真浏览器验证时：`browse` / `qa`（本地另有 [chrome-devtools](../zone-c-operationalization/chrome-devtools.md)，两者只需保留一个以免行为不一致）

**不用于**：
- **客户仓库上的 `ship` / `land-and-deploy`** —— 它们会自动 commit、push、开 PR、改 VERSION/CHANGELOG。这是给"自己产品高速迭代"设计的，在客户现场必须换成本地约定：先问、再提交，绝不自动 push
- `ios-*` 组：目标是 **SwiftUI iOS 真机**，不是 macOS 桌面打包（`docs/macos_app_packaging.md` / `appbuild/` 那条线用不上，别误触发）
- 纯数据/工业接入任务（Zone B 的 connector/corpus 工作没有对应 gstack skill，用 DuckDB/Firecrawl/HF 那一族）
- 需要严格证据链的架构建模 → [architecture-visualization-suite](architecture-visualization-suite.md)（GStack 的图偏沟通，不带 sourceRefs 门禁）

## 最佳实践
- **与 superpowers 族二选一做主线**：两套都主张强流程，同开会互相抢触发。本项目建议：**主线用 superpowers（纪律+TDD），需要某个 GStack 强项时定点调用**（`cso`、`canary`、`make-pdf`、`document-*`、`benchmark`）
- `guard`/`freeze` 在客户现场是很好用的"防手滑"开关：进入只读分析阶段前 `freeze`，改动阶段 `guard` 限定目录
- `autoplan` 会**自动替你做决策**（按 6 条决策原则串行跑四类评审）——产出要逐条复核，不能当"已通过评审"直接进交付
- `review` 与已装的 [code-review](code-review.md)（CodeRabbit）功能重叠：一个走 PR 机器人、一个走本地流程。选一个作门禁，另一个作补充，**不要两边同时要求修同一处风格问题**
- `skillify` 是这套里最被低估的一个：把一次成功的抓取/验证流程固化成常驻 skill，等于自制 fde-scope 的 `skills/` 沉淀
- 版本与污染：`gstack-upgrade` 会拉上游；本仓库不要提交 `~/.claude/skills/gstack` 生成的项目内文件（确认 `.gitignore` 覆盖 `CLAUDE.md` 之类的写入）
- 未注册的 10 个 skill 用前先 `Read .../gstack/1.58.5/<name>/SKILL.md`，按其步骤手工执行并说明来源

## 项目应用位点
- Zone D 交付物三件套的**实际来源**就是本套件（已在三张单页头部标注）
- `cso` 可补 fde-scope 目前缺的"交付前安全审计"证据：与 [security-scan](security-scan.md) 一起构成 LLM 应用 + 传统 Web 双视角
- `canary` + `benchmark` 对应 Zone C 的 SLO gate：把"上线后观察"变成有脚本支撑的动作
- `learn` 的项目学习记录机制与 fde-scope 的 flywheel（经验回流）思路一致，可作为其外部参考实现

## 相关
[using-superpowers-family](using-superpowers-family.md) · [knowledge-work-suite](knowledge-work-suite.md) · [code-review](code-review.md) · [security-scan](security-scan.md) · [document-generate](../zone-d-handoff/document-generate.md) · [investigate](../zone-c-operationalization/investigate.md)
