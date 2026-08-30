workspace "FDE Scope" "FDE Scope 现状架构模型（current-state，证据见 system-model.evidence.md）" {

    model {
        # ---------- 人物 ----------
        fde = person "FDE" "Forward Deployed Engineer，驻客户现场的交付工程师"

        # ---------- 外部系统 ----------
        dataSources = softwareSystem "客户数据源" "CSV 文件、MySQL、OPC UA、MQTT-Sparkplug、ROS2 bag、MES、Historian、Zammad、Salesforce" {
            tags "External"
        }
        mimo = softwareSystem "MiMo Token Plan" "OpenAI 兼容 LLM（可选）。凭据仅走环境变量 FDE_SCOPE_MIMO_API_KEY，失败回退规则路径" {
            tags "External"
        }
        agentscope = softwareSystem "AgentScope 2.0.x" "可选运行时（optional extra，实测窗口 >=2.0.4.post1,<3）。函数内延迟导入：deploy/（app_service/permission_builder/sandbox_config/tenant_manager/toolkit）+ connectors/documents.py（agentscope.rag 解析器）" {
            tags "External"
        }
        qwenpawHost = softwareSystem "QwenPaw 桌面宿主" "PawApp 宿主：提供 LLM(ctx.chat)、沙箱、存储、App Center" {
            tags "External"
        }

        # ---------- 目标系统 ----------
        fdeScope = softwareSystem "FDE Scope" "FDE 现场操作系统：18 阶段 SOP 状态机 + 10 个可执行 gate，覆盖 ticket 与 manufacturing 双场景" {

            cli = container "CLI 工作台" "Typer 命令行：connect/corpus/deploy/eval/flywheel/engage-*/gate-*/handoff/kpi/profiles/web/qwenpaw-*/skill-*" "Python 3.11+ / Typer"

            webConsole = container "Web 控制台" "FastAPI 三视图工作台（workbench 聚合 + journal + skills），27 个路由" "Python / FastAPI (optional extra web)"

            pawapp = container "PawApp 插件应用" "QwenPaw 桌面形态：后端薄封装 18 路由挂载 /api/fde-scope + 2 个 Agent 工具 + skill_provider" "Python / QwenPaw PawApp SDK"

            coreEngine = container "核心引擎 fde_scope" "纯 Python 库，零配置可跑（agentscope 为 optional extra、全函数内延迟导入）。engagement/connectors/corpus/deploy/eval/flywheel/integrations/profiles/skills + 横切 llm/config/templates/paths" "Python package"

            fileStore = container "文件事实源" "零数据库文件库（位置由 fde_scope/paths.py::data_root() 解析：FDE_SCOPE_HOME > 项目 .fde_scope > ~/Documents/FDE Scope > CWD）：engagements/（SOP 状态快照）、skills/（技能 draft→published→archived）、uploads/；reports/ 存 HTML 报告与 runbook" "JSON / JSONL / Markdown / HTML files"
        }

        # ---------- 关系 ----------
        fde -> cli "engage/gate/corpus/deploy/eval/handoff…"
        fde -> webConsole "浏览器操作三视图"
        fde -> qwenpawHost "桌面端使用"
        qwenpawHost -> pawapp "App Center 加载（registerRoutes 挂载 /api/fde-scope）"

        cli -> coreEngine "函数内延迟导入全部模块"
        webConsole -> coreEngine "顶层+延迟导入（engagement/profiles/skills/corpus/…）"
        pawapp -> coreEngine "薄封装，延迟导入"

        coreEngine -> dataSources "connectors 读取：CSV/MySQL/OPC UA/MQTT/ROS2/MES/Historian/Zammad/Salesforce"
        coreEngine -> mimo "llm.py MiMoClient（可选注入，失败回退规则）"
        coreEngine -> agentscope "延迟导入：deploy/（运行时三支柱）+ connectors/documents.py（rag 解析器），optional extra [agentscope]"
        coreEngine -> fileStore "读写 engagement 快照 / 技能库 / 语料"
        coreEngine -> qwenpawHost "integrations 导出 QwenPaw 蓝图与 Agent Skills；PawApp 复用宿主 LLM/存储"

        # ---------- 视图 ----------
        views {
            systemContext fdeScope "SystemContext" "FDE Scope 系统上下文" {
                include *
                autoLayout
            }
            container fdeScope "Containers" "FDE Scope 容器视图" {
                include *
                autoLayout
            }
            theme default
        }
    }
}
