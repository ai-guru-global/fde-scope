# ui-designer

> 状态：✅ 已安装 · 类型：设计/原型 · FDE 位点：Zone B prototype

## 能做什么
Web UI 设计与原型专家：建立设计系统、视觉风格，输出可运行 MVP 原型。偏"从 0 定系统"，比 frontend-design 更上游。

## 何时使用
- 新客户工作台/产品需要先定视觉体系（色板、字体、组件规范）再多人/多页开发
- "帮我设计一个 XX 应用界面"级别的完整任务

**不用于**：已有设计系统只缺页面（→ frontend-design / shadcn）；单张小海报图类物料。

## 新人上手

- **触发**：说「帮我设计一个 XX 应用界面」「给新工作台定一套设计系统」这类完整设计任务（SKILL.md When to Activate：新网站/落地页/Web 应用、要 MVP 原型、提到 "UI"/"design"/"vibe coding"）
- **第一步**：把产品定位和受众一段话给 agent，让它按默认技术栈（React + Vite + Tailwind + TypeScript + shadcn/ui）先出设计系统（CSS 变量 token）再落可运行 MVP 原型
- **常见坑**：该 skill 激活时会覆盖"避免过度设计"类默认约束（SKILL.md 开头明说 rich design systems/动画/渐变 ARE the goal）——评审前原型只保真到"能讲清交互"，别按它默认深度过度实现
- **常见坑**：已有设计系统只缺页面时不要用它重新定风格（页面"不用于"→ frontend-design/shadcn），多套 token 并存风格漂移更难救

## 最佳实践
- Do：设计系统产出以 token 形式落文档（色/距/字阶），交接时客户运维能延续
- Do：原型只保真到"能讲清交互"的深度，别在评审前过度实现
- Don't：不要跳过它直接写码再"顺手设计"，风格漂移更难救

## 项目应用位点
- 多客户 engagement 时按品牌色派生工作台主题
- pawapp 桌面端 UI 风格基线（配合 `pawapp/ui`）

## 相关
[frontend-design](frontend-design.md) · [shadcn](shadcn.md) · [design-system](#)
