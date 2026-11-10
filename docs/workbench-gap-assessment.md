# FDE Scope 工作台差距评估

> **评估日期**：2026-11-03 · **性质**：只读评估快照，不是路线图
> **配套计划**：[`workbench-development-plan.md`](workbench-development-plan.md)
> **评估范围**：工程质量 + 三个使用场景（FDE 入门学习 / 查阅 skills / 现场履约）
> **方法**：本机实测 + 代码/文档只读核对。文中每个数字都标注了来源；推断项单独标注。

---

## 0. 一句话结论

**这是一个工程纪律罕见、定位清晰，但“最后一公里”尚未闭环的 alpha 项目。**

- 作为**开源单机工作台**：约 **7.6 / 10**。
- 作为**企业可采购产品**：约 **4.5 / 10**。
- 三个目标场景的完成度：**入门学习 ~70% · 查阅 skills ~60% · 现场履约 ~70%**。
- 它自己的判断依然准确：**“一个有真实引擎的 showroom”**。引擎是真的，展示层与客户案例仍是 mock。

---

## 1. 实测基线

| 项目 | 实测结果 |
|---|---|
| 源码规模 | `fde_scope/` 约 **30,900 行**、117 个 Python 文件；测试约 **19,400 行** |
| 测试用例 | **1268 条收集**，全量 **exit 0**，4 条环境门控跳过（MySQL / OPC UA / MQTT / rosbag2） |
| 测试时长 | 本机约 **7 分钟**（主要耗时在 course verifier 为每个 lab 起 CLI 子进程） |
| 提交历史 | 144 commits，**单人维护**，首提交 2026-08-04，最近 2026-10-29 |
| 版本/发布 | `0.1.0` Alpha；**0 个 git tag，未上 PyPI** |
| 运行环境 | macOS Darwin 25.6.0 · Python 3.12.13 · agentscope 2.0.8 · ruff 0.16.8 |
| 零 key 链路 | `connect` + `corpus` + `course doctor` 实跑通过 |
| 契约守卫 | `tests/test_architecture_guard.py` **11 passed** |
| 文档目录检查 | skills-catalog / github-resources 两个脚本均通过 |

**这是一个真实可运行的系统，不是只有 README 的项目。**

---

## 2. 真正的优势

### 2.1 门禁引擎是谓词，不是勾选框
`Engagement.advance()` 每次无条件重评当前阶段全部门禁，过期通过记录不放行；`force=True` 仍评估、仍记录（`fde_scope/engagement/engagement.py:84`）。这是项目最有价值的设计。

### 2.2 分层与可选依赖干净
核心层（connectors / corpus / eval）零 agentscope 顶层依赖，`pip install -e ".[dev]"` 可跑；deploy / flywheel 延迟导入。对“客户机器不能装一堆东西”的现场场景，这是正确取舍。

### 2.3 安全边界可测
- token 只从环境变量读，中间件逐请求按 `scope["server"]` 判回环/非回环（`fde_scope/web/auth.py:233`）；
- `fsutil.safe_child()` 统一收口路径穿越；
- `atomic_write_text` + AST 守卫禁止裸写（`tests/test_architecture_guard.py:222`）；
- `SECURITY.md` 明确区分“代码强制什么”和“有意不做什么”。

### 2.4 文档纪律罕见
`AGENTS.md` 不变量、`CHANGELOG.md` release gate、逐项差距修复状态、课程漂移守卫、路由数守卫——这套“可测量的诚实”是项目真正的品牌资产。

### 2.5 测试不是摆设
177 条 web 测试、62 条课程判分测试、49 条 skills、44 条 gates、22 条 auth；课程判分真的起子进程跑学生要敲的 CLI。

---

## 3. 实测发现的问题

### 3.1 P0：当前 CI 是红的（4 处，均可复现）

| 检查 | CI 命令 | 实测结果 |
|---|---|---|
| Lint | `ruff check .` | **3 errors (UP031)**：`GTM/dist_stage.py:57,58,82` |
| Format | `ruff format --check .` | **2 files would be reformatted**：`GTM/dist_stage.py`、`fde_scope/web/course.py` |
| Type | `mypy fde_scope` | **2 errors**：`fde_scope/web/sop.py:107`、`fde_scope/web/course.py:423` |
| Coverage | `pytest --cov=fde_scope --cov=pawapp/backend` | **89.83% < fail_under 90** |

覆盖率归因：

| 范围 | 语句 | 覆盖率 |
|---|---|---|
| `fde_scope/` 单独 | 9,605 | **90.82%** |
| `pawapp/backend/main.py` | 272 | **55%**（122 未覆盖） |
| 合计 | 9,877 | **89.83%** |

**只差 0.17 个百分点**。前三项是机械修复；第四项补 `pawapp/backend` 的测试即可过线。

