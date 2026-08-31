# Code Review Checklist — fde-scope

可重复执行的代码评审流程。每次评审（自查或 AI 评审）按本文件走一遍；
发现新类别的 bug 就把它追加到「案例库」，让清单越长越准。

## 评审流程（5 步）

1. **定范围** — `git status --short` + `git diff` 列出全部改动文件，逐文件确认改动意图。
2. **双通道审查** —
   - AI 子代理评审（CodeReview agent）：给它改动范围 + 项目背景 + 重点检查项，要求按严重程度分级输出、每条给文件:行号与证据；
   - 人工/AI 自查：重读每个新文件全文（不是只看 diff），对照下面的清单。
3. **验证每个发现** — 逐条打开代码确认属实（评审报告可能有误报），按 Critical/High/Medium/Low 分级。
4. **修复 + 回归测试** — 每个 bug 修复时在测试文件补一个以 bug 命名的回归测试（`test_<issue>_...`），防止复发。
5. **门禁验证** — `ruff check` + `ruff format --check` + `mypy fde_scope` + `pytest`（全绿才算完）+ 真实环境冒烟（有外部依赖时）。

## 通用检查清单

### A. LLM 集成点（本项目最高频改动区）

- [ ] **回退路径真实可达**：每条 LLM 路径的 `except` 是否覆盖实际异常类型？
  （案例：`chat()` 返回 None 不抛错，下游 `_parse_json_list(None)` 抛 TypeError 才被外层吞掉——根因被掩盖）
- [ ] **契约一致**：新路径是否绕过模块既有契约？
  （案例：LLM 合成路径绕过质量门检 + `per_gap_cap` 上限，违背 docstring 承诺）
- [ ] **顺序正确**：过滤/截断的先后（先门检后截断 vs 先截断后门检，前者不浪费好样本）。
- [ ] **解析鲁棒**：LLM 输出按最坏情况处理——null/空串、markdown fence、非字符串元素、嵌套结构、多位数字（"10" ≠ 1 分）。
- [ ] **溯源诚实**：回退发生后不得再输出"由 LLM 生成"类声明（返回 `(result, used_llm)` 元组）。
- [ ] **失败语义**：可回退的场景静默回退；不可回退的（eval 被测 Agent 挂了）要干净退出（exit 1 + 人话错误），不吐 traceback。
- [ ] **凭据安全**：key 只走环境变量；不出现在异常消息、日志、manifest、报告 HTML、测试、git 文件中。

### B. 异步与阻塞（web 层）

- [ ] `async def` 端点内不得有同步网络/磁盘重 IO —— 用 `run_in_threadpool`（FastAPI）或改 `def`（自动进线程池）。
- [ ] 判断依据：这个调用最坏情况耗时多久？（LLM 60s×N 次会冻结整个事件循环）

### C. 测试隔离

- [ ] 新引入的环境变量驱动行为 → conftest 加 autouse fixture 清理（否则开发者 shell 里的变量会让 CI 外的测试打真实付费 API）。
- [ ] mock HTTP 断言 header 时大小写不敏感（`urllib` 会把 `api-key` 规范化为 `Api-key`）。
- [ ] 新公开 API（函数/类/命令）至少有成功 + 失败两条路径的测试——零覆盖的 API 正是 bug 藏身处。

### D. 环境与打包（本项目踩过的坑）

- [ ] editable 安装在项目根**外**不生效 → 检查 `.venv/lib/python3.12/site-packages/*.pth` 是否带 macOS `hidden` flag：
  `ls -lO .venv/lib/python3.12/site-packages/*.pth`（第 5 列出现 `hidden` 即中招）。
  修复：`chflags -R nohidden .venv`。CPython site.py 会静默跳过 UF_HIDDEN 的 .pth。
- [ ] 验证方法：`cd /tmp && .venv/bin/python -c "import fde_scope"`（不要在项目根下验证——cwd 会掩盖问题）。

### E. 项目特有

- [ ] gates 是可执行代码：改动 `engagement/` 后确认 `Engagement.evaluate_gate` 的 blocker/warning 语义未变。
- [ ] 核心层零依赖承诺：`fde_scope/` 核心模块不得新增第三方 import（LLM 客户端只用标准库 urllib）。
- [ ] `pyproject.toml` 的 optional extras（agentscope/mysql/opcua/web）不得泄漏进核心依赖。
- [ ] 工业连接器 mock 测试不得要求真实服务器（MySQL/OPC UA 集成测试用 marker skip）。

## 案例库（2026-08 评审，MiMo LLM 接入）

| # | 严重度 | Bug | 根因类别 |
|---|---|---|---|
| 1 | High | LLM 合成绕过质量门 + 上限，垃圾样本直接入库 | 契约一致 |
| 2 | High | `/api/forge` async 端点内阻塞 LLM 调用，全服务冻结 | 异步阻塞 |
| 3 | High | `chat()` 对 `content: null` 返回 None（违约），`handoff --llm` 崩溃 | 回退/契约 |
| 4 | Med | `_parse_json_list` 把非字符串 `str()` 成 Python repr 垃圾入库 | 解析鲁棒 |
| 5 | Med | `eval --agent mimo` 中途网络错误 → traceback + 全部进度丢失 | 失败语义 |
| 6 | Med | 测试未隔离 LLM env，有 key 机器打真实 API、断言翻转 | 测试隔离 |
| 7 | Low | 回退模板后仍打印 "drafted by MiMo"（溯源造假） | 溯源诚实 |
| 8 | Low | `_score_llm` 取首位数字，"10" 解析为 1 分 | 解析鲁棒 |
| 9 | Env | .pth 带 macOS hidden flag，editable 安装静默失效 | 环境打包 |

对应回归测试：`tests/test_llm.py` 中 `# Review fixes` 一节。

## 案例库（2026-08-31 全量质量检查，catalog 构建器）

| # | 严重度 | Bug | 根因类别 |
|---|---|---|---|
| 1 | High | `build_catalog_site.py` 把 README 行与页面 .md（转录第三方 skill 简介的**不可信内容**）未经转义直接插值进 Markdown→HTML 管线，任何含 `<img onerror>`/`<script>` 的简介都会成为存储型 XSS | 信任边界/输出转义 |
| 2 | Low | 同一构建器 JSON payload 只中和 `</`，`<!--` + `<script` 仍可吞掉整页脚本块 | 输出转义 |

修复原则（2026-08-31 落地）：先整体 `html.escape(quote=True)` 再做行内 markdown 变换（escape-then-transform，单一转义点）；JSON 块把所有 `<` 替换为 `\u003c`。对应回归测试：`tests/test_build_catalog_site.py`。
检查入口：凡是「构建器/生成器把外部转录内容渲染成 HTML 或嵌进 `<script>`」的改动，按存储型 XSS（High）评审。

## 门禁命令

```bash
.venv/bin/ruff check fde_scope tests
.venv/bin/ruff format --check fde_scope tests
.venv/bin/mypy fde_scope
.venv/bin/python -m pytest          # 263 passed, 3 skipped（基线）
```
