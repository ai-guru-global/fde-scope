# shifu

> 状态：✅ 已安装（`~/.qoder/skills/shifu`）· 类型：教学/培训 · FDE 位点：Zone D enable

## 能做什么
把 Markdown 知识库 / llm-wiki 语料库变成**交互式教学**：诊断已有水平 → 产出学习路径 → 逐课精讲 + 检查点测验 → 间隔重复复习题 → 结课检验，并把学习状态与掌握度写回记忆文件。触发词：教我/系统学习/复习/考我/学习计划。

## 何时使用
- 交接前需要让客户方工程师"真的会"而不只是拿到文档（培训环节）
- 自己要在两周内变成某行业领域（如汽车焊装、半导体厂务）的可用专家
- 有一堆客户文档/wiki 语料但没人能读完整套

**不用于**：一次性事实查询；文档摘要（那是阅读任务）；排障（→ [investigate](../zone-c-operationalization/investigate.md)）；需要记忆卡片时（→ [remember](remember.md)）。

## 新人上手

- **触发**：对 agent 说 "教我" / "我想学 XX" / "复习" / "考我"，或直接喊 "shifu/师傅"（SKILL.md trigger_keywords 原词）
- **第一步**：指定语料范围开课，例如："教我 `05-网络/` 里的 K8s 网络概念"——文件夹/全库会先出 30 秒学习计划等你确认；想跳过摸底二问就说"直接开讲"
- **常见坑**：
  - 不给语料范围就开课，教学深度不稳定——先给目录（单文件走快速通道：不排计划、点题即讲第一课）
  - 学习进度写在 `<语料库根>/.shifu/progress.md`（含已学课程与复习队列），要纳入版本管理或归档进项目目录，否则交接后没人能续学

## 最佳实践
- 先给语料范围（指定目录），否则教学深度不稳定
- 让客户方也用同一套：培训效果可量化（掌握度记录就是验收证据）
- 学习状态文件纳入版本管理或至少归档到项目目录，交接后才有人能续上
- 与 [qmind-knowledge](../zone-a-pre-engagement/qmind-knowledge.md) 组合：qmind 管知识沉淀，shifu 管知识传递
- 注意：课程质量上限 = 语料质量；语料缺口要在结课前作为风险列出，别当作已教会

## 项目应用位点
- Zone D `enable`：客户培训与能力转移
- `.fde_scope/skills/` 现场经验沉淀后的对内/对外教学通道

## 相关
[remember](remember.md) · [qmind-knowledge](../zone-a-pre-engagement/qmind-knowledge.md) · [visual-deck-builder](visual-deck-builder.md)
