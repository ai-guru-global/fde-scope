# zread

> 状态：✅ 已安装 · 类型：工具/文档生成 · FDE 位点：Zone A · site-survey（代码系统摸底）

## 能做什么
用 `zread` CLI 为代码仓库生成 wiki 式知识库（输出在 `./.zread/wiki/`）：模块拆解、架构说明、上手文档；可浏览、可服务本地站点。也可反向用于"理解陌生 repo 前先读生成的页面"，避免逐文件爬源码。

## 何时使用
- 接手客户陌生系统，需要快速建立整体认知（对应 Zone A `site-survey`）
- 需要给交接对象一份"这个 repo 干什么"的入门文档（Zone D 也用得上）
- 用户提到 zread / 项目 wiki / repo walkthrough

**不用于**：一次性事实查询（直接搜代码）；非代码文档库（→ qmind-knowledge）。

## 新人上手

- **触发**：想"理解/上手/总结一个陌生 repo"、"这个项目是干嘛的"，或直接点名 zread / repo walkthrough——触发的是意图，不必说出"zread"这个词
- **第一步**：先看 `./.zread/wiki/current` 是否存在：存在就直接读 `wiki.json` 和页面 Markdown，无需再跑 CLI；不存在才经用户确认后 `zread generate -y`
- **常见坑**：无人值守跑 `generate` 必须带 `-y`，否则会停在目录确认门上不动；`generate` 消耗 LLM token 且大 repo 要跑很多分钟，启动前先跟用户确认
- **常见坑**：看到 `.zread/wiki/drafts/` 说明上次没跑完——`--draft resume` 续跑或 `--draft clear` 重来；静默失败查 `~/.zread/log/zread.log`

## 最佳实践
- Do：先看 `./.zread/wiki/current` 是否存在，存在就读现成页面
- Do：大 repo 首次生成放后台跑，别阻塞主任务
- Don't：不要把它当实时真相——代码大改后要 `zread generate` 重生成
- 组合拳：zread（结构层）+ architecture-visualization（校验/补充视图）覆盖"文档 vs 代码"一致性

## 项目应用位点
- 现场用 fde-scope 服务客户时，对客户 repo 出摸底 wiki
- examples/ 中制造业语料的来源系统画像

## 相关
[qmind-knowledge](qmind-knowledge.md) · [architecture-visualization-suite](../cross-cutting/architecture-visualization-suite.md) · [shifu](../zone-d-handoff/shifu.md)
