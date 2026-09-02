# playwright-cli

> 状态：📦 可安装 · registry 真名 `microsoft/playwright-cli@playwright-cli`（与建档名一致）· 类型：工具 · FDE 位点：Zone B · 部署（交付 demo 浏览器验收）
> 安装：`npx skills add microsoft/playwright-cli@playwright-cli --directory ~/.qoder/skills -y` · 装机量：137.1K（skills.sh，2026-08-31）· 详情：https://skills.sh/microsoft/playwright-cli/playwright-cli

## 能做什么
微软官方、专为 AI agent 设计的省 token 浏览器自动化 CLI：以子命令驱动 Chromium/Firefox/WebKit/Edge 完成导航（`open`/`goto`/`reload`/`go-back`）、交互（`click`/`type`/`fill`/`press`/`hover`/`select`/`check`）、取证（`screenshot`/`snapshot`/`console`/`requests`）、网络与诊断（`route`/`unroute` 请求 mock、`tracing-start`/`tracing-stop`、`video-start`/`video-stop`）、`generate-locator`/`eval`、`dialog-accept`/`dialog-dismiss`、多标签（`tab-new`/`tab-select`）与 cookie/localStorage/sessionStorage 管理，可直接执行并调试 Playwright 测试。它管"跑"——交付 demo 的浏览器验收执行器。

## 何时使用
- 交付 demo 前的浏览器验收走查：登录 → 业务操作 → 报表导出整条流程真跑一遍，留截图/trace/video 证据
- 前端原型（[frontend-design](frontend-design.md) 等产出）装完后让 agent 自主冒烟，不靠肉眼
- 客户环境 web 控制台联调：先 headless 跑通全流程，再带客户演示

**不用于**：运行时性能/内存/CDP 级调试——那是 [chrome-devtools](../zone-c-operationalization/chrome-devtools.md) 的分工（chrome-devtools 调试向，本页测试执行向）。

## 新人上手
- **触发**：对 agent 说"用 playwright 把这个 demo 从登录到报表导出整条流程跑一遍，每步截图"
- **第一步**：`npx skills add microsoft/playwright-cli@playwright-cli --directory ~/.qoder/skills -y` 装 skill；CLI 本体还需 `npm install -g @playwright/cli`，然后 `playwright-cli open http://localhost:8000 --headed` 起会话，紧跟 `playwright-cli snapshot` 拿元素 ref 清单
- **常见坑**：元素定位必须用 `snapshot` 返回的 ref（如 `click e15`）；页面状态变了 ref 就失效，每次操作后要重新 snapshot，别让 agent 自己猜 CSS selector
- **常见坑**：Windows 下 URL 带 `&` 会截断命令（cmd 用 `^&`、PowerShell 用 `--%` 转义）；默认 headless，现场演示想看见画面要加 `--headed`

## 最佳实践
- 固定节奏：`open` → `snapshot` → 按 ref 操作 → 再 `snapshot` 验证；成序列的脚本比零散点击可复现
- 用 `route`/`unroute` mock 后端依赖，前端验收不必等接口就绪；交付证据用 `tracing-start`/`video-start` 留档
- 验收序列写成脚本随 demo 入 repo，别只留在会话历史里
- Do：会话用 `-s` 命名隔离，避免并行任务互相抢页面。Don't：把坐标点击当定位手段，ref 失效就重 snapshot

## 项目应用位点
- Zone B 部署阶段：交付 demo 的浏览器验收，截图/trace 作为交付证据
- Zone B 原型阶段：原型 UI 的 agent 自主冒烟回归
- 制造业/air-gap 客户现场 web 控制台的联调走查

## 相关
[frontend-design](frontend-design.md) · [postman](postman.md) · [../zone-c-operationalization/chrome-devtools](../zone-c-operationalization/chrome-devtools.md)

同主题兄弟条目（未单独立页）：`currents-dev/playwright-best-practices-skill@playwright-best-practices`（77.5K，管 E2E 测试怎么写）、`testdino-hq/playwright-skill`（70+ E2E 模式库）；写测试规范可加装，测试执行归本页。
