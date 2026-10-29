"""Compose the standalone CDN edition of the GTM board from the authored pages.

The authored pages (``index.html`` / ``en/index.html``) are the console-mounted
edition: every link is same-origin (``/sop``, ``/docs/readme``, ``./en/``), which
only resolves inside ``fde-scope web``. On the CDN project each surface is its own
origin and the CDN does no directory indexing, so the published tree needs absolute
links and file-style locale paths. That layer lives here — the authored files are
never rewritten, and ``dist/`` is git-ignored and excluded by ``.dockerignore``.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"

# Real console (Meoo image deploy of fde_scope.web.app:app).
CONSOLE = "https://fg1yhfxa65dj.meoo.fun"
KUBA = "https://github.com/kudig-io/kuba"

# Incident档案 links, in sync-log row order. sync_log.py resolves them from a local
# kuba checkout, which this machine has not — without them the generated rows lose
# their source, so the published edition restores them here.
CASE_URLS = [
    f"{KUBA}/blob/main/incidents/saas-platforms/2015-05-28-ctrip-code-deletion.md",
    f"{KUBA}/blob/main/incidents/cloud-infrastructure/2022-12-18-aliyun-hongkong-outage.md",
    f"{KUBA}/blob/main/incidents/sa-architecture/2025-09-18-clerk-database-incident.md",
    f"{KUBA}/blob/main/incidents/sa-architecture/2025-06-26-clerk-cloudrun-outage.md",
    f"{KUBA}/blob/main/incidents/sa-architecture/2023-09-12-unity-runtime-fee.md",
    f"{KUBA}/blob/main/incidents/networking-dns/2021-10-04-facebook-bgp.md",
]

CASE_SPAN = re.compile(r'<span class="log-case"><span class="(zh|en)">(.*?)</span></span>')

# Console routes carried by the authored pages, longest/most-specific first so
# "/#quickstart" is consumed before the bare "/" rule.
ROUTE_LINKS = [
    ('href="/#quickstart"', "/#quickstart"),
    ('href="/catalog/index.html"', "/catalog/index.html"),
    ('href="/sop"', "/sop"),
    ('href="/"', "/"),
]
DOC_SLUGS = [
    "readme",
    "architecture",
    "ontology",
    "agentscope_api_mapping",
    "manufacturing_scenario",
    "license",
    "notice",
]
LEDE_KUBA = {
    "zh": ("公开复盘库 kuba-database。", '公开复盘库 <a href="%s" target="_blank" rel="noopener">kuba-database</a>。' % KUBA),
    "en": ("postmortem database kuba-database.", 'postmortem database <a href="%s" target="_blank" rel="noopener">kuba-database</a>.' % KUBA),
}
LOCALE_LINK = {"zh": ('href="./en/"', "./en/index.html"), "en": ('href="../"', "../index.html")}

EXTERNAL = re.compile(r'<a href="(https?://[^"]+)"(?![^>]*target=)')


def rewrite(html: str, locale: str) -> str:
    # console route links → absolute, opening in a new tab so the board keeps its context
    for old, path in ROUTE_LINKS:
        html = html.replace(old, f'href="{CONSOLE}{path}" target="_blank" rel="noopener"')
    for slug in DOC_SLUGS:
        html = html.replace(
            f'href="/docs/{slug}"', f'href="{CONSOLE}/docs/{slug}" target="_blank" rel="noopener"'
        )
    html = html.replace(*LEDE_KUBA[locale])
    old, new = LOCALE_LINK[locale]
    html = html.replace(old, f'href="{new}"')

    spans = CASE_SPAN.findall(html)
    if len(spans) != len(CASE_URLS):
        sys.exit(f"{locale}: expected {len(CASE_URLS)} case rows, found {len(spans)}")
    it = iter(CASE_URLS)
    html = CASE_SPAN.sub(
        lambda m: '<a class="log-src" href="%s" target="_blank" rel="noopener">%s ↗ %s</a>'
        % (next(it), m.group(2).split(" · ")[0], m.group(2).split(" · ")[1]),
        html,
    )
    return html


def check(html: str, locale: str) -> None:
    for token in ("--accent:oklch(0.545 0.243 262)", "--layer-01", "--fs-hero"):
        if token not in html:
            sys.exit(f"{locale}: ramp token missing from published tree: {token}")
    if re.search(r'href="/(?!/)', html):
        sys.exit(f"{locale}: unrewritten console link remains")
    for stray in (LOCALE_LINK[locale][0], "blob/main/docs"):
        if stray in html:
            sys.exit(f"{locale}: stray link form survived: {stray}")


def main() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "en").mkdir(parents=True)
    pages = {"zh": ROOT / "index.html", "en": ROOT / "en/index.html"}
    out = {"zh": DIST / "index.html", "en": DIST / "en/index.html"}
    for locale, src in pages.items():
        html = src.read_text(encoding="utf-8")
        rendered = rewrite(html, locale)
        check(rendered, locale)
        out[locale].write_text(rendered, encoding="utf-8")
        print(f"{locale}: {len(html)} -> {len(rendered)} bytes")
    for asset in ("fonts", "images"):
        shutil.copytree(ROOT / asset, DIST / asset)
        print(f"copied {asset}/ -> {len(list((DIST / asset).rglob('*')))} entries")
    live = [m.group(1) for m in EXTERNAL.finditer((DIST / "index.html").read_text(encoding="utf-8"))]
    print(f"external links without target=_blank: {len(live)}")


if __name__ == "__main__":
    main()
