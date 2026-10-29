# GitHub 资源库 · forward-deployed engineer

把 GitHub 上与 `topic:forward-deployed-engineer` 相关的仓库抓到本地、标注来源、
沉淀成 fde-scope 站内可检索的资源页（`/resources`、`/en/resources`），方便团队不再重复翻 GitHub。

建档仓库 804 个 · 逐字镜像 12 个仓库 · 镜像文件 99 个

数据源是包内的 `fde_scope/resources/data/resources.yaml`（随 wheel 分发，安装版也能检索），
本目录只放**逐字正文镜像** `mirror/` 与**生成的静态门户** `site/`。
计数被 `scripts/check_resources_catalog.py` 与 `make check-resources` 钉死，改了镜像就要重跑。

## 两条正交的轴（永不合并）

- **许可**（`license_spdx`）决定能不能把正文**逐字**搬进本仓库：
  - `NONE` = 上游明确声明无任何许可；`NOASSERTION` = GitHub 认不出（null / 自定义 / 非标准）。
    这两个是**不同**的哨兵值，永不折叠、永不为 null——把「认不出」当成「上游说没有」会伪造上游意图。
  - 只有宽松许可（MIT / Apache-2.0 / BSD / CC-BY* / MIT-0 / CC0 …）才允许逐字镜像正文。
- **相关度**（`relevance`）决定值不值得看：`core` / `adjacent` / `noise`。

**镜像门槛同时要求两者**：`permissive-license AND relevance != noise`。
无许可 / 认不出 / copyleft 的仓库**只存元数据 + 我们自己撰写的双语摘要 + 上游链接**，正文不复制。

站内与门户把每个 GitHub 地址一律渲染成**不可点的纯文本**（不出站）；
上游原文（`upstream_description`）是**不可信外部输入**，渲染前一律 HTML 转义。

## 逐字镜像清单（12 个宽松许可仓库）

`mirror/<owner>__<repo>/` 下是原样 Markdown，每个文件字节头带 provenance
（repo / license / commit / upstream path / retrieved）。下表路径即读取路径。

| 仓库 | 许可 | commit | 文件 | 本地目录 |
|---|---|---|---|---|
| pierpaolo28/Awesome-FDE-Roadmap | MIT | 24d652e | 2 | `mirror/pierpaolo28__Awesome-FDE-Roadmap/` |
| suboss87/FDEOps | MIT | ed184c8 | 12 | `mirror/suboss87__FDEOps/` |
| guocong-bincai/ai-interview-guide | MIT | cdb5d0f | 10 | `mirror/guocong-bincai__ai-interview-guide/` |
| calmrocks/ai-engineer-notebooks | MIT | 3bf1d77 | 9 | `mirror/calmrocks__ai-engineer-notebooks/` |
| global-fde/awesome-fde-resources | CC-BY-4.0 | 27e9877 | 12 | `mirror/global-fde__awesome-fde-resources/` |
| libaice/Awesome-FDE | MIT | b9135a9 | 2 | `mirror/libaice__Awesome-FDE/` |
| gxfde/fde-workbench | MIT | 5ded7b3 | 4 | `mirror/gxfde__fde-workbench/` |
| memovai/openfde | MIT | fda7b06 | 6 | `mirror/memovai__openfde/` |
| dataPro-lgtm/fde-interview-fieldbook | MIT | 6b851a9 | 9 | `mirror/dataPro-lgtm__fde-interview-fieldbook/` |
| Dan-Cleary/fdestack | MIT | 5524460 | 9 | `mirror/Dan-Cleary__fdestack/` |
| LowyShin/giip-fde-agent | Apache-2.0 | 83d1dd0 | 12 | `mirror/LowyShin__giip-fde-agent/` |
| goday-org/FDE-Handbook | MIT | 229db7b | 12 | `mirror/goday-org__FDE-Handbook/` |

## 重新抓取 / 构建

```bash
make fetch-resources      # gh 触网：枚举 → reconcile → 镜像合格条目 → 写 manifest + snapshot
make check-resources      # 校验本 README 计数 ⇔ manifest ⇔ 磁盘 ⇔ NOTICE
make build-resources-site # 由同一 manifest 生成 site/index.html 与 site/en/index.html
```

`fetch` 需要 `gh`（token 由 `gh` 自己从 keyring 读，Python 不经手、不记录、不落盘）。
增量：tree/blob SHA 未变则不重抓、不重写；抓取失败绝不删已有镜像，只在 `mirror_reason` 追加原因。
