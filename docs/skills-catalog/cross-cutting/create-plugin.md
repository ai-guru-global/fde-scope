# create-plugin

> 状态：✅ 已安装（qoder-create-plugin，Qoder 内置插件包）· 类型：元能力/分发 · FDE 位点：横切

## 能做什么
把外部或本地来源转成**可分发的 Qoder 原生插件**：GitHub 上的 SKILL.md、本地 skill 目录、Qoder Marketplace URL、skills.sh 条目、粘贴的 skill 内容、已有类插件目录 → 生成规范的插件结构（skills/ + 元数据），供团队安装。

## 何时使用
- 团队要统一使用某套流程：把自建 skills 打包成一个插件，一条命令装齐
- 想把生态里的单个 skill 整理成受控版本分发（而不是各自 `npx skills add`）
- 交付结束时把现场沉淀（连接器配置、SOP checklist）打包给客户复用

**不用于**：只给自己用（放 `~/.qoder/skills/` 就够）；写 skill 内容本身（→ [writing-skills](writing-skills.md)）；评估外部插件（→ [skill-criticagent](skill-criticagent.md)）。

## 新人上手

- **触发**：把 GitHub SKILL.md 链接 / 本地 skill 目录 / Qoder Marketplace URL / skills.sh 条目 / 粘贴的 skill 内容丢给 agent，说「打包成 Qoder 插件」——这七类来源就是它的合法 ARGUMENTS
- **第一步**：对 agent 说清来源与目标插件名；产出必须含 `.qoder-plugin/plugin.json` + `README.md` + `skills/`，交付前跑离线校验：`python3 scripts/validate_qoder_plugin.py <plugin-root-or-zip>`
- **常见坑**：插件根目录名与 `plugin.json.name` 必须是同一个 kebab-case 名；manifest 只能声明真实存在的组件——写了 `hooks` / `mcpServers` / `commands` 却没建对应文件会被校验打回
- **常见坑**：不硬编码私有凭据（用占位符或 `CONNECTORS.md` 写 setup 说明）；`.DS_Store`、`__MACOSX/`、临时缓存、smoke-test settings 不许进包

## 最佳实践
- 打包前先逐个确认来源 skill 的 LICENSE 与再分发条款（生态里既有 MIT 也有 proprietary，例：本地 `pptx` skill 标的是 Proprietary）；不确定就不要打进插件
- 一个插件一个主题（如 "fde-delivery-toolkit"），不要把无关 skill 塞一起，否则触发互相污染
- 版本与变更说明要写：插件一旦发给团队，升级成本远高于新建
- 打包后必须做**安装冒烟**：新机器安装 → 触发一次代表性任务 → 确认路由正确（架构可视化插件的 `architecture-health` 里也有同类 skill 激活冒烟要求）
- 客户交付物里的插件要脱敏：清掉客户名、内网地址、真实凭据样例

## 项目应用位点
- 横切：把 FDE 交付工具箱沉淀为团队插件
- Zone D：客户交接时可交付"能力包"而不只是文档

## 相关
[create-skill](create-skill.md) · [writing-skills](writing-skills.md) · [skill-criticagent](skill-criticagent.md)
