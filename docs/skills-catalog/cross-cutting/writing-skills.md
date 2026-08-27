# writing-skills

> 状态：✅ 已安装（superpowers 插件 v5.1.0）· 类型：元能力/skill 质量 · FDE 位点：横切

## 能做什么
按 skill 工程规范**编写与改进 skill 并验证部署**：结构（frontmatter 触发描述、渐进披露、反模式清单）、写作纪律（先写失败案例再写指令）、部署后校验（新装的 skill 是否真的被路由到）。与 [create-skill](create-skill.md) 的区别：create-skill 负责"建骨架"，writing-skills 负责"写得好且真的生效"。

## 何时使用
- 自己写/改 skill，特别是发现"装了却没被触发"
- 把现场 SOP 转成 agent 可执行指令时，需要写作方法约束
- 评审别人（含 AI）生成的 skill 是否只是漂亮废话

**不用于**：评估**外部**待装 skill 的质量与安全（→ [skill-criticagent](skill-criticagent.md)）；创建插件包（→ [create-plugin](create-plugin.md)）。

## 最佳实践
- description 要包含"不使用边界"——本 catalog 每页的 **不用于** 段就是这个思路的来源
- 指令写成可验证的动作（"跑 X 命令并检查输出含 Y"），不写成愿望（"确保质量"）
- 用真实任务回归：写完后拿一个历史任务重跑，对比有无 skill 的产出差异
- 一个 skill 内的引用文件按需加载，别把所有参考塞进主文件（上下文成本）
- 与 [skill-criticagent](skill-criticagent.md) 配合：先自评（writing）→ 再外评（critic）→ 才安装/分发

## 项目应用位点
- 横切：fde-scope 现场沉淀 skill 的写作标准
- `.fde_scope/skills/` 文件库与外部 skill 的格式对齐参考

## 相关
[create-skill](create-skill.md) · [skill-criticagent](skill-criticagent.md) · [create-plugin](create-plugin.md)
