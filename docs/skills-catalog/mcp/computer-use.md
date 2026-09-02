# computer-use（MCP server）

> 状态：✅ 已连接（插件 computer-use，bundler 分发，磁盘无版本层）· 类型：MCP 服务器 · **10 个工具** · FDE 位点：横切（客户桌面环境操作）

## 能做什么

**macOS 原生应用**的自动化：不进浏览器，直接驱动桌面应用的辅助功能（Accessibility）树。10 个工具：`list_apps`（枚举运行中应用）、`get_app_state`（读某应用的 AX 树）、`click` / `perform_secondary_action`（右键/长按）、`drag`、`scroll`、`type_text` / `press_key` / `set_value`（直接给控件赋值）、`select_text`（选中文本）。

与浏览器类工具的分工：网页用 [chrome-devtools](chrome-devtools-mcp.md) / [browser-use](browser-use.md)；Finder、系统设置、Native.app、不带网页界面的客户端软件用本 server。

## 何时使用

- 客户给的交付物是**桌面应用**（如 PyInstaller 打包的 .app），需要演示或验证 GUI 行为
- 浏览器覆盖不到的环节：系统偏好设置、证书信任、Finder 拖拽、菜单栏操作
- 无法脚本化又必须人工点的现场流程，需要 agent 代做并留痕

**不用于**：网页操作（浏览器工具更精准）；纯后台任务（直接 Bash 更快）；需要像素级游戏/图形操作的场景（AX 树覆盖不到自绘界面）。

## 新人上手

- **触发**：对 agent 说"打开系统设置把 X 勾上 / 在这个 .app 里走一遍登录 / 帮我操作 Finder"
- **第一步**：agent 先 `list_apps` 确认目标应用在运行，再 `get_app_state` 读 AX 树，然后才 `click`/`set_value`——顺序不能反
- **常见坑**：应用刚启动 AX 树可能未就绪，重取一次 state 再动手；盲点坐标在 Retina 屏极不可靠；动系统设置/权限前必须向用户确认——影响的是客户机器本身

## 最佳实践

- **先 `get_app_state` 再操作**：AX 树给出控件标识，`click`/`set_value` 基于它定位；盲点坐标在 Retina 屏上极不可靠
- `set_value` 优先于模拟键盘输入：直接赋值绕过输入法/焦点问题，且更快
- 操作前 `list_apps` 确认目标应用在运行；应用刚启动时 AX 树可能未就绪，重取一次 state 再动手
- 涉及系统设置/权限的操作先向用户确认——这类动作影响的是客户机器本身，不只是页面
- 客户机器上运行前说明将要执行的点击序列，尤其是会打开网络面板、修改配置的操作

## 项目应用位点

- fde-scope 打包交付（PyInstaller → macOS .app / PawApp 插件）：安装后的 GUI 冒烟验证
- 客户现场：把"按文档点一遍"的验收流程交给 agent 执行并输出逐步截图
- 与 [record-and-replay](record-and-replay.md) 组合：真人演示一遍桌面流程，录制流再加工成可复用 skill

## 相关

[总览](overview.md) · [chrome-devtools](chrome-devtools-mcp.md) · [browser-use](browser-use.md) · [record-and-replay](record-and-replay.md) · [huggingface-local-models](../zone-b-build/huggingface-local-models.md)（本地 .app 交付场景）
