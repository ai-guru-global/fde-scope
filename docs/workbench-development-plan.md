# FDE Scope 工作台开发计划（2026-11-03）

> **配套评估**：[`workbench-gap-assessment.md`](workbench-gap-assessment.md)
> **计划周期**：12 周（按单人、5 天/周估算；兼职按比例拉长）
> **目标**：把项目从“有真实引擎的 showroom”变成“FDE 每天打开的工作台”
> **覆盖场景**：入门学习 · 查阅 skills · 现场履约

---

## 0. 原则与非目标

### 原则

1. **先收口，再扩面。** 本周期不新增阶段、不新增连接器、不新增课程章节，只补“最后一公里”。
2. **每个任务都有可复跑的验收命令。** 不接受“看起来好了”。
3. **可测量的诚实。** 新文档里出现的数字必须有出处或守卫；推断项明确标注“待实测”。
4. **单人节奏。** 同时只开一个里程碑；每周五出一个可安装的候选版本。
5. **不破坏七条不变量。** 门禁实时重评、ID 服务端生成、凭据只走 env、原子写、规则即权限、AgentScope 窗口 measured、Web 路由认证。

### 非目标（本周期明确不做）

- 多租户 / RBAC / SSO（需要单独架构决策）。
- Android 上架、Windows 桌面（先做 PWA，再评估）。
- Level 2 课程、更多 catalog 页面。
- 新连接器、新 ontology 功能。
- 在线证书核验、真实电子签后端（先做逐项确认与证据链）。
- 自动训练流水线。

---

## 1. 里程碑总览

| 里程碑 | 周期 | 交付结果 | 退出标准（Exit Criteria） |
|---|---|---|---|
| **M0 止血与发布** | Week 1 | CI 全绿，`v0.1.0` 可安装 | 四条回归锚全绿；覆盖率 ≥90；干净 venv 装 wheel 后 `/course` 可用 |
| **M1 安装与入门闭环** | Week 2–3 | 装完就能学、进度不丢 | `pip install` + `fde-scope demo` + 浏览器完成 D1；进度重启后仍在 |
| **M2 技能检索闭环** | Week 4–5 | 一个搜索框查全站 | catalog / 个人技能 / 文档 / SOP 同框检索；安装态可查 122 页 |
| **M3 现场工作台** | Week 6–9 | 手机能采集、离线能看 | 飞行模式完成“拍照 + 记录 + 看 Today”，回网后同步 |
| **M4 交付物与客户闭环** | Week 10–11 | 每阶段产出可生成、客户可确认 | 一个 engagement 一键生成 D2/D3/D5/D7 四件；客户可逐项确认 |
| **M5 团队与硬化** | Week 12+ | 小团队可用、可备份、可气隙 | 命名 token 进审计；export/import 往返；离线包安装成功 |

---

## 2. M0 · 止血与发布（Week 1，约 4 天）

### 目标

让 `master` 重新变成“可发布”的状态。当前 CI 四处红；不修完，后面所有分发都无从谈起。

### 任务

| ID | 任务 | 主要改动 | 验收 | 估时 |
|---|---|---|---|---|
| M0-01 | 修 lint/format | `GTM/dist_stage.py:57,58,82` 的 UP031；重排 `GTM/dist_stage.py`、`fde_scope/web/course.py` | `ruff check .`、`ruff format --check .` 均 exit 0 | 0.5d |
| M0-02 | 修 mypy | `fde_scope/web/sop.py:107`、`fde_scope/web/course.py:423` 的返回类型注解 | `mypy fde_scope` exit 0 | 0.25d |
| M0-03 | 覆盖率过线 | 优先补 `pawapp/backend/main.py` 的测试（122 未覆盖，补到 ~70% 即可过线）；不改 `fail_under` | `pytest --cov=fde_scope --cov=pawapp/backend` ≥ 90% | 1d |
| M0-04 | 修文档漂移 | README/features 101→122；api-reference 69→83；gap-analysis PyPI 行；README 覆盖率口径 | `grep` 不再命中旧数字；新增守卫 | 0.75d |
| M0-05 | 加文档计数守卫 | 把 README / api-reference 的可计数声明纳入 `tests/test_architecture_guard.py` 或独立守卫 | 人为改坏任一数字 → 测试红 | 0.5d |
| M0-06 | 发布 0.1.0 | `CHANGELOG` 收口；`python -m build`；干净 venv 安装；`git tag v0.1.0`；PyPI（或先 TestPyPI） | 干净 venv 中 `fde-scope --version`、`/console`、`/course` 正常 | 1d |

