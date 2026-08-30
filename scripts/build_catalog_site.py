#!/usr/bin/env python3
"""把 docs/skills-catalog/ 构建成单文件门户（GTM 风格主页 + 全部页面跳转）。

    make build-site    # 等价 python3 scripts/build_catalog_site.py

输出 docs/skills-catalog/site/index.html：零依赖、离线可用、双击即开。
数据源是 README 表格与各页 Markdown，所以门户永远和手册库同源；
改了 catalog 之后重新跑一次本脚本即可。

仓库自检（make check-catalog）不读本文件产物，两边互不干扰。
"""

from __future__ import annotations

import json
import posixpath
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "docs" / "skills-catalog"
SITE = CATALOG / "site"
OUT = SITE / "index.html"

ZONES = [
    ("zone-a-pre-engagement", "Zone A · Pre-engagement", "调研 · 摸底 · 干系人 · 成功标准", "#6366f1"),
    ("zone-b-build", "Zone B · Build", "数据接入 · 语料 · 原型 · 验证 · 部署 · 评估", "#0ea5e9"),
    ("zone-c-operationalization", "Zone C · Operationalization", "SLO · 监控 · 排障 · 事件 · 训练迭代", "#f59e0b"),
    ("zone-d-handoff", "Zone D · Handoff", "文档 · 培训 · 移交演示", "#10b981"),
    ("cross-cutting", "横切 · 元能力", "skill 工程 · 评审 · 计划 · 调度 · 平台套件", "#8b5cf6"),
]

# (标题, 说明, [(展示名, 相对 catalog 的页面路径)])；构建时校验目标存在
SCENARIOS = [
    ("接手陌生系统", "wiki 化摸底 → 证据建模 → 根因排查", [
        ("zread", "zone-a-pre-engagement/zread.md"),
        ("architecture-visualization 套件", "cross-cutting/architecture-visualization-suite.md"),
        ("investigate", "zone-c-operationalization/investigate.md"),
        ("qmind-knowledge", "zone-a-pre-engagement/qmind-knowledge.md"),
    ]),
    ("客户调研摸底", "联网检索 → 抽取 → 入知识库 → 需求探索", [
        ("firecrawl-search", "zone-a-pre-engagement/firecrawl-search.md"),
        ("firecrawl-scrape", "zone-a-pre-engagement/firecrawl-scrape.md"),
        ("firecrawl-parse", "zone-a-pre-engagement/firecrawl-parse.md"),
        ("qmind-knowledge", "zone-a-pre-engagement/qmind-knowledge.md"),
        ("brainstorming", "zone-a-pre-engagement/brainstorming.md"),
    ]),
    ("方案书与选型", "模型决策 → 讲清楚 → 画出来 → 交付格式", [
        ("huggingface-best", "zone-b-build/huggingface-best.md"),
        ("bailian-cli 家族", "cross-cutting/bailian-cli.md"),
        ("architecture-communicator", "zone-a-pre-engagement/architecture-communicator.md"),
        ("drawio", "zone-a-pre-engagement/drawio.md"),
        ("pptx", "zone-d-handoff/pptx.md"),
    ]),
    ("数据接入与语料", "画像 → 转换 → 挂库 → 查询 → 协议接入", [
        ("read-file", "zone-b-build/read-file.md"),
        ("convert-file", "zone-b-build/convert-file.md"),
        ("attach-db", "zone-b-build/attach-db.md"),
        ("query", "zone-b-build/query.md"),
        ("mqtt-development", "zone-b-build/mqtt-development.md"),
        ("firecrawl-crawl", "zone-a-pre-engagement/firecrawl-crawl.md"),
    ]),
    ("训练与评估", "数据集 → 嵌入训练 → 本地评测 → 闭环", [
        ("huggingface-datasets", "zone-b-build/huggingface-datasets.md"),
        ("train-sentence-transformers", "zone-b-build/train-sentence-transformers.md"),
        ("huggingface-community-evals", "zone-b-build/huggingface-community-evals.md"),
        ("phoenix-evals", "zone-b-build/phoenix-evals.md"),
        ("bailian-train-deploy", "zone-b-build/bailian-train-deploy.md"),
    ]),
    ("部署上线", "本地推理 → 容器 → 编排 → IaC → 快速 demo", [
        ("huggingface-local-models", "zone-b-build/huggingface-local-models.md"),
        ("vllm-deploy-docker", "zone-b-build/vllm-deploy-docker.md"),
        ("docker-build-deploy", "zone-b-build/docker-build-deploy.md"),
        ("kubernetes-specialist", "zone-b-build/kubernetes-specialist.md"),
        ("alibabacloud-spec-ops-suite", "zone-b-build/alibabacloud-spec-ops-suite.md"),
        ("vercel-deploy", "zone-b-build/vercel-deploy.md"),
    ]),
    ("运维与排障", "根因 → 浏览器取证 → 可观测性 → AIOps", [
        ("investigate", "zone-c-operationalization/investigate.md"),
        ("systematic-debugging", "zone-c-operationalization/systematic-debugging.md"),
        ("chrome-devtools", "zone-c-operationalization/chrome-devtools.md"),
        ("datadog", "zone-c-operationalization/datadog.md"),
        ("sentry-mcp", "zone-c-operationalization/sentry-mcp.md"),
        ("starops", "zone-c-operationalization/starops.md"),
    ]),
    ("文档与移交", "补文档 → 出版级 PDF → 规范 → 课程 → 播客", [
        ("document-generate", "zone-d-handoff/document-generate.md"),
        ("make-pdf", "zone-d-handoff/make-pdf.md"),
        ("anthropic-documentation", "zone-d-handoff/anthropic-documentation.md"),
        ("slidev", "zone-d-handoff/slidev.md"),
        ("shifu", "zone-d-handoff/shifu.md"),
        ("podcast", "zone-d-handoff/podcast.md"),
    ]),
    ("工程纪律（横切）", "计划 → 执行 → 评审 → 安全 → 生态与调度", [
        ("writing-plans", "cross-cutting/writing-plans.md"),
        ("executing-plans", "cross-cutting/executing-plans.md"),
        ("code-review", "cross-cutting/code-review.md"),
        ("security-scan", "cross-cutting/security-scan.md"),
        ("skill-discovery", "cross-cutting/skill-discovery.md"),
        ("using-git-worktrees", "cross-cutting/using-git-worktrees.md"),
        ("schedule", "cross-cutting/schedule.md"),
        ("cloud-agents", "cross-cutting/cloud-agents.md"),
    ]),
]


