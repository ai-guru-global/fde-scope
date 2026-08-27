# FDE Scope 整体架构风险与质量评审

> - 产出技能：`risk-quality-reviewer`（架构可视化插件）+ `graphviz`（风险图格式）
> - 评审日期：2026-08-27 · 代码状态：master @ 0547c59（git_dirty 工作区含本地构建产物）
> - 评审范围：全仓 current-state（静态代码 / 配置 / CI / 文档 / 测试）；**无生产运行时遥测**
> - 干系人：维护者单人开发为主；风险容忍度高（Alpha 阶段本地 workbench），评审以「低成本防坍塌」为目标
> - 同族工件：[`architecture-health-report.md`](architecture-health-report.md)（文档一致性）、[`system-model.evidence.md`](system-model.evidence.md)、[`risk-map.dot`](risk-map.dot)、[`quality-scenarios.md`](quality-scenarios.md)、[`remediation-plan.md`](remediation-plan.md)

---

## 一句话结论

代码库整体健康度**高于同规模 Alpha 项目平均水平**：核心引擎（18 阶段 SOP 状态机、10 个可执行 gate、语料管线）设计严谨、失败语义显式、防御性编码一致。主要债务集中在**外围持久化一致性**（三条写入路径三种风格）、**文档↔依赖契约漂移**、以及**跨入口的数据目录假设**——三者共同构成「多人/多入口使用时才开始付费」的技术债，现在修都是小时级改动。

> **整改注记（2026-08-27 追加）**：P0 三项已全部落地并有验收证据——A1 `[full]` extra、A2 远程绑定门禁、A3 原子写收口（`fde_scope/fsutil.py`），连同验收依赖 B3（`tests/test_architecture_guard.py` 5 例 + 原子写注入/往返测试 2 例）；全部改动位于工作区未提交状态。逐项证据见 [`remediation-plan.md`](remediation-plan.md) 文末「完成记录」。本报告其余发现（R1/R5/R6/R7 及 B/C 级项）仍为待办有效项。

## 最高优先级发现（摘要）

| # | 发现 | 严重度 | 可能性 | 置信度 |
|---|---|---|---|---|
| R4 | engagement JSON **非原子直写**，崩溃窗口丢失整条记录；与打包文档承诺矛盾 | 中-高 | 低-中（本地单机） | 高 |
| R2 | Web 控制台 **零认证** 且 CLI 允许任意 `--host` 绑定，误绑后局域网可读写含 PII 数据 | 中（误用时高） | 低（默认 loopback 安全） | 高 |
| R3 | README `[full]` extra **不存在**；Makefile full 语义不一致；架构守护测试建议未落地 | 中 | 已发生 | 高 |
| R1 | 三入口共用**相对路径** `.fde_scope/`，数据落地随 CWD 漂移 | 中 | 中（多入口场景） | 高 |
| R7 | **零依赖锁定**（无 uv.lock/constraints），`agentscope>=2.0.4` 浮动 pin 上游破坏直达用户 | 中 | 中 | 高 |
| R6 | 测试盲区：跨进程并发写、打包产物 E2E 不在 CI、README 测试数字人工同步 | 低-中 | 中 | 高 |
| R5 | `web/app.py`(1244 行)/`cli.py`(1043 行) 单文件集中化 | 低（趋势恶化） | — | 高 |

---

## 架构理解摘要（current-state）

细节见既有 system-model 三件套，此处只列与风险相关的骨架事实（全部 high confidence）：