### Week 1 逐日

- **Day 1**：M0-01 / M0-02，跑四条回归锚。
- **Day 2**：M0-03，补 pawapp 测试，确认覆盖率 ≥90%。
- **Day 3**：M0-04 / M0-05，修文档 + 加守卫。
- **Day 4**：M0-06，构建、干净 venv 冒烟、tag、发布。
- **Day 5**：缓冲 + 写 release notes。

### 出口标准

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy fde_scope
.venv/bin/python -m pytest --cov=fde_scope --cov=pawapp/backend   # >= 90
.venv/bin/python -m pytest -m agentscope
```

全部 exit 0；且干净 venv 安装 wheel 后 `/api/health`、`/console`、`/course` 返回 200。

---

## 3. M1 · 安装与入门闭环（Week 2–3，约 7 天）

### 目标

让一个没有仓库、没有 uv 的人，用一条命令装好、看到一个 demo、完成第一天的 lab，并且下次打开时进度还在。

### 任务

| ID | 任务 | 主要改动 | 验收 | 估时 |
|---|---|---|---|---|
| M1-01 | 安装包带上内容 | `pyproject.toml` force-include `docs/skills-catalog/site` + 精选 docs（README/user-guide/api-reference/onboarding/features/architecture）；sdist 同步；更新 wheel 体积累计说明 | 干净 venv 装 wheel 后 `/catalog` 与 `/docs/user-guide` 有内容，不是提示页 | 1d |
| M1-02 | DMG 带上内容与冒烟 | `appbuild/FDEScope.spec` 的 `datas` 增加 `_data/course-level-1`、`docs/skills-catalog/site`、精选 docs；`macos-smoke` 增加 `/course`、`/catalog` 断言 | 构建出的 DMG 中两页非空 | 1d |
| M1-03 | `fde-scope demo` | 新 CLI 命令：播种一个明显虚构的 demo engagement + 3 条技能 + 一份 corpus；打印 10 分钟走查；`--reset` | 空数据根执行后 `/console` 有 demo，且命令可重复执行 | 1.5d |
| M1-04 | 学习进度落盘 | 新增 `fde_scope/course/progress.py`；`GET/PUT /api/course/progress`；课程 JS 优先服务端、离线回退 localStorage；原子写 | 清浏览器缓存/换浏览器后进度仍在；断网时仍可勾选 | 2d |
| M1-05 | Lab 历史 | `run_lab` 结果落盘（day、时间、通过数/总数、失败项 id）；课程页显示最近一次与历史 | 连跑 D3 两次，历史有两条 | 1d |
| M1-06 | 节级搜索 + 分章加载 | 构建期生成节级索引；搜索返回节级结果与锚点；课程页支持按章懒加载 | 搜索“门禁”能列出具体小节并可跳转；首屏加载量明显下降 | 1.5d |

### 出口标准

- 干净 venv：`pip install fde-scope && fde-scope demo && fde-scope web`，浏览器完成 D1 判分。
- 清空 localStorage 或换浏览器，阅读进度与练习勾选仍在。
- `/en/course` 的正文语言限制在页面显著位置说明（本周期不翻译正文）。

---

## 4. M2 · 技能检索闭环（Week 4–5，约 8 天）

### 目标

一个搜索框，同时查到：手册页、我的技能、文档、SOP；并且能把查到的内容变成动作。

### 任务

| ID | 任务 | 主要改动 | 验收 | 估时 |
|---|---|---|---|---|
| M2-01 | catalog 索引 | 构建期生成 `catalog_index.json`（slug/title/zone/phases/gates/status/summary_zh/en/url）；随 wheel 发布 | 索引条数 = 122；与 README 行数一致 | 1d |
| M2-02 | catalog API | `GET /api/catalog/search?q=&phase=&gate=&status=`；只读、认证规则与其它读路由一致 | 按 phase=connect 能返回 5 页；未知参数 422 | 1d |
| M2-03 | 统一搜索 API | `GET /api/search?q=` 聚合 catalog / skills / docs / SOP；返回类型、标题、摘要、深度链接；分组 + 排序 | 搜 `opcua` 同时命中手册页、个人技能、文档 | 1.5d |
| M2-04 | Ctrl+K 搜索 UI | 控制台与课程页共用搜索面板；键盘可达；移动端全屏 | 键盘打开、Esc 关闭、回车跳转 | 1.5d |
| M2-05 | 技能库检索升级 | 分词、字段权重（title > tags > body）、分页；保留子串兜底 | 相关度排序有测试；50 条上限改为分页 | 1.5d |
| M2-06 | 动作化 | 手册页“复制命令”；“插入到当前 engagement 的 journal / runbook”；个人技能“引用到 journal” | 插入后原子落盘并进审计 | 1d |
| M2-07 | 命名与 i18n | UI/文档统一为“工具手册”vs“现场技能库”；i18n 键补齐 | 中英两版无遗漏；i18n 漂移守卫绿 | 0.5d |

### 出口标准

- 安装态（wheel）能打开 `/catalog` 并搜索。
- 一个搜索框覆盖四类内容；结果可键盘导航。
- 从手册页一次操作把命令/模板带进当前 engagement。

---

## 5. M3 · 现场工作台（Week 6–9，约 14 天）

### 目标

手机/平板在现场能打开、能采集、能看“今天该干什么”；断网不阻塞。

### 任务

| ID | 任务 | 主要改动 | 验收 | 估时 |
|---|---|---|---|---|
| M3-01 | PWA 壳 | `manifest.webmanifest`、`sw.js`、离线缓存 app shell 与静态资源；版本化缓存；安装提示 | Lighthouse PWA 可安装；断网打开显示缓存壳 | 2d |
| M3-02 | 现场模式 | ≤640px 的极简布局：采集 / 门禁 / 今天 / 下一件事；大按钮、单手可达 | 375px 宽度下四个动作首屏可见 | 2d |
| M3-03 | 快速采集 | `JournalEntry` 增加 `attachments: list[str]`；图片/语音/文件上传；手机 `<input capture>`；复用 evidence 存储与 sha256 | 手机拍照 + 一句话 → 一条 journal；文件在 `.fde_scope/uploads/` | 3d |
| M3-04 | Today API/UI | `GET /api/today`：当前阶段、下一门禁与 blockers、任务、SLA 剩余、最近 journal；SLA 从 audit + context 实时算 | 控制台首屏显示“今天”；SLA 随推进变化 | 2d |
| M3-05 | 任务模型 | 在 `EngagementContext` 增加 `tasks`（title/owner/due/status/phase），向后兼容默认空；API + UI；跨 engagement Inbox | 旧 engagement JSON 可加载；任务可增删改查 | 2d |
| M3-06 | Workspace 导出/导入 | `fde-scope export --out bundle.tar.gz` / `import`；含 engagements/skills/reports/audit；排除凭据；原子写 | 导出→新数据根导入→内容一致；损坏包明确报错 | 2d |
| M3-07 | 离线验收脚本 | 一份可复跑的现场演练脚本（飞行模式、拍照、恢复网络） | 每步有断言或截图证据 | 1d |

### 出口标准

- 飞行模式下：能打开 PWA、看 Today、拍照记录；恢复网络后记录同步到服务端。
- 两个设备之间用 export/import 迁移 workspace，内容不丢。
- 375px 宽度下采集流程 ≤3 步完成。

---

## 6. M4 · 交付物与客户闭环（Week 10–11，约 8 天）

### 目标

每个阶段的交付物能从 Context 一键生成；客户能对交付物逐项确认，而不是只在最后签一个 ack。

### 任务

| ID | 任务 | 主要改动 | 验收 | 估时 |
|---|---|---|---|---|
| M4-01 | 交付物生成器 | 新增 `fde_scope/engagement/deliverables.py` + 包内模板：客户 brief(D2)、数据体检(D3)、验证记录(D5)、培训材料(D7)；CLI + API | 一个 engagement 生成四件，内容来自 context | 3d |
| M4-02 | 客户逐项确认 | 分享页对每个交付物/门禁显示“确认/有异议”；写入审计（actor=share token 前缀） | 客户确认后审计有事件；状态可见 | 2d |
| M4-03 | 交付物 PDF/哈希 | 生成 PDF 或 Markdown 导出；文件 sha256 + 时间戳入审计；文档明确“不是数字签名” | 导出文件哈希可复算 | 1d |
| M4-04 | 连接测试 | 控制台“测试连接”按钮：读 env 配置，发一次只读探测；不存凭据、不回显值 | 成功/失败明确；日志无凭据 | 1d |
| M4-05 | 文档与测试 | 更新 user-guide / api-reference / onboarding；补 web/CLI 测试 | 文档链接无断链；守卫绿 | 1d |

### 出口标准

- 从 demo engagement 一键生成 D2/D3/D5/D7 四件交付物。
- 客户通过分享链接逐项确认，审计可导出。
- 所有新增能力都有 CLI 与 Web 两条路径（或明确只支持一条并写清）。

---

## 7. M5 · 团队与硬化（Week 12+，约 10 天）

### 任务

| ID | 任务 | 主要改动 | 验收 | 估时 |
|---|---|---|---|---|
| M5-01 | 命名 operator token | `FDE_SCOPE_API_TOKENS="alice:tok1,bob:tok2"`；中间件解析并注入 actor；旧单 token 兼容 | 两人操作在审计中可区分；旧配置不破 | 1.5d |
| M5-02 | 备份/恢复 | `fde-scope backup` / `restore`；校验和；文档写清保留策略 | 备份→清空→恢复，engagement/skills/audit 完整 | 1.5d |
| M5-03 | 静态加密/OS 指引 | 至少提供 OS 级加密指引；评估字段级加密（PII in engagement JSON） | 文档与验收清单；不承诺未实现的能力 | 1.5d |
| M5-04 | 离线/气隙包 | `scripts/build_offline_bundle.sh`：按 extras 下载 wheelhouse；离线安装文档 | 无网络机器安装成功并跑 `course doctor` | 2d |
| M5-05 | 英文课程正文 | 按章增量翻译；每章标注“译文/原文”来源 | 至少 8 章完成；导航不混语言 | 持续 |
| M5-06 | Windows 形态 | 先做 PWA/浏览器安装；Windows 打包只做 spike，不承诺 | spike 结论写入 docs | 2d |

---

## 8. 全量任务优先级总表

| 优先级 | ID | 任务 | 依赖 | 估时 |
|---|---|---|---|---|
| P0 | M0-01/02 | lint + mypy 止血 | — | 0.75d |
| P0 | M0-03 | 覆盖率过线 | — | 1d |
| P0 | M0-04/05 | 文档漂移 + 守卫 | — | 1.25d |
| P0 | M0-06 | 发布 0.1.0 | M0-01..05 | 1d |
| P0 | M1-01/02 | wheel/DMG 带内容 | M0-06 | 2d |
| P0 | M1-03 | `fde-scope demo` | M0-06 | 1.5d |
| P0 | M3-01/02/03 | PWA + 现场模式 + 快速采集 | M1-02 | 7d |
| P1 | M1-04/05 | 进度与 lab 历史 | M1-01 | 3d |
| P1 | M1-06 | 节级搜索/分章加载 | M1-04 | 1.5d |
| P1 | M2-01..05 | catalog 索引 + 统一搜索 | M1-01 | 6.5d |
| P1 | M2-06/07 | 动作化 + 命名 | M2-03 | 1.5d |
| P1 | M3-04/05 | Today + 任务模型 | M3-03 | 4d |
| P1 | M3-06/07 | export/import + 离线验收 | M3-03 | 3d |
| P1 | M4-01..05 | 交付物 + 客户确认 | M2-03 | 8d |
| P2 | M5-01..06 | 团队/备份/气隙/英文/Windows | M3/M4 | 10d+ |

**总计约 51 人日**（≈10–11 周；12 周留缓冲）。

---

## 9. 第一个 5 个 PR（建议顺序）

1. `chore(ci): green ruff/format/mypy`（M0-01/02）
2. `test(pawapp): lift coverage to the 90% gate`（M0-03）
3. `docs: fix counted claims + add drift guards`（M0-04/05）
4. `build: ship catalog/docs in wheel and DMG`（M1-01/02）
5. `feat(cli): add fde-scope demo`（M1-03）

前三个 PR 都是小改动、低风险，先让主干可信；后两个直接改善“装完能不能用”。

---

## 10. 发布门禁（每个里程碑都要跑）

```bash
# 1. 测试与契约
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/test_architecture_guard.py -q
.venv/bin/python -m pytest -m agentscope

