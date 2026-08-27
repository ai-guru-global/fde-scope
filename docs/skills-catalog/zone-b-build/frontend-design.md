# frontend-design

> 状态：✅ 已安装 · 类型：实现/设计 · FDE 位点：Zone B prototype

## 能做什么
产出有辨识度、生产级质量的前端界面（网页/组件/dashboard/海报/app），规避"AI 通用审美"（千篇一律的紫渐变、Inter 字体、卡片套卡片）。用户要求构建 Web 组件、页面、落地页或美化任何 UI 时使用。

## 何时使用
- 给客户做 demo 工作台、结果展示页、汇报用视觉物料
- `fde_scope/web` 工作台前端升级观感

**不用于**：只要功能不要脸的内部脚本页（直接写）；设计系统咨询（→ ui-designer 更系统）。

## 最佳实践
- Do：先定设计方向（受众、情绪、参考）再写码——它是"设计+实现"一体的技能
- Do：现场 demo 保持"一屏看懂"：KPI 大数字 + 流程图 + 少量交互
- Don't：不要堆动效炫技抢演示焦点；不要引入需联网的字体/CDN（air-gap 环境失效）
- 离线检查：交付前断网开一遍，资源加载失败的 demo 比丑更致命

## 项目应用位点
- Zone B `prototype-on-real-data` 的展示层
- examples/ 的 corpus HTML 报告美化（templates/corpus_report.html.j2）

## 相关
[ui-designer](ui-designer.md) · [shadcn](shadcn.md) · [canvas](#)（可视化制品）
