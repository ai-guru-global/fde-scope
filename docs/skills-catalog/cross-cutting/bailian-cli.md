# bailian-cli（百炼 `bl` 家族入口）

> 状态：✅ 已安装（`~/.qoder/skills/bailian-cli` v1.17.1，requires bin `bl`）· 类型：平台 CLI hub · FDE 位点：横切（Zone B 训练/部署 / Zone C 用量治理）
> 官方安装方式是**整包**：`bl skill init`（hub + protocol + 各业务 skill 同装），不要只装 hub 一个

## 能做什么
阿里云百炼 / DashScope 的**资源管理与命令入口总机**：应用调用（`bl app`）、应用记忆、知识库检索、模型目录/列表、用量与额度配额（含免费额度）、工作空间、MCP 市场、pipeline、文件上传、console API、登录鉴权与配置、以及 agent skill 的安装/列出/更新/卸载（`bl skill add|list|update|remove`）。

它是**家族 hub**——本地已装共 **9 个** `bailian-*`：本 hub + 6 个业务 skill + 1 个文档知识库 + 1 个共享协议：

| 成员 | 管什么 | 关键命令 |
|---|---|---|
| `bailian-protocol` | 共享执行协议：consent、版本预检、鉴权/安装、错误上报、文件与输出约定（**非业务入口**） | — |
| `bailian-gen` | 生图/生视频/配音/TTS/ASR/图文与视频理解（默认生成类都走它） | `bl image\|video\|speech\|omni\|vision` |
| `bailian-finetune` | 精调训练全链：校验数据 → 上传 → 建任务 → watch → export → deploy | `bl dataset\|finetune\|deploy` |
| `bailian-managed-agent` | `agents.yaml` 声明式托管 Agent（IaC：init/validate/plan/apply/destroy） | `bl managed-agent` |
| `bailian-web-search` | 联网搜索的**路径分发**（Token Plan 自带搜索 vs MCP 搜索 + 一次兜底） | `bl search web` |
| `bailian-model-recommend` | 场景 → 模型选型决策（不是查资料，是帮做决定） | — |
| `bailian-docs-llm-wiki` | 百炼官方文档知识库（模型市场结构化数据 + wiki 合成层 + raw 层） | — |
| `bailian-train-deploy` | "数据→训练→部署→调用"闭环剧本（本库另有一页） | 见 [该页](../zone-b-build/bailian-train-deploy.md) |

## 何时使用
- 用户**点名**百炼 / DashScope / `bl`，或续跑既有 `bl` 工作流
- 用量、额度、配额、工作空间、知识库、MCP 市场等资源侧问题
- 不知道哪条 `bl` 命令做这件事 → hub 的 `reference/<group>.md` 是权威清单（不要凭记忆拼命令）
- 首次环境搭建 / 鉴权失败 / `bl` 报错要上报

**不用于**：普通问答、编程、写作、翻译、摘要、泛搜索、图片理解——**宿主自己能做的任务不触发本 skill**（skill 描述里写明了反触发边界）；用户点名火山方舟/ark 的训练不走 `bailian-finetune`；调已上线的百炼应用走 `bl app`，不是 `managed-agent`。

## 新人上手

- **触发**：点名「百炼 / DashScope / `bl`」或续跑既有 `bl` 工作流——skill 描述写明反触发边界：普通问答、编程、写作、翻译、摘要、泛搜索不触发
- **第一步**：首次环境先跑 `bl skill init` 整包安装（hub + protocol + 各业务 skill 同装，别只装 hub），之后 `bl app list --output json`、`bl usage stats`、`bl model list --model qwen` 都是入口级命令
- **常见坑**：执行前必读 `bailian-protocol/SKILL.md`（consent / 版本预检 / 鉴权），协议文件缺失就停下重跑 `bl skill init`，不要猜鉴权；命令不凭记忆拼——先查 `reference/<group>.md` 或 `bl <cmd> --help`，跑前先 `bl --version`
- **常见坑**：console 登录必须显式带 `--console-site domestic|international`；未指明产品先问清再跑 `bl usage` / `bl quota`（否则查的额度是错的对象）；写操作先 `--dry-run`，`managed-agent apply/destroy` 必须 `plan` 看 diff 后带 `--yes`

## 最佳实践
- **执行前必读 `bailian-protocol/SKILL.md`**（provider 选择与 consent、版本与更新预检、setup/auth、错误上报）。协议文件缺失就停下先跑 `bl skill init`，**不要猜鉴权和 consent**
- 版本预检是硬步骤：`bl` 是快速迭代的 CLI，旧版本上的"正确命令"可能已改名；先看 `bl --version` 与 `bl <cmd> --help`
- **写操作先 `--dry-run` 预览**；`managed-agent apply/destroy` 必须带 `--yes`，且**必须先 `plan` 把 diff 给用户看**再要确认
- 凭据只走环境变量/密钥管理，不进仓库、不进日志、不进文档
- 未指明产品就问清楚用哪个产品，再跑 `bl usage` / `bl quota`（否则查出来的额度是错的对象）
- 家族 skill 之间是**软交接**：按名字 Read 对应 skill，装了就参考，没装就回落到 `bl … --help`，不要因为缺文件就中断任务
- 与 MiMo/AgentScope 的关系：fde-scope 的 LLM 抽象层可指向百炼 compatible-mode 端点；`bl` 管的是**平台资源生命周期**，不是运行时调用库——别把两者混为一层

## 项目应用位点
- Zone B：把语料（`fde_scope/corpus/`）产出物送进百炼做精调、把专属模型部署成 endpoint 供 [rag-agent-builder](../zone-b-build/rag-agent-builder.md) 或 web 控制台调用
- Zone C：额度/用量巡检（交付期成本可控性是客户关心项）；知识库检索用于交付后客户自助
- Zone D：`bl managed-agent` 的 `agents.yaml` 是**可交付的声明式基建**，比口头描述部署方式更适合进交接包
- 反例提醒：fde-scope 内置的是 MiMo（OpenAI 兼容）路径，凭据只走 `FDE_SCOPE_MIMO_API_KEY`；用百炼时同样坚持"凭据只走环境变量"

## 相关
[bailian-train-deploy](../zone-b-build/bailian-train-deploy.md) · [vllm-deploy-docker](../zone-b-build/vllm-deploy-docker.md) · [rag-agent-builder](../zone-b-build/rag-agent-builder.md) · [create-skill](create-skill.md)（`bl skill` 与本地 skill 是两套 registry，别混淆）
