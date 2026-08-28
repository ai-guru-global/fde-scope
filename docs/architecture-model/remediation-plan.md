# 整改计划 — FDE Scope 风险评审配套（2026-08-27)

> 排序原则：爆炸半径 × 业务影响 × 可逆性 ÷ 工作量。owner 默认为单人维护者；
> 工作量刻度 XS(<15min)/S(<半天)/M(1-2天)/L(>2天)。每项自带验收标准，
> 完成后在表格打勾并把证据链接追加到本文末尾「完成记录」。

## P0 — 本周，全部小时级

| ID | 动作 | 关联风险 | 量 | 验收标准 |
|---|---|---|---|---|
| A1 ✅ | pyproject 增加 `full = ["dev","agentscope","mysql","opcua","web"]` extra，README:326 与 Makefile:15 三处口径对齐（Makefile 含 opcua+web） | R3 | S | 干净 venv `pip install -e ".[full]"` 成功；`tests/test_architecture_guard.py`（见 A4）守护 extras 集合 |
| A2 ✅ | `cli.py web()` 当 host 非 loopback 时打印红色警示并要求 `FDE_SCOPE_ALLOW_REMOTE=1` 才放行 | R2 | XS | 本地 loopback 启动不受影响；绑 0.0.0.0 且未设 env → exit 2 带 README 链接提示 |
| A3 ✅ | `EngagementContext.save()` 改为临时文件 + `os.replace`（复用 `skills/store.py:_atomic_write` 模式，抽公共 helper 即可） | R4 | S | QAV-DUR-1 注入测试通过；同步把 [`macos_app_packaging.md`](../macos_app_packaging.md) 「写入均为原子写」一句的适用范围改为与实现一致 |

## P1 — 两周内

| ID | 动作 | 关联风险 | 量 | 验收标准 |
|---|---|---|---|---|
| B1 ✅ | 新建 `fde_scope/paths.py`：单一函数解析根目录（`FDE_SCOPE_HOME` > App 目录约定 > cwd 兜底），connectors/corpus 输出、engagements、skills、reports、uploads 全部收口；launcher 改为只设该 env | R1 | M | 三入口在同一 `FDE_SCOPE_HOME` 下看到同一份 engagements；README 迁移段落说明旧目录一次性搬运方式 |
| B2 ✅ | 提交 `uv.lock`（或最小 constraints.txt），`agentscope>=2.0.4,<3`；CI 安装步骤改走 lock 并断言关键包版本号打印 | R7 | S/M | CI 中出现版本断言步骤；模拟"上游发新版"演练时 CI 安装结果不变 |
| B3 ✅ | 落地 `tests/test_architecture_guard.py`（health-report #40 建议）：18 phases、10 gate 注册数、connector registry slugs、extras 集合、README `[full]` 存在性断言 | R3/R6 | S | 人为改坏任一契约 → 该测试红 |
| B4 ✅ | 最小 `AGENTS.md`（机器可读）：列出关键不变量（gate 实时重评语义、id 服务端生成、凭据仅 env、原子写约定）、危险操作区（state machine 相关字段直接赋值）、回归锚点（跑哪些测试） | BAF「Agent 指令使用」缺口 | XS | AI 协作者据此能在不读全文档的情况下避开三类高风险修改 |
| B5 ✅ | 适配 AgentScope 2.0.5+ 的权限兜底语义：`deploy/permission_builder.py::build_context()` 不再把「无规则命中」的处理交给上游默认值，显式固化（HITL→ASK、UNATTENDED→DENY），再放宽 `pyproject.toml` 的 `<2.0.5` 窗口 | R7（已实测，见完成记录 2026-08-28） | M | `pytest -m agentscope` 在 2.0.4.post1 与 2.0.5+ 上均绿；窗口放宽后 CI 仍绿 |

## P2 — 按需（机会成本驱动，不设死线）

| ID | 动作 | 关联风险 | 量 | 验收标准 |
|---|---|---|---|---|
| C1 | `web/app.py` 按资源族拆 router、公共助手下沉；`cli.py` 同策略（接触时顺手做） | R5 | M | 任一文件 ≤400 行；现有测试全绿 |
| C2 | 可选 macOS runner 定期 job：跑 `build_release.sh --arch arm64 --no-dmg` 冒烟（签名降级 ad-hoc 分支即可） | R6 | L | schedule job 周级运行；失败通知维护者 |
| C3 ✅ | README 测试数字改为不含硬计数的措辞（或由 CI 徽章承载），消除人工同步点 | R6 | XS | grep README 不再出现裸数字 "333" |
| C4 | engagement 冲突检测：save 前 mtime 校验，冲突则报错引导刷新（配合 B1 一并设计） | R1/R6 | M | QAV-CON-1 双进程测试通过 |

