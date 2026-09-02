# huggingface-best

> 状态：✅ 已安装（hugging-face 插件 v1.0.0）· 类型：模型选型 · FDE 位点：Zone A 方案设计 / Zone B build

## 能做什么
回答"这个任务用什么模型最好"：按任务类型、榜单成绩、生态成熟度对比候选模型并给出推荐。核心是**帮客户做决策**，不是罗列资料。

## 何时使用
- 客户/方案书里的模型选型章节："我们要做缺陷分类，选哪个模型？"
- 现有模型不达标时的替代候选调研
- 与 [bailian-model-recommend](../cross-cutting/bailian-cli.md) 互补：本 skill 覆盖**开源/HF 生态**，bailian 覆盖**百炼商用 API**——客户问"开源自部署还是直接买 API"时两边都要出数

**不用于**：合同已锁定模型的场景（别推翻商业决定）；百炼在售模型选型（→ bailian-model-recommend）；榜单之外需要实测的最终决策（推荐只是假设，→ [huggingface-community-evals](huggingface-community-evals.md) 实测）。

## 新人上手

- **触发**：直接问选型问题，如"缺陷分类用什么模型最好"、"哪个模型能跑在我的 MacBook 上"（skill 的触发词就是 "best model for X"、"what model should I use for" 这类问句）
- **第一步**：一句话给出任务 + 硬件约束，如"我要做工单文本分类，只有 16GB 内存的 Mac，推荐几个模型"——skill 会查 HF 官方 benchmark 榜单、按设备内存过滤并输出带分数的候选对比表
- **常见坑**：不说硬件约束——skill 会跳过设备过滤直接返回最强模型，推荐出一堆现场跑不动的（内存换算：fp16≈内存GB÷2、Q4≈内存GB×2）；把推荐当结论——推荐只是"待验证假设"，上下文窗口/许可证/硬件三查之后还要在客户数据上实测（→ [huggingface-community-evals](huggingface-community-evals.md)）才能写进方案

## 最佳实践
- 推荐 ≠ 测评：把推荐当"待验证假设"，在**客户自己的数据**上跑 eval 后才写进方案
- 三查必做：上下文窗口（对得上客户工单/图纸文本长度吗）、许可证（商用/air-gap 是否允许）、硬件需求（客户机房有什么卡）
- 榜单分数与客户任务分布未必对齐：写清"推荐依据 + 未覆盖的假设"，别把 Leaderboard 当真理
- 输出物固定为对比表：候选 × 上下文/许可/硬件/预估成本，留档进方案书，未来换模型有基线
- 小模型优先：边缘/内网场景，3B~8B 能过验收就不用 70B（→ [huggingface-local-models](huggingface-local-models.md)）

## 项目应用位点
- Zone A 成功标准定义时的"模型假设"一行（谁、哪个尺寸、什么许可）
- fde-scope 语料管线的嵌入模型选型（对接 train-sentence-transformers 前的候选筛选）

## 相关
[huggingface-community-evals](huggingface-community-evals.md) · [huggingface-local-models](huggingface-local-models.md) · [bailian-cli 家族（含 model-recommend）](../cross-cutting/bailian-cli.md)
