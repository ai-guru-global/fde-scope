# architecture-communicator

> 状态：✅ 已安装（架构可视化插件）· 类型：场景技能 · FDE 位点：Zone A/D · 干系人沟通与交付视图

## 能做什么
把已有架构模型按**受众**重新表达：高管要能力地图、产品要边界与流程、运维要拓扑、安全要信任边界——裁剪范围、调整语言粒度、决定图的详细度，并产出对应交付物。

## 何时使用
- "给我老板/客户/运维团队讲清楚这个系统"
- stakeholder-map 阶段为不同干系人准备不同视图
- 移交文档需要受众定制版

**不用于**：还没有模型可讲时（先走 `explore` → `system-modeler` 建模）；风险评审（→ risk-quality-reviewer）。

## 新人上手

- **触发**：对 agent 说「给我老板/客户/运维团队讲清楚这个系统」「为 XX 干系人准备架构讲解」——诉求里带明确**受众**的架构表达
- **第一步**：告诉 agent 三件事：受众是谁、他要做什么决策、时间/细节约束（如「给高管 10 分钟版能力地图」），让它按 workflow 挑 1-3 个视图再翻译语言
- **常见坑**：手上还没有证据模型时别直接用它——先走 `explore` → `system-modeler` 建模，本技能只做"受众翻译"，不发明架构事实
- **常见坑**：简化不能把实质性风险和假设一起删掉；支撑材料要保留 `sourceRefs` 与稳定 ID 溯源；别把所有受众塞进同一张图

## 最佳实践
- Do：先确认受众的决策问题是什么，再选视图层级（L0 能力 → L4 代码）
- Do：复用 [architecture-visualization-suite](../cross-cutting/architecture-visualization-suite.md) 产出的证据模型，不重画一套事实
- Don't：不要给技术团队发高管版简图，也不要给高管画 L4 依赖网
- 组合：本技能做"翻译"，格式由 c4model/graphviz 基础技能承担

## 项目应用位点
- Zone A `stakeholder-map` 产出物
- Zone D `knowledge-transfer` 的分角色讲解材料

## 相关
[architecture-visualization-suite](../cross-cutting/architecture-visualization-suite.md) · [drawio](drawio.md) · [shifu](../zone-d-handoff/shifu.md)
