"""Build guard for the GTM board (``GTM/i18n_split.py``).

``GTM/index.html`` and ``GTM/en/index.html`` are *generated* from
``GTM/index.bilingual.html``, but they had drifted: hand edits to the shipped
files (the in-app nav labels) never reached the source, so re-running the split
silently reverted them. These tests pin that the shipped artifacts are exactly
what the generator produces, that the no-external-anchor invariant
``tests/test_web.py`` enforces on the served pages also holds in the source they
are built from, and that each split is monolingual without dropping a label.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

GTM_DIR = Path(__file__).resolve().parents[1] / "GTM"
SCRIPT = GTM_DIR / "i18n_split.py"

pytestmark = pytest.mark.skipif(not SCRIPT.exists(), reason="GTM site not present in this checkout")


def _load():
    spec = importlib.util.spec_from_file_location("gtm_i18n_split", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_shipped_pages_are_reproducible_from_the_bilingual_source() -> None:
    """Editing a shipped page by hand is a build error: change
    ``GTM/index.bilingual.html`` and re-run ``python GTM/i18n_split.py``."""
    mod = _load()
    src = (GTM_DIR / "index.bilingual.html").read_text(encoding="utf-8")
    for path, built in ((mod.ZH_OUT, mod.build_zh(src)), (mod.EN_OUT, mod.build_en(src))):
        assert path.read_text(encoding="utf-8") == built, f"{path} is out of sync with the split"


def test_no_external_anchor_anywhere_in_the_build() -> None:
    """The board is served from inside the app at ``/GTM/`` and stays
    self-contained: repo prose is linked through the in-app readers
    (``/docs/readme``, ``/sop``, ``/docs/license``), never github.com."""
    for name in ("index.bilingual.html", "index.html", "en/index.html"):
        text = (GTM_DIR / name).read_text(encoding="utf-8")
        assert re.search(r'<a [^>]*href="https?://', text) is None, name
        assert 'target="_blank"' not in text, name


def test_no_anchor_labels_an_in_app_route_as_github() -> None:
    """``href="/"`` is the console. Labelling it "GitHub" sent every visitor to
    the wrong place on both locales (the entry the P0 fix removed)."""
    for name in ("index.bilingual.html", "index.html", "en/index.html"):
        text = (GTM_DIR / name).read_text(encoding="utf-8")
        assert re.search(r'<a [^>]*href="/"[^>]*>[^<]*GitHub', text) is None, name
        assert "Star on GitHub" not in text, name


def test_zh_artifact_carries_no_english_twin_or_unfolded_pair() -> None:
    """The Chinese build is monolingual. Every ``<span class="en">`` is deleted
    and every ``.en``/``.zh`` pair is folded into a bare ``<span class="zh">``
    (or plain text where a copy chip reads ``firstChild.nodeValue``), so neither
    an English twin nor a leftover ``lang="zh"`` marker may survive."""
    text = (GTM_DIR / "index.html").read_text(encoding="utf-8")
    assert '<span class="en">' not in text
    assert '<span class="zh" lang="zh">' not in text


def test_zh_artifact_keeps_every_glossed_label() -> None:
    """Folding rewrites the wrapper, never the text. The split once ate whole
    label families (the quick-start crib), and a reproducible-but-lossy build
    still passes the byte-exact test above, so coverage is checked per label."""
    mod = _load()
    src = (GTM_DIR / "index.bilingual.html").read_text(encoding="utf-8")
    zh = (GTM_DIR / "index.html").read_text(encoding="utf-8")
    norm = lambda s: re.sub(r"\s+", " ", s).strip()  # noqa: E731
    folded = norm(zh)
    missing = [c for c in mod.ZH_SPAN.findall(src) if norm(c) and norm(c) not in folded]
    assert not missing, f"zh build dropped {len(missing)} glossed labels: {missing[:5]}"


def test_en_artifact_has_no_cjk_in_prose() -> None:
    """Mirror of the splitter's own guard, so a regression is a failing test and
    not a broken build. ``<code>`` blocks quote real repo paths and CLI output,
    ``data-copy`` holds the literal a copy chip writes, and the ``hreflang``
    link is the locale switch; those three legitimately carry Chinese."""
    mod = _load()
    src = (GTM_DIR / "index.bilingual.html").read_text(encoding="utf-8")
    leaks = mod.en_cjk_leaks(mod.build_en(src))
    assert not leaks, f"en output leaks CJK into prose: {leaks[:5]}"
    assert '<span class="zh">' not in (GTM_DIR / "en" / "index.html").read_text(encoding="utf-8")
