# 整改计划 — FDE Scope 风险评审配套（2026-08-27)

> 排序原则：爆炸半径 × 业务影响 × 可逆性 ÷ 工作量。owner 默认为单人维护者；
> 工作量刻度 XS(<15min)/S(<半天)/M(1-2天)/L(>2天)。每项自带验收标准，
> 完成后在表格打勾并把证据链接追加到本文末尾「完成记录」。

## P0 — 本周，全部小时级

| ID | 动作 | 关联风险 | 量 | 验收标准 |
|---|---|---|---|---|
| A1 | pyproject 增加 `full = ["dev","agentscope","mysql","opcua","web"]` extra，README:326 与 Makefile:15 三处口径对齐（Makefile 含 opcua+web） | R3 | S | 干净 venv `pip install -e ".[full]"` 成功；`tests/test_architecture_guard.py`（见 A4）守护 extras 集合 |
| A2 | `cli.py web()` 当 host 非 loopback 时打印红色警示并要求 `FDE_SCOPE_ALLOW_REMOTE=1` 才放行 | R2 | XS | 本地 loopback 启动不受影响；绑 0.0.0.0 且未设 env → exit 2 带 README 链接提示 |
| A3 | `EngagementContext.save()` 改为临时文件 + `os.replace`（复用 `skills/store.py:_atomic_write` 模式，抽公共 helper 即可） | R4 | S | QAV-DUR-1 注入测试通过；同步把 [`macos_app_packaging.md`](../macos_app_packaging.md) 「写入均为原子写」一句的适用范围改为与实现一致 |

## P1 — 两周内

| ID | 动作 | 关联风险 | 量 | 验收标准 |
|---|---|---|---|---|
| B1 | 新建 `fde_scope/paths.py`：单一函数解析根目录（`FDE_SCOPE_HOME` > App 目录约定 > cwd 兜底），connectors/corpus 输出、engagements、skills、reports、uploads 全部收口；launcher 改为只设该 env | R1 | M | 三入口在同一 `FDE_SCOPE_HOME` 下看到同一份 engagements；README 迁移段落说明旧目录一次性搬运方式 |
| B2 | 提交 `uv.lock`（或最小 constraints.txt），`agentscope>=2.0.4,<3`；CI 安装步骤改走 lock 并断言关键包版本号打印 | R7 | S/M | CI 中出现版本断言步骤；模拟"上游发新版"演练时 CI 安装结果不变 |
| B3 | 落地 `tests/test_architecture_guard.py`（health-report #40 建议）：18 phases、10 gate 注册数、connector registry slugs、extras 集合、README `[full]` 存在性断言 | R3/R6 | S | 人为改坏任一契约 → 该测试红 |
| B4 | 最小 `AGENTS.md`（机器可读）：列出关键不变量（gate 实时重评语义、id 服务端生成、凭据仅 env、原子写约定）、危险操作区（state machine 相关字段直接赋值）、回归锚点（跑哪些测试） | BAF「Agent 指令使用」缺口 | XS | AI 协作者据此能在不读全文档的情况下避开三类高风险修改 |

## P2 — 按需（机会成本驱动，不设死线）

| ID | 动作 | 关联风险 | 量 | 验收标准 |
|---|---|---|---|---|
| C1 | `web/app.py` 按资源族拆 router、公共助手下沉；`cli.py` 同策略（接触时顺手做） | R5 | M | 任一文件 ≤400 行；现有测试全绿 |
| C2 | 可选 macOS runner 定期 job：跑 `build_release.sh --arch arm64 --no-dmg` 冒烟（签名降级 ad-hoc 分支即可） | R6 | L | schedule job 周级运行；失败通知维护者 |
| C3 | README 测试数字改为不含硬计数的措辞（或由 CI 徽章承载），消除人工同步点 | R6 | XS | grep README 不再出现裸数字 "333" |
| C4 | engagement 冲突检测：save 前 mtime 校验，冲突则报错引导刷新（配合 B1 一并设计） | R1/R6 | M | QAV-CON-1 双进程测试通过 |

## 明确不做（有意决策，防范围蔓延）

- ❌ 给本地单用户工具引入完整 auth 系统（数据库/用户体系）——与产品定位不符；A2 的 opt-in 门已是恰当防线。
- ❌ 专项大规模重构 R5——单人项目机会成本过高，采用「接触即改善」策略。
- ❌ 补 runtime topology 图——仓库尚无生产运行时遥测，画了只能是推测（遵守 evidence-first）。

## 完成记录

<!-- 格式：日期 · ID · 证据（提交哈希/测试名/截图路径） -->
