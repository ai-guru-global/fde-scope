# superpowers 套件（方法论族 14 件套）

> 状态：✅ 已安装（Quest Marketplace 插件 `superpowers` v5.1.0，作者 Jesse Vincent）· 类型：套件档案 · FDE 位点：横切（约束 Zone B~D 的执行纪律）
> 本地路径：`~/.qoder/plugins/cache/qoder-marketplace/superpowers/5.1.0`（skill 同时镜像到 `~/.qoder/skills/`）
> 特点：**带 hooks**（`hooks/session-start`）——会话启动即注入 `using-superpowers` 的强制规则，是本目录里唯一会主动改变 agent 默认行为的套件

## 能做什么
把"随手改代码"强行拉回一条固定流水线：**explore → brainstorm → plan → TDD → review → verify → finish**。14 个 skill 全是流程纪律，没有一个业务能力，因此它们必须与领域 skill（数据/训练/部署/文档）搭配使用。

| Skill | 触发时机 | 已有单页 |
|---|---|---|
| `using-superpowers` | 每次会话开始：先查有无适用 skill，再动手（连澄清问题之前都要查） | — |
| `brainstorming` | 任何创造性工作之前（做新功能/组件/改行为） | ✅ [Zone A](../zone-a-pre-engagement/brainstorming.md) |
| `writing-plans` | 有多步需求的 spec，**动代码之前** | ✅ [本页同层](writing-plans.md) |
| `executing-plans` | 执行已写好的计划，带评审检查点 | ✅ [本页同层](executing-plans.md) |
| `subagent-driven-development` | 在当前会话内用子 agent 跑计划里的独立任务 | — |
| `dispatching-parallel-agents` | 2 个以上无共享状态的任务并行派发 | ✅ [本页同层](dispatching-parallel-agents.md) |
| `test-driven-development` | 写实现代码之前先写测试 | — |
| `systematic-debugging` | 遇到任何 bug / 测试失败 / 意外行为，**在给修复方案之前** | ✅ [Zone C](../zone-c-operationalization/systematic-debugging.md) |
| `verification-before-completion` | 声称"完成/修好了/通过了"之前，必须真跑验证命令并贴输出 | — |
| `requesting-code-review` | 完成任务、上大 feature、合并前 | — |
| `receiving-code-review` | 收到评审意见后、动手改之前（尤其意见可疑时） | — |
| `using-git-worktrees` | 需要隔离工作区时 | ✅ [本页同层](using-git-worktrees.md) |
| `finishing-a-development-branch` | 实现完成、测试全绿后决定如何合流 | — |
| `writing-skills` | 新建/编辑 skill、部署前校验 | ✅ [本页同层](writing-skills.md) |

## 何时使用（按 FDE 阶段）
- Zone B 实施：`writing-plans` → `executing-plans` / `subagent-driven-development` → `test-driven-development`，这是把 fde-scope 的模块改动落地的正链
- Zone C 排障：`systematic-debugging` 必须在任何"看起来是这个问题"的修复之前（客户现场的复现成本极高，猜一次亏一天）
- 收口阶段：`verification-before-completion` + `requesting-code-review` + `finishing-a-development-branch`，对应 gate 需要证据的纪律
- 横切：本 catalog 的建档本身就是 `writing-plans` + 分批执行 + 完成前逐项校验的产物

**不用于**：纯只读问答与检索（族内 skill 会说"先检查 skill"，但不代表每个都要跑）；`using-superpowers` 明确写了 **SUBAGENT-STOP**——被派发去执行特定任务的子 agent 应忽略它，不要在工作子进程里再套一层方法论；紧急生产事故止血阶段先恢复再补流程（但事后仍要走 `systematic-debugging` 复盘）。

## 最佳实践
- **冲突时以本仓约定为准**：superpowers 的规则很强硬（"哪怕 1% 可能适用也必须调用"）。在 fde-scope 里，文档/小改动场景按 [../README.md](../README.md) 的维护规约裁剪，别为改一行 README 走完整 TDD
- 计划文件要落盘可评审（`writing-plans` 的产物），别只在会话里说过——`executing-plans` 依赖它做检查点
- `verification-before-completion` 是本族**性价比最高**的一条：要求贴真实命令输出。把它当交付前的固定门禁
- `receiving-code-review` 与 `requesting-code-review` 要搭配本库的 [code-review](code-review.md)（CodeRabbit）与 [security-scan](security-scan.md) 使用——机器评审出意见，人按 `receiving-code-review` 的判断流程处置，不盲从也不硬抗
- hooks 会带来会话开销与额外上下文占用：若某会话不需要这套纪律，可临时禁用该插件而不是逐个 skill 绕
- 版本注意：`~/.qoder/skills/` 下有同名镜像（早期散装安装），插件升级后以插件版本为准，**不要两边各改各的**

## 项目应用位点
- `docs/code_review_checklist.md` 与本族的 review 类 skill 是同一层规范，可互相引用
- fde-scope 的 10 个 gate 本质是"人工版 verification-before-completion"——把 skill 纪律映射进 gate 证据要求，是本套件在该项目最落地的用法
- 测试基线（`tests/`，含 `test_app_service.py`/`test_roles.py`/`test_documents_connector.py`）遵循 `test-driven-development` 的"先测后码"

## 相关
[gstack-suite](gstack-suite.md)（同类流程套件，偏 startup 交付视角） · [architecture-visualization-suite](architecture-visualization-suite.md) · [knowledge-work-suite](knowledge-work-suite.md) · [create-skill](create-skill.md) · [skill-discovery](skill-discovery.md)