## 明确不做（有意决策，防范围蔓延）

- ❌ 给本地单用户工具引入完整 auth 系统（数据库/用户体系）——与产品定位不符；A2 的 opt-in 门已是恰当防线。
- ❌ 专项大规模重构 R5——单人项目机会成本过高，采用「接触即改善」策略。
- ❌ 补 runtime topology 图——仓库尚无生产运行时遥测，画了只能是推测（遵守 evidence-first）。

## 完成记录

<!-- 格式：日期 · ID · 证据（提交哈希/测试名/截图路径） -->

- 2026-08-27 · A1 · pyproject.toml 新增 `full` meta-extra（self-referential extras 全覆盖 dev/agentscope/mysql/opcua/web）；Makefile install-full 改用 `".[full]"`；README 本就宣导 `.[full]`，无需改。**验收**：干净 venv（uv, CPython 3.12）安装 `-e ".[full]"` 成功，`import asyncua, mysql.connector, fastapi` 全部 OK，`fde-scope profiles` 正常输出。
- 2026-08-27 · A2 · `cli.py` 新增 `_host_is_loopback()`（IPv6 loopback 一并处理）+ web 命令门禁：非 loopback 且未设 `FDE_SCOPE_ALLOW_REMOTE=1` → 红字说明风险后 exit 2。Mac App launcher 固定 127.0.0.1 直启 uvicorn，不经此路径，不受影响。
- 2026-08-27 · A3 · 新共享模块 `fde_scope/fsutil.py::atomic_write_text()`（mkstemp + os.replace + 失败回滚临时文件）；`EngagementContext.save()` 与 `SkillStore._atomic_write()` 均收口至该实现 —— CLI/Web/PawApp 三入口持久化自动受益（pawapp 的保存同样委托 ctx.save）。
- 2026-08-27 · B3 · 新增 tests/test_architecture_guard.py（5 例：18 phases/10 gates/registry 卫生/extras 契约/三处文档一致）与 test_engagement.py 原子写注入+往返 2 例。**回归**：新增 7 例全部通过（0.18s）；全量 pytest exit 0（仅原有 3 个集成跳过）；ruff check/format 全绿。注：`docs/superpowers/plans/…skills.md` 的未提交 diff 为本轮之前的遗留工作区变更，与本整改无关。
- 2026-08-28 · B2 部分 + B5 前置 · 实测 AgentScope 兼容窗口（隔离环境逐版本跑 `-m agentscope` 12 例）：`2.0.4` ❌ `agentscope.rag` 无 `ExcelParser`（`deploy/app_service.py:41` ImportError）；`2.0.4.post1` ✅ 12/12；`2.0.5 / 2.0.6 / 2.0.7` ❌ 无规则命中的工具兜底变成 `allow`，`test_approval_policy_decides_the_fate_of_an_unmatched_tool[hitl_escalates|unattended_refuses]` 期望 ask/deny 却拿到 allow。据此把 `agentscope` extra 从浮动的 `>=2.0.4`（该 floor 从未成立）改为实测窗口 `agentscope[ollama,service]>=2.0.4.post1,<2.0.5`：`ollama`（新版别名 `model-ollama`）与 `service`→`apscheduler` 是真实运行时的硬需求（2.0.7 起 `OllamaChatModel.__init__` 与 create_app 的调度工具在导入期就要它们），CI 的 `Real-library runtime tests` 步骤此前正因缺这两个包而假红。本机 `uv.lock`（未纳入版本控制）随 `uv lock` 重解析为 2.0.4.post1。**遗留**：uv.lock 仍未提交、CI 仍走 pip 解析，B2 的「lock 入库 + 版本断言」未做；2.0.5+ 语义适配转 B5。
- 2026-08-28 · B5 · 根因定位与适配：实测的「兜底变 allow」实为 2.0.5 新增 **read-only fast path**（`_check_read_only_fast_path` 插在 DEFAULT/DONT_ASK 规则检查后、allow 规则前，`is_read_only=True` 即放行），**非 mode 默认变更**——非 read-only 无规则工具仍走 mode 兜底（ASK/DENY，与 2.0.4.post1 源码逐行一致）；且 `Agent._engine = PermissionEngine(...)` 硬编码、规则按 tool_name 精确分桶无通配，引擎与规则层均不可注入。**适配**（固化点从计划的 `build_context` 移到 `build_toolkit`，因上述不可注入性）：`deploy/toolkit.py` 三处 FunctionTool 一律 `is_read_only=False`（绑定工具本就全量入 allow_rules，行为不回退；规则收回=真收回）；`permission_builder.py` 模块 docstring 显式声明兜底契约（DEFAULT→ASK、DONT_ASK→DENY）；新测试 `test_read_only_flag_is_never_a_permission_grant` 按版本锁定上游差异（再变即红）。**验收**：窗口放宽至 `>=2.0.4.post1,<3` 后，2.0.4.post1（本地 .venv）与 2.0.7.post1（隔离 uv venv）各 11 例 real-runtime 全绿；docs/agentscope_api_mapping.md 实测矩阵同步改写；B3 守护测试（specifier 逐字一致）恢复绿；全量 pytest exit 0、ruff 全绿。
- 2026-08-28 · B2 · `uv.lock` 解除 gitignore 并入库，锁定实测基线 agentscope 2.0.4.post1（与本地 .venv、文档基准三者一致）；CI agentscope job 从裸 pip 改为 `uv sync --locked --extra dev --extra agentscope`（lock 与 pyproject 不一致即红——上游发新版不可能再静默改变 CI 被测对象），新增「安装版本 == uv.lock 版本」断言步骤；升级协议写入 CI 注释（`uv lock --upgrade` + 逐版本矩阵复测）。**验收**：`UV_PROJECT_ENVIRONMENT` 隔离演练 `uv sync --locked` 安装成功、版本断言逻辑通过；ci.yml YAML 语法校验通过。
- 2026-08-28 · B4 · 新增根目录 `AGENTS.md`（机器可读）：6 条关键不变量（gate 实时重评、id 服务端生成、凭据仅 env、原子写约定、规则是唯一授权通道、agentscope 窗口 measured）、4 类危险操作区（state machine 字段直赋/相位与 gate 注册表/权限管线/窗口放宽）、4 个回归锚点（全量 pytest / `-m agentscope` / 守护测试 / ruff）。
- 2026-08-28 · B1 · 新建 `fde_scope/paths.py`：`data_root()` 按优先级 （`FDE_SCOPE_HOME` env > `~/Documents/FDE Scope` 已存在时 > CWD 保持相对路径）解析单一数据根；提供 `engagements_dir()`/`skills_dir()`/`skills_export_dir()`/`uploads_dir()`/`reports_dir()` 五个辅助函数（每次重新解析，不缓存），connectors/corpus 输出、engagements、skills、reports、uploads 全部收口。`cli.py`/`web/app.py`/`pawapp/backend/main.py`/`appbuild/launcher.py` 四处硬编码路径均改为经 `paths` 访问（去掉各模块顶层的 `_ENGAGEMENTS_DIR`/`_REPORTS_DIR`/`_SKILLS_DIR` 常量），launcher 从 `chdir` 改为 `os.environ['FDE_SCOPE_HOME']=...`。三入口在同一 `FDE_SCOPE_HOME` 下看到同一份 engagements（验收：全量 pytest 400 绿；ruff/mypy 全绿；check-catalog/check-local 全绿）。
- 2026-08-28 · C3 · README:306 的 pytest 注释改为「CI badge (top) shows current pass/skip status」——CI badge 已在行 7，无需新增；同步修正行 56 的 stale "2.0.5 API" → "2.0.4.post1–2.0.x API"，行 346 文档节 "2.0.5" → "2.0.x（measured version matrix）"。**验收**：`grep -E "[0-9]+ passed" README.md` 无结果（0 条硬计数）。
- 2026-08-28 · B1 加固 · 实机回归发现 app 足迹目录（`~/Documents/FDE Scope`，由打包 app 首启创建）存在时优先级压过 CWD，令 `monkeypatch.chdir` 的测试隔离失效（8 例本地翻红、CI 因无该目录而假绿），且项目目录自带的 `.fde_scope` 被无视。修复：优先级改为 `FDE_SCOPE_HOME` > CWD 已含 `.fde_scope`（项目数据自留）> app 足迹 > 相对 CWD；conftest 增加 autouse `_isolated_data_root`（每测试钉死 `FDE_SCOPE_HOME`）；新增 `tests/test_paths.py` 6 例钉住优先级契约。**验收**：全量 pytest 406 绿（app 目录真实存在的机器上）；ruff/mypy 全绿；pawapp 真实宿主校验 18 路由 200。
