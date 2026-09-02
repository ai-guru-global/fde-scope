# shadcn

> 状态：✅ 已安装（vercel 插件 v0.44.0，priority=6 自动触发）· 类型：组件体系/工作流 · FDE 位点：Zone B demo

## 能做什么
shadcn/ui 全套能力：CLI 初始化（非交互）、组件添加（`npx shadcn@latest add`）、组件组合成产品级 UI、自定义 registry 发布、Tailwind 主题/暗色定制、组件问题排查。核心概念：组件是**复制进仓库的源码**，不是 npm 依赖——所以完全可改。

## 何时使用
- fde-scope Web 控制台（`fde_scope/web/`）的 React 面板需要成体系的组件与主题时
- 现场 demo 要在几小时内做出"像成品"的表格/表单/对话框/侧栏组合
- 路径命中 `components.json`、`components/ui/**`、`npx shadcn ...` 时该 skill 会自动激活

**不用于**：纯静态单页原型（→ [ui-designer](ui-designer.md) 或 [frontend-design](frontend-design.md) 足够）；非 React 技术栈（Vue/Svelte）不要硬套。

## 新人上手

- **触发**：路径命中 `components.json`、`components/ui/**` 或命令出现 `npx shadcn init/add` 时自动激活（SKILL.md metadata 的 pathPatterns/bashPatterns，priority=6）；对 agent 说「加一个 Dialog 组件」「调主题」同样命中
- **第一步**：项目根跑 `npx shadcn@latest init` 用非交互参数初始化（页面 Do：避免 agent 卡在交互提示上），然后按需 `npx shadcn@latest add <component>`
- **常见坑**：项目用 AI Elements 时必须 `npx shadcn@latest init -d --base radix -f`——SKILL.md 内置校验规则：Base UI 与 Radix API（asChild/openDelay）不兼容，装错基底组件会带类型错
- **常见坑**：别 `add` 全家桶——组件是复制进仓库的源码不是 npm 依赖，一次性 add 全部会塞满没人维护的副本；主题统一走 CSS 变量 + Tailwind token，逐组件改颜色后面改不动

## 最佳实践
- Do：`npx shadcn@latest init` 用非交互参数，避免 agent 卡在提示上
- Do：只 add 真正用到的组件——一次性 add 全部会把仓库塞满没人维护的副本
- Do：主题走 CSS 变量 + Tailwind token，不要逐个组件改颜色
- Warning：若项目使用 AI Elements，必须 `npx shadcn@latest init -d --base radix -f`（Base UI 与 Radix API 不兼容，skill 里带此校验规则）
- 组合优于新增：优先用已有组件拼（Card/Table/Dialog/Form），而不是自己造轮子

## 项目应用位点
- Zone B demo/原型：Web 控制台的组件底座与主题一致性
- 与 [frontend-design](frontend-design.md) 配合：shadcn 出结构，frontend-design 管设计质量下限

## 相关
[frontend-design](frontend-design.md) · [ui-designer](ui-designer.md) · [vercel-deploy](vercel-deploy.md)