- **分层**：`connectors → corpus → deploy(延迟导入 agentscope) → eval → flywheel`，顶层 `engagement/` SOP 状态机编排，`profiles/` 场景选择器；横切 `llm.py`（可选 LLM）、`skills/`（经验库）；桌面形态 `pawapp/`。与 `docs/architecture.md` 声明一致（其健康报告 12 项中 11 项已核实一致，剩余 1 项已在 2026-08-26 后修正落地）。
- **SOP 核心**：`Engagement.advance()` 对当前阶段 gates **无条件实时重评估**（陈旧 pass 记录永不豁免）；`rollback` 带 profile 可见性防护（防止把非工业项目滚入不可推进阶段）——见 `fde_scope/engagement/engagement.py:79-117`。
- **部署蓝图诚实边界**：三层隔离（workspace/collection/PermissionEngine）在 **manifest 组装层**证实（`tenant_manager.py:156` `corpus_collection = f"corpus_{tenant.id}"`）；**真实 Agent 启动未实现**（README Roadmap `Real AgentScope agent startup` 未勾选，`TenantDeployer.stop()` 仅关闭句柄并标记 manifest）。
- **LLM 横切**：无 key 即规则路径，`MiMoClient` 显式 `LLMError`、60s 超时、响应体截断 ≤300 字符（`fde_scope/llm.py:93-147`）。

## 风险发现详表

### R4 · engagement 持久化为非原子直写（数据完整性）

- **证据**：`fde_scope/engagement/context.py:127-131` — `save()` 直接 `p.write_text(self.model_dump_json(...))` 到目标文件；对照 `fde_scope/skills/store.py:113-124` 已实现 `mkstemp + os.replace` 原子写。`fde_scope/web/app.py:75-77` `_save()` 经此路径；`app.py:84-87` `_all_engagements()` 捕获 `ValueError` **静默跳过**损坏条目。
- **后果链**：崩溃/OOM/断电落在写入窗口 → 截断 JSON → 该 engagement 从工作台列表**无声消失**（下次列表加载 skip），相当于静默数据丢失。且与 [`docs/macos_app_packaging.md`](../macos_app_packaging.md) 运行机制第 4 条「写入均为原子写」的直接矛盾（文档契约漂移的又一实例）。
- **可能性/影响/置信度**：低-中 / 中-高 / 高。owner：维护者。
- **验证路径（修复验收）**：新增测试——monkeypatch 写入中途抛异常后，目标 JSON 仍为旧完整版本（成功语义），无 `.tmp-*` 残留。

### R2 · Web/PawApp API 零认证 + 可绑定任意网卡（机密性）

- **证据**：`fde_scope/web/app.py` 全部 26 条路由无任何 auth dependency；上传/创建/journal/skills 均为写操作；`fde_scope/cli.py:701-720` `web --host` 自由参数无约束无警告（默认 `127.0.0.1` 安全）；`pawapp/backend/main.py` 同样无鉴权（由宿主 QwenPaw 会话域保护，风险较低）。
- **后果**：用户 `fde-scope web --host 0.0.0.0` 演示一次局域网访问后忘了关 → 局域网内任何人可读取 engagement（含客户名、干系人、SLO）并向 `/api/forge` 上传/触发含公司数据的语料处理（服务端接管 MiMo key 调用）。
- **可能性/影响/置信度**：低（默认安全）/ 高（误用时机密性）/ 高（机制确证，非推测）。
- **缓解成本**：极低——非 loopback 地址时打印醒目警告或要求 `FDE_SCOPE_ALLOW_REMOTE=1` opt-in。

### R3 · 文档↔打包契约漂移（开发者第一印象风险）

- **证据**：
  - `README.md:326` 宣称 `pip install -e ".[full]" # everything`，但 `pyproject.toml:32-46` optional-dependencies 仅 `agentscope/mysql/opcua/web/dev`，**无 `full` extra**（按 [PEP 735 extras 语义安装必失败]）；
  - `Makefile:15-16` `install-full := .[dev,agentscope,mysql]` 又缺 opcua/web——三处三种口径；
  - `docs/architecture-model/architecture-health-report.md:40` 建议的「架构守护测试」（18 phases/10 gates/路由计数固化为 tests）截至本轮**未见落地**（tests/ 27 文件中无 arch-guard 类目）——同类计数漂移已发生过一次（"sync test counts" 提交 3d3cae5 人工同步 333 数字至 `README.md:306`）。
