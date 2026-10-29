# 质量属性场景 — FDE Scope（risk-quality-reviewer 配套工件）

> 与 [`risk-quality-review.md`](risk-quality-review.md) 的 R# 编号一一对应；
> 只收录当前态场景。度量列给出「今天实测什么」与「目标值」，无遥测的项目如实标注。

## QAV-DUR-1 · 数据完整性：写入中断后 engagement 可恢复性（对应 R4）

| 要素 | 内容 |
|---|---|
| 刺激 | 进程在持久化 `EngagementContext` 时被 SIGKILL / 断电 |
| 环境 | 本地文件系统，Web 或 CLI 入口 |
| 当前响应证据 | `context.py:127-131` 直写目标文件；损坏后 `_all_engagements()` 捕 `ValueError` **静默跳过**（`web/app.py:84-87`） |
| 缺口 | 截断 JSON = 该记录静默消失；文档却承诺「原子写」 |
| 目标响应 | 写临时文件 + `os.replace`；中断后目标文件要么旧版完整、要么新版完整 |
| 度量 | 注入型测试：强制 mid-write 异常 → 断言目标文件仍为完整 JSON 且无 `.tmp-*` 残留 |

## QAV-CON-1 · 一致性：多入口并发访问同一 engagement（对应 R1×R6）

| 要素 | 内容 |
|---|---|
| 刺激 | Mac App 与终端 CLI 同时打开/推进同一个 engagement id |
| 环境 | 同机双进程（或 Web + CLI） |
| 当前响应证据 | 无锁、last-writer-wins（静态推断，**无测试佐证**） |
| 缺口 | journal 追加历史丢失；gate 记录回退到旧状态且无提示 |
| 目标响应 | 短期：写前 mtime 检测冲突并拒绝覆盖（或文件锁）；长期由统一 paths 根保证单实例语义沿用 launcher 已有探活机制 |
| 度量 | 双进程并发写集成测试：后写方收到明确冲突错误而非静默覆盖 |

## QAV-SEC-1 · 机密性：误绑定外网网卡后的暴露面（对应 R2）

| 要素 | 内容 |
|---|---|
| 刺激 | 用户执行 `fde-scope web --host 0.0.0.0` 做局域网演示并保持运行 |
| 环境 | 公司/家庭局域网，含客户 PII 语料的 `.fde_scope/` |
| 当前响应证据 | 两层门（2026-10-06 实测）：CLI 在非回环绑定缺 token 时 exit 2；`ApiTokenAuthMiddleware` 逐请求判 `scope["server"]`，未设 token 且请求从非回环地址到达 → 403，设了 token 则非白名单路由 401/200。同一 `0.0.0.0` 监听器：本机 127.0.0.1 → 200，局域网地址 → 403 |
| 缺口 | 单 token 无用户维度（谁做了什么靠 `operator` 自报进审计）；免 token 的回环模式下本机浏览器仍可被跨站表单 POST 打到；同机反向代理落在回环上、不被中间件拦，需自行鉴权 |
| 目标响应 | ✅ 已达成：非回环路径要么有 token 要么拒绝服务，且默认绑回环。后续 P5：多用户/RBAC、CSRF、代理侧鉴权文档化 |
| 度量 | 另一设备 curl `/api/engagements` 返回 403（无 token）或 401（有 token）；`fde-scope web --host <ip>` 无 token → exit 2。回归：`tests/test_web_auth.py` |

## QAV-EVO-1 · 演进性：AgentScope 上游破坏性升级（对应 R7）

| 要素 | 内容 |
|---|---|
| 刺激 | agentscope 发布 2.1/3.0，改变 `Toolkit/PermissionContext/create_app` 签名 |
| 环境 | 新装用户直接拉最新版本（无锁）；CI 也随解安装最新 |
| 当前响应证据 | `agentscope>=2.0.4` 无上限；CI 有 real-import 断言 job ✅ 会红——**但用户本地不会** |
| 缺口 | lockfile 缺失使「CI 绿」与「用户环境」解耦延迟一个发布周期 |
| 目标响应 | lockfile + `<3` 上限；升级走专项 PR：解限 → CI 全绿 → 再固定 |
| 度量 | CI 安装步骤改用 lockfile 且输出被断言等于 lock 版本 |

## QAV-REG-1 · 可验证性：契约类回归的自动拦截（对应 R3/R6）

| 要素 | 内容 |
|---|---|
| 刺激 | 文档计数漂移（phases/gates/extra 名）、依赖 extras 重命名等「小改动大破坏」合入 |
| 环境 | PR 阶段 |
| 当前响应证据 | 架构守护测试建议（health-report #40）未落地；README 数字人工同步已有先例（commit 3d3cae5） |
| 目标响应 | `tests/test_architecture_guard.py`：18 phases / 10 gates / registry slugs / optional-dependencies ∋ {agentscope,mysql,opcua,web} 断言；README 中 `[full]` 被 grep 守护 |
| 度量 | 人为制造漂移 → CI 红；恢复 → 绿 |

## QAV-MNT-1 · 可维护性：控制台入口文件改动半径（对应 R5）

| 要素 | 内容 |
|---|---|
| 刺激 | 新增一个 console 视图或 API（如 Roadmap 的 Studio 集成） |
| 环境 | `web/app.py`（1244 行，路由+助手+模板内嵌同文件） |
| 当前响应证据 | 单文件内已有清晰分段注释，review 抽查可读；但 diff 半径与合并冲突面随功能线性放大 |
| 目标响应 | 按资源族拆分 router（engagements/skills/workbench），公共助手下沉 `web/_common.py`；不要求专项重构，**下次触碰时顺手搬移** |
| 度量 | 任一 router 文件 ≤400 行；`git diff --stat` 显示新功能只触碰单个 router |
