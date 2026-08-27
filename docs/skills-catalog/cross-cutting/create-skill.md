# create-skill

> 状态：✅ 已安装（Qoder 内置 skill）· 类型：元能力/skill 工程 · FDE 位点：横切

## 能做什么
在当前工作区创建新的 Agent Skill：生成标准 `SKILL.md` 骨架（name/description/触发词/工作流/质量门），并放到正确的 skills 目录，使新流程能被后续会话自动检索与复用。

## 何时使用
- 同一类现场任务做了三次以上，值得固化成 skill（例：客户环境体检、OPC UA 连通性检查、交付验收 checklist）
- 想把个人经验从"对话记忆"升级为"仓库资产"
- 团队要统一某个流程的执行方式

**不用于**：写一次性脚本（直接写代码）；知识性内容整理（走 `.fde_scope/skills/` 文件库或 [qmind-knowledge](../zone-a-pre-engagement/qmind-knowledge.md)）；把 skill 打包分发（→ [create-plugin](create-plugin.md)）；写作规范与部署校验（→ [writing-skills](writing-skills.md)）。

## 最佳实践
- **description 决定生死**：写清"做什么 + 何时用 + 触发词"，agent 只靠它路由；模糊描述等于没装
- 一个 skill 只解决一类问题；宽泛的"万能交付 skill"不会被触发也不可维护
- 正文控制在几百行内，细节放 `references/` 按需加载（ progressive disclosure）
- 写完必须真跑一次同类任务验证触发与产出，再提交（未验证的 skill 是负资产）
- 装自己的 skill 前先过 [skill-criticagent](skill-criticagent.md)——用同一把尺子量自己
- 归属规则：通用工程流程 → `~/.qoder/skills/`；项目专属 → 仓库内项目级 skills，避免污染其他项目路由

## 项目应用位点
- 横切：把 FDE 现场 SOP 片段沉淀为可复用 skill
- 与 [find-skills](skill-discovery.md) 形成"找 → 评 → 装 → 造"闭环

## 相关
[writing-skills](writing-skills.md) · [create-plugin](create-plugin.md) · [skill-criticagent](skill-criticagent.md)
