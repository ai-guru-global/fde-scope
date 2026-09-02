# security-scan

> 状态：✅ 已安装（Qoder 内置插件包 qoder-bundler/security-scan）· 类型：安全门禁 · FDE 位点：横切（推送/发布前）

## 能做什么
Qoder 安全扫描：全仓库或指定路径的云端扫描，分 **L2 轻量** 与 **L3 深度** 两档；在 push / 开 PR / 发布 / 部署等"把手提交给外部"的节点上会被要求先提供 L3 深度评审。修复批准需单独确认（不会因上次扫描通过而默认授权）。

## 何时使用
- 任何 `git push`、开 PR/MR、release、deploy 之前
- 交付包出件前的最后一道安全体检（客户安全部门常要求）
- 新增连接器/凭据处理/子进程执行（`fde_scope/integrations/subprocess_runner.py`）之后

**不用于**：替代 [code-review](code-review.md) 的逻辑评审；渗透测试与红队（那是人工/专业服务）；依赖许可证合规审查（另有工具链）。

## 新人上手

- **触发**：对 agent 说 `/security-scan`，或在 `git push` / 开 PR/MR / merge / release / deploy 前被自动要求先过 L3 深度评审（skill 描述明确列出这些动作）
- **第一步**：裸敲 `/security-scan` 会弹固定三选一——L3 深度扫描 / L2 轻量扫描 / 项目与文件扫描：日常小改动选 L2，涉及认证、凭据、子进程、部署配置选 L3；要按路径扫描就选「项目与文件扫描」并给出明确路径（全仓库才用 `--all`）
- **常见坑**：云端扫描有 10000 行代码的规模上限，超限直接提示不支持，不要自行拆分/缩小范围重试；扫描常需数分钟且中途无输出，别当成卡死中断重跑
- **常见坑**：修复批准必须单独确认——上次扫描通过不会默认授权修下次的发现；扫描结果是候选不是事实，逐条判真/误报

## 最佳实践
- 档位选择：日常小改动 L2；涉及认证、凭据、外部输入、子进程、部署配置一律 L3
- 扫描结果是**候选**，不是事实：逐条判定真/误报，误报要在项目里记录理由并做规则抑制
- 交付敏感项优先级：硬编码凭据 > 越权/路径穿越 > 反序列化/子进程注入 > 依赖漏洞（本仓库靠环境变量注入密钥，扫描最该确认的是"没有绕过 env 的地方"）
- 不把扫描报告原文交给客户前先看是否含内部路径/凭据样例，必要时脱敏
- 与 fde-scope gate 结合：安全类发现应写入对应阶段的 gate 证据，而不是散在对话里
- 一次修复只做一类改动，便于回归与审计追溯

## 项目应用位点
- 横切：Zone B→C 发布门禁、Zone D 交付前体检
- 制造业客户的功能安全/合规语境（配合 `engagement/gates/functional_safety.py`、`conformity.py`）

## 相关
[code-review](code-review.md) · [risk-quality-reviewer](architecture-visualization-suite.md) · [kubernetes-specialist](../zone-b-build/kubernetes-specialist.md)