# 2. 风格与类型
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy fde_scope

# 3. 覆盖率
.venv/bin/python -m pytest --cov=fde_scope --cov=pawapp/backend --cov-report=term

# 4. 干净 venv 安装冒烟
python -m venv /tmp/fde-smoke && /tmp/fde-smoke/bin/pip install dist/*.whl
FDE_SCOPE_HOME=/tmp/fde-smoke-home /tmp/fde-smoke/bin/fde-scope demo
FDE_SCOPE_HOME=/tmp/fde-smoke-home /tmp/fde-smoke/bin/fde-scope web --port 8099 &
curl -sf http://127.0.0.1:8099/api/health
curl -sf http://127.0.0.1:8099/course        >/dev/null
curl -sf http://127.0.0.1:8099/catalog/      >/dev/null
curl -sf http://127.0.0.1:8099/docs/user-guide >/dev/null

# 5. 课程自检
.venv/bin/python -m fde_scope course doctor
```

任一项红，不 tag、不发布。

---

## 11. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| 单人维护、周期被拉长 | 里程碑延期 | 每周五出候选版；M0/M1 不允许插队；范围变更写入 backlog，不夹带 |
| `app.py` 巨石导致改动冲突 | 迭代变慢 | 本周期只做“接触即拆”：新功能进独立 router（如 `web/field_api.py`、`web/search_api.py`），不强制大重构 |
| 打包体积增长（catalog 652KB×2 + docs） | 安装包变大 | 只带 `site/` 与精选 docs；catalog 正文按需；在 release notes 记录体积 |
| Service Worker 缓存旧页面 | 用户看到旧版 | 缓存版本号随 build 注入；`skipWaiting` + 刷新提示 |
| 任务/附件 schema 变更 | 旧 engagement 加载失败 | pydantic 默认值；加一条“旧 JSON 可加载”的回归测试 |
| AgentScope 上游变更 | 真库测试红 | 保持 `uv.lock`；不主动放宽窗口；升级走逐版本矩阵 |
| 客户数据安全预期被拉高 | 信任风险 | `SECURITY.md` 明确“单机边界、明文存储、非签名审计”；M5 只做指引与备份，不夸大为加密产品 |
| 文档再次漂移 | 品牌资产受损 | M0 的计数守卫必须进 CI；新增数字必须带出处或守卫 |

---

## 12. Definition of Done（每个任务）

- [ ] 代码 + 测试（含至少一个失败路径）
- [ ] 文档：用户可见变化写进 `docs/user-guide.md` 或对应文档
- [ ] 数字有出处；推断项标注“待实测”
- [ ] 四条回归锚全绿
- [ ] 不新增裸写、不新增凭据落盘、不绕过门禁
- [ ] 安装态（wheel 或 DMG）验证过，不只在本机源码树里可用

---

## 13. 一句话

**先让 `0.1.0` 真的发出去，再让人装完就能学、查得到、带得走；移动采集和统一检索是这 12 周的主线，其它都往后放。**