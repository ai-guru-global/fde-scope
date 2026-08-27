# qmind-knowledge

> 状态：✅ 已安装（PROD ONLY，CLI 按需下载）· 类型：工具/知识管理 · FDE 位点：Zone A/D · 知识库检索与维护

## 能做什么
QMind 知识库工具箱：知识检索、notebook 管理、批量上传文件、编译生成知识卡片、lint 断链/质量检查。适合把散落的调研材料、SOP、故障案例沉淀成可检索知识域。

## 何时使用
- 用户提到 知识库 / knowledge base / 上传文档 / 知识卡片 / notebook / compile / lint
- Zone A 调研材料的集中入库与检索
- 与 `shifu`/`podcast` 配合：qmind 存知识，shifu 教知识，podcast 播知识

**不用于**：代码仓库理解（→ zread）；fde-scope 自身语料（→ `fde_scope.corpus` 管道，不要混仓）。

## 最佳实践
- Do：批量上传后先 compile 出卡片再 lint，把质量问题在入库阶段解决
- Do：按"知识域"建 notebook（如 05-网络/），与用户既有的目录习惯对齐
- Don't：生产环境操作前先确认 CLI 认证与权限（PROD ONLY 属性）

## 项目应用位点
- 客户现场 FAQ / 故障处理知识的沉淀容器
- 工单语料的上游素材库（用户主业：语料工程）

## 相关
[zread](zread.md) · [firecrawl-crawl](firecrawl-crawl.md) · [shifu](../zone-d-handoff/shifu.md)
