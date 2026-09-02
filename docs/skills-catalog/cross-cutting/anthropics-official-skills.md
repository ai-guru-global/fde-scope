# anthropics-official-skills（anthropics/skills）

> 状态：📦 可安装（**未装**，且**只按需单装、不要整包**）· 类型：套件档案 · FDE 位点：横切
> 来源：`anthropics/skills`（Anthropic 官方，"Public repository for Agent Skills"；repo **172,723★**，2026-08-31 GitHub API 核对）· 上游：https://github.com/anthropics/skills
> 规模事实（2026-08-31 GitHub API 核对）：仓库根 `skills/` 下 **19 个 skill**——academy-guide、algorithmic-art、brand-guidelines、canvas-design、claude-api、discernment-nudge、doc-coauthoring、docx、frontend-design、internal-comms、mcp-builder、pdf、pptx、skill-creator、slack-gif-creator、theme-factory、web-artifacts-builder、webapp-testing、xlsx；README 将其分为 example skills（Apache 2.0）与 document skills（docx/pdf/pptx/xlsx，**source-available 非开源**），并附免责声明 "for demonstration and educational purposes only"
> 热度：主力 `skill-creator` 367.1K 装机（skills.sh，2026-08-31）
> 安装：repo 级单 skill 挑装：`npx skills add https://github.com/anthropics/skills --skill skill-creator --directory ~/.qoder/skills -y`——**按需单装勿整包**（把 `--skill` 后的 skill 名换成要装的成员）；Claude Code 侧另有 `/plugin install example-skills@anthropic-agent-skills` / `/plugin install document-skills@anthropic-agent-skills` 通道
> 建档名说明：registry 无 `anthropics-official-skills` 单条目，本页是对 `anthropics/skills` 整仓库的套件档案，各成员真名按 `<owner/repo>@<skill>` 计

## 能做什么
Anthropic 官方技能库，两大类：**文档四件套**（docx/pdf/pptx/xlsx 的创建与编辑）与 **example/methodology skills**。对本库最相关的成员：`skill-creator`（官方 skill 编写方法论，367.1K）、`mcp-builder`（MCP server 脚手架）、`webapp-testing`（web 应用自动化测试流程）、`claude-api`（Claude API 集成参考）、`doc-coauthoring`（文档协同写作）、`internal-comms`（内部沟通稿）、`brand-guidelines`（品牌规范）。

与相邻套件的差别：knowledge-work-suite 管岗位化知识工作产出物（另一 repo `anthropics/knowledge-work-plugins`）；superpowers/gstack 管工程流程纪律；本仓库是 Anthropic 官方的**能力基线与 authoring 方法论**来源。

## 何时使用
| 需求 | 装这个 | 对应 FDE 位点 |
|---|---|---|
| 把现场流程沉淀成自制 skill | `skill-creator` | `.fde_scope/skills/` 沉淀流程 |
| 给制造业客户把设备/业务数据源包成 MCP server | `mcp-builder` | Zone B 集成 |
| web 应用交付前的端到端测试 | `webapp-testing` | Zone B validate |
| AgentScope 接 Claude 系模型的 API 细节 | `claude-api` | Zone B build |
| 与客户协同写方案/交付文档 | `doc-coauthoring` | Zone A→D |
| 对内汇报/对外公告文稿 | `internal-comms` | 横切 |

**不用于**：整包安装 19 个 skill（污染触发空间）；与已有页分工——`skill-creator` 与 [create-skill](create-skill.md) / [writing-skills](writing-skills.md) 互补（官方 authoring 方法论 vs superpowers 流程纪律）、`mcp-builder` 与 [mcp-criticagent](mcp-criticagent.md) 组成"建 + 评"闭环（脚手架 vs 评估）、`webapp-testing` 与 playwright-cli（Zone B，2026-08-31 同批建档）分工（方法论 vs CLI 工具）、文档四件套与 zone-a 既有 pdf/docx/xlsx 页重叠（装前按"替代了谁的哪部分"过门禁）。

## 新人上手

- **触发**：按需点名，如"用 skill-creator 帮我把这个部署流程写成 skill"
- **第一步**：单装主力件：`npx skills add https://github.com/anthropics/skills --skill skill-creator --directory ~/.qoder/skills -y`（`--directory ~/.qoder/skills` 必带，否则装进 `.claude/skills/` Qoder 看不到）；装完用它走一遍"描述 → 草稿 → 验证"，产出第一个自制 SKILL.md
- **常见坑**：文档四件套（docx/pdf/pptx/xlsx）是 **source-available 非开源**，商用分发前先看 LICENSE 条款；README 免责声明明确 example skills 仅供演示/教学，生产使用前自行评估
- **常见坑**：`claude-api`、`brand-guidelines` 这类名字与描述相当通用，与其他来源撞车概率高——装前跑 [skill-criticagent](skill-criticagent.md) 门禁并写清替代关系

## 最佳实践
- **一次只装一个**，先过 [skill-criticagent](skill-criticagent.md)，装完在本页表格对应行标注"已装"（沿用 [knowledge-work-suite](knowledge-work-suite.md) 的维护方式）
- `skill-creator` 是官方 authoring 方法论：自制 skill 先按它的结构起稿，再用 superpowers 的 [writing-skills](writing-skills.md) 做流程校验——两套互补不二选一
- `mcp-builder` 只管"建"，上线前必须过 [mcp-criticagent](mcp-criticagent.md) 评估——构成建评闭环
- 官方 skill 的产出术语偏通用 SaaS 语境，用于制造业客户要换词（OEE、停机时长、缺陷率、节拍）

## 项目应用位点
- `.fde_scope/skills/` 自制 skill 文件库：`skill-creator` 提供起稿方法论；现场沉淀走本仓库规约，与外部生态手册不互相覆盖
- 制造业客户数据集成：`mcp-builder` 起脚手架 → [mcp-criticagent](mcp-criticagent.md) 验收
- Zone B 交付 web 界面时：`webapp-testing` 定测试流程，playwright-cli（Zone B 同批建档）提供执行工具

## 相关
[create-skill](create-skill.md) · [writing-skills](writing-skills.md) · [mcp-criticagent](mcp-criticagent.md) · [knowledge-work-suite](knowledge-work-suite.md)
