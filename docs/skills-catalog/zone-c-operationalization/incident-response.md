# incident-response 📦

> 状态：📦 可安装（未装）· 类型：事件响应流程 · FDE 位点：Zone C operate（生产事件）
> 来源：`anthropics/knowledge-work-plugins@incident-response`（官方 org）· 热度：5.3K installs · https://skills.sh/anthropics/knowledge-work-plugins/incident-response
> 备选：`alirezarezvani/claude-skills@incident-commander`（602，指挥官视角）
> 安装：`npx skills add anthropics/knowledge-work-plugins@incident-response --directory ~/.qoder/skills -y`

## 能做什么
结构化事件响应：严重度分级与角色分工（指挥/沟通/处置）、时间线记录、遏制优先于根因、对外沟通模板（客户/内部）、复盘（postmortem）产出与行动项跟踪。

## 何时使用
- 交付系统在生产上真的炸了：客户在线、管理层在问、工程师在改——需要一套秩序
- 需要给客户正式的事件说明与复盘（工业客户常把它写进合同 SLA 罚则）
- 值班机制建立前的过渡期（我方 FDE 兼值班）

**不用于**：日常小 bug（→ [systematic-debugging](systematic-debugging.md)）；已知故障的按步处置（→ [sre-runbooks](sre-runbooks.md)，runbook 是"平时写、事件时读"）；根因分析工具链（→ [starops](starops.md) / [sentry-mcp](sentry-mcp.md)）。

## 新人上手

- **触发**：对 agent 说「启动 incident response，这事按 P1 处理」「给客户出一份事件说明/复盘」——真的在生产炸了才用，日常小 bug 不走这套
- **第一步**：先安装：`npx skills add anthropics/knowledge-work-plugins@incident-response --directory ~/.qoder/skills -y`，然后让 agent 按流程开时间线（谁/何时/做了什么/观察到什么）并做严重度分级与角色分工
- **常见坑**：事件期只做"分级 → 遏制 → 通信"三件事，根因留到复盘——别让它边查边猜，遏制永远优先于根因
- **常见坑**：对外沟通禁止承诺未经确认的恢复时间（用"影响 + 现状 + 下次更新时间"三段式）；涉及停线/安全的事件，agent 只出建议不执行，处置动作必须客户授权人在场

## 最佳实践
- 事件期只做三件事：**分级 → 遏制 → 通信**。根因留到复盘阶段，别在群里边查边猜
- 时间线从事件第一分钟开始记（谁在何时做了什么、观察到什么），这是复盘与免责的唯一凭据
- 对外沟通用"影响 + 现状 + 下次更新时间"三段式，禁止承诺未经确认的恢复时间
- 工业现场红线：涉及停线/安全的事件，任何处置动作必须客户授权人在场，agent 只出建议不执行
- 复盘要产**可跟踪行动项 + 负责人 + 截止日**，并回流到 runbook（否则同类事件必然重演）
- 与 fde-scope 整合：事件与复盘记录可作为 engagement 状态机的输入（`shift_handover` gate 的交接材料）

## 项目应用位点
- Zone C `operationalize`：值班与事件响应机制建设
- `engagement/gates/shift_handover.py`（`ShiftHandover`）：交接材料的事件部分

## 相关
[sre-runbooks](sre-runbooks.md) · [starops](starops.md) · [investigate](investigate.md)
