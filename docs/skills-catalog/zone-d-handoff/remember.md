# remember

> 状态：✅ 已安装（`~/.qoder/skills/remember`）· 类型：记忆/复习 · FDE 位点：Zone D enable
> ⚠️ 范围提醒：该 skill **不是通用闪卡工具**，其定位是 Kubernetes 网络概念（Service / Ingress / CNI / DNS / NetworkPolicy / Gateway API）的混淆对比记忆卡。README 索引里的一句话已按实际范围修正。

## 能做什么
生成/复习闪卡，用间隔重复对抗"相似概念记混"：Service 与 Ingress 的边界、CNI 与 NetworkPolicy 的关系、Gateway API 与 Ingress 的取舍等。触发词：记卡片/生成闪卡/复习/考我/混淆对比。

## 何时使用
- 现场 K8s 网络问题需要快速判断层次（客户集群排障最常见卡点）
- 面试/认证/上岗前的知识点固化
- 培训后巩固：与 [shifu](shifu.md) 衔接（shifu 教、remember 记）

**不用于**：端到端学习新领域（→ [shifu](shifu.md)）；一次性事实查询；非 K8s 网络的自定义闪卡（当前 skill 语料聚焦 K8s 网络，其他领域要自行扩卡片或改副本）。

## 新人上手

- **触发**：对 agent 说 "记忆闪卡" / "生成闪卡" / "复习卡片"，或 "我老是混淆 Service 和 Ingress"（SKILL.md 触发词与 intent_queries 原句）
- **第一步**：对 agent 说"生成 service 主题的卡片"或"混淆 Service Ingress"——它先读语料源文件（默认 `05-网络/01-K8s网络核心/`），按布鲁姆分层出卡并展示预览，你删改确认后才写入卡池
- **常见坑**：
  - 语料只覆盖 K8s 网络（Service/Ingress/CNI/DNS/NetworkPolicy/Gateway API）：其他领域要复制 skill 到 `~/.qoder/skills/<name>-domain/` 改语料，直接改上游安装版会被 `npx skills update` 覆盖
  - 复习必须先闭卷作答再翻面（答案要自己产出，不许"看完答案说会了"）；一次生成 ≤8 张、单场复习默认 ≤10 张，进度存 `<语料库根>/.remember/`（`deck.md` + `progress.md`）

## 最佳实践
- 卡片要写成"易混对比"而不是"名词解释"——交付现场需要的是区分能力
- 复习节奏固定（如每天 5 分钟），间隔重复的价值来自频率而非单次时长
- 客户现场遇到的真实混淆点回写成新卡片，卡片库才会持续增值
- 若要推广到其他领域：复制该 skill 到 `~/.qoder/skills/<name>-domain/` 改语料，**不要直接改上游安装版本**（否则 `npx skills update` 会覆盖）

## 项目应用位点
- Zone D `enable`：培训后巩固环节
- K8s 客户环境排障前的知识准备（配合 [kubernetes-specialist](../zone-b-build/kubernetes-specialist.md)）

## 相关
[shifu](shifu.md) · [kubernetes-specialist](../zone-b-build/kubernetes-specialist.md) · [podcast](podcast.md)
