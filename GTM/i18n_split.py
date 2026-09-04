#!/usr/bin/env python3
"""Split the bilingual GTM board into language-specific files.

Reads GTM/index.bilingual.html (the en-first + .zh-annotated single file),
emits:
  - GTM/index.html      Chinese-primary board (default entry, what Meoo serves)
  - GTM/en/index.html   English-only board (sub-path /en/)

Run GTM/sync_log.py --lang zh --page index.html and
      GTM/sync_log.py --lang en --page en/index.html afterwards to fill the
incident-log sentinels per language.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "index.bilingual.html"
ZH_OUT = ROOT / "index.html"
EN_OUT = ROOT / "en" / "index.html"

TITLE_ZH = "FDE Scope：把完整 FDE 作业流程固化为门禁强制的状态机"
META_ZH = (
    "FDE Scope 把完整的外派工程师（FDE）作业流程（4 大区、18 阶段、10 个可执行门禁）"
    "固化为门禁强制推进的状态机：证据不齐，拒绝推进。软件现场与工厂车间共用同一台引擎。"
)
TITLE_EN = "FDE Scope: The Full FDE SOP, Enforced"
META_EN = (
    "FDE Scope turns the complete Forward-Deployed-Engineer SOP (4 zones, 18 phases, "
    "10 executable gates) into a gate-enforced state machine. Software desks and factory floors alike."
)

# state badges -> per-language display
STATE_ZH = {
    "SIGNED": "已签收",
    "RUNBOOK": "运行中",
    "BLOCKED": "阻断",
    "FLYWHEEL": "飞轮",
    "PROTOTYPE": "原型",
    "DEMO DATA · 演示数据 · seeded by examples/seed_mock_engagements.py; every record engine-generated.":
        "演示数据 · 由 examples/seed_mock_engagements.py 种入；每条门禁记录均由引擎生成。",
    "VERIFIED BY: CI-green suite · contract pins tests/test_architecture_guard.py · evidence model docs/architecture-model/architecture-map.md":
        "验证来源：CI 全绿套件 · 契约测试 tests/test_architecture_guard.py · 证据模型 docs/architecture-model/architecture-map.md",
    "LIVE CAPTURE · FDE-Scope-0.1.0-universal2.app · 1440×952 @2x · macOS window · $ ./appbuild/build_release.sh":
        "实机截图 · FDE-Scope-0.1.0-universal2.app · 1440×952 @2x · macOS 窗口 · $ ./appbuild/build_release.sh",
    "COPY": "复制",
    "COPIED ✓": "已复制 ✓",
}

# <b>EN label</b>[en gloss]<span class="zh">detail</span> list items -> zh label
B_LABELS = {
    "ROSTER": "花名册",
    "SUBAGENT TEMPLATE": "子代理模板",
    "AGENTCREATE · TEAM SAY": "AGENTCREATE · TEAM SAY",
    "SERVE": "SERVE",
    "SKILL CAPTURE": "技能捕获",
    "REVIEW": "审阅",
    "PUBLISH": "发布",
    "EXPORT": "导出",
    "18-phase SOP": "18 阶段 SOP",
    "2 profiles": "2 套场景",
    "10 data connectors": "10 个数据连接器",
    "Corpus forge": "语料锻造",
    "Eval + industrial KPI": "评估 + 工业 KPI",
    "Skills library": "技能库",
    "Ontology semantic layer": "本体语义层",
    "Deploy three-pillar": "部署三支柱",
    "Handoff + flywheel": "交接 + 飞轮",
    "Core layers": "核心层",
    "Cross-cutting": "横切层",
    "deploy/": "deploy/",
    "connectors/documents.py": "connectors/documents.py",
    "4 surfaces": "4 个界面",
    "Evidence model": "证据模型",
    "Live gate re-evaluation": "门禁实时重评",
    "Server-generated IDs": "服务端生成 ID",
    "Credentials env-only": "密钥仅存环境变量",
    "Atomic writes": "原子写入",
    "Rule grants only": "仅规则授权",
    "Measured AgentScope window": "实测 AgentScope 窗口",
}

# figure captions
FIGCAP_ZH = {
    "<b>ENGAGEMENT CONSOLE · 工作台</b><small>cross-project matrix · gates · recent skills</small>":
        "<b>工作台</b><small>跨项目矩阵 · 门禁 · 最近技能</small>",
    "<b>FUNCTIONAL OVERVIEW · 功能总览</b><small>18 phases · 4 zones · 10 gates · 10 connectors</small>":
        "<b>功能总览</b><small>18 阶段 · 4 大区 · 10 门禁 · 10 连接器</small>",
}
FIGCAP_EN = {
    "<b>ENGAGEMENT CONSOLE · 工作台</b>": "<b>ENGAGEMENT CONSOLE</b>",
    "<b>FUNCTIONAL OVERVIEW · 功能总览</b>": "<b>FUNCTIONAL OVERVIEW</b>",
}

JS_ZH = {
    "REFUSED · functional_safety: hazard analysis missing":
        "拒绝推进 · functional_safety：缺少危害分析",
    "OK · phase 12 runbook": "OK · 第 12 阶段 · 运行手册",
    "advance → REFUSED<br>hazard analysis missing": "advance → 拒绝推进<br>缺少危害分析",
    "industrial-only · 工业专属，ticket 不适用": "工业专属 · ticket 不适用",
    '"COPIED"': '"已复制"',
}

ZH_SPAN = re.compile(r'<span class="zh" lang="zh">(.*?)</span>', re.S)


def zh_fold_spans(html: str) -> str:
    """Fold bilingual patterns into pure Chinese, in bounded-safe order.

    Every pattern is anchored so it cannot span structural boundaries:
    lede/board-sub blocks are fenced by (?!</p>), inline pairs by [^<],
    and the text-node rule cannot cross a tag.
    """
    # 1. paragraph blocks whose English run ends at the zh span (may contain
    #    inline <a> tags, so fence on the closing </p> only)
    html = re.sub(
        r'(<p class="(?:lede|board-sub)">)(?:(?!</p>).)*?<span class="zh" lang="zh">(.*?)</span>\s*</p>',
        lambda m: m.group(1) + m.group(2) + "</p>",
        html,
        flags=re.S,
    )
    # 2. <span class="en">EN</span><span class="zh">ZH</span> -> ZH
    html = re.sub(
        r'<span class="en">[^<]*</span><span class="zh" lang="zh">(.*?)</span>',
        r"\1",
        html,
        flags=re.S,
    )
    # 3. <b>EN label</b>[en gloss]<span class="zh">ZH</span> -> <b>zh label</b>ZH
    html = re.sub(
        r"<b>([^<]+)</b>[^<]*<span class=\"zh\" lang=\"zh\">(.*?)</span>",
        lambda m: f"<b>{B_LABELS.get(m.group(1), m.group(1))}</b>{m.group(2)}",
        html,
        flags=re.S,
    )
    # 4. text node + zh span -> zh (drop the English text node)
    html = re.sub(
        r'([^<>]+)<span class="zh" lang="zh">(.*?)</span>',
        r"\2",
        html,
        flags=re.S,
    )
    # 5. any remaining zh span: unwrap
    html = ZH_SPAN.sub(r"\1", html)
    return html


def en_drop_spans(html: str) -> str:
    return ZH_SPAN.sub("", html)


def zh_head(html: str) -> str:
    html = html.replace('lang="en"', 'lang="zh-CN"', 1)
    html = re.sub(r"<title>.*?</title>", f"<title>{TITLE_ZH}</title>", html, count=1, flags=re.S)
    html = re.sub(
        r'<meta name="description" content="[^"]*"',
        f'<meta name="description" content="{META_ZH}"',
        html,
        count=1,
    )
    return html


def en_head(html: str) -> str:
    html = re.sub(r"<title>.*?</title>", f"<title>{TITLE_EN}</title>", html, count=1, flags=re.S)
    html = re.sub(
        r'<meta name="description" content="[^"]*"',
        f'<meta name="description" content="{META_EN}"',
        html,
        count=1,
    )
    return html


def zh_title_sections(html: str) -> str:
    # h1: pull the .h1-zh line into the heading, then drop the line
    html = re.sub(
        r"(<h1[^>]*>)(.*?)</h1>\s*<p class=\"h1-zh\"[^>]*>(.*?)</p>",
        lambda m: f"{m.group(1)}{m.group(3)}</h1>",
        html,
        flags=re.S,
    )
    # h2: replace heading text with the zh-line copy, drop the zh-line
    html = re.sub(
        r"(<h2[^>]*>)(.*?)</h2>\s*<p class=\"zh-line\"[^>]*>(.*?)</p>",
        lambda m: f"{m.group(1)}{m.group(3)}</h2>",
        html,
        flags=re.S,
    )
    return html


def en_title_sections(html: str) -> str:
    html = re.sub(r"\s*<p class=\"zh-line\"[^>]*>.*?</p>", "", html, flags=re.S)
    html = re.sub(r"\s*<p class=\"h1-zh\"[^>]*>.*?</p>", "", html, flags=re.S)
    return html


def split_labels(html: str, keep: str) -> str:
    """crib-label etc. hold 'EN · 中文'; keep one side."""
    cls = "crib-label|ledger-head|gates-hint|ps-label"

    def fix(m):
        en, zh = m.group(2), m.group(3)
        return f'<span class="{m.group(1)}">{(en if keep == "en" else zh).strip()}</span>'

    return re.sub(
        rf'<span class="({cls})">([^<]*?)\s*·\s*([^<]*?)</span>', fix, html
    )


def zh_buttons(html: str) -> str:
    html = html.replace("TICKET · 客服工单", "客服工单")
    html = html.replace("MANUFACTURING · 工厂", "工厂")
    return html


def en_buttons(html: str) -> str:
    html = html.replace("TICKET · 客服工单", "TICKET")
    html = html.replace("MANUFACTURING · 工厂", "MANUFACTURING")
    return html


def nav_links(html: str, lang: str) -> str:
    if lang == "zh":
        html = html.replace(
            '<a href="https://github.com/ai-guru-global/fde-scope/blob/main/docs/fde_sop_full.md" target="_blank" rel="noopener">SOP DOCS</a>',
            '<a href="https://github.com/ai-guru-global/fde-scope/blob/main/docs/fde_sop_full.md" target="_blank" rel="noopener">SOP 文档</a>',
        )
        html = html.replace(
            '<a href="https://github.com/ai-guru-global/fde-scope/blob/main/docs/skills-catalog/site/index.html" target="_blank" rel="noopener">SKILLS · 技能库</a>',
            '<a href="https://github.com/ai-guru-global/fde-scope/blob/main/docs/skills-catalog/site/index.html" target="_blank" rel="noopener">技能手册库</a>',
        )
        html = html.replace(
            '<a href="#crib">QUICK START</a>',
            '<a href="#crib">快速开始</a><a href="./en/" hreflang="en" lang="en">ENGLISH</a>',
        )
        html = html.replace(
            "<small>FORWARD-DEPLOYED OPERATING SYSTEM · MIT</small>",
            "<small>外派工程师作业系统 · MIT</small>",
        )
        html = html.replace("FDE SCOPE · GTM BOARD", "FDE SCOPE · GTM 看板")
    else:
        html = html.replace(
            '<a href="https://github.com/ai-guru-global/fde-scope/blob/main/docs/skills-catalog/site/index.html" target="_blank" rel="noopener">SKILLS · 技能库</a>',
            '<a href="https://github.com/ai-guru-global/fde-scope/blob/main/docs/skills-catalog/site/index.html" target="_blank" rel="noopener">SKILLS</a>',
        )
        html = html.replace(
            '<a href="#crib">QUICK START</a>',
            '<a href="#crib">QUICK START</a><a href="../" hreflang="zh-CN" lang="zh-CN">中文</a>',
        )
    return html


def zh_states(html: str) -> str:
    for en, zh in STATE_ZH.items():
        html = html.replace(f">{en}</", f">{zh}</")
    for en, zh in JS_ZH.items():
        html = html.replace(en, zh)
    return html


def rewrite_assets_for_en(html: str) -> str:
    # en/index.html lives one level deeper; relative assets need ../
    html = html.replace("url(fonts/", "url(../fonts/")
    html = html.replace('src="images/', 'src="../images/')
    return html


def build_zh(src: str) -> str:
    html = zh_head(src)
    html = zh_title_sections(html)
    html = zh_fold_spans(html)
    html = split_labels(html, "zh")
    html = zh_buttons(html)
    html = nav_links(html, "zh")
    for en, zh in FIGCAP_ZH.items():
        html = html.replace(en, zh)
    html = zh_states(html)
    html = html.replace("DIRECTION: SHIFT BOARD · SEED 773793EF", "DIRECTION: ENTERPRISE LIGHT · SEED 773793EF")
    return html


def build_en(src: str) -> str:
    html = en_head(src)
    html = en_title_sections(html)
    html = en_drop_spans(html)
    html = split_labels(html, "en")
    html = en_buttons(html)
    html = nav_links(html, "en")
    for en, en2 in FIGCAP_EN.items():
        html = html.replace(en, en2)
    html = html.replace("DIRECTION: SHIFT BOARD · SEED 773793EF", "DIRECTION: ENTERPRISE LIGHT · SEED 773793EF")
    html = rewrite_assets_for_en(html)
    return html


def main() -> None:
    src = SRC.read_text(encoding="utf-8")
    zh = build_zh(src)
    en = build_en(src)
    for path, text, lang in ((ZH_OUT, zh, "zh"), (EN_OUT, en, "en")):
        path.write_text(text, encoding="utf-8")
        residual = len(ZH_SPAN.findall(text))
        print(f"wrote {path} ({len(text)} chars, {residual} residual zh spans)")
        if lang == "zh" and residual:
            sys.exit(f"zh output still contains {residual} zh spans")
    print(f"zh/en char ratio: {len(zh) / len(en):.2f}")


if __name__ == "__main__":
    main()
