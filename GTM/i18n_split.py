#!/usr/bin/env python3
"""Split the bilingual GTM board into language-specific files.

Reads GTM/index.bilingual.html (the authored source: English-first, every
Chinese line carried in a `<span class="zh" lang="zh">` twin), emits:
  - GTM/index.html      Chinese-primary board (default entry)
  - GTM/en/index.html   English-only board (sub-path /en/)

Neither artifact is ever hand-edited; both are regenerated from the source, and
tests/test_gtm_site_guard.py fails the build unless the output matches this
script byte for byte.

Why the rules look the way they do
----------------------------------
Both artifacts are monolingual, so `.en` and `.zh` are never simultaneously
visible. Any CSS that styled `.zh` as a *second* line under its English twin was
therefore dead code, and the surviving convention is the opposite one: where the
Chinese text is the page's primary content it stays wrapped in `<span class="zh">`
(so `.zh{font-family:var(--zh)}` reaches it), and only the English twin is
removed. Folding never erases a wrapper that carries content.

  rule 0  pairs      <span class="en">A</span><span class="zh" lang="zh">B</span>
                        -> <span class="zh">B</span>
                     Consuming: dropping `lang="zh"` doubles as an
                     "already folded" marker, so rules 1/3a/3/4 (all keyed on
                     `<span class="zh" lang="zh">`) can never re-match a pair,
                     and it makes the zh artifact assertible.
  rule 1  paragraphs  <p class="lede|board-sub">…<span class="zh">B</span></p> -> B
                     The English run may contain inline <span class="mono">, so
                     it is fenced on </p>, not on "<".
  rule 2  station chips <b>L</b> gloss<span class="zh">D</span>
                        -> <b>L</b><span class="zh">D</span>
                     .station is a flex column: label and detail already stack,
                     so an em-dash seam would sit alone on the second line.
                     Station labels are Latin codes -> no B_LABELS lookup.
  rule 3  list items  <b>L</b> gloss<span class="zh">D</span>
                        -> <b>zh(L)</b> — <span class="zh">D</span>
                     These glosses flow INLINE (.log-catch, .lists-col li), so
                     the em-dash seam is kept: without it CJK runs collide
                     ("运行手册回滚路径与安全"). L translates through B_LABELS;
                     stamps with no mapping stay Latin on purpose.
  rule 4  text nodes  TEXT<span class="zh">D</span> -> D
                     Deliberately BARE (no wrapper). `copyText` reads and
                     restores `btn.firstChild.nodeValue` on the copy chips; an
                     Element there makes nodeValue null and silently breaks the
                     button.

`main()` asserts the two invariants that replaced the old residual-span check:
the zh artifact holds zero `<span class="en">` and zero `<span class="zh"
lang="zh">`; the en artifact holds zero CJK outside `<code>`, `data-copy` and the
locale-switch link.

Both outputs are served from inside the app at /GTM/, so every anchor points at
an in-app route: tests/test_web.py fails the build if an external href or a
target="_blank" appears in either artifact. Repo prose is linked through the
in-app readers (/docs/readme, /sop, /docs/license) instead of github.com URLs.
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

# rule 3: <b> label -> Chinese label. Keys are the 31 translated list-item labels.
# The six mono log stamps (FDE · GATE slo, SA · PHASE 07 · REAL DATA, ...) and the
# path names deploy/ and connectors/documents.py are absent by design: technical
# field names stay Latin in both builds.
B_LABELS = {
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
    "MIT license": "MIT 开源协议",
    "Community support": "社区支持",
    "Everything in Community": "社区版全量",
    "Per-seat subscription": "按席位订阅",
    "Priority support": "优先支持",
    "Team onboarding": "团队导入",
    "Everything in Pro": "Pro 全量",
    "Audit + evidence chain": "审计 + 证据链",
    "Custom connector adaptation": "专属连接器",
    "SLA": "SLA 保障",
}

# CJK prose: Han, CJK punctuation, fullwidth forms. Circled numerals
# (U+2460-U+24FF, e.g. the gate chip "G7") are deliberately excluded: they are
# diagram furniture, present in both builds.
CJK = re.compile("[\\u4e00-\\u9fff\\u3000-\\u303f\\uff00-\\uffef]")

ZH_PAIR = re.compile(r'<span class="en">[^<]*</span><span class="zh" lang="zh">([^<]*)</span>')
ZH_SPAN = re.compile(r'<span class="zh"[^>]*>(.*?)</span>', re.S)
ZH_FENCE = re.compile(r"[ \t]*//i18n-zh-begin\n.*?//i18n-zh-end\n", re.S)
ZH_FENCE_KEEP_INNER = re.compile(r"[ \t]*//i18n-zh-(?:begin|end)\n", re.S)


def zh_fold_spans(html: str) -> str:
    """Fold bilingual patterns into Chinese-primary, in bounded-safe order."""
    # 0. consuming pair fold (see module docstring)
    html = ZH_PAIR.sub(lambda m: f'<span class="zh">{m.group(1)}</span>', html)
    # 1. lede / board-sub paragraphs: the Chinese run is the primary copy
    html = re.sub(
        r'(<p class="(?:lede|board-sub)">)(?:(?!</p>).)*?<span class="zh" lang="zh">(.*?)</span>\s*</p>',
        lambda m: m.group(1) + m.group(2) + "</p>",
        html,
        flags=re.S,
    )
    # 2. station chips: flex column, no seam, label stays Latin
    html = re.sub(
        r'<span class="station"><b>([^<]+)</b>[^<]*<span class="zh" lang="zh">([^<]*)</span>',
        lambda m: f'<span class="station"><b>{m.group(1)}</b><span class="zh">{m.group(2)}</span>',
        html,
    )
    # 3. inline label + gloss: translate the label, keep the em-dash seam
    html = re.sub(
        r"<b>([^<]+)</b>[^<]*<span class=\"zh\" lang=\"zh\">([^<]*)</span>",
        lambda m: f'<b>{B_LABELS.get(m.group(1), m.group(1))}</b> — <span class="zh">{m.group(2)}</span>',
        html,
    )
    # 4. bare text node + gloss: the Chinese replaces it, wrapper-free
    html = re.sub(
        r'([^<>]+)<span class="zh" lang="zh">([^<]*)</span>',
        r"\2",
        html,
    )
    return html


def en_drop_spans(html: str) -> str:
    return ZH_SPAN.sub("", html)


def en_drop_script_block(html: str) -> str:
    """Remove the Chinese L10N reassignment from the English build."""
    return ZH_FENCE.sub("", html)


def zh_drop_fence_markers(html: str) -> str:
    """Keep the reassignment, drop the comments that delimit it."""
    return ZH_FENCE_KEEP_INNER.sub("", html)


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


def language_switch(html: str, lang: str) -> str:
    """Append the sibling-locale link to the top nav.

    Anchored on `</nav>` rather than on a specific link's label, so relabelling
    or reordering nav items cannot silently drop the switch.
    """
    switch = (
        '<a href="./en/" hreflang="en" lang="en">ENGLISH</a>'
        if lang == "zh"
        else '<a href="../" hreflang="zh-CN" lang="zh-CN">中文</a>'
    )
    if "</nav>" not in html:
        sys.exit("nav language switch not injected: no </nav> in the source")
    return html.replace("</nav>", switch + "</nav>", 1)


def rewrite_assets_for_en(html: str) -> str:
    # en/index.html lives one level deeper; relative assets need ../
    html = html.replace("url(fonts/", "url(../fonts/")
    html = html.replace('src="images/', 'src="../images/')
    return html


def build_zh(src: str) -> str:
    html = zh_head(src)
    html = zh_title_sections(html)
    html = zh_fold_spans(html)
    html = zh_drop_fence_markers(html)
    html = language_switch(html, "zh")
    return html


def build_en(src: str) -> str:
    html = en_head(src)
    html = en_title_sections(html)
    html = en_drop_script_block(html)
    html = en_drop_spans(html)
    html = language_switch(html, "en")
    html = rewrite_assets_for_en(html)
    return html


def en_cjk_leaks(html: str) -> list[str]:
    """CJK surviving in the English artifact, excluding the three sanctioned kinds.

    `<code>` blocks quote real repo paths and CLI output, and `data-copy` holds
    the literal text a copy chip writes to the clipboard; both legitimately carry
    Chinese and never render as prose. So does the locale switch: a link to the
    Chinese build reads 中文 by definition, in either direction.
    """
    probe = re.sub(r"<code\b[^>]*>.*?</code>", "", html, flags=re.S)
    probe = re.sub(r"\sdata-copy=\"[^\"]*\"", "", probe)
    probe = re.sub(r'<a [^>]*hreflang="zh-CN"[^>]*>[^<]*</a>', "", probe)
    return [
        re.sub(r"\s+", " ", probe[max(0, m.start() - 60) : m.start() + 40]).strip()
        for m in CJK.finditer(probe)
    ]


def zh_residual_spans(html: str) -> tuple[int, int]:
    return (
        len(re.findall(r'<span class="en"', html)),
        len(re.findall(r'<span class="zh" lang="zh"', html)),
    )


def main() -> None:
    src = SRC.read_text(encoding="utf-8")
    zh = build_zh(src)
    en = build_en(src)

    en_spans, un_folded = zh_residual_spans(zh)
    if en_spans or un_folded:
        sys.exit(f'zh output: {en_spans} <span class="en">, {un_folded} unfoldable zh spans')
    leaks = en_cjk_leaks(en)
    if leaks:
        sys.exit("en output leaks CJK into prose:\n  " + "\n  ".join(leaks[:12]))

    ZH_OUT.write_text(zh, encoding="utf-8")
    EN_OUT.write_text(en, encoding="utf-8")
    print(f"wrote {ZH_OUT} ({len(zh)} chars, zero English twins, zero unfoldable spans)")
    print(f"wrote {EN_OUT} ({len(en)} chars, zero CJK in prose)")
    print(f"zh/en char ratio: {len(zh) / len(en):.2f}")


if __name__ == "__main__":
    main()