- **正面闭环备注**：健康报告的另一条整改（`docs/architecture.md:96` 延迟导入表述）**已完成落地** ✅。
- **可能性/影响/置信度**：已发生（`[full]` 必然报错）/ 中 / 高。
- **验证路径**：干净 venv 内 `pip install -e ".[full]"` 复现报错即证实。

### R1 · 多入口共用相对路径 `.fde_scope/`（数据一致性）

- **证据**：`web/app.py:30-31` `_ENGAGEMENTS_DIR = Path(".fde_scope/engagements")`、`_REPORTS_DIR = Path("reports")`；`skills/store.py:21` 默认 `Path(".fde_scope/skills")`；Mac App launcher 切换 CWD 至 `~/Documents/FDE Scope`；CLI 用户在 repo 目录运行则落在仓库内。`pawapp/backend/main.py` 沿宿主 CWD。
- **后果**：同一 FDE 双击 App 创建的 engagement，在终端 CLI 里看不见；备份/迁移遗漏一部分数据。「数据都在哪」的心智模型破裂。
- **可能性/影响/置信度**：中 / 中 / 高（代码级确证；未实测三个入口并存场景）。
- **缓解**：单一 `paths.py` 解析 `FDE_SCOPE_HOME`（launcher 已引入该约定），CLI/Web/pawapp 全部走它；这是小改动大收益项。

### R7 · 供应链：零锁文件 + 浮动 upper bound

- **证据**：仓库根无 `uv.lock`/`requirements*.txt`/`constraints*.txt`（ls 实测）；`pyproject.toml:35` `agentscope>=2.0.4` 无上限 pin；`ci.yml:82-83` 打印实际安装版本但不断言 floor==lock。
- **历史佐证**：QwenPaw 宿主曾发生 **2.1.0 skill_provider contract gap**（`ci.yml:133-134` 注释自述）——已经付过一次学费，且有 `scripts/verify_pawapp_host.py` real-host 冒烟护栏（✅ 好），但对 agentscope 本体升级仍无 pre-flight。
- **可能性/影响/置信度**：中 / 中 / 高。
- **缓解**：提交 `uv lock`（或 CI 用 constraints），agentscope 加 `<3` 上限 + 专项升级流程。

### R6 · 测试矩阵盲区（回归防线）