# --------------------------------------------------------------------------- README 解析

def parse_readme() -> dict[str, list[tuple[str, str, str, str]]]:
    """分区标题 -> [(名称, 相对路径, 状态, 一句话)]，按 README 表格顺序。"""
    text = (CATALOG / "README.md").read_text(encoding="utf-8")
    sections: dict[str, list[tuple[str, str, str, str]]] = {}
    current: str | None = None
    row_re = re.compile(r"^\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|\s*(✅|📦|⚰️)\s*\|\s*(.+?)\s*\|\s*$")
    head_re = re.compile(r"^##\s+(Zone [A-D]|横切)")
    for line in text.splitlines():
        m = head_re.match(line)
        if m:
            current = m.group(1)
            sections.setdefault(current, [])
            continue
        if current:
            rm = row_re.match(line)
            if rm:
                sections[current].append((rm.group(1), rm.group(2), rm.group(3), rm.group(4)))
    return sections


README_KEY = {"Zone A": "Zone A", "Zone B": "Zone B", "Zone C": "Zone C", "Zone D": "Zone D", "横切": "横切"}


# --------------------------------------------------------------------------- 极简 Markdown 渲染

CODE_FENCE = re.compile(r"^```")


def render_inline(text: str, page_rel: str, page_set: set[str]) -> str:
    """转义后的行内文本 -> HTML（代码/加粗/链接）。"""
    parts = re.split(r"(`[^`]+`)", text)
    out: list[str] = []
    for part in parts:
        if part.startswith("`") and part.endswith("`") and len(part) > 1:
            out.append(f"<code>{part[1:-1]}</code>")
            continue
        part = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", part)
        part = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: _link(m, page_rel, page_set), part)
        out.append(part)
    return "".join(out)


