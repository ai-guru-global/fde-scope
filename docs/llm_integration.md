# LLM 集成指南（小米 MiMo Token Plan）

> 2026-08 引入：`fde_scope/llm.py` 统一客户端 + 6 个接入点。
> 核心立场：**LLM 是可选增强，不是依赖**——无 key 时全链路走确定性规则路径。

## 设计原则（4 条）

1. **可选注入，签名不变** —— 各层接受可选 `llm` 参数（`CorpusSynthesizer(llm=...)`、
   `QualityGate(llm=...)`、`build_stages(config, llm=...)`、`CorpusForge(cfg, llm=...)`），
   `fill_gaps` / `ReplyFn` 等既有签名完全向后兼容。
2. **失败自动回退** —— 网络错误、坏 JSON、`content: null`、超时都不中断流水线；
   唯一例外是 `eval --agent mimo`（被测 Agent 挂了无法"回退规则"），改为干净退出。
3. **零新依赖** —— `MiMoClient` 纯标准库 `urllib` 实现，核心层零依赖承诺不破。
4. **溯源诚实** —— 回退发生时输出如实标注：`llm_runbook` 返回 `(text, used_llm)`，
   回退模板后 CLI 打印黄字提示，绝不谎称 "drafted by MiMo"。

## MiMo Token Plan 协议要点

| 项 | 值 |
|---|---|
| Base URL | `https://token-plan-cn.xiaomimimo.com/v1`（中国集群；新加坡 `-sgp-`、欧洲 `-ams-`） |
| 认证头 | `api-key: tp-...`（**不是** `Authorization: Bearer`） |
| Key 类型 | `tp-` 前缀 = Token Plan 包量凭证，与按量付费 `sk-` 不通用 |
| 默认模型 | `mimo-v2.5-pro` |
| 请求体 | OpenAI 兼容，但用 `max_completion_tokens`（非 `max_tokens`） |
| 端点 | `POST /chat/completions` |

## 配置

| 环境变量 | 默认 | 说明 |
|---|---|---|
| `FDE_SCOPE_MIMO_API_KEY` | 无 | `tp-` 凭据；未设置 → 客户端 `available=False`，全链路规则路径 |
| `FDE_SCOPE_MIMO_BASE_URL` | 中国集群 | 可切换 `-sgp-` / `-ams-` 或任何 OpenAI 兼容端点 |
| `FDE_SCOPE_MIMO_MODEL` | `mimo-v2.5-pro` | 模型名 |

```bash
export FDE_SCOPE_MIMO_API_KEY="tp-..."   # 唯一凭证入口
```

**凭据安全规范**：key 只走环境变量——禁止写入任何 git 文件、报告 HTML、manifest、
日志、异常消息（已审计：`describe()` 不含 key，`LLMError` 消息只含 HTTP 状态与响应体）、
测试代码与记忆。测试套件永不打真实 API（见「测试策略」）。

## 客户端 API（`fde_scope/llm.py`）

```python
from fde_scope.llm import MiMoClient, LLMError

client = MiMoClient()                    # env 配置；也可显式传 api_key/base_url/model
client.available                         # bool — 有 key 才 True
client.describe()                        # {"provider","base_url","model","available"} → manifest 用
client.chat(messages, temperature=0.7, max_tokens=1024) -> str
client.complete(prompt, system=None, ...) -> str   # chat 的单轮便捷封装
```

**错误契约**：所有公开方法失败必抛 `LLMError`，绝不静默返回部分数据。
包括 `"content": null`（内容审查拒绝/工具调用场景）——返回值必须是
非空 str，null/空白即抛错。这条契约是下游回退逻辑的正确性基础。

## 六个接入点

| # | 接入点 | 位置 | 启用方式 | 回退语义 |
|---|---|---|---|---|
| 1 | 语料合成 | `corpus/synthesizer.py` | `fde-scope corpus --input … --llm` | 坏 JSON/异常 → 规则变异 |
| 2 | 质量评分 | `corpus/agents.py` `QualityGate.score_text` | 随 #1 自动 | 垃圾输出/异常 → 规则分 |
| 3 | Eval 被测 Agent | `eval/benchmark.py` `MiMoReplyFn` | `fde-scope eval --agent mimo` | **不可回退** → exit 1 |
| 4 | Runbook 起草 | `engagement/operationalization.py` `llm_runbook` | `fde-scope handoff <id> --llm` | 失败 → Jinja 模板 + 如实标注 |
| 5 | 部署清单 | `cli.py` deploy | 自动（有 key 即写入） | 无 key → manifest 无 `llm` 段 |
| 6 | Web Forge | `web/app.py` `/api/forge` | 自动感知 env，零配置 | 无 key → 规则路径 |

### 1. 语料合成（关键路径）

每个覆盖缺口类别一次 LLM 调用，prompt 附同类种子样本（风格参考、防照抄），
要求输出 JSON 字符串数组。解析管线：