- **证据**：27 个测试文件 ~5819 行、CI 四 job（matrix py3.11/3.12 + agentscope 真 import + sdist/wheel + PawApp real-host）、coverage ≈89%（README 自述 + codecov badge）——底子扎实。缺：
  1. **跨入口并发写**同一 engagement（R1×R4 叠加面）无任何测试；
  2. Mac 打包链路（appbuild/* + release.yml）完全不在 CI，仅本机人工验证；
  3. gate 阻塞 → skill 草稿自动生成这类跨模块副作用只有单元级覆盖（`test_skills.py` 存在但未模拟 Web 入口并发）。
- **可能性/影响/置信度**：中 / 低-中 / 高（前三类盲区为结构性缺失，非猜测）。

### R5 · 巨型单文件（可维护性）

- **证据**：`wc -l` 实测 `web/app.py`=1244（路由+业务+持久化助手+页面模板内嵌）、`cli.py`=1043。其余模块普遍 <340 行且职责单一。
- **风险定级**：低——单人项目下尚可控；随功能膨胀（Roadmap Studio 集成等）会加速恶化。适合在下次改这两个文件时顺手拆 router/service，避免专项重构投入。

## Business Application Fitness（业务应用适配度）

> fde-scope 属 workflow-heavy 业务工具（engagement 生命周期、租户、审批策略齐全），适用 BAF 维度评估；按 reference 要求采用定性分级而非数值打分。

| 维度 | 分级 | 证据要点 |
|---|---|---|
| 业务模型清晰度 | **强** | Engagement/Phase/Gate/Skill/TenantConfig 均有显式模型与生命周期枚举；anti-pattern 具名（Sponsor Collapse 等 12 个）进入种子数据与文档 |
| 数据与状态理解 | **中-强** | 文件即库 + skills 原子写 ✅；但 engagement 主实体**非原子写**（R4）、软删除/审计仅 journal 追加式，无 retention 概念（本地工具属性下可接受） |
| 端到端路径接地 | **强** | `test_e2e_manufacturing.py` + 六个 seed 案例（gate 记录由引擎自身产出保证自洽）+ PawApp real-host 冒烟 |
| Agent 指令使用 | **缺口** | 仓库**无** AGENTS.md / CLAUDE.md / copilot-instructions；docs 面向人类读者。AI 协作者拿不到「哪些是关键业务不变量（如 gate 重评估语义）、动哪里会破坏回归」的机器可读指引 |
| 业务校验就绪度 | **强** | CI 四 job + coverage 门 + real-agent 真库 import 断言 job（`must not be empty, must not skip`）设计出色 |

## 正面发现（同等重要的证据）

1. **Gate 语义正确**：pass 记录永不信任、每次 advance 全量重评（`engagement.py:66-92`）——这是把 SOP 变成工程物的核心不变量，实现无误。
2. **注册表防呆**：connector 忘写 `type` slug 或撞 reserved slug 都被拒（`connectors/base.py:79-96`）。
3. **上传防御三件套一致复用**：10MiB 有界读 → UTF-8 校验 → `Path(filename).name`（`web/app.py:34-41,286-290`；pawapp 同款）。
4. **不可信目录防御**：QwenPaw validator 对非法 agent id 短路、绝不拼接探测外路径（`integrations/validator.py:18-62`，commit 9a85400 安全加固可追溯）。
5. **engagement id 路径防护**：resolve + `is_relative_to` 双保险（`web/app.py:61-63`）；Skill id 全部服务端随机生成（`SkillDraft` 无 id 字段），遍历攻击面不存在。
6. **凭据卫生**：API key 仅环境变量流转，manifest/报告不带 key（`llm.py` 设计 + `config.py` 注释契约）。

## Unknowns 与假设（不得当作事实引用）

- ❓ CLI 侧 `engage` 的保存是否同样走 `context.save()` 非原子路径（web/pawapp 已确证；cli 极大概率同源，未逐行核实）。
- ❓ 三个入口（App/CLI/Web）**同时运行**的实际冲突表现——纯静态推断为 last-writer-wins，无并发测试佐证。
- ❓ codecov badge 当前真实百分比（badge 无法在离线评审中核实；89% 来自 README 自述）。
- ⚠️ 假设：单人维护者即是全部发现的隐式 owner；若引入协作者，R1/R2/R7 优先级应整体上调一档。

## 下一步检查清单

> 2026-08-27 状态更新：1、2 已随 P0 验收闭合；3 因 A2 门禁落地而降级为可选；4 已启动（P0+B3 完成）。

1. ✅ 干净环境安装 `-e ".[full]"` —— 已随 A1 验收完成：干净 uv venv（CPython 3.12）安装成功，`import asyncua, mysql.connector, fastapi` 全部通过（R3 复现证据随之失效）。
2. ✅ 模拟 writing-midway 崩溃验证文件留存 —— 已以注入测试闭合：`tests/test_engagement.py::test_save_is_atomic_keeps_previous_version_on_failure`（monkeypatch `os.replace` 抛 OSError → 目标文件保留旧完整版、无 `.tmp-` 残留）。真机 kill -9 未单独演练，但崩溃窗口已由 os.replace 内核级原子语义消除。
3. ⬇️（可选）`--host 0.0.0.0` 后从另一设备 curl `/api/engagements` 量化暴露面 —— A2 门禁已使未设 `FDE_SCOPE_ALLOW_REMOTE=1` 的非 loopback 绑定直接 exit 2，默认路径下不再可达；该验证仅在需要量化 opt-in 后的真实暴露面时才有意义。
4. ▶ 阅读 [`remediation-plan.md`](remediation-plan.md) 按 P0 → P2 执行 —— P0（A1/A2/A3）+ B3 已完成并在文末「完成记录」留档；余下 B1/B2/B4（两周内）、C1–C4（按需）待办。