> 注意：AGENTS.md 回归锚写的是 `ruff check fde_scope tests`，它是绿的；但 CI 和 `make lint` 跑的是 `.`，因此红。这个口径差本身值得记一笔。

### 3.2 P1：文档漂移，正好打在项目最强的主张上

| 文档 | 写的 | 实际 |
|---|---|---|
| `README.md:795`、`docs/features.md:234` | “101 页 skill 手册库” | **122 页**（catalog README 与检查脚本均为 122） |
| `docs/api-reference.md:326,328,459` | “69 条 served 路由” | **83 条 served**（`app.openapi()` 实测），声明 86 条 |
| `docs/commercialization-gap-analysis.md:134` | “PyPI 包：可用，0.1.0 Alpha” | README 自己写 **PyPI 404、未发布** |
| README 覆盖率 | §Tests 写 ~89%，P3 记录写 92.08% | 本次实测 **89.83%**（含 pawapp） |
| `docs/commercialization-gap-analysis.md` 部署表 | “36 路由” | 86 声明 / 83 served |

守护测试只覆盖了它自己选中的 11 处声明，没有读 README 的 101/122、api-reference 的 69/83，也没有读覆盖率数字。

### 3.3 P1：语料引擎的合成数据存在质量与泄漏风险

用 quickstart 的 20 行真实 CSV 实跑：

```
20 real + 395 synthetic = 415 total   → 合成占 95%
```

规则版 synthesizer 是“种子文本 + 开头语 + 结尾语 + 同义词替换”（`fde_scope/corpus/synthesizer.py:1`）。跨 split 相似度实测：

| split | 在 train 中存在 ≥0.90 近重复 | ≥0.85 |
|---|---|---|
| eval（41 条） | **12 / 41（29%）** | 23 / 41（56%） |
| test（42 条） | **15 / 42（36%）** | 27 / 42（64%） |

根因：合成发生在 dedup **之后**（`fde_scope/corpus/pipeline.py:85-110`），split 只是随机打乱（同文件 `_split`），没有按 provenance / template family 分层。**不接 LLM 时，默认 eval 指标会偏乐观。**

建议：合成后再 dedup；默认禁止 synthetic 进入 eval/test；给 synthetic ratio 设上限；报告分离“真实覆盖率”和“合成后覆盖率”。

### 3.4 P1：分发与商业化未闭环

- **无 tag、无 PyPI、无 release**（README 自述 PyPI 404）。
- **MIT vs “双许可”未定**：`pyproject.toml:11` 是 MIT，路线图 P4 又写“开源核心 + 企业版功能开关”，且自己标注“⚠️ 未定，需维护者拍板”。
- **客户案例 100% mock**：10 个 engagement 全部脚本生成；`PRODUCT.md` 明确“未决：无真实客户授权”。
- **没有真实 POC**：P3 遗留项“用真实连接器跑通一个 POC，替换至少一个 mock 案例”仍未完成。

### 3.5 P1：安装形态会丢内容

- **wheel**：`pyproject.toml:103` 只 force-include 了 `course-level-1`；`[tool.hatch.build.targets.sdist]` 也只含 `fde_scope` / `course-level-1` / README。**`docs/skills-catalog`（122 页手册）和 `docs/` 阅读器不随安装包发布。**
- **macOS App**：`appbuild/FDEScope.spec:31` 的 `datas` 只有 `fde_scope/templates`，没有 `_data/course-level-1`，也没有 `docs/`。按当前配置，DMG 里的 `/course` 很可能落到“缺少课程源”的提示页。**这一条是代码推断，需在构建出的 DMG 上实测 `/course` 与 `/catalog` 确认。**
- CI 的 macOS smoke 只跑 `--help`，覆盖不到这两个页面。

### 3.6 P2：结构性维护风险

| 文件 | 行数 | 说明 |
|---|---|---|
| `fde_scope/web/app.py` | **4,215** | 83 条 served 路由、HTML/CSS/JS 全在一个文件 |
| `fde_scope/cli.py` | 2,019 | 命令 + 业务逻辑混排 |
| `fde_scope/web/i18n.py` | 1,695 | 手工双语对照表 |
| `fde_scope/course/catalog.py` | 1,326 | 课程 rubric 与执行引擎耦合 |
| `pawapp/backend/main.py` | 529 | 明确“mirror fde_scope.web.app”，第二套路由实现 |

`docs/enhancement-plan.md` 已把 `app.py` 拆分、PawApp 共享层、i18n 框架化列为未完成项。

### 3.7 P2：供应链与可持续性

- `agentscope = ">=2.0.4.post1,<3"`；CI 的 `uv.lock` 钉在 **2.0.4.post1**，本机实际 **2.0.8**。窗口两端都有人测是加分，但用户 `pip install` 会拿到未来 2.x，CI 不会测。
- 上游 2.0.5 已改过一次权限语义（read-only fast path），这类兼容税会长期存在。
- 144 commits 全部来自一人；维护面覆盖 18 阶段 / 10 门禁 / 86 路由 / 课程 / 本体 / PawApp。**bus factor 是当前最大的非技术风险。**

---

## 4. 三场景差距

### 4.1 FDE 入门学习（约 70%）

**已经能用：**

- **26 章、15,096 行**的 Level-1 教材（`course-level-1/`）。
- **8 天实验、91 个机器判分项 + 9 个人工项**；判分真的跑学生要敲的 CLI（`fde_scope/course/verifier.py`）。
- `course doctor` 开工前自检；零 key 路径可跑通。
- 浏览器阅读页有目录、全文搜索、阅读进度、练习勾选、逐日判分面板。
- `/certification` 是认证市场调研；`/showcase` 是 D8 作品集本地审计。

**差距：**

| # | 差距 | 证据 / 影响 | 优先级 |
|---|---|---|---|
| L1 | 安装是“第一堵墙” | README 自述无一条命令安装路径；PyPI 404；无浏览器内沙箱 | P0 |
| L2 | 学习状态不是资产 | 阅读进度/练习勾选只在 `localStorage`（`web/course.py:608`），按章不按节；换设备归零；lab 结果不落盘 | P1 |
| L3 | 检索粒度太粗 | 整章命中/隐藏（`courseFilter`），无节级结果/高亮；整课渲染约 **944KB** 单页 | P1 |
| L4 | 英文学习者用不了正文 | `/en/course` 只翻译导航与标题，26 篇正文仍为中文 | P2 |
| L5 | 安装形态丢内容 | wheel 有课程但无 docs/catalog；DMG 按 spec 连课程也未打包（待实测） | P0 |
| L6 | 没有“入门 → 进阶”路径 | 8 天线性的；无前置知识图、无 Level 2、无结业凭证 | P2 |

**最小补齐：** PyPI + `fde-scope demo`；进度与 lab 历史落盘；节级搜索 + 分章懒加载；wheel/DMG 同时打包课程、docs、catalog。

### 4.2 查阅 skills（约 60%）

**已经能用：**

- **122 页** skill 手册库，统一六段模板，带 ✅/📦 状态与 Zone A–D 分类（`docs/skills-catalog/README.md:4`）。
- 生成式单文件门户 **652KB**，离线可开、客户端全文搜索、中英双壳。
- 18 个阶段各挂 **2–5 页**相关手册（`fde_scope/engagement/catalog_map.py`），引导 tab 可直接点入。
- 个人技能库有 CRUD、draft→published→archived、facets、ontology 概念扩展检索、双格式导出。

**差距：**

| # | 差距 | 证据 / 影响 | 优先级 |
|---|---|---|---|
| S1 | 两个“skills”不是一个东西 | 手册库是第三方 agent 工具（Firecrawl/drawio/pdf…）；个人库是现场经验；入口与命名冲突 | P0 |
| S2 | 两套检索互不相通 | 手册库是静态站、无 JSON API；个人库是内存子串匹配、上限 50（`skills/service.py`） | P0 |
| S3 | 装完就看不到 | catalog 不进 wheel、不进 DMG、不进 sdist | P0 |
| S4 | 只能读，不能做 | 无“复制命令 / 插入 journal / 插入 runbook / 试用”动作 | P1 |
| S5 | 没有新鲜度与归属 | 无负责人、复核日期、使用次数、评分；✅/📦 依赖 `~/.qoder` 对账 | P2 |
| S6 | 正文仍是中文 | 英文门户只翻译壳、分类、一句话简介 | P2 |

**最小补齐：** 构建期生成 `catalog_index.json` 随包发布；`/api/catalog/search` + 统一搜索；手册页加“复制命令 / 插入 engagement”；统一命名。

### 4.3 现场履约（约 70%）

**已经能用：**

- 12 个详情 tab：概览 / 引导 / SOP / Gates / Context / Corpus / KPI / 现场记录 / 证据 / 交接 / 审计 / 复盘；另有 Skills、Deploy、Ontology、Ops 视图。
- 引导模式把 18 阶段的交付物、门禁阻塞项、下一步动作翻成可执行建议（`engagement/guided.py`），并能生成项目目标的任务清单（`web/guided_api.py:80`）。
- Context 卡片覆盖现场、干系人、成功标准、安全姿态、SLO。
- Journal 三类记录可沉淀为技能；证据上传带 sha256 + 时间戳；runbook / 交接包 / SLO / 监控模板可生成。
- 复盘能重放审计流，算阶段停留与 SLA 时钟；分享链接可只读查看并签收。

