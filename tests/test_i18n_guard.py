"""i18n key-drift guards (plan §10.1 step 1).

``to_en`` is exact-substring replacement: if someone edits a Chinese string in
``app.py`` without updating its pair in ``I18N_PAIRS``, the English console
silently keeps serving Chinese for that spot. These tests make that drift
loud: every key must still exist in the zh rendering target, no key may be
duplicated (order-dependent replaces make duplicates a trap), and the EN
output must stay free of CJK except the deliberate language switcher.
"""

from __future__ import annotations

import re

CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]")


def test_every_i18n_key_exists_in_its_zh_target() -> None:
    """A pair whose zh key no longer appears in the shells it translates is
    dead weight at best and a silent gap at worst — fail so the pair gets
    fixed or removed when the source string changes."""
    from fde_scope.web.app import _DASHBOARD_HTML, _OVERVIEW_HTML
    from fde_scope.web.i18n import I18N_PAIRS

    target = _DASHBOARD_HTML + _OVERVIEW_HTML
    missing = [zh for zh, _en in I18N_PAIRS if zh not in target]
    assert missing == [], f"{len(missing)} i18n key(s) no longer match their zh source: {missing[:5]}"


def test_i18n_keys_are_unique() -> None:
    """Replacement is applied longest-key-first over the whole document; a
    duplicated key makes the result depend on list order, which is a trap."""
    from fde_scope.web.i18n import I18N_PAIRS

    keys = [zh for zh, _en in I18N_PAIRS]
    duplicates = sorted({k for k in keys if keys.count(k) > 1})
    assert duplicates == [], f"duplicated i18n keys: {duplicates[:5]}"


def test_en_dashboard_has_no_untranslated_cjk() -> None:
    """The EN console is fully translated except the deliberate language
    switcher link. This is the running version of the diagnostic used while
    closing the P1 i18n gap: add a pair or justify an exception, never ship
    zh leftovers."""
    from fde_scope.web.app import _DASHBOARD_HTML
    from fde_scope.web.i18n import to_en

    en = to_en(_DASHBOARD_HTML)
    leftovers = [ln.strip()[:120] for ln in en.split("\n") if CJK.search(ln)]
    assert leftovers == ['<a class="lang" href="/console" title="中文版" aria-label="切换到中文">中文</a>'], (
        f"untranslated CJK reached the EN console: {leftovers[:5]}"
    )


def test_en_home_has_no_untranslated_cjk() -> None:
    from fde_scope.web.app import _OVERVIEW_HTML
    from fde_scope.web.i18n import to_en

    en = to_en(_OVERVIEW_HTML)
    leftovers = [ln.strip()[:120] for ln in en.split("\n") if CJK.search(ln)]
    assert leftovers == ['<a class="lang" href="/" title="中文版" aria-label="切换到中文">中文</a>'], (
        f"untranslated CJK reached the EN home page: {leftovers[:5]}"
    )
