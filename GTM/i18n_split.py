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
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "index.bilingual.html"
ZH_OUT = ROOT / "index.html"
EN_OUT = ROOT / "en" / "index.html"

ZH_SPAN = re.compile(r'<span class="zh" lang="zh">(.*?)</span>', re.S)
ZH_PAIR = re.compile(
    r"((?:<[^>]+>)+)(.*?)(<span class=\"zh\" lang=\"zh\">)(.*?)(</span>)(.*?)((?:</[^>]+>)+)",
    re.S,
)
ZH_LINE = re.compile(r"\s*<p class=\"zh-line\" lang=\"zh\">(.*?)</p>", re.S)
H1_ZH = re.compile(r"\s*<p class=\"h1-zh\" lang=\"zh\">(.*?)</p>", re.S)

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
    "LIVE CAPTURE · 实机截图 · FDE-Scope-0.1.0-universal2.app · 1440×900 @2x · $ ./appbuild/build_release.sh":
        "实机截图 · FDE-Scope-0.1.0-universal2.app · 1440×900 @2x · $ ./appbuild/build_release.sh",
    "COPY": "复制",
    "COPIED ✓": "已复制 ✓",
}
STATE_EN = {v: k for k, v in STATE_ZH.items()}


def unwrap_zh_span(html: str) -> str:
    """For each 'EN...<span class=zh>ZH</span>...' inside a tag, keep only ZH."""
    prev = None
    while prev != html:
        prev = html
        html = ZH_PAIR.sub(lambda m: f"{m.group(1)}{m.group(4)}{m.group(7)}", html)
    return html


def drop_zh_span(html: str) -> str:
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
    html = html.replace('lang="en"', 'lang="en"', 1)
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
    def h1_sub(m):
        h1, h1_zh = m.group(1), m.group(2)
        return f"{h1}{h1_zh}</h1>"

    html = re.sub(r"(<h1[^>]*>)(.*?)</h1>\s*<p class=\"h1-zh\"[^>]*>([^<]*)</p>", h1_sub, html, flags=re.S)
    # h2: replace heading text with the zh-line copy, drop the zh-line
    html = re.sub(r"(<h2[^>]*>)(.*?)</h2>\s*<p class=\"zh-line\"[^>]*>([^<]*)</p>",
                  lambda m: f"{m.group(1)}{m.group(3)}</h2>", html, flags=re.S)
    return html


def en_title_sections(html: str) -> str:
    html = ZH_LINE.sub("", html)
    html = H1_ZH.sub("", html)
    return html


def zh_labels(html: str) -> str:
    # "Install · 安装" -> "安装"; "Name the crew · 点名" -> "点名"
    def fix(m):
        return f"<span class=\"{m.group(1)}\">{m.group(2)}</span>"

    html = re.sub(
        r'<span class="(crib-label|ledger-head|gates-hint|ps-label)">[^<]*·([^<]*)</span>',
        lambda m: f'<span class="{m.group(1)}">{m.group(2).strip()}</span>',
        html,
    )
    # station zh spans already folded by unwrap; fold "EN ·" divider labels
    html = re.sub(r"<span class=\"(zh-line|h1-zh)\"[^>]*></span>", "", html)
    return html


def en_labels(html: str) -> str:
    html = re.sub(
        r'<span class="(crib-label|ledger-head|gates-hint|ps-label)">([^<]*?)·[^<]*</span>',
        lambda m: f'<span class="{m.group(1)}">{m.group(2).strip()}</span>',
        html,
    )
    return html


def zh_states(html: str) -> str:
    for en, zh in STATE_ZH.items():
        html = html.replace(f">{en}</", f">{zh}</")
    return html


def en_states(html: str) -> str:
    for zh, en in STATE_EN.items():
        html = html.replace(f">{zh}</", f">{en}</")
    return html


def zh_links(html: str) -> str:
    # keep kuba links alive in the zh board (the zh copy has plain text)
    html = html.replace(
        "kuba-database",
        '<a href="https://github.com/kudig-io/kuba" target="_blank" rel="noopener">kuba-database ↗</a>',
    )
    return html


def build_zh(src: str) -> str:
    html = zh_head(src)
    html = zh_title_sections(html)
    html = unwrap_zh_span(html)
    html = zh_labels(html)
    html = zh_states(html)
    html = zh_links(html)
    html = html.replace("FDE SCOPE · GTM BOARD", "FDE SCOPE · GTM BOARD")
    html = html.replace("DIRECTION: SHIFT BOARD · SEED 773793EF", "DIRECTION: ENTERPRISE LIGHT · SEED 773793EF")
    return html


def build_en(src: str) -> str:
    html = en_head(src)
    html = en_title_sections(html)
    html = drop_zh_span(html)
    html = en_labels(html)
    html = en_states(html)
    html = html.replace("DIRECTION: SHIFT BOARD · SEED 773793EF", "DIRECTION: ENTERPRISE LIGHT · SEED 773793EF")
    return html


def main() -> None:
    src = SRC.read_text(encoding="utf-8")
    zh = build_zh(src)
    en = build_en(src)
    for path, text in ((ZH_OUT, zh), (EN_OUT, en)):
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path} ({len(text)} chars)")


if __name__ == "__main__":
    main()