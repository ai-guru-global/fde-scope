# qoder-qmind（MCP server）

> 状态：✅ 已连接（客户端内置，磁盘无安装文件）· 类型：MCP 服务器 · **7 个工具** · FDE 位点：Zone A 调研 / Zone D 知识沉淀
> skill 页：[qmind-knowledge](../zone-a-pre-engagement/qmind-knowledge.md)

## 能做什么

QMind 知识库的会话内工具面，7 个工具分三组：

- **检索**：`search`（知识库关键词/语义检索）、`retrieve`（按查询取证据片段，带 source 定位）——回答"资料库里有没有、说了什么"
- **Notebook**：`list_notebooks`——浏览知识库的 Notebook 结构
- **Source 管理**：`list_sources` / `get_source` / `read_source` / `add_source`——列出、查看、读取知识源；把**文本、HTTPS 链接、本地文件**加入知识库

## 何时使用

- 调研产出要**沉淀成可检索资产**：抓回来的网页/报告/会议纪要 `add_source` 入库，之后任何会话都能 `retrieve`
- 回答"我们之前是不是研究过 X"：先 `search`/`retrieve` 知识库，再决定要不要重新联网查
- 交付前引用审计：`retrieve` 返回的 source 定位可直接引用到方案书

**不用于**：实时信息（知识库是快照，新动态用 [firecrawl-search](../zone-a-pre-engagement/firecrawl-search.md)）；还没入库的本地大文件分析（先读文件，有沉淀价值再 `add_source`）。

## 新人上手

- **触发**：对 agent 说"资料库里有没有 X / 把这份报告入库 / 查一下我们之前研究过什么"
- **第一步**：动手联网前先让 agent `search`/`retrieve` 一次知识库——命中就省一次重复调研；入库用 `add_source`（文本 / HTTPS 链接 / 本地文件均可）
- **常见坑**：知识库是快照不是实时源，新动态要用 firecrawl-search；本地文件入库前确认无客户密钥/凭证——`add_source` 是持久化写入，半年后的检索命中率取决于入库质量

## 最佳实践

- **检索先行**：动手联网/重新分析前先 `search` 一次，避免重复劳动——这是 QMind 存在的意义
- `add_source` 时给清晰的标题/元信息，半年后 `search` 命中率取决于当初的入库质量
- 本地文件入库前确认无敏感信息（客户密钥、凭证）——知识库是持久化存储
- `retrieve` 的证据要**带 source 出处**引用，不要只复述结论
- 与 [qmind-knowledge](../zone-a-pre-engagement/qmind-knowledge.md) skill 的分工：skill 提供批量上传/编译等 CLI 流程，MCP 工具覆盖会话内的即时读写

## 项目应用位点

- Zone A：调研摸底管线（firecrawl 抓取 → `add_source` 入库 → 方案书里 `retrieve` 引用）
- Zone D：项目结束时的经验沉淀——把交付过程文档入库，成为下一个项目的先验
- 客户知识库场景：给客户演示"企业资料 + AI 检索"时，QMind 就是现成的参考实现

## 相关

[总览](overview.md) · [qmind-knowledge](../zone-a-pre-engagement/qmind-knowledge.md) · [firecrawl-search](../zone-a-pre-engagement/firecrawl-search.md) · [zread](../zone-a-pre-engagement/zread.md)
