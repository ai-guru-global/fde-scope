# document-generate

> 状态：✅ 已安装（gstack 插件 v1.58.5）· 类型：文档生成 · FDE 位点：Zone D handoff

## 能做什么
从零补齐缺失文档：针对一个 feature、模块或整个项目，读取代码/测试/配置生成结构化文档（README、API、架构、使用指南），避免"文档靠脑补"。

## 何时使用
- 接手客户遗留系统后需要先补一份能读的现状文档（配合 [zread](../zone-a-pre-engagement/zread.md)）
- fde-scope 新模块落地但文档为空（例：`docs/` 里某些主题只有骨架）
- 交接前发现"只有代码没有说明"，需要一次性补齐

**不用于**：发布后的增量文档同步（→ [document-release](document-release.md)）；把文档排版成 PDF 交付物（→ [make-pdf](make-pdf.md)）；面向高管的架构讲法（→ [architecture-communicator](../zone-a-pre-engagement/architecture-communicator.md)）。

## 新人上手

- **触发**：对 agent 说 "document this feature" / "generate documentation" / "explain this module"（SKILL.md triggers 原词），或中文"给这个模块补文档"
- **第一步**：指定范围开跑，例如："给 `fde_scope/deploy/` 生成文档，输出到 `deploy/README`"——它会先做代码考古（读代码 + 读测试 + 读现有文档）再动笔，并先问你文档落点（写进现有文件 / 独立 `docs/` / 两者都要，推荐"两者都要"）
- **常见坑**：
  - 别让它一次生成整仓文档：它按 Diataxis 四象限出文档计划，超过 5 份才会再次向你确认，整仓直跑极易留下已废弃签名的 API 说明——分模块跑，交付前逐条回代码核对引用
  - 自动生成的数字与清单（路由数、gate 数、连接器数）必须来自可复跑命令，不要接受"约 10 个"这类模糊写法，否则验收时对不上数

## 最佳实践
- 先定读者再定内容：客户运维手册 ≠ 开发者文档 ≠ 验收报告，一份文档只服务一类读者
- 生成后**逐条核对代码引用**：自动生成的 API 说明最容易留下已废弃签名（本仓库刚做过同类校验，见 `docs/architecture-model/architecture-health-report.md`）
- 数字与清单要来自可复跑的命令（路由数、gate 数、连接器数），不要写"约 10 个"
- 与本项目约定一致：文档落 `docs/`，图走 `docs/architecture-model/`，每个声明可回溯到文件
- 别一次生成整站文档——按模块分批，每批都人工过一遍再提交

## 项目应用位点
- Zone D `handoff`：客户侧文档补齐的主力
- 现状缺口示例：`docs/runbooks/`、`deploy/README`（配合 [docker-build-deploy](../zone-b-build/docker-build-deploy.md)）

## 相关
[document-release](document-release.md) · [make-pdf](make-pdf.md) · [zread](../zone-a-pre-engagement/zread.md)
