# anthropic-documentation 📦

> 状态：📦 可安装（未装）· 类型：写作规范 · FDE 位点：Zone D handoff
> 真实条目：`anthropics/knowledge-work-plugins@documentation`（官方 org）· 热度：8.8K installs · https://skills.sh/anthropics/knowledge-work-plugins/documentation
> 安装：`npx skills add anthropics/knowledge-work-plugins@documentation --directory ~/.qoder/skills -y`
> 说明：早期建档记作 `anthropic-documentation`，registry 无该名；已更正为官方 `documentation`。审计状态安装前在 skills.sh 页面复核。
> 同类备选：`sammcj/agentic-coding@writing-documentation-with-diataxis`（573，Diátaxis 四象限写作法）

## 能做什么
按官方写作规范产出工程文档：文档类型划分（教程 / 操作指南 / 参考 / 解释）、信息架构、标题与术语一致性、示例可运行性、审阅清单。解决"每篇文档都不一样"的问题。

## 何时使用
- 交付文档要成体系（教程 + 手册 + API 参考 + 背景解释）而不是散装 README
- 客户方要接手维护，需要他们能持续沿用同一写作标准
- 本仓库文档风格需要统一（现有 `docs/` 文件风格并不完全一致）

**不用于**：文档内容的技术正确性校验（→ [architecture-health](../cross-cutting/architecture-visualization-suite.md)）；PPT/演示（→ [visual-deck-builder](visual-deck-builder.md)）；一次性内部备忘。

## 最佳实践
- 采用 Diátaxis 四象限前先定"这一篇属于哪一格"，混写是文档不可用的首因
- 与客户确认术语表（工单/缺陷/告警/停机 等中文术语），避免同物不同名
- 规范落地为仓库内 checklist（`docs/writing-style.md`），比装第三个写作 skill 更有效
- 判断是否值得安装：若 [document-generate](document-generate.md) + 项目自身规范已够用，**可以长期不装**——避免 skill 功能重叠导致路由抖动
- 装后回填本页：安装日期、实际用法、与 document-generate 的分工

## 项目应用位点
- Zone D：交付文档体系标准
- 与本仓库既有文档骨架（`docs/fde_playbook.md`、`docs/skills.md`、`docs/code_review_checklist.md`）对齐风格，形成写作 + 落位双约束

## 相关
[document-generate](document-generate.md) · [document-release](document-release.md) · [make-pdf](make-pdf.md)