def _link(m: re.Match, page_rel: str, page_set: set[str]) -> str:
    label, target = m.group(1), m.group(2)
    if target.startswith(("http://", "https://", "mailto:")):
        return f'<a href="{target}" target="_blank" rel="noopener">{label}</a>'
    base = posixpath.dirname(page_rel)
    resolved = posixpath.normpath(posixpath.join(base, target))
    if resolved.endswith(".md") and resolved[:-3] in page_set:
        return f'<a href="#/{resolved[:-3]}">{label}</a>'
    from_site = posixpath.relpath(resolved, "site")
    return f'<a href="{from_site}" target="_blank" rel="noopener">{label}</a>'


def render_markdown(md: str, page_rel: str, page_set: set[str]) -> str:
    """覆盖本库页面实际用到的 Markdown 子集，够用且无依赖。"""
    html: list[str] = []
    para: list[str] = []
    quote: list[str] = []
    table: list[str] = []
    ul: list[str] = []
    fence = False

    def flush_para():
        nonlocal para
        if para:
            body = "<br>".join(render_inline(l, page_rel, page_set) for l in para)
            html.append(f"<p>{body}</p>")
            para = []

    def flush_quote():
        nonlocal quote
        if quote:
            body = "<br>".join(render_inline(l, page_rel, page_set) for l in quote)
            html.append(f'<div class="page-meta">{body}</div>')
            quote = []

    def flush_table():
        nonlocal table
        if not table:
            return
        rows = [r for r in table if not re.match(r"^\|[\s:|-]+\|$", r)]
        parsed = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
        if parsed:
            head, *body = parsed
            thead = "".join(f"<th>{render_inline(c, page_rel, page_set)}</th>" for c in head)
            trs = "".join(
                "<tr>" + "".join(f"<td>{render_inline(c, page_rel, page_set)}</td>" for c in r) + "</tr>"
                for r in body
            )
            html.append(f"<table><thead><tr>{thead}</tr></thead><tbody>{trs}</tbody></table>")
        table = []

    def flush_ul():
        nonlocal ul
        if ul:
            html.append("<ul>" + "".join(f"<li>{i}</li>" for i in ul) + "</ul>")
            ul = []

    for raw in md.splitlines():
        line = raw.rstrip()
        if fence:
            html.append(line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
            if CODE_FENCE.match(line):
                html.append("</code></pre>")
                fence = False
            continue
        if CODE_FENCE.match(line):
            flush_para(); flush_quote(); flush_table(); flush_ul()
            html.append('<pre><code>')
            fence = True
            continue
        if line.startswith("|"):
            flush_para(); flush_quote(); flush_ul()
            table.append(line)
            continue
        flush_table()
        if line.startswith("> "):
            flush_para(); flush_ul()
            quote.append(line[2:])
            continue
        flush_quote()
        if not line:
            flush_para(); flush_ul()
            continue
        if line.startswith("### "):
            flush_para(); flush_ul()
            html.append(f"<h3>{render_inline(line[4:], page_rel, page_set)}</h3>")
            continue
        if line.startswith("## "):
            flush_para(); flush_ul()
            html.append(f"<h2>{render_inline(line[3:], page_rel, page_set)}</h2>")
            continue
        if line.startswith("# "):
            flush_para(); flush_ul()
            html.append(f"<h1>{render_inline(line[2:], page_rel, page_set)}</h1>")
            continue
        m = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        if m:
            flush_para()
            ul.append(render_inline(m.group(2), page_rel, page_set))
            continue
        m = re.match(r"^\d+\.\s+(.*)$", line)
        if m:
            flush_para()
            ul.append(render_inline(m.group(1), page_rel, page_set))
            continue
        para.append(line)
    flush_para(); flush_quote(); flush_table(); flush_ul()
    return "\n".join(html)


# --------------------------------------------------------------------------- 组装数据

def build_data() -> dict:
    readme = parse_readme()
    zone_rows = {
        "zone-a-pre-engagement": readme.get("Zone A", []),
        "zone-b-build": readme.get("Zone B", []),
        "zone-c-operationalization": readme.get("Zone C", []),
        "zone-d-handoff": readme.get("Zone D", []),
        "cross-cutting": readme.get("横切", []),
    }
    page_set = {path[:-3] for rows in zone_rows.values() for _, path, _, _ in rows}

    zones = []
    all_pages: list[dict] = []
    for zone_id, label, tag, accent in ZONES:
        skills = []
        for name, rel, status, blurb in zone_rows[zone_id]:
            page_file = CATALOG / rel
            md = page_file.read_text(encoding="utf-8") if page_file.exists() else f"# {name}\n\n页面缺失：{rel}"
            page_rel = posixpath.splitext(rel)[0]
            skills.append({"name": name, "route": page_rel, "status": status, "blurb": blurb})
            all_pages.append({
                "route": page_rel,
                "zone": label,
                "zoneId": zone_id,
                "status": status,
                "html": render_markdown(md, page_rel, page_set),
            })
        zones.append({"id": zone_id, "label": label, "tag": tag, "accent": accent, "skills": skills})

    scenarios = []
    for title, desc, items in SCENARIOS:
        missing = [rel for _, rel in items if rel[:-3] not in page_set]
        if missing:
            raise SystemExit(f"场景「{title}」引用了不存在的页面：{missing}")
        scenarios.append({
            "title": title, "desc": desc,
            "items": [{"name": n, "route": rel[:-3]} for n, rel in items],
        })

    installed = sum(1 for p in all_pages if p["status"] == "✅")
    installable = sum(1 for p in all_pages if p["status"] == "📦")
    return {
        "zones": zones,
        "scenarios": scenarios,
        "pages": all_pages,
        "stats": {
            "total": len(all_pages),
            "installed": installed,
            "installable": installable,
            "zoneCount": len(zones),
            "scenarioCount": len(scenarios),
        },
    }


# --------------------------------------------------------------------------- HTML 模板

CSS = """
:root{--bg:#f6f7fb;--card:#fff;--ink:#111827;--muted:#6b7280;--line:#e5e7eb;
--accent:#4f46e5;--ok:#059669;--pkg:#d97706;--radius:14px;--mono:ui-monospace,SFMono-Regular,Menlo,monospace}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
background:var(--bg);color:var(--ink);line-height:1.65}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.nav{position:sticky;top:0;z-index:50;display:flex;align-items:center;gap:18px;padding:12px 28px;
background:rgba(255,255,255,.92);backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.nav .brand{font-weight:800;font-size:16px;color:var(--ink);cursor:pointer;white-space:nowrap}
.nav .brand span{color:var(--accent)}
.nav .zlinks{display:flex;gap:14px;overflow-x:auto}
.nav .zlinks a{color:var(--muted);font-size:13px;white-space:nowrap}
.nav input{margin-left:auto;width:230px;padding:7px 12px;border:1px solid var(--line);border-radius:99px;
font-size:13px;outline:none;background:#fff}
.nav input:focus{border-color:var(--accent)}
.hero{background:linear-gradient(135deg,#312e81 0%,#4f46e5 55%,#7c3aed 100%);color:#fff;padding:64px 28px 56px;text-align:center}
.hero h1{font-size:34px;letter-spacing:.5px}
.hero p{margin:14px auto 0;max-width:760px;color:#e0e7ff;font-size:15px}
.hero .stats{display:flex;justify-content:center;gap:14px;margin-top:28px;flex-wrap:wrap}
.stat{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.25);border-radius:99px;
padding:7px 18px;font-size:13px}
.stat b{font-size:16px;margin-right:4px}
.wrap{max-width:1120px;margin:0 auto;padding:36px 24px 72px}
.section-h{display:flex;align-items:baseline;gap:12px;margin:8px 0 18px}
.section-h h2{font-size:21px}
.section-h p{color:var(--muted);font-size:13px}
.scen-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:16px}
.scen{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:18px 20px;
transition:box-shadow .15s,transform .15s}
.scen:hover{box-shadow:0 10px 30px rgba(17,24,39,.08);transform:translateY(-2px)}
.scen h3{font-size:15px;margin-bottom:4px}
.scen .d{color:var(--muted);font-size:12.5px;margin-bottom:12px}
.scen .links{display:flex;flex-wrap:wrap;gap:8px}
.scen .links a{font-size:12.5px;background:#eef2ff;border:1px solid #e0e7ff;color:#4338ca;
padding:4px 11px;border-radius:99px}
.scen .links a:hover{background:#e0e7ff;text-decoration:none}
.zone-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:16px;margin-top:6px}
.zone{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;
display:flex;flex-direction:column}
.zone .zh{padding:16px 20px 12px;border-top:3px solid var(--accent)}
.zone .zh h3{font-size:15.5px}
.zone .zh p{color:var(--muted);font-size:12.5px;margin-top:2px}
.zone .zs{padding:6px 14px 16px;display:flex;flex-wrap:wrap;gap:7px}
.zone .zs a{font-size:12.5px;padding:4px 10px;border-radius:8px;background:#f3f4f6;color:#374151;
border:1px solid var(--line)}
.zone .zs a:hover{text-decoration:none;border-color:var(--accent);color:var(--accent)}
.zone .zs a .st{font-size:11px;margin-right:3px}
.toolbar{display:flex;gap:10px;align-items:center;margin:4px 0 16px;flex-wrap:wrap}
.chip{border:1px solid var(--line);background:#fff;border-radius:99px;padding:5px 14px;font-size:12.5px;
cursor:pointer;color:var(--muted)}
.chip.on{background:var(--ink);color:#fff;border-color:var(--ink)}
.all-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:12px}
.sk{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;display:block;color:var(--ink);
transition:box-shadow .15s,transform .15s}
.sk:hover{box-shadow:0 8px 22px rgba(17,24,39,.08);transform:translateY(-1px);text-decoration:none}
.sk .t{display:flex;align-items:center;gap:8px;font-weight:650;font-size:14px}
.sk .b{color:var(--muted);font-size:12.5px;margin-top:4px}
.sk .z{font-size:11px;color:#9ca3af;margin-top:6px}
.badge{font-size:11px;border-radius:99px;padding:2px 9px;font-weight:600}
.badge.ok{background:#d1fae5;color:#065f46}
.badge.pkg{background:#fef3c7;color:#92400e}
.badge.dead{background:#f3f4f6;color:#6b7280}
.crumb{font-size:13px;color:var(--muted);margin-bottom:6px}
.crumb a{color:var(--muted)}
.article{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);
padding:36px 44px;max-width:900px;margin:0 auto}
.article h1{font-size:24px;margin:4px 0 14px}
.article h2{font-size:17px;margin:26px 0 10px;padding-left:10px;border-left:3px solid var(--accent)}
.article h3{font-size:15px;margin:18px 0 8px}
.article p{margin:8px 0}
.article ul{margin:8px 0 8px 22px}
.article li{margin:4px 0}
.article code{font-family:var(--mono);font-size:.86em;background:#f3f4f6;border:1px solid var(--line);
border-radius:5px;padding:1px 5px;word-break:break-all}
.article pre{background:#0f172a;color:#e2e8f0;border-radius:10px;padding:14px 16px;overflow-x:auto;margin:10px 0}
.article pre code{background:none;border:none;color:inherit;padding:0;font-size:12.5px;line-height:1.55}
.article table{border-collapse:collapse;width:100%;margin:12px 0;font-size:13px}
.article th,.article td{border:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}
.article th{background:#f9fafb}
.article .page-meta{background:#f8f9ff;border:1px solid #e0e7ff;border-left:3px solid var(--accent);
border-radius:10px;padding:12px 16px;margin:6px 0 16px;font-size:13px;color:#374151}
.pager{display:flex;justify-content:space-between;gap:16px;max-width:900px;margin:14px auto 0}
.pager a{font-size:13px;color:var(--muted);border:1px solid var(--line);background:#fff;
border-radius:10px;padding:8px 14px;max-width:46%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pager a:hover{color:var(--accent);text-decoration:none;border-color:var(--accent)}
.empty{display:none;text-align:center;color:var(--muted);padding:40px 0}
footer{border-top:1px solid var(--line);margin-top:56px;padding:26px 28px 40px;color:var(--muted);
font-size:12.5px;text-align:center}
footer code{font-family:var(--mono);background:#f3f4f6;border-radius:5px;padding:1px 5px}
@media(max-width:720px){.article{padding:22px 18px}.nav .zlinks{display:none}.nav input{width:150px}}
"""

JS = r"""
const DATA = JSON.parse(document.getElementById('catalog-data').textContent);
const PAGES = {}; DATA.pages.forEach((p,i)=>{PAGES[p.route]=i;});
const app = document.getElementById('app');

function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');}
function badge(st){
  const cls = st==='✅' ? 'ok' : (st==='📦' ? 'pkg' : 'dead');
  const txt = st==='✅' ? '已安装' : (st==='📦' ? '可安装' : '已移除');
  return `<span class="badge ${cls}">${st} ${txt}</span>`;
}
function nav(){
  return `<nav class="nav">
    <div class="brand" onclick="location.hash='#/'">FDE Skills <span>手册库</span></div>
    <div class="zlinks">${DATA.zones.map(z=>`<a href="#/" onclick="goZone('${z.id}')">${z.label.split('·')[0].trim()}</a>`).join('')}</div>
    <input id="q" type="search" placeholder="搜索 89+ skills…" oninput="onSearch(this.value)">
  </nav>`;
}
function goZone(id){ location.hash='#/'; setTimeout(()=>{const el=document.getElementById('zone-'+id); if(el) el.scrollIntoView({behavior:'smooth'});},30); }

function home(){
  const s = DATA.stats;
  return `${nav()}
  <header class="hero">
    <h1>FDE Skills 手册库</h1>
    <p>每个 skill 一页档案：能做什么 · 何时用（含反向边界）· 最佳实践 · 在 fde-scope 项目中的应用位点。按 FDE 四阶段 + 横切元能力组织，先选场景，再进页面。</p>
    <div class="stats">
      <span class="stat"><b>${s.total}</b>个 skill 档案</span>
      <span class="stat"><b>${s.installed}</b>已安装</span>
      <span class="stat"><b>${s.installable}</b>可安装</span>
      <span class="stat"><b>${s.zoneCount}</b>大区</span>
      <span class="stat"><b>${s.scenarioCount}</b>场景入口</span>
    </div>
  </header>
  <div class="wrap">
    <div id="scen-sec">
      <div class="section-h"><h2>按任务开始</h2><p>GTM 场景速查：从任务进入，而不是从目录进入</p></div>
      <div class="scen-grid">
        ${DATA.scenarios.map(sc=>`<div class="scen"><h3>${sc.title}</h3><div class="d">${sc.desc}</div>
          <div class="links">${sc.items.map(i=>`<a href="#/${i.route}">${i.name}</a>`).join('')}</div></div>`).join('')}
      </div>
    </div>
    <div id="zones-sec" style="margin-top:40px">
      <div class="section-h"><h2>按阶段浏览</h2><p>FDE 四 Zone + 横切元能力</p></div>
      <div class="zone-grid">
        ${DATA.zones.map(z=>`<div class="zone" id="zone-${z.id}">
          <div class="zh" style="--accent:${z.accent}"><h3>${z.label}</h3><p>${z.tag} · ${z.skills.length} 项</p></div>
          <div class="zs">${z.skills.map(k=>`<a href="#/${k.route}"><span class="st">${k.status}</span>${k.name}</a>`).join('')}</div>
        </div>`).join('')}
      </div>
    </div>
    <div id="all-sec" style="margin-top:40px">
      <div class="section-h"><h2>全部 skills</h2><p>支持搜索与状态筛选</p></div>
      <div class="toolbar">
        <button class="chip on" data-f="all" onclick="setFilter(this)">全部</button>
        <button class="chip" data-f="✅" onclick="setFilter(this)">✅ 已安装</button>
        <button class="chip" data-f="📦" onclick="setFilter(this)">📦 可安装</button>
        <span id="hit" style="color:var(--muted);font-size:12.5px"></span>
      </div>
      <div class="all-grid" id="all-grid"></div>
      <div class="empty" id="nohit">没有匹配的 skill</div>
    </div>
  </div>
  ${footer()}`;
}

let statusFilter='all';
function setFilter(btn){
  document.querySelectorAll('.chip').forEach(c=>c.classList.remove('on'));
  btn.classList.add('on'); statusFilter=btn.dataset.f; renderAll();
}
function renderAll(){
  const q=(document.getElementById('q')?.value||'').toLowerCase();
  const grid=document.getElementById('all-grid'); if(!grid) return;
  const items=[];
  DATA.zones.forEach(z=>z.skills.forEach(k=>{
    if(statusFilter!=='all' && k.status!==statusFilter) return;
    if(q && !(k.name+' '+k.blurb+' '+z.label).toLowerCase().includes(q)) return;
    items.push({k,z});
  }));
  grid.innerHTML=items.map(({k,z})=>`<a class="sk" href="#/${k.route}">
    <div class="t">${k.name} ${badge(k.status)}</div><div class="b">${esc(k.blurb)}</div>
    <div class="z">${z.label}</div></a>`).join('');
  document.getElementById('nohit').style.display=items.length?'none':'block';
  const hit=document.getElementById('hit'); if(hit) hit.textContent=`${items.length} 项`;
}
function onSearch(v){
  const hasQ=!!v;
  ['scen-sec','zones-sec','hero'].forEach(id=>{const el=document.getElementById(id)||document.querySelector('.hero'); if(el) el.style.display=(hasQ&&id!=='all-sec')?'none':'';});
  const allSec=document.getElementById('all-sec');
  if(hasQ && allSec) allSec.scrollIntoView({behavior:'smooth'});
  renderAll();
}

function page(route){
  const i=PAGES[route]; if(i===undefined){location.hash='#/';return '';}
  const p=DATA.pages[i];
  const prev=DATA.pages[i-1], next=DATA.pages[i+1];
  return `${nav()}
  <div class="wrap">
    <div class="crumb"><a href="#/">主页</a> › ${p.zone} › <b style="color:var(--ink)">${route.split('/').pop()}</b></div>
    <article class="article">${p.html}</article>
    <div class="pager">
      ${prev?`<a href="#/${prev.route}">← ${prev.route.split('/').pop()}</a>`:'<span></span>'}
      ${next?`<a href="#/${next.route}">${next.route.split('/').pop()} →</a>`:'<span></span>'}
    </div>
  </div>
  ${footer()}`;
}

function footer(){
  const s=DATA.stats;
  return `<footer>
    <div>FDE Skills 手册库 · ${s.total} 页（✅ ${s.installed} · 📦 ${s.installable}）· 建档 2026-08-27 · 数据源 README + 各页 Markdown</div>
    <div style="margin-top:6px">一致性门禁 <code>make check-catalog</code> · 本地对账 <code>make check-local</code> · 改目录后 <code>make build-site</code> 重新生成本页</div>
  </footer>`;
}

function render(){
  const h=location.hash.replace(/^#\/?/,'');
  app.innerHTML = h ? page(h) : home();
  renderAll();
  window.scrollTo(0,0);
}
window.addEventListener('hashchange',render);
render();
"""


def build_html(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FDE Skills 手册库 · 门户</title>
<style>{CSS}</style>
</head>
<body>
<div id="app"></div>
<script id="catalog-data" type="application/json">{payload}</script>
<script>{JS}</script>
</body>
</html>
"""


def main() -> None:
    data = build_data()
    SITE.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build_html(data), encoding="utf-8")
    s = data["stats"]
    print(f"OK {OUT.relative_to(ROOT)} ｜ {s['total']} 页（✅ {s['installed']} / 📦 {s['installable']}）｜ {OUT.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
