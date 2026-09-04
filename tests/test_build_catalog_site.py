"""Regression tests for ``scripts/build_catalog_site.py`` (site portal builder).

Review fixes (2026-08-31 overall quality review): the Markdown→HTML pipeline
inserted catalog content into the portal unescaped — the same sink class as
the historical ``web/app.py`` storage XSS — and the JSON payload only
neutralized ``</``, leaving the ``<!--`` + ``<script`` parser escape open.
These tests pin the escape-then-transform contract end to end.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "build_catalog_site.py"


def _load():
    spec = importlib.util.spec_from_file_location("build_catalog_site", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_render_inline_escapes_raw_html() -> None:
    bs = _load()
    out = bs.render_inline("<img src=x onerror=alert(1)>", "zone-a/x", set())
    assert "<img" not in out
    assert "&lt;img" in out


def test_render_inline_escapes_inline_code_content() -> None:
    bs = _load()
    out = bs.render_inline("run `<script>alert(1)</script>` now", "zone-a/x", set())
    assert "<script" not in out


def test_link_cannot_inject_attributes_via_target() -> None:
    bs = _load()
    out = bs.render_inline('[x](a"onmouseover="alert(1))', "zone-a/x", set())
    assert 'onmouseover="' not in out
    assert "&quot;" in out


def test_bold_and_internal_links_still_render() -> None:
    bs = _load()
    out = bs.render_inline("**b** and [l](x.md)", "zone-a/y", {"zone-a/x"})
    assert "<strong>b</strong>" in out
    assert '<a href="#/zone-a/x">l</a>' in out


def test_render_markdown_escapes_hostile_headings_and_tables() -> None:
    bs = _load()
    md = "# <img src=x onerror=alert(1)>\n\n| a | b |\n|---|---|\n| <script>alert(1)</script> | ok |"
    out = bs.render_markdown(md, "zone-a/x", set())
    assert "<img" not in out
    assert "<script" not in out
    assert "<table>" in out


def _hostile_catalog(tmp_path: Path) -> None:
    zone = tmp_path / "zone-a-pre-engagement"
    zone.mkdir()
    (zone / "evil.md").write_text("# evil\n\n<script>alert(1)</script>\n", encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "## Zone A\n\n| [<b>evil</b>](zone-a-pre-engagement/evil.md) | ✅ | <img src=x onerror=alert(1)> |\n",
        encoding="utf-8",
    )


def test_build_data_escapes_readme_derived_fields(tmp_path, monkeypatch) -> None:
    bs = _load()
    _hostile_catalog(tmp_path)
    monkeypatch.setattr(bs, "CATALOG", tmp_path)
    monkeypatch.setattr(bs, "SCENARIOS", [])
    data = bs.build_data("zh")
    skill = data["zones"][0]["skills"][0]
    assert "<b>" not in skill["name"]
    assert "<img" not in skill["blurb"]
    assert "<b>" not in data["pages"][0]["html"]


def test_build_html_never_produces_injectable_output(tmp_path, monkeypatch) -> None:
    bs = _load()
    _hostile_catalog(tmp_path)
    monkeypatch.setattr(bs, "CATALOG", tmp_path)
    monkeypatch.setattr(bs, "SCENARIOS", [])
    html = bs.build_html(bs.build_data("zh"))
    assert "<img" not in html
    assert "<script>alert" not in html
    payload = re.search(
        r'<script id="catalog-data" type="application/json">(.*?)</script>', html, re.S
    ).group(1)
    assert "<" not in payload, (
        "payload must not contain a raw '<' (else <!-- + <script can swallow the portal)"
    )
    assert "89+" not in html, "skill count must come from computed stats, not a hardcoded string"