```
LLM 原始输出 → markdown fence 剥离 → json.loads → 仅保留 str 元素
→ 与种子去重 → 逐条质量门检（LLM 打分，规则分兜底）→ 截断到缺口数
```

**顺序契约：门检在截断之前**——先截断会因模型开头返回垃圾而浪费后面的好样本。
LLM 样本 `trace=["synthesize:llm"]`，与规则路径的 `synthesize:<strategy>` 可区分。

### 2. 质量评分

`score_text(content)` 让 LLM 打 1-5 整数分（temperature=0，max_tokens=16），
**解析完整整数后钳位到 [1,5]**（`"10"` → 5，不是 1）。批量 `__call__` 保持规则评分——
token 成本权衡见下。

### 3. Eval 被测 Agent

`MiMoReplyFn(llm, tenant=...)` 与 `MockReplyFn` 实现同一 `ReplyFn` 协议（`str -> str`），
system prompt 把模型设定为该租户的客服 Agent。运行中 `LLMError` 由 CLI 捕获：
打印 `MiMo eval failed: <原因>` 后 exit 1，不吐 traceback。

### 4. Runbook 起草

prompt 注入客户名 / profile / 当前阶段 / SLO 与告警路由等真实上下文，产出五章节
Markdown 运维手册。返回 `(runbook_text, used_llm)`——CLI 据实打印
`🤖 Runbook drafted by MiMo (模型名)` 或 `Runbook rendered from template (MiMo draft failed)`。

### 6. Web Forge（注意线程模型）

`forge_rows` 含阻塞 LLM 调用（单次上限 60s），端点用
`fastapi.concurrency.run_in_threadpool` 执行——直接在 `async def` 里调用会
冻结整个事件循环，所有端点无响应。

## 失败语义矩阵

| 场景 | 行为 | 退出码 |
|---|---|---|
| 无 key + 显式要求（`corpus --llm` / `eval --agent mimo` / `handoff --llm`） | 红字报错，提示设置 env | 2 |
| 无 key + 隐式入口（web forge / deploy） | 静默走规则路径（deploy 显示"未配置"） | 0 |
| LLM 中途失败 + 可回退（合成/评分/runbook） | 静默回退规则路径，流水线不中断 | 0 |
| LLM 中途失败 + 不可回退（eval 被测 Agent） | `MiMo eval failed: …` | 1 |
| `content: null` / 空白 | 抛 `LLMError`，按上两行处理 | — |

## 成本模型

一次 `corpus --llm` 的调用量 ≈ **缺口类别数**（合成，每次 ≤2048 token）+
**入选合成样本数**（逐条评分，每次 ≤16 token）。实测参考：小数据集（约 6 个
缺口类别）的 `corpus --llm` 耗时数分钟（串行）；`handoff --llm` 只有一次调用
（单次超时上限 60s，实测一次即返）。

**批量质量评分保持规则路径**是文档化权衡：对全部真实样本逐条 LLM 打分的
token 成本不可接受，v0 只对 LLM 合成出的新样本逐条评分（它们没有历史分数）。

## 测试策略

`tests/test_llm.py`（30 用例）三层 mock，全离线、永不依赖真 key：

1. **FakeLLM** —— 脚本化假客户端（可设定回复/抛错/记录调用），覆盖业务层分支；
2. **monkeypatch urlopen** —— 传输层 mock，断言真实 URL / `api-key` 头 / payload
   形状（header 断言须小写化：urllib 会把 `api-key` 规范化成 `Api-key`）；
3. **CLI 无 key 路径** —— CliRunner 验证 exit 2 与提示文案。

`tests/conftest.py` 的 autouse fixture `_no_llm_env` 全局清理三个环境变量——
否则开发者 shell 里的 key 会让 web forge 测试打真实付费 API、翻转 LLM 状态断言。
`# Review fixes` 小节是 2026-08 评审 9 项修复的回归测试（null content、门检截断、
非字符串元素、双位数评分、runbook 溯源、eval 干净退出等）。

## 评审加固记录

2026-08 代码评审发现并修复 9 项（3 High / 3 Medium / 2 Low / 1 环境级），
完整案例库见 [`code_review_checklist.md`](code_review_checklist.md)。要点：
LLM 路径不得绕过质量门与 `per_gap_cap` 上限；async 端点禁阻塞调用；
`null` content 必抛错；回退后溯源必须诚实。

## 扩展其他 Provider

- **OpenAI 兼容端点**（vLLM 自建 / DeepSeek / Moonshot 等）：只改
  `FDE_SCOPE_MIMO_BASE_URL`（+ 模型名），无需改代码。
- **非 OpenAI 兼容**：在 `llm.py` 旁新增同级 Client 类，实现
  `available` / `describe()` / `chat()` / `complete()` 鸭子接口即可被全部 6 个
  接入点复用——各层只依赖这四个成员，不 import 具体类。