**差距：**

| # | 差距 | 证据 / 影响 | 优先级 |
|---|---|---|---|
| F1 | 移动端与离线缺失 | 无 PWA / service worker / manifest；需本机起服务；Android 是 debug WebView demo（`android/README.md` 自述不可上架） | P0 |
| F2 | 采集能力太窄 | Journal 只有文本（`engagement/context.py:84`）；无照片/语音/附件/OCR；证据上传是独立流程 | P0 |
| F3 | 没有“今天”视图 | 当前阶段、下一门禁、任务、SLA 剩余、下次拜访散在各 tab；SLA 只在事后复盘计算 | P1 |
| F4 | 行动项不成体系 | `guided_plan` 只是单目标清单；无负责人、截止日、优先级、跨 engagement 收件箱 | P1 |
| F5 | 每阶段交付物未全打通 | 有 runbook/交接包/SLO/监控；缺 brief(D2)、数据体检(D3)、验证记录(D5)、培训材料(D7) 的一键生成 | P1 |
| F6 | 客户闭环单向 | 分享只读 + ack；无逐项评论/确认；无电子签（文档已诚实说明） | P1 |
| F7 | 协作与数据安全 | 单 token、单数据根、进程内锁；明文 PII；无静态加密；无 workspace 导出/导入 | P2 |
| F8 | 控制台与 CLI 不对齐 | 连接器/凭据/connect/deploy-serve 仍以 CLI+env 为主；Ops 只能看状态，不能测连通性 | P1 |
| F9 | 没有全局搜索 | engagement/journal/skills/docs/catalog 各自为政 | P1 |

**最小补齐：** PWA + 现场模式 + 快速采集；Today 仪表盘 + 任务 due date + 实时 SLA；每阶段交付物生成；workspace 导出/导入；命名 operator token。

---

## 5. 分维度评分

| 维度 | 分数 | 理由 |
|---|---|---|
| 产品概念与定位 | **8.5 / 10** | 全生命周期 FDE SOP + 工业 overlay，差异化真实存在 |
| 架构与分层 | **8.5 / 10** | 可选依赖、延迟导入、单一数据根、门禁引擎干净 |
| 代码质量 | **8 / 10** | 类型/文档/命名整体优秀；巨石文件与手工 i18n 拉低 |
| 测试与守卫 | **8 / 10** | 1268 条、行为级、契约守卫强；CI 当前红、套件偏慢 |
| 安全（单机定位） | **8.5 / 10** | 认证、路径、原子写、凭据处理都有代码与测试 |
| 安全（企业多租户） | **3 / 10** | 单 token、无 RBAC/SSO、无 TLS、审计非签名（明确 out of scope） |
| 文档 | **8.5 / 10** | 质量极高；存在可测量漂移 |
| 商业化/可运维 | **4 / 10** | 无发布、无真实 POC、license 边界未定、mock 数据 |
| 可持续性 | **6 / 10** | 单人维护 + 宽表面，bus factor 风险高 |

**综合：开源 alpha 7.6 / 10；企业产品 4.5 / 10。**

---

## 6. 附录：实测命令与结果

```bash
# 全量测试（exit 0；1268 collected；4 skipped）
.venv/bin/python -m pytest -q

# CI 的四条检查（前三条 exit 1）
.venv/bin/python -m ruff check .                 # 3 errors: GTM/dist_stage.py:57,58,82
.venv/bin/python -m ruff format --check .        # 2 files: GTM/dist_stage.py, fde_scope/web/course.py
.venv/bin/python -m mypy fde_scope               # 2 errors: web/sop.py:107, web/course.py:423
.venv/bin/python -m pytest --cov=fde_scope --cov=pawapp/backend --cov-report=term
                                                 # 89.83% < 90; fde_scope alone 90.82%; pawapp 55%

# 契约守卫（11 passed）
.venv/bin/python -m pytest tests/test_architecture_guard.py -q

# 零 key 链路
.venv/bin/python -m fde_scope course doctor
.venv/bin/python -m fde_scope connect --type csv --source examples/quickstart_csv/sample_tickets.csv
.venv/bin/python -m fde_scope corpus --input examples/quickstart_csv/sample_tickets.csv \
  --config fde_scope/templates/corpus_config.yaml --out /tmp/corpus.html

# 合成质量分析（quickstart 20 行真实数据）
# 20 real + 395 synthetic = 415 total
# eval: 12/41 在 train 中有 >=0.90 近重复；test: 15/42
```

**数据口径提醒**：本文数字是 2026-11-03 的快照。代码一变，覆盖率、路由数、测试数都可能漂移；发布前请重跑上面的命令，不要引用本文数字作为“当前值”。