# podcast

> 状态：✅ 已安装（`~/.qoder/skills/podcast`）· 类型：音频生成 · FDE 位点：Zone D enable / 传播

## 能做什么
把知识库目录下的 Markdown 文档提炼成**双人对话播客稿**并合成 MP3：指定知识域目录（如 `05-网络/`）即可产出一期节目，适合碎片时间吸收。

## 何时使用
- 交接后让客户工程师在通勤路上把系统背景"听会"
- 长文档（SOP、行业背景、故障复盘）转化为可口头传播的形态
- 团队内部知识广播（每周一条 10 分钟）

**不用于**：需要精确数字与图形材料的学习（听觉不擅长，走 [shifu](shifu.md) 或图表）；对外正式发布（未审校的口播稿有风险）；把 PPT 变音频（先转成文稿）。

## 新人上手

- **触发**：对 agent 说"生成播客" / "把 `05-网络/` 做成一期播客" / "把文档变成音频"（SKILL.md trigger_keywords 与 description 原词）
- **第一步**：先过环境检查——脚本会跑 `which ffmpeg` 和 `python3 -c "import edge_tts"`（ffmpeg 缺失直接停）；然后对 agent 说"把 `05-网络/` 做成一期播客"，未指定目录时默认 `05-网络/`、产物落 `38-消化/<目录名>-播客/`
- **常见坑**：
  - 播客稿解析契约：每个回合独立一行、以 `小K：`/`小云：` 开头，稿内不得出现表格、代码块、Markdown 链接——破坏契约 TTS 脚本就解析失败
  - `edge-tts` 装不上（PEP 668 限制）时用 `pip3 install --user --break-system-packages edge-tts`；MP3 体积大不进 git，放对象存储/网盘，仓库只留播客稿 Markdown

## 最佳实践
- 生成前确认文稿的"可朗读性"：表格、代码、URL 要在稿子里改写为口语，否则听感灾难
- **术语与数字必须人工审校**：TTS 读错专有名词/单位（如 "k8s"、"ms"、"OPC UA"）会直接误导学习者
- 敏感信息过滤：客户名、实例 ID、内网地址一律不得进音频（音频容易被转发，泄漏面比文档大）
- 存档管理：MP3 体积大，不要提交进 git；放对象存储/网盘，仓库里只留播客稿 Markdown
- 组合用法：同一份文档 → [podcast](podcast.md)（听）+ [notion-infographic](notion-infographic.md)（看）+ [remember](remember.md)（记），三种通道覆盖不同学习习惯

## 项目应用位点
- Zone D `enable`：培训材料的多形态输出
- `.fde_scope/skills/` 沉淀经验的对内广播

## 相关
[shifu](shifu.md) · [notion-infographic](notion-infographic.md) · [qmind-knowledge](../zone-a-pre-engagement/qmind-knowledge.md)
