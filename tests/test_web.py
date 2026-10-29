"""Tests for the Web UI FastAPI app."""

from __future__ import annotations

import re
from html import escape
from pathlib import Path

import pytest

from fde_scope.web.mdrender import fenced_indices

pytestmark = pytest.mark.filterwarnings("ignore")


@pytest.fixture
def client(tmp_path, monkeypatch):
    # run the app out of a tmp dir so engagements/uploads/reports don't
    # pollute the repo working tree
    monkeypatch.chdir(tmp_path)
    from fastapi.testclient import TestClient

    from fde_scope.web.app import app

    return TestClient(app)


def test_health(client) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_reports_real_checks(client, monkeypatch) -> None:
    monkeypatch.delenv("FDE_SCOPE_MIMO_API_KEY", raising=False)
    monkeypatch.delenv("FDE_SCOPE_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("FDE_SCOPE_LLM_API_KEY", raising=False)
    body = client.get("/api/health").json()
    checks = body["checks"]
    assert checks["data_root"]["ok"] is True
    assert "path" in checks["data_root"]
    assert checks["reports_dir"]["ok"] is True
    assert checks["llm"] == {"ok": True, "configured": False}
    assert checks["engagements_count"] == {"ok": True, "count": 0}


def test_health_counts_engagements(client) -> None:
    client.post("/api/engagements", data={"customer": "HealthCo", "profile": "ticket"})
    body = client.get("/api/health").json()
    assert body["checks"]["engagements_count"]["count"] == 1
    assert body["status"] == "ok"


def test_health_llm_configured_via_env(client, monkeypatch) -> None:
    monkeypatch.setenv("FDE_SCOPE_MIMO_API_KEY", "tp-health")
    resp = client.get("/api/health")
    assert resp.json()["checks"]["llm"]["configured"] is True
    assert "tp-health" not in resp.text  # the key itself never leaves the env


def test_overview_html(client) -> None:
    """The landing page at / shows the feature overview."""
    r = client.get("/")
    assert r.status_code == 200
    assert "FDE Scope" in r.text
    assert "SOP" in r.text  # the overview mentions the SOP


def test_console_html(client) -> None:
    """The engagement console lives at /console."""
    r = client.get("/console")
    assert r.status_code == 200
    assert "Engagement Console" in r.text


def test_console_uses_the_shared_shell(client) -> None:
    """Guard against regressing to a hand-copied shell in the console page."""
    for path in ("/console", "/en/console"):
        html = client.get(path).text
        assert 'class="shell"' in html and 'class="side"' in html
        assert "grid-template-columns:300px" not in html  # 旧手抄侧栏
        assert 'use href="#i-gauge"/></svg>工作台' not in html  # 旧图标按钮
        assert "--z-toast" in html  # console 专属块仍在


# ---------------------------------------------------------------------------
# bilingual routes（/en/* 英文壳，与 zh 同源模板经 to_en 生成）
# ---------------------------------------------------------------------------
def test_en_overview_html(client) -> None:
    """/en/ serves the English overview shell."""
    r = client.get("/en/")
    assert r.status_code == 200
    assert '<html lang="en">' in r.text
    assert "Ontology semantic layer · TBox + ABox" in r.text
    assert "Ontology 语义层" not in r.text


def test_en_console_html(client) -> None:
    """/en/console serves the English console shell."""
    r = client.get("/en/console")
    assert r.status_code == 200
    assert '<html lang="en">' in r.text
    assert "Workbench</button>" in r.text
    assert "Skills</button>" in r.text
    assert "工作台</button>" not in r.text


def test_language_switcher_badges(client) -> None:
    """zh pages badge to /en/*; EN pages flip the badge back to zh routes."""
    zh_home = client.get("/").text
    zh_console = client.get("/console").text
    en_home = client.get("/en/").text
    en_console = client.get("/en/console").text
    assert 'href="/en/"' in zh_home
    assert 'href="/en/console"' in zh_console
    assert 'aria-label="Switch to English"' in zh_home
    assert 'aria-label="切换到中文"' in en_home
    assert 'aria-label="切换到中文"' in en_console


def test_glossary_tooltips_are_gone_from_the_shells(client) -> None:
    """The inline ?-tooltips were removed; terms live on /glossary only."""
    for path in ("/", "/en/", "/console", "/en/console"):
        html = client.get(path).text
        assert "__GLOSSARY__" not in html
        assert '<span class="term"' not in html
        assert ".term .tip" not in html
        assert "window.glossify" not in html


# ---------------------------------------------------------------------------
# glossary（/glossary · 术语按主题分组，独立成页）
# ---------------------------------------------------------------------------
def test_glossary_html(client) -> None:
    """/glossary serves every term of the shared vocabulary, grouped."""
    from fde_scope.web.i18n import GLOSSARY_ZH

    r = client.get("/glossary")
    assert r.status_code == 200
    assert '<html lang="zh">' in r.text
    assert "名词解释" in r.text
    assert "__GLOSSARY__" not in r.text
    assert "__ICON_SPRITE__" not in r.text  # placeholder is filled by app.py
    missing = [term for term, _ in GLOSSARY_ZH if term not in r.text]
    assert missing == []
    assert r.text.count('<div class="card" data-t=') == len(GLOSSARY_ZH)  # no duplicates


def test_en_glossary_html(client) -> None:
    """/en/glossary is rendered from paired literals (no to_en pass), so no
    Chinese can leak in: the only CJK left is the deliberate source-term
    alias and the 中文 switch back to the zh page."""
    import re

    from fde_scope.web.i18n import GLOSSARY_EN

    r = client.get("/en/glossary")
    assert r.status_code == 200
    assert '<html lang="en">' in r.text
    assert "Every term in this material, one line each" in r.text
    missing = [term for term, _ in GLOSSARY_EN if term not in r.text]
    assert missing == []
    assert r.text.count('<div class="card" data-t=') == len(GLOSSARY_EN)

    stripped = r.text.replace('<a class="lang" href="/glossary">中文</a>', "")
    stripped = re.sub(r'<span class="alias">[^<]*</span>', "", stripped)
    # the per-card search haystack deliberately carries the zh alias — it is
    # machine-read, not rendered text
    stripped = re.sub(r'data-t="[^"]*"', "", stripped)
    leaked = [ln for ln in stripped.splitlines() if re.search(r"[\u4e00-\u9fff]", ln)]
    assert leaked == []


def test_glossary_has_instant_search_and_glosses_are_escaped(client) -> None:
    """≈80 terms with no filter was unusable (plan §4.1); the search box hides
    non-matching cards and empty groups client-side. Glosses and aliases go
    through ``html.escape`` so a future dynamic source cannot become an XSS
    sink (plan §4.3), and a back-to-top link closes the long page (§4.5)."""
    from fde_scope.web.glossary import GLOSSARY_ZH, render

    html = render("zh")
    assert 'id="gl-q"' in html and 'oninput="glFilter(this.value)"' in html
    assert 'aria-label="搜索术语"' in html
    assert "glFilter" in html and "gl-empty" in html
    assert 'id="top"' in html and "回到顶部" in html
    # every card is filterable on term, alias and gloss
    assert html.count("data-t=") == len(GLOSSARY_ZH)
    en = render("en")
    assert 'aria-label="Search terms"' in en and "No matching terms." in en


def test_glossary_grouping_is_total(client) -> None:
    """Every term is filed into exactly one group; nothing falls to the
    catch-all, which would mean a term rendered under 『其他』."""
    from fde_scope.web.glossary import _GROUPS, _group_terms
    from fde_scope.web.i18n import GLOSSARY_ZH

    keys = [term for term, _ in GLOSSARY_ZH]
    listed = [term for *_, group in _GROUPS for term in group]
    assert sorted(listed) == sorted(keys)  # no term twice, none unlisted
    groups = _group_terms(keys)
    assert len(groups) == len(_GROUPS)  # no catch-all group was appended
    assert "其他" not in client.get("/glossary").text


def test_glossary_en_labels_cover_every_cjk_key() -> None:
    """A CJK-keyed term must carry an English label, or /en/glossary would
    render it as Chinese."""
    from fde_scope.web.glossary import _EN_TERM, _is_cjk, _label
    from fde_scope.web.i18n import GLOSSARY_EN, GLOSSARY_ZH

    cjk_keys = [term for term, _ in GLOSSARY_ZH if _is_cjk(term)]
    assert cjk_keys, "the CJK-keyed terms are the reason this mapping exists"
    assert [t for t in cjk_keys if t not in _EN_TERM] == []
    for term in cjk_keys:
        assert not _is_cjk(_label(term, en=True))
    # the English list shares the keys, so the tips line up without a lookup
    assert [t for t, _ in GLOSSARY_EN] == [t for t, _ in GLOSSARY_ZH]


def test_glossary_nav_links_both_ways(client) -> None:
    """Every shell links to the glossary, and it links back to them."""
    for path in ("/", "/console", "/certification"):
        assert 'href="/glossary"' in client.get(path).text
    for path in ("/en/", "/en/console", "/en/certification"):
        html = client.get(path).text
        assert 'href="/en/glossary"' in html
        assert "名词解释" not in html  # translated by to_en / paired literals
    zh = client.get("/glossary").text
    assert 'href="/"' in zh and 'href="/console"' in zh and 'href="/certification"' in zh
    assert 'href="/en/glossary"' in zh  # lang switcher
    en = client.get("/en/glossary").text
    assert 'href="/en/"' in en and 'href="/en/console"' in en
    assert 'href="/glossary"' in en  # lang switcher flips back


def test_glossary_gateway_is_public(client, monkeypatch) -> None:
    """A static shell like / and /certification: no engagement data, so it is
    whitelisted, and the page carries no token-leaking fetch."""
    monkeypatch.setenv("FDE_SCOPE_API_TOKEN", "gloss-token-123456")
    assert client.get("/glossary").status_code == 200
    assert client.get("/en/glossary").status_code == 200
    assert "gloss-token-123456" not in client.get("/glossary").text


# ---------------------------------------------------------------------------
# course（/course · Level 1 全部课程文档，按仓库源文件渲染）
# ---------------------------------------------------------------------------
def test_course_serves_every_chapter(client) -> None:
    """/course carries all twenty-five lessons, each with its own anchor, title
    and the source filename it was read from."""
    from fde_scope.web.course import _CHAPTERS

    r = client.get("/course")
    assert r.status_code == 200
    assert '<html lang="zh">' in r.text
    assert "小白 FDE 炼金术：一天入门，七天变现" in r.text
    assert "__ICON_SPRITE__" not in r.text  # placeholder is filled by app.py
    for key, filename, zh_title, *_ in _CHAPTERS:
        assert f'id="doc-{key}"' in r.text
        assert zh_title in r.text
        assert f"course-level-1/{filename}" in r.text  # source named per chapter
    assert r.text.count('class="chap"') == len(_CHAPTERS)


def test_course_titles_match_the_source_headings() -> None:
    """The chapter titles are hand-written metadata while the lessons are the
    source of truth: if a lesson renames its ``# `` heading, this page must
    not keep advertising the old name."""
    from fde_scope.web.course import _CHAPTERS, _default_root

    root = _default_root()
    for _key, filename, zh_title, *_ in _CHAPTERS:
        heading = (root / filename).read_text(encoding="utf-8").splitlines()[0]
        assert heading.startswith("# "), filename
        assert heading[2:].strip() == zh_title, filename


def test_course_rail_groups_cover_every_chapter(client) -> None:
    """The rail's chapter groups must cover ``_CHAPTERS`` exactly once, in
    source order — a key dropped from ``_GROUPS`` would silently vanish from
    the rail, and reordering would make the scroll highlight zigzag."""
    from fde_scope.web.course import _CHAPTERS, _GROUPS

    assert [key for _zh, _eng, keys in _GROUPS for key in keys] == [key for key, *_ in _CHAPTERS]
    zh = client.get("/course").text
    assert zh.count('<div class="sgrp">') == len(_GROUPS)
    en = client.get("/en/course").text
    for _zh, eng, _keys in _GROUPS:
        # side_nav html-escapes captions, so "Overview & foundation" reaches the
        # page as "&amp;" — comparing the raw label would fail on a correct page.
        assert f'<div class="sgrp">{escape(eng)}</div>' in en


def test_course_links_are_rewritten(client) -> None:
    """No href points at a bare lesson filename or off-site: sibling lessons
    go to their anchor on this page, repo citations go to the local reader
    pages, and unresolvable paths strip to their label. Fenced template
    examples (the appendix is full of markdown-link samples) are left
    byte-identical."""
    import re

    from fde_scope.web.course import _CHAPTERS

    html = client.get("/course").text
    assert re.search(r'href="(?!#|https?://)[^"]*\.md"', html) is None
    # the rail anchors every chapter, so both the rail and the in-body
    # cross-references resolve in-page
    for key, *_ in _CHAPTERS:
        assert f'href="#doc-{key}"' in html
    assert 'href="#doc-readme"' in html  # the appendix points back at the overview
    # repo citations resolve to the local reader pages now, not GitHub
    assert 'href="/sop"' in html  # docs/fde_sop_full.md
    assert 'href="/docs/readme"' in html
    assert 'href="/docs/fde-research"' in html
    assert 'href="/docs/course-en"' in html
    # nothing jumps off-site any more
    assert 'href="http' not in html
    assert 'rel="noopener' not in html
    # fenced template examples keep their link syntax
    assert "[REDACTED](PHONE)" in html
    assert "[REDACTED](EMAIL)" in html


def test_course_code_blocks_survive_rendering(client) -> None:
    """Every fenced block in the sources reaches the page. Regression anchor:
    the ``<br>`` restoration splits on ``<pre>`` and a non-capturing split
    silently deleted all 69 of them once."""
    import re

    from fde_scope.web.course import _CHAPTERS, _default_root

    root = _default_root()
    # up to three leading spaces, the CommonMark rule: two of the fences sit
    # indented inside a list item
    fence = re.compile(r"^ {0,3}```")
    fences = sum(
        bool(fence.match(line))
        for _key, filename, *_ in _CHAPTERS
        for line in (root / filename).read_text(encoding="utf-8").splitlines()
    )
    assert fences and fences % 2 == 0  # every fence is closed
    r = client.get("/course")
    assert r.text.count("<pre") == fences // 2
    # and the mermaid diagram keeps its literal <br/> instead of gaining <br>
    assert "&lt;br/&gt;" in r.text


def test_course_task_items_become_checkboxes(client) -> None:
    """Every ``- [ ]`` practice item renders as a real checkbox (state lives
    in localStorage), the stats row's practice count equals the checkbox
    count, and the numbers come from the token stream — literals in fenced
    examples can no longer inflate them (plan §5.2/§5.6)."""
    from fde_scope.web.course import _CHAPTERS, _default_root

    root = _default_root()
    expected = 0
    for _key, fn, *_ in _CHAPTERS:
        lines = (root / fn).read_text(encoding="utf-8").split("\n")
        fenced = fenced_indices(lines)
        expected += sum(1 for i, ln in enumerate(lines) if i not in fenced and re.match(r"^\s*- \[ \] ", ln))
    html = client.get("/course").text
    assert html.count('class="taskbox"') == expected
    assert "- [ ]" not in html
    # the 练习 stat is the checkbox count, not every literal ☐ in the prose
    assert f'<div class="num">{expected}</div><div class="lab">项练习</div>' in html
    assert html.count("☐") < expected  # remaining ☐ glyphs are prose mentions, not items


def test_course_has_progress_and_search(client) -> None:
    """Read-progress toggles per chapter, a progress bar, and an in-page
    filter across every chapter — all client-side, zero backend
    (plan §5.4/§5.5)."""
    from fde_scope.web.course import _CHAPTERS

    html = client.get("/course").text
    assert "toggleRead" in html and "refreshProgress" in html
    assert 'class="readbtn"' in html and html.count('data-ch="') == len(_CHAPTERS)
    assert 'id="cr-bar"' in html and 'id="cr-lab"' in html
    assert 'id="cr-q"' in html and "courseFilter" in html
    assert 'id="cr-empty"' in html
    en = client.get("/en/course").text
    assert "mark read" in en
    assert 'aria-label="Search the course"' in en


def test_en_course_translates_the_chrome_and_says_the_lessons_are_chinese(
    client,
) -> None:
    """The English page is rendered from paired literals (no to_en pass), so
    the chrome cannot leak Chinese — and it states plainly that the lesson
    bodies are served as authored rather than pretending to be translated."""
    r = client.get("/en/course")
    assert r.status_code == 200
    assert '<html lang="en">' in r.text
    assert "Beginner FDE Alchemy · Level 1" in r.text
    assert "served as authored" in r.text
    assert 'lang="zh-Hans"' in r.text  # the bodies are marked as Chinese
    assert "入门课程" not in r.text
    assert ">00 Method<" in r.text and ">12 Appendix<" in r.text  # rail translated


def test_course_states_the_honesty_boundary(client) -> None:
    """The course's own boundary (no employment or income promise, fictional
    cases) must survive onto the web page in both locales."""
    zh = client.get("/course").text
    assert "不承诺就业、不承诺收入" in zh
    assert "所有客户案例均为虚构演示数据" in zh
    en = client.get("/en/course").text
    assert "not a promise of employment or income" in en
    assert "fictional demo data" in en


def test_course_nav_links_both_ways(client) -> None:
    """Every shell links to the course, and it links back to them."""
    for path in ("/", "/console", "/glossary", "/certification"):
        assert 'href="/course"' in client.get(path).text
    for path in ("/en/", "/en/console", "/en/glossary", "/en/certification"):
        html = client.get(path).text
        assert 'href="/en/course"' in html
        assert "入门课程" not in html  # translated by to_en / paired literals
    zh = client.get("/course").text
    assert 'href="/"' in zh and 'href="/console"' in zh
    assert 'href="/glossary"' in zh and 'href="/certification"' in zh
    assert 'href="/en/course"' in zh  # lang switcher
    en = client.get("/en/course").text
    assert 'href="/en/"' in en and 'href="/en/glossary"' in en
    assert 'href="/course"' in en  # lang switcher flips back


def test_course_gateway_is_public(client, monkeypatch) -> None:
    """A static reading page like /glossary: no engagement data, so it is
    whitelisted, and the page carries no token-leaking fetch."""
    monkeypatch.setenv("FDE_SCOPE_API_TOKEN", "course-token-123456")
    assert client.get("/course").status_code == 200
    assert client.get("/en/course").status_code == 200
    assert "course-token-123456" not in client.get("/course").text


def test_course_degrades_when_the_sources_are_missing(tmp_path) -> None:
    """Neither the repo-root directory nor the wheel's package-data copy is
    readable: the page must explain that and keep its anchors, not raise."""
    from fde_scope.web.course import _CHAPTERS, render

    html = render("zh", root=tmp_path)
    assert "course-level-1" in html
    assert "读不到课程文件" in html
    assert html.count('id="doc-') == len(_CHAPTERS)
    assert html.count("这一章读不到") == len(_CHAPTERS)


def test_course_root_prefers_the_checkout_and_falls_back_to_package_data(tmp_path) -> None:
    """A checkout wins over the installed copy so that editing a lesson is
    what ``/course`` serves; an installed app, which has no repo root, still
    finds the lessons inside the package (see ``force-include`` in
    pyproject.toml). With neither present the repo path is returned so the
    notice names the directory a reader can actually restore."""
    from fde_scope.web.course import _choose_root

    repo, packaged = tmp_path / "repo", tmp_path / "packaged"
    packaged.mkdir()
    assert _choose_root(repo, packaged) == packaged
    repo.mkdir()
    assert _choose_root(repo, packaged) == repo
    missing = tmp_path / "missing"
    assert _choose_root(missing, tmp_path / "also-missing") == missing


def test_installed_course_root_renders_the_lessons(tmp_path, monkeypatch) -> None:
    """End-to-end form of the fallback above, exercising the real resolver:
    lay out an installed tree (package data present, repo root absent), point
    the module at it, and ``/course`` must serve the chapters rather than the
    notice."""
    import shutil

    from fde_scope.web import course

    packaged = tmp_path / "fde_scope" / "_data" / course._COURSE_DIRNAME
    (tmp_path / "fde_scope" / "web").mkdir(parents=True)
    shutil.copytree(course._default_root(), packaged)
    monkeypatch.setattr(course, "__file__", str(tmp_path / "fde_scope" / "web" / "course.py"))

    assert course._default_root() == packaged
    html = course.render("zh")
    assert "读不到课程文件" not in html
    assert "这一章读不到" not in html


def test_course_reports_one_unreadable_chapter_without_losing_the_rest(
    tmp_path,
) -> None:
    """One bad lesson must not take the other twenty-four down with it."""
    from fde_scope.web.course import _CHAPTERS, render

    for _key, filename, *_ in _CHAPTERS[1:]:
        (tmp_path / filename).write_text(f"# {filename}\n\nok\n", encoding="utf-8")
    html = render("zh", root=tmp_path)
    assert html.count("这一章读不到") == 1  # only README.md is missing
    assert "ok" in html


# ---------------------------------------------------------------------------
# certification centre（/certification · 三家平台认证细则 + 渠道尽调）
# ---------------------------------------------------------------------------
def test_certification_html(client) -> None:
    """/certification serves the certification centre with graded sources."""
    r = client.get("/certification")
    assert r.status_code == 200
    assert '<html lang="zh">' in r.text
    assert "FDE 认证与渠道准入" in r.text
    assert "__ICON_SPRITE__" not in r.text  # placeholders are filled by app.py
    for tier in ('class="tier official"', 'class="tier noted"', 'class="tier gap"'):
        assert tier in r.text


def test_en_certification_html(client) -> None:
    """The EN certification page is rendered from paired literals (no to_en
    pass), so the two locales cannot silently drift into each other."""
    r = client.get("/en/certification")
    assert r.status_code == 200
    assert '<html lang="en">' in r.text
    assert "FDE certification and channel admission" in r.text
    assert "Study guide" in r.text
    assert "备考指南" not in r.text
    assert "查不到的就写查不到" not in r.text


def test_certification_nav_links_both_ways(client) -> None:
    """Both existing shells link to the centre, and it links back."""
    for path in ("/", "/console"):
        assert 'href="/certification"' in client.get(path).text
    for path in ("/en/", "/en/console"):
        assert 'href="/en/certification"' in client.get(path).text
        assert "认证中心" not in client.get(path).text  # to_en translated the nav
    zh = client.get("/certification").text
    assert 'href="/"' in zh and 'href="/console"' in zh
    assert 'href="/en/certification"' in zh  # lang switcher
    en = client.get("/en/certification").text
    assert 'href="/en/"' in en and 'href="/en/console"' in en
    assert 'href="/certification"' in en  # lang switcher flips back


def test_certification_weight_tables_sum_to_100() -> None:
    """The two published module weightings must stay complete."""
    from fde_scope.web.certification import _ALIYUN_ACP_WEIGHTS, _WORKBUDDY_APPLICATION_WEIGHTS

    assert sum(w for _, _, w in _WORKBUDDY_APPLICATION_WEIGHTS) == 100
    assert sum(w for _, _, w in _ALIYUN_ACP_WEIGHTS) == 100


def test_certification_states_gaps_instead_of_filling_them(client) -> None:
    """A vendor with no public certification catalogue is reported as a gap,
    never filled with an invented exam."""
    from fde_scope.web.certification import _SOURCES

    assert {s[3] for s in _SOURCES} == {"OFFICIAL", "NOTED", "GAP"}
    html = client.get("/certification").text
    assert "查不到的就写查不到" in html
    assert "缺口" in html


def test_certification_practice_items_are_labelled_non_official(client) -> None:
    """The researched page must not pass original items off as real papers."""
    html = client.get("/certification").text
    assert "不是官方真题，也不是官方答案" in html
    assert "官方公开样题" in html


def test_certification_gateway_is_public(client, monkeypatch) -> None:
    """It is a static shell like / and /console: no engagement data, so it is
    whitelisted; its page carries no token-leaking fetch."""
    monkeypatch.setenv("FDE_SCOPE_API_TOKEN", "cert-token-123456")
    assert client.get("/certification").status_code == 200
    assert client.get("/en/certification").status_code == 200
    assert "cert-token-123456" not in client.get("/certification").text


def test_profiles_api(client) -> None:
    r = client.get("/api/profiles")
    data = r.json()
    assert "ticket" in data
    assert "manufacturing" in data
    assert data["manufacturing"]["industrial"] is True


def test_phases_api_manufacturing(client) -> None:
    r = client.get("/api/phases?profile=manufacturing")
    data = r.json()
    assert data["is_industrial"] is True
    assert len(data["phases"]) == 18


def test_phases_api_ticket_excludes_industrial(client) -> None:
    r = client.get("/api/phases?profile=ticket")
    data = r.json()
    slugs = [p["slug"] for p in data["phases"]]
    assert "site_survey" not in slugs  # industrial-only dropped


def test_create_and_advance_engagement(client) -> None:
    # create
    r = client.post("/api/engagements", data={"customer": "TestCo", "profile": "ticket"})
    assert r.status_code == 200
    eid = r.json()["engagement_id"]
    assert r.json()["current_phase"] == "qualification"

    # advance (no gate on qualification → free)
    r = client.post(f"/api/engagements/{eid}/advance")
    assert r.json()["advanced"] is True

    # status reflects new phase
    r = client.get(f"/api/engagements/{eid}")
    assert r.json()["current_phase"] == "stakeholder_map"


def test_advance_blocked_returns_result(client) -> None:
    r = client.post("/api/engagements", data={"customer": "BlockedCo", "profile": "ticket"})
    eid = r.json()["engagement_id"]
    # jump to success_criteria phase without sponsors/criteria
    client.post(f"/api/engagements/{eid}/context", json={"success_criteria": [], "stakeholders": []})
    # manually move context forward to success_criteria
    from fde_scope.engagement import Engagement, EngagementContext
    from fde_scope.web.deps import _eng_path

    eng = Engagement(EngagementContext.load(_eng_path(eid)))
    eng.ctx.current_phase = "success_criteria"
    eng.ctx.save(_eng_path(eid))

    r = client.post(f"/api/engagements/{eid}/advance")
    assert r.json()["advanced"] is False
    assert r.json()["result"]["passed"] is False


def test_gates_endpoint(client) -> None:
    r = client.post("/api/engagements", data={"customer": "GateCo", "profile": "manufacturing"})
    eid = r.json()["engagement_id"]
    r = client.get(f"/api/engagements/{eid}/gates")
    gates = r.json()
    # manufacturing profile exposes industrial gates
    assert "functional_safety" in gates


def test_forge_endpoint(client, sample_csv_bytes: bytes) -> None:
    r = client.post(
        "/api/forge",
        files={"file": ("t.csv", sample_csv_bytes, "text/csv")},
        data={"min_samples": "5", "synth_per_gap": "2"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1
    assert data["report_id"]
    assert data["html_url"].endswith(".html")


def test_kpi_endpoint_manufacturing(client) -> None:
    import json

    payload = "\n".join(
        json.dumps(
            {
                "availability": 0.9,
                "performance": 0.95,
                "quality": 0.99,
                "uptime_hours": 100,
                "failures": 2,
                "repair_hours": 4,
                "good_units": 95,
                "started_units": 100,
                "defects": 5,
                "opportunities_per_unit": 1,
                "grasp_successes": 80,
                "grasp_attempts": 100,
                "tasks_succeeded": 90,
                "tasks_attempted": 100,
                "interventions": 3,
                "cycles": 1000,
            }
        )
        for _ in range(3)
    )
    r = client.post(
        "/api/kpi",
        files={"file": ("s.jsonl", payload.encode(), "application/jsonl")},
        data={"profile": "manufacturing"},
    )
    assert r.status_code == 200
    kpis = r.json()["kpis"]
    assert "oee" in kpis and kpis["oee"] > 0


# ---------------------------------------------------------------------------
# security + error-handling regression tests
# ---------------------------------------------------------------------------
def test_create_engagement_sanitizes_customer_in_eid(client, tmp_path) -> None:
    """A path-traversal customer name must not escape the engagements dir."""
    r = client.post("/api/engagements", data={"customer": "a/../../../escaped", "profile": "ticket"})
    assert r.status_code == 200
    eid = r.json()["engagement_id"]
    assert "/" not in eid and ".." not in eid
    # the file landed inside .fde_scope/engagements, not outside it
    eng_dir = tmp_path / ".fde_scope" / "engagements"
    assert (eng_dir / f"{eid}.json").exists()
    assert not (tmp_path / "escaped.json").exists()


def test_eng_path_rejects_traversal_eid(client) -> None:
    """_eng_path refuses ids that resolve outside the engagements dir."""
    from fastapi import HTTPException

    from fde_scope.web.deps import _eng_path

    with pytest.raises(HTTPException) as exc_info:
        _eng_path("../../outside")
    assert exc_info.value.status_code == 400


#: ``%2e%2e`` survives routing as one path segment (a literal ``..`` in the URL
#: is normalised away before it ever reaches a handler) and used to resolve to
#: the skills store's *parent* directory.
_TRAVERSAL_SID = "%2e%2e"


@pytest.mark.parametrize(
    ("method", "url", "kw"),
    [
        ("get", "/api/skills/{sid}", {}),
        ("patch", "/api/skills/{sid}", {"json": {"title": "x"}}),
        ("post", "/api/skills/{sid}/publish", {}),
        ("post", "/api/skills/{sid}/archive", {}),
        ("post", "/api/skills/{sid}/export", {"json": {"format": "agentscope"}}),
    ],
)
def test_skill_routes_refuse_traversal_sid(client, tmp_path, method, url, kw) -> None:
    """Every ``{sid}`` route refuses instead of reading/writing outside the store."""
    r = getattr(client, method)(url.format(sid=_TRAVERSAL_SID), **kw)
    assert r.status_code == 400, r.text
    assert "unsafe identifier" in r.json()["detail"]
    # the parent of the skills dir (.fde_scope/) was not populated or emptied
    assert not (tmp_path / ".fde_scope" / "meta.json").exists()
    assert not (tmp_path / "meta.json").exists()


def test_skill_delete_of_traversal_sid_leaves_the_store_intact(client, tmp_path) -> None:
    """The pre-fix damage case: ``delete("..")`` unlinked the store's parent."""
    created = client.post(
        "/api/skills",
        json={"title": "keep me", "category": "research", "tags": [], "body_md": "body"},
    )
    assert created.status_code == 200
    sid = created.json()["id"]
    assert client.patch(f"/api/skills/{_TRAVERSAL_SID}", json={"title": "x"}).status_code == 400
    assert client.get(f"/api/skills/{sid}").status_code == 200


@pytest.mark.parametrize("target", ["%2e%2e", "%2e%2e%2f.."])
def test_ontology_read_routes_refuse_traversal(client, target) -> None:
    """The ontology routes resolve ids the same way and must 400, not 500."""
    for url in (
        f"/api/ontology/schema/{target}",
        f"/api/ontology/store/{target}",
        f"/api/ontology/export/{target}",
        f"/api/ontology/schema/{target}/diagram",
    ):
        r = client.get(url)
        assert r.status_code in (400, 404), (url, r.status_code, r.text)


def test_forge_sanitizes_upload_filename(client, tmp_path, sample_csv_bytes: bytes) -> None:
    """An upload named ../../x.csv must not escape the uploads dir."""
    r = client.post(
        "/api/forge",
        files={"file": ("../../x.csv", sample_csv_bytes, "text/csv")},
        data={"min_samples": "5", "synth_per_gap": "2"},
    )
    assert r.status_code == 200
    assert (tmp_path / ".fde_scope" / "uploads" / "x.csv").exists()
    assert not (tmp_path / "x.csv").exists()


def test_forge_refuses_a_dotdot_filename(client, tmp_path, sample_csv_bytes: bytes) -> None:
    """``Path("..").name`` is still ``..``, so taking the basename is not a
    guard on its own. Before safe_child this resolved onto the uploads dir
    itself and died as a 500."""
    r = client.post(
        "/api/forge",
        files={"file": ("..", sample_csv_bytes, "text/csv")},
        data={"min_samples": "5", "synth_per_gap": "2"},
    )
    assert r.status_code == 400, r.text
    assert "unsafe identifier" in r.json()["detail"]
    assert not list((tmp_path / ".fde_scope" / "uploads").iterdir())


def test_forge_upload_is_owner_readable_only(client, tmp_path, sample_csv_bytes: bytes) -> None:
    """The uploaded CSV is customer data that has *not* passed the scrub stage
    yet, so it must not land world-readable: fsutil's mkstemp creates 0600,
    ``Path.write_text`` created 0644."""
    r = client.post(
        "/api/forge",
        files={"file": ("tickets.csv", sample_csv_bytes, "text/csv")},
        data={"min_samples": "5", "synth_per_gap": "2"},
    )
    assert r.status_code == 200
    up = tmp_path / ".fde_scope" / "uploads" / "tickets.csv"
    assert up.stat().st_mode & 0o077 == 0


def test_evidence_refuses_a_dotdot_name(client, tmp_path) -> None:
    """Evidence (signed FAT/SAT scans) is the same customer-derived class of
    file; ``name=..`` must be refused instead of replacing a directory."""
    r = client.post("/api/engagements", data={"customer": "CritCo", "profile": "ticket"})
    eid = r.json()["engagement_id"]
    r = client.post(
        f"/api/engagements/{eid}/evidence",
        data={"name": ".."},
        files={"file": ("whatever.txt", b"scan", "text/plain")},
    )
    assert r.status_code == 400, r.text
    assert "unsafe identifier" in r.json()["detail"]
    stored = list((tmp_path / ".fde_scope" / "evidence" / eid).iterdir())
    assert stored == []


def test_update_context_rejects_string_success_criteria(client) -> None:
    """success_criteria must be a list of strings; a bare string is 422 and
    must not corrupt the persisted engagement."""
    r = client.post("/api/engagements", data={"customer": "CritCo", "profile": "ticket"})
    eid = r.json()["engagement_id"]
    r = client.post(f"/api/engagements/{eid}/context", json={"success_criteria": "not-a-list"})
    assert r.status_code == 422
    # the engagement is still intact and loadable afterwards
    r = client.get(f"/api/engagements/{eid}")
    assert r.status_code == 200


def test_update_context_rejects_a_non_object_assets_container(client) -> None:
    """Asset *values* stay free-form, but the container has to be an object:
    ``assets`` as a string or number reached ``dict.update`` directly and
    surfaced as a 500, and a list of pairs merged silently as keys."""
    r = client.post("/api/engagements", data={"customer": "CritCo", "profile": "ticket"})
    eid = r.json()["engagement_id"]
    for bad in ("kv", 7, ["k", "v"]):
        r = client.post(f"/api/engagements/{eid}/context", json={"assets": bad})
        assert r.status_code == 422, f"assets={bad!r} → {r.status_code}"
    # nothing half-merged, and the engagement still loads
    assert client.get(f"/api/engagements/{eid}").json()["engagement_id"] == eid
    # an odd value shape is *not* rejected here — gates interpret assets
    r = client.post(f"/api/engagements/{eid}/context", json={"assets": {"fat": "done"}})
    assert r.status_code == 200


def test_list_engagements_skips_corrupt_file(client, tmp_path) -> None:
    """One corrupt engagement file must not 500 the whole listing."""
    r = client.post("/api/engagements", data={"customer": "GoodCo", "profile": "ticket"})
    assert r.status_code == 200
    bad = tmp_path / ".fde_scope" / "engagements" / "eng-corrupt.json"
    bad.write_text("{not valid json", encoding="utf-8")
    r = client.get("/api/engagements")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_advance_completed_engagement_returns_reason(client) -> None:
    """Advancing a terminal engagement returns advanced=False, not a 500."""
    r = client.post("/api/engagements", data={"customer": "DoneCo", "profile": "ticket"})
    eid = r.json()["engagement_id"]
    from fde_scope.engagement import Engagement, EngagementContext
    from fde_scope.web.deps import _eng_path

    eng = Engagement(EngagementContext.load(_eng_path(eid)))
    eng.ctx.current_phase = "disengage"
    eng.ctx.save(_eng_path(eid))

    r = client.post(f"/api/engagements/{eid}/advance")
    assert r.status_code == 200
    assert r.json() == {"advanced": False, "reason": "complete"}


def test_rollback_moves_phase_and_audits(client) -> None:
    """``POST …/rollback`` goes through ``Engagement.rollback`` and leaves a trace.

    P1 wired the domain transition (already present in ``engagement.py`` and the
    CLI) to the web layer; the route must not assign ``current_phase`` itself,
    and the reason/operator the UI now collects must land in the audit record.
    """
    eid = client.post("/api/engagements", data={"customer": "RollCo", "profile": "ticket"}).json()[
        "engagement_id"
    ]
    assert client.post(f"/api/engagements/{eid}/advance").json()["advanced"] is True
    assert client.get(f"/api/engagements/{eid}").json()["current_phase"] == "stakeholder_map"

    r = client.post(
        f"/api/engagements/{eid}/rollback",
        data={"to_phase": "qualification", "reason": "客户改需求", "operator": "ada"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["rolled_back"] is True
    assert (body["from_phase"], body["to_phase"]) == ("stakeholder_map", "qualification")
    assert body["status"]["current_phase"] == "qualification"
    # the persisted record moved too, not just the response
    assert client.get(f"/api/engagements/{eid}").json()["current_phase"] == "qualification"

    events = [
        e
        for e in client.get(f"/api/engagements/{eid}/audit").json()["events"]
        if e["action"] == "engagement.rollback"
    ]
    assert len(events) == 1
    assert events[0]["detail"]["to_phase"] == "qualification"
    assert events[0]["detail"]["reason"] == "客户改需求"
    assert events[0]["detail"]["operator"] == "ada"


def test_rollback_unknown_phase_is_404(client) -> None:
    eid = client.post("/api/engagements", data={"customer": "Roll404", "profile": "ticket"}).json()[
        "engagement_id"
    ]
    r = client.post(f"/api/engagements/{eid}/rollback", data={"to_phase": "not_a_phase"})
    assert r.status_code == 404
    assert "not_a_phase" in r.json()["detail"]


def test_rollback_forward_is_400(client) -> None:
    """Rollback is one-directional: a later phase is a 400, not a silent jump."""
    eid = client.post("/api/engagements", data={"customer": "RollFwd", "profile": "ticket"}).json()[
        "engagement_id"
    ]
    r = client.post(f"/api/engagements/{eid}/rollback", data={"to_phase": "stakeholder_map"})
    assert r.status_code == 400
    assert "forward" in r.json()["detail"].lower()
    assert client.get(f"/api/engagements/{eid}").json()["current_phase"] == "qualification"


def test_audit_json_is_free_but_md_export_is_licensed(client, monkeypatch) -> None:
    """``?format=md`` writes the same report as ``/audit/export``, so it carries
    the same tier gate — reading events stays free.

    Regression: the export branch used to skip ``_require_feature``, making
    ``GET …/audit?format=md`` a one-query-string bypass of the paid feature.
    """
    from fde_scope import license as lic

    eid = client.post("/api/engagements", data={"customer": "LicCo", "profile": "ticket"}).json()[
        "engagement_id"
    ]
    assert client.get(f"/api/engagements/{eid}/audit").status_code == 200
    assert client.get(f"/api/engagements/{eid}/audit?format=md").status_code == 200

    monkeypatch.delenv(lic.ENV_LICENSE_KEY, raising=False)
    assert client.get(f"/api/engagements/{eid}/audit").status_code == 200
    assert client.get(f"/api/engagements/{eid}/audit?format=md").status_code == 402
    assert client.get(f"/api/engagements/{eid}/audit/export").status_code == 402


def test_phases_unknown_profile_404(client) -> None:
    r = client.get("/api/phases?profile=nope")
    assert r.status_code == 404


def test_kpi_unknown_profile_404(client) -> None:
    r = client.post(
        "/api/kpi",
        files={"file": ("s.jsonl", b'{"a": 1}\n', "application/jsonl")},
        data={"profile": "nope"},
    )
    assert r.status_code == 404


def test_kpi_invalid_jsonl_422(client) -> None:
    r = client.post(
        "/api/kpi",
        files={"file": ("s.jsonl", b"{not json}\n", "application/jsonl")},
        data={"profile": "ticket"},
    )
    assert r.status_code == 422


def test_kpi_non_utf8_422(client) -> None:
    r = client.post(
        "/api/kpi",
        files={"file": ("s.jsonl", b"\xff\xfe\x00bad", "application/jsonl")},
        data={"profile": "ticket"},
    )
    assert r.status_code == 422


def test_forge_non_utf8_422(client) -> None:
    r = client.post(
        "/api/forge",
        files={"file": ("t.csv", b"\xff\xfe\x00bad", "text/csv")},
        data={"min_samples": "5", "synth_per_gap": "2"},
    )
    assert r.status_code == 422


def test_evaluate_unknown_gate_404(client) -> None:
    r = client.post("/api/engagements", data={"customer": "Gate404Co", "profile": "ticket"})
    eid = r.json()["engagement_id"]
    r = client.post(f"/api/engagements/{eid}/gate/no_such_gate")
    assert r.status_code == 404


def test_detail_includes_full_context(client) -> None:
    """GET /api/engagements/{eid} must carry the full context for the
    Context tab (stakeholders / site / safety / slos / assets), not just
    the status summary."""
    r = client.post("/api/engagements", data={"customer": "CtxCo", "profile": "ticket"})
    eid = r.json()["engagement_id"]
    r = client.get(f"/api/engagements/{eid}")
    assert r.status_code == 200
    data = r.json()
    assert data["context"]["customer"] == "CtxCo"
    assert "stakeholders" in data["context"]
    assert "success_criteria" in data["context"]
    assert "assets" in data["context"]


def test_console_has_context_tab_renderer(client) -> None:
    """The Context tab must render friendly cards, not raw JSON, and stay
    XSS-safe (no unescaped interpolation of user-supplied context)."""
    html = client.get("/console").text
    assert "function contextHtml(ctx)" in html
    assert "contextHtml(s.context)" in html
    # every user-supplied field rendered inside the tab goes through escapeHtml
    for needle in (
        "esc(site.location)",
        "esc(x.name)",
        "esc(x.role)",
        "esc(x.success_metric||'—')",
        "esc(c)",
    ):
        assert needle in html


# ---------------------------------------------------------------------------
# XSS / upload-limit regression tests
# ---------------------------------------------------------------------------
def test_console_escapes_user_supplied_fields(client) -> None:
    """The console JS must escape every user-supplied field before innerHTML."""
    payload = "<script>alert(1)</script>"
    r = client.post("/api/engagements", data={"customer": payload, "profile": "ticket"})
    assert r.status_code == 200
    # the API preserves the raw value (escaping is a render-layer concern) …
    assert r.json()["customer"] == payload

    html = client.get("/console").text
    # … and every user-controlled interpolation point in the console is escaped
    for needle in (
        "escapeHtml(s.customer)",
        "escapeHtml(s.current_phase)",
        "escapeHtml(s.current_zone)",
        "escapeHtml(s.engagement_id)",
        "escapeHtml(s.next_phase||'— (完成)')",
        "escapeHtml(g.name)",
        "escapeHtml(b)",
        "escapeHtml(w)",
    ):
        assert needle in html, f"console must escape {needle!r}"


def test_forge_oversized_upload_413(client, sample_csv_bytes: bytes) -> None:
    """An upload beyond the size limit is refused with 413, not processed."""
    from fde_scope.web.app import MAX_UPLOAD_BYTES

    big = sample_csv_bytes + b"x" * (MAX_UPLOAD_BYTES + 1)
    r = client.post(
        "/api/forge",
        files={"file": ("big.csv", big, "text/csv")},
        data={"min_samples": "5", "synth_per_gap": "2"},
    )
    assert r.status_code == 413


def test_kpi_oversized_upload_413(client) -> None:
    """KPI uploads share the same size limit."""
    from fde_scope.web.app import MAX_UPLOAD_BYTES

    big = b"x" * (MAX_UPLOAD_BYTES + 1)
    r = client.post(
        "/api/kpi",
        files={"file": ("big.jsonl", big, "application/jsonl")},
        data={"profile": "manufacturing"},
    )
    assert r.status_code == 413


# ---------------------------------------------------------------------------
# skills API
# ---------------------------------------------------------------------------
def test_skills_api_roundtrip(client, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    r = client.post(
        "/api/skills",
        json={
            "title": "OPC UA 排查",
            "category": "implementation",
            "tags": ["opcua"],
            "body_md": "# 步骤",
            "phase_slug": "deploy",
        },
    )
    assert r.status_code == 200
    sid = r.json()["id"]
    assert r.json()["status"] == "draft"
    assert client.post(f"/api/skills/{sid}/publish").status_code == 200
    got = client.get(f"/api/skills/{sid}")
    assert got.status_code == 200 and got.json()["status"] == "published"
    lst = client.get("/api/skills?category=implementation")
    assert lst.status_code == 200 and len(lst.json()) == 1
    drafts = client.get("/api/skills/drafts")
    assert drafts.status_code == 200 and len(drafts.json()) == 0  # 已发布
    exp = client.post(f"/api/skills/{sid}/export", json={"format": "agentscope"})
    assert exp.status_code == 200
    assert exp.json()["files"][0]["name"].endswith("SKILL.md")
    arch = client.post(f"/api/skills/{sid}/archive")
    assert arch.status_code == 200 and arch.json()["status"] == "archived"


def test_skills_facets_power_the_console_filters(client) -> None:
    """``/api/skills/facets`` backs the tag / profile / gate / phase selects
    added to the skills view in P1 §1.2.

    The search endpoint has accepted these params all along (``api_skills``),
    but the console only ever sent ``q`` / ``category`` / ``status`` — the four
    remaining filters were dead capability. Facets return the distinct values
    that actually exist so the UI offers selects instead of making the user
    guess a slug."""
    sid = client.post(
        "/api/skills",
        json={
            "title": "OPC UA 排查",
            "category": "implementation",
            "tags": ["opcua", "plc"],
            "phase_slug": "deploy",
            "gate_slug": "solution_blueprint",
            "applies_to": ["manufacturing"],
        },
    ).json()["id"]
    client.post(f"/api/skills/{sid}/publish")  # the default list is status=published
    f = client.get("/api/skills/facets")
    assert f.status_code == 200
    assert f.json() == {
        "tags": ["opcua", "plc"],
        "phases": ["deploy"],
        "gates": ["solution_blueprint"],
        "profiles": ["manufacturing"],
    }
    # each of the four filters really filters, in both directions
    assert len(client.get("/api/skills?tag=plc").json()) == 1
    assert client.get("/api/skills?tag=nope").json() == []
    assert len(client.get("/api/skills?profile=manufacturing").json()) == 1
    assert client.get("/api/skills?profile=ticket").json() == []
    assert len(client.get("/api/skills?phase=deploy").json()) == 1
    assert client.get("/api/skills?phase=qualification").json() == []
    assert len(client.get("/api/skills?gate=solution_blueprint").json()) == 1
    assert client.get("/api/skills?gate=no-such-gate").json() == []


# ---------------------------------------------------------------------------
# journal（现场记录）
# ---------------------------------------------------------------------------
def test_journal_api_roundtrip(client) -> None:
    eid = client.post("/api/engagements", data={"customer": "Acme"}).json()["engagement_id"]
    assert client.get(f"/api/engagements/{eid}/journal").json() == []
    r = client.post(f"/api/engagements/{eid}/journal", json={"kind": "research", "note": "产线 A 调研"})
    assert r.status_code == 200
    assert r.json()["kind"] == "research"
    entries = client.get(f"/api/engagements/{eid}/journal").json()
    assert len(entries) == 1 and entries[0]["note"] == "产线 A 调研"
    # 校验：非法 kind / 空 note
    assert (
        client.post(f"/api/engagements/{eid}/journal", json={"kind": "oops", "note": "x"}).status_code == 422
    )
    assert client.post(f"/api/engagements/{eid}/journal", json={"note": "  "}).status_code == 422


def test_journal_to_skill_bridge(client) -> None:
    eid = client.post("/api/engagements", data={"customer": "Aurora"}).json()["engagement_id"]
    jid = client.post(
        f"/api/engagements/{eid}/journal", json={"kind": "implementation", "note": "部署完成"}
    ).json()["id"]
    r = client.post(f"/api/engagements/{eid}/journal/{jid}/skill")
    assert r.status_code == 200
    rec = r.json()
    assert rec["category"] == "implementation"  # kind → category 映射
    assert rec["source_engagement"] == eid
    assert rec["status"] == "draft"
    # skill_id 回写 journal entry
    entries = client.get(f"/api/engagements/{eid}/journal").json()
    assert entries[0]["skill_id"] == rec["id"]
    # 重复沉淀 → 409；未知 jid → 404
    assert client.post(f"/api/engagements/{eid}/journal/{jid}/skill").status_code == 409
    assert client.post(f"/api/engagements/{eid}/journal/jn-nope/skill").status_code == 404


# ---------------------------------------------------------------------------
# workbench（工作台聚合）
# ---------------------------------------------------------------------------
def test_workbench_api_empty(client) -> None:
    data = client.get("/api/workbench").json()
    assert data["stats"] == {
        "active_projects": 0,
        "phase_distribution": {},
        "draft_skills": 0,
        "total_skills": 0,
    }
    assert data["matrix"] == []
    assert data["recent_skills"] == []


def test_workbench_api_stats_matrix_recent(client) -> None:
    client.post("/api/engagements", data={"customer": "Acme"})
    client.post("/api/engagements", data={"customer": "Aurora", "profile": "manufacturing"})
    wb = client.get("/api/workbench").json()
    assert wb["stats"]["active_projects"] == 2
    assert wb["stats"]["phase_distribution"] == {"qualification": 2}
    assert len(wb["matrix"]) == 2
    assert wb["matrix"][0]["customer"] in ("Acme", "Aurora")
    # 技能：草稿计入 draft_skills；发布后进入 recent_skills
    sid = client.post(
        "/api/skills", json={"title": "OPC UA 踩坑", "category": "implementation", "tags": ["opcua"]}
    ).json()["id"]
    assert client.get("/api/workbench").json()["stats"]["draft_skills"] == 1
    client.post(f"/api/skills/{sid}/publish")
    wb2 = client.get("/api/workbench").json()
    assert wb2["stats"]["draft_skills"] == 0
    assert wb2["stats"]["total_skills"] == 1
    assert wb2["recent_skills"][0]["id"] == sid


def test_console_has_workbench_and_skills_views(client) -> None:
    """控制台包含工作台/技能库视图与现场记录 tab（单页无构建）。"""
    r = client.get("/console")
    assert r.status_code == 200
    assert 'id="view-workbench"' in r.text
    assert 'id="view-skills"' in r.text
    assert ">工作台</button>" in r.text
    assert ">技能库</button>" in r.text
    assert "现场记录" in r.text
    assert "沉淀为技能" in r.text
    assert "草稿审阅队列" in r.text


def test_console_skills_view_sends_every_backend_filter(client) -> None:
    """The skills search endpoint accepts ``tag``/``profile``/``gate``/``phase``
    (`api_skills`); the console must actually send them, backed by facets.

    A filter param the front-end never sends is dead capability — the exact
    gap the plan called out for this view, so the wiring is pinned here."""
    html = client.get("/console").text
    for control in ("sk-tag", "sk-profile", "sk-gate", "sk-phase"):
        assert f'id="{control}"' in html, f"missing facet control: {control}"
    for param in ("'tag', tag", "'profile', prof", "'gate', gate", "'phase', phase"):
        assert f"params.set({param})" in html, f"filter param not sent: {param}"
    assert "/api/skills/facets" in html
    assert "api('/api/skills/facets')" in html
    # the facet selects re-run the search on change, like the existing ones
    for control in ("sk-tag", "sk-profile", "sk-gate", "sk-phase"):
        assert f'id="{control}" onchange="loadSkills()"' in html


def test_en_console_translates_skills_facet_filters(client) -> None:
    html = client.get("/en/console").text
    assert "<label>Applies to</label>" in html
    assert "<label>Gate</label>" in html
    assert "<label>Phase</label>" in html


# ---------------------------------------------------------------------------
# deploy plan API（角色 → 连接器 → 工具绑定）
# ---------------------------------------------------------------------------
def test_deploy_parse_reports_line_numbers(client) -> None:
    """Textarea parsing moved server-side (P1 §1.2): a malformed line comes
    back with its line number and a reason instead of vanishing in the browser.

    The old JS parser silently dropped anything without ``name: role`` — the
    agent simply disappeared from the plan with no explanation."""
    ok = client.post(
        "/api/deploy/parse",
        json={
            "agents_text": "analyst: 数据分析:qwen-max\n\narchivist: 文件分析",
            "sources_text": "csv=data/a.csv",
        },
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["errors"] == []
    assert body["agents"] == [
        {"name": "analyst", "role": "数据分析", "model": "qwen-max"},
        {"name": "archivist", "role": "文件分析"},
    ]
    assert body["sources"] == {"csv": "data/a.csv"}

    bad = client.post(
        "/api/deploy/parse",
        json={
            "agents_text": "analyst: 数据分析\nno-role-here\n: 缺名字",
            "sources_text": "csv=data/a.csv\nno-equals-sign\n=empty-key",
        },
    ).json()
    assert [(e["field"], e["line"], e["text"]) for e in bad["errors"]] == [
        ("agents", 2, "no-role-here"),
        ("agents", 3, ": 缺名字"),
        ("sources", 2, "no-equals-sign"),
        ("sources", 3, "=empty-key"),
    ]
    # the well-formed lines still come through despite the errors
    assert bad["agents"] == [{"name": "analyst", "role": "数据分析"}]
    assert bad["sources"] == {"csv": "data/a.csv"}


def test_console_deploy_parses_on_the_server(client) -> None:
    """The deploy view must not ship its own parser: it cannot report line
    numbers, and a second parser drifts from the CLI/backend behaviour."""
    html = client.get("/console").text
    assert "_parseAgentLines" not in html and "_parseSourceLines" not in html
    assert "/api/deploy/parse" in html
    assert "parsed.errors" in html
    assert "输入格式有误" in html
    en = client.get("/en/console").text
    assert "Input format errors" in en
    assert "<th>Raw line</th>" in en


def test_deploy_plan_binds_configured_sources(client) -> None:
    """配了源的角色拿到工具，没配的诚实标 unbound，并进入 ALLOW 规则。"""
    r = client.post(
        "/api/deploy/plan",
        json={
            "tenant": "swift",
            "name": "迅捷出行",
            "sources": {"csv": "data/t.csv", "documents": "docs/"},
            "agents": [{"name": "analyst", "role": "数据分析"}, {"name": "archivist", "role": "文件分析"}],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["summary"] == {
        "bound_tools": ["csv_sample", "csv_schema", "documents_sample", "documents_schema"],
        "unbound_tools": ["mes_sample", "mes_schema", "mysql_sample", "mysql_schema"],
        "agents": 2,
    }
    agents = body["manifest"]["agents"]
    assert [a["role_bucket"] for a in agents] == ["data", "files"]
    allowed = {tool for tool, _ in body["manifest"]["permissions"]["allow"]}
    assert "csv_sample" in allowed and "mes_sample" not in allowed


def test_deploy_plan_defaults_to_single_agent(client) -> None:
    """不声明 agents 时回退单 Agent（角色 = 租户名 → 不绑任何连接器）。"""
    body = client.post("/api/deploy/plan", json={"tenant": "acme"}).json()
    assert body["summary"]["agents"] == 1
    assert body["manifest"]["agents"][0]["name"] == "acme_agent"
    assert body["summary"]["bound_tools"] == []
    assert body["summary"]["unbound_tools"] == []


def test_deploy_plan_rejects_bad_agent_spec(client) -> None:
    r = client.post("/api/deploy/plan", json={"tenant": "acme", "agents": [{"role": "缺名字"}]})
    assert r.status_code == 422


def test_ontology_export_api_schema_jsonld(client) -> None:
    """内置 schema 可直接导出 JSON-LD（与 CLI ontology export 同一实现）。"""
    r = client.get("/api/ontology/export/fde-core")
    assert r.status_code == 200
    doc = r.json()
    assert "@context" in doc and "@graph" in doc


def test_ontology_stores_api_lists_workspace_stores(client) -> None:
    """store 列表端点供 console 本体库视图使用（id / ontology_ref / individuals）。"""
    from fde_scope.ontology.models import InstanceStore
    from fde_scope.ontology.store import OntologyStore

    OntologyStore().save_store(
        InstanceStore(
            id="acme-tickets",
            ontology_ref="fde-core@1.0.0",
            individuals=[{"curie": "ex:evt-1"}],
        )
    )
    r = client.get("/api/ontology/stores")
    assert r.status_code == 200
    entry = next(e for e in r.json() if e["id"] == "acme-tickets")
    assert entry == {"id": "acme-tickets", "ontology_ref": "fde-core@1.0.0", "individuals": 1}


def test_ontology_export_api_store_wraps_tbox(client) -> None:
    """实例库导出带 TBox 上下文：individuals 来自 store，classes 来自其 ontology_ref。"""
    from fde_scope.ontology.models import InstanceStore
    from fde_scope.ontology.store import OntologyStore

    store = OntologyStore()
    store.save_store(InstanceStore(id="acme-tickets", ontology_ref="fde-core@1.0.0"))
    r = client.get("/api/ontology/export/acme-tickets")
    assert r.status_code == 200
    doc = r.json()
    assert "@context" in doc and "@graph" in doc


def test_ontology_export_api_unknown_target_404(client) -> None:
    r = client.get("/api/ontology/export/does-not-exist")
    assert r.status_code == 404
    assert r.json()["detail"] == "unknown ontology export target: does-not-exist"


def test_ontology_diagram_api_returns_mermaid(client) -> None:
    """`ontology/diagram.py` had a CLI entry but no Web surface (P1 §1.2):
    the schema card's 类图 button renders this source."""
    r = client.get("/api/ontology/schema/fde-core/diagram")
    assert r.status_code == 200
    body = r.json()
    assert body["schema_id"] == "fde-core" and body["version"]
    assert body["mermaid"].startswith("classDiagram")
    assert "<|--" in body["mermaid"]
    assert client.get("/api/ontology/schema/nope/diagram").status_code == 404


def test_ontology_validate_api_tbox_and_abox(client) -> None:
    """One endpoint, both layers — same semantics as CLI validate/check."""
    r = client.get("/api/ontology/validate/fde-core")
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "schema" and body["target"].startswith("fde-core@")
    assert body["ok"] is True and body["errors"] == []
    assert client.get("/api/ontology/validate/nope").status_code == 404


def test_ontology_diff_api_reports_breaking_and_impact(client) -> None:
    """D1-D4 diff plus ABox impact across every workspace store referencing
    the old schema — the migration-effort evidence CLI diff prints."""
    from fde_scope.ontology.models import InstanceStore
    from fde_scope.ontology.store import OntologyStore

    store = OntologyStore()
    core = store.load_schema("fde-core")
    assert core is not None
    v2 = core.model_copy(deep=True)
    v2.id = "fde-core-webdiff"
    v2.version = "1.1.0"
    v2.classes = v2.classes[:-1]  # drop one class → D1 breaking change
    dropped = core.classes[-1].curie
    store.save_schema(v2)
    store.save_store(InstanceStore(id="acme-webdiff", ontology_ref="fde-core@1.0.0"))

    r = client.post("/api/ontology/diff", json={"old": "fde-core", "new": "fde-core-webdiff"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["from"] == "fde-core@1.0.0" and body["to"] == "fde-core-webdiff@1.1.0"
    d1 = [c for c in body["breaking"] if c["kind"] == "D1"]
    assert d1 and d1[0]["subject"] == dropped

    # unknown ids → 404 naming the missing one; missing params → 422
    miss = client.post("/api/ontology/diff", json={"old": "fde-core", "new": "ghost"})
    assert miss.status_code == 404 and "ghost" in miss.json()["detail"]
    assert client.post("/api/ontology/diff", json={"old": "fde-core"}).status_code == 422


def test_ops_connectors_api_reports_import_truth_and_env_booleans(client, monkeypatch) -> None:
    """The connectors panel is import-level truth plus env *booleans* —
    credential values must never reach a response (invariant 3)."""
    monkeypatch.setenv("FDE_SCOPE_MQTT_USERNAME", "super-secret-value")
    r = client.get("/api/connectors")
    assert r.status_code == 200
    body = r.json()
    by_slug = {c["slug"]: c for c in body["connectors"]}
    assert by_slug["csv"]["import_ok"] is True
    assert "JSONL" in by_slug["csv"]["note"]
    mqtt = by_slug["mqtt_sparkplug"]
    assert mqtt["env"]["FDE_SCOPE_MQTT_USERNAME"] is True
    assert mqtt["env"]["FDE_SCOPE_MQTT_PASSWORD"] is False
    assert "super-secret-value" not in r.text  # the value never leaves the process
    # every slug in the module table is accounted for, importable or not
    from fde_scope.connectors._registry import _MODULE_BY_TYPE

    assert set(by_slug) == set(_MODULE_BY_TYPE)


def test_ops_eval_info_and_mock_run(client) -> None:
    """Eval panel: metrics + LLM availability up front; a mock run needs no
    LLM; an unconfigured mimo run says so with 502 instead of pretending."""
    info = client.get("/api/eval/info").json()
    assert "intent_accuracy" in info["metrics"]
    assert info["llm_available"] is False  # conftest clears the LLM env

    run = client.post(
        "/api/eval/run",
        json={
            "agent": "mock",
            "cases": [{"id": "t1", "input": "怎么退款", "expected_category": "退款"}],
        },
    )
    assert run.status_code == 200
    report = run.json()
    assert report["case_count"] == 1
    assert "intent_accuracy" in report["metrics"]
    assert "metric_labels" in report

    assert client.post("/api/eval/run", json={"agent": "mock"}).status_code == 422
    assert client.post("/api/eval/run", json={"agent": "nope", "cases": []}).status_code == 422
    mimo = client.post("/api/eval/run", json={"agent": "mimo", "cases": [{"id": "t1", "input": "x"}]})
    assert mimo.status_code == 502
    assert "mock" in mimo.json()["detail"]


def test_ops_flywheel_api_is_honestly_process_local(client) -> None:
    """The counters are this process's in-memory engine and the retrain jobs
    are descriptors — the payload says both, so no UI can inherit the old
    "scheduled" lie."""
    body = client.get("/api/flywheel").json()
    assert body["process_local"] is True
    assert {"collected", "golden", "store_total"} <= set(body["snapshot"])
    names = {j["name"] for j in body["jobs"]}
    assert "weekly_incremental_retrain" in names
    weekly = next(j for j in body["jobs"] if j["name"] == "weekly_incremental_retrain")
    assert weekly["cron"] == "0 2 * * 1"


def test_ops_license_api_reports_tier_without_the_key(client) -> None:
    """Read-only license facts; the key value never appears — only where the
    key was found."""
    from fde_scope import license as lic

    r = client.get("/api/license")
    assert r.status_code == 200
    body = r.json()
    assert body["tier"] == "pro"  # conftest issues a pro env license
    assert body["key_source"] == "env"
    assert body["features"]["evidence"] is True
    assert body["features"]["sop"] is True
    assert body["features"]["multi_tenant"] is False
    # the actual key text must not leak into the payload
    assert lic._read_key() not in r.text  # type: ignore[operator]


def test_console_has_ops_view(client) -> None:
    """The ops view: nav button, container, hash route, four panels, eval runner."""
    html = client.get("/console").text
    assert """onclick="go('ops')""" in html
    assert 'id="view-ops"' in html
    assert "loadOps" in html and "runEval" in html
    assert "#ops" in html  # boot + hashchange routing
    assert "/api/connectors" in html and "/api/flywheel" in html and "/api/license" in html
    assert "/api/eval/run" in html
    # honesty pinned in the UI: process-local counters, descriptor-only jobs
    assert "本服务进程" in html and "描述符" in html
    en = client.get("/en/console").text
    assert "onclick=\"go('ops')\">Ops</button>" in en
    assert "<h2>Connector registry</h2>" in en
    assert "<h2>Eval benchmark</h2>" in en
    assert "mock (rule-based, no LLM)" in en
    assert "Key source: " in en


def test_workbench_list_has_search_and_filters(client) -> None:
    """The engagement list filters client-side (P1 §1.2): text search over
    customer/eid plus phase and zone selects — filtering an in-page matrix
    needs no new API surface, and the selections survive a re-render."""
    html = client.get("/console").text
    assert 'id="wb-q"' in html and "applyWbFilter" in html
    assert 'id="wb-phase"' in html and 'id="wb-zone"' in html
    assert 'id="wb-cards"' in html
    assert "wbFilteredMatrix" in html and "wbMatrix" in html
    # re-render reads back the previous selections instead of resetting them
    assert "prevQ = sel('wb-q')" in html and "prevPhase = sel('wb-phase')" in html
    en = client.get("/en/console").text
    assert 'placeholder="Search customer / engagement id"' in en
    assert '<option value="">All phases</option>' in en
    assert '<option value="">All zones</option>' in en
    assert "<label>Zone</label>" in en


def test_console_context_tab_has_json_editor(client) -> None:
    """The Context tab's six cards were read-only; P1 §1.2 adds a JSON editor
    that reuses the existing ``POST …/context`` patch path, and renders the
    backend's pydantic errors with their field paths."""
    html = client.get("/console").text
    assert "contextEditorHtml(ctx)" in html
    assert 'id="ctx-json"' in html and "saveContextJson" in html
    assert "CONTEXT_EDITABLE_KEYS" in html
    # only the keys the endpoint actually patches are offered
    assert "['site','safety','success_criteria','stakeholders','slos','assets']" in html
    # field-level errors: loc path + message, from pydantic's errors() body
    assert "(x.loc||[]).join('.')" in html
    assert "字段校验失败" in html
    en = client.get("/en/console").text
    assert "Edit context (JSON · gates are re-evaluated on save)" in en
    assert "Save and re-evaluate gates</button>" in en
    assert "Field validation failed" in en


def test_console_ontology_view_has_three_subviews(client) -> None:
    """diagram / validate / diff were CLI-only; the ontology view now exposes
    all three (buttons on the cards + a diff form)."""
    html = client.get("/console").text
    assert "showDiagram(" in html and ">类图</button>" in html
    assert "validateTarget(" in html and ">校验</button>" in html
    assert "runOntoDiff" in html and "ot-diff-old" in html and "ot-diff-new" in html
    assert "/api/ontology/diff" in html
    en = client.get("/en/console").text
    assert ">Class diagram</button>" in en
    assert ">Validate</button>" in en
    assert "<h2>Version diff (D1-D4 + ABox impact)</h2>" in en
    assert "Mermaid source" in en


def test_console_has_ontology_view(client) -> None:
    """console 提供只读 ontology 视图（导航 + 容器 + 加载器 + hash 路由）。"""
    html = client.get("/console").text
    assert 'data-view="ontology"' in html
    assert 'id="view-ontology"' in html
    assert "loadOntology" in html
    assert "location.hash === '#ontology'" in html


def test_overview_has_ontology_section(client) -> None:
    """落地页有 ontology section，并链向 console 的 ontology 视图。"""
    html = client.get("/").text
    assert "Ontology 语义层" in html
    assert 'href="/console#ontology"' in html


# ---------------------------------------------------------------------------
# guided mode（引导模式：只读引导 + catalog 本地 serve）
# ---------------------------------------------------------------------------
def test_guided_endpoint_structure(client) -> None:
    r = client.post("/api/engagements", data={"customer": "GuidedCo", "profile": "ticket"})
    eid = r.json()["engagement_id"]
    r = client.get(f"/api/engagements/{eid}/guided")
    assert r.status_code == 200
    body = r.json()
    assert body["phase"]["slug"] == "qualification"
    assert body["deliverables"]
    assert isinstance(body["llm_available"], bool)
    assert body["catalog_pages"] and all("url" in p and "route" in p for p in body["catalog_pages"])


def test_guided_endpoint_404(client) -> None:
    assert client.get("/api/engagements/nope/guided").status_code == 404


def test_guided_translates_blockers_into_next_steps(client) -> None:
    r = client.post("/api/engagements", data={"customer": "StepCo", "profile": "ticket"})
    eid = r.json()["engagement_id"]
    # walk to success_criteria (qualification/stakeholder_map have no gates for ticket)
    for _ in range(2):
        client.post(f"/api/engagements/{eid}/advance")
    body = client.get(f"/api/engagements/{eid}/guided").json()
    assert body["phase"]["slug"] == "success_criteria"
    gate = body["gates"]["success_criteria"]
    assert gate["passed"] is False
    assert gate["next_steps"] and all(s["advice"] for s in gate["next_steps"])


def test_guided_does_not_record_gates(client) -> None:
    """Guidance is read-only: no gate_records are written by /guided."""
    r = client.post("/api/engagements", data={"customer": "ROCo", "profile": "ticket"})
    eid = r.json()["engagement_id"]
    before = client.get(f"/api/engagements/{eid}").json()["context"]["gate_records"]
    client.get(f"/api/engagements/{eid}/guided")
    after = client.get(f"/api/engagements/{eid}").json()["context"]["gate_records"]
    assert before == after


def test_existing_routes_survive_guided_router(client) -> None:
    """Route-snapshot guard: the guided router must not shadow existing API."""
    from fde_scope.web.app import app

    paths = set(app.openapi()["paths"])
    for expected in (
        "/api/health",
        "/api/profiles",
        "/api/phases",
        "/api/engagements",
        "/api/engagements/{eid}",
        "/api/engagements/{eid}/gates",
        "/api/engagements/{eid}/advance",
        "/api/engagements/{eid}/gate/{slug}",
        "/api/engagements/{eid}/journal",
        "/api/engagements/{eid}/context",
        "/api/forge",
        "/api/kpi",
        "/api/deploy/plan",
        "/api/workbench",
        "/api/skills",
        "/api/engagements/{eid}/guided",
    ):
        assert expected in paths, f"missing route: {expected}"


def test_console_has_guided_tab(client) -> None:
    html = client.get("/console").text
    assert """tab('guided',this)""" in html
    assert "guidedHtml" in html
    # every sibling tab is still there
    for name in DETAIL_TAB_NAMES:
        assert f"""tab('{name}',this)""" in html


#: the 11 engagement-detail tabs, in strip order (``DETAIL_TABS`` in app.py)
DETAIL_TAB_NAMES = (
    "overview",
    "guided",
    "sop",
    "gates",
    "context",
    "forge",
    "kpi",
    "journal",
    "evidence",
    "handoff",
    "audit",
    "retro",
)


def test_console_detail_tab_strip_and_panes_line_up(client) -> None:
    """Each tab button has a real ``role``/``data-tab`` and a matching pane container.

    A tab whose pane id drifted would render as a button that silently does
    nothing, and nothing else in the suite would notice.
    """
    html = client.get("/console").text
    for name in DETAIL_TAB_NAMES:
        assert f'data-tab="{name}"' in html, f"tab button missing data-tab: {name}"
        assert f'id="t-{name}"' in html, f"pane container missing: t-{name}"
    assert 'role="tablist"' in html
    # DETAIL_TABS drives aria-selected bookkeeping and the #t:<name> hash, so it
    # must stay in sync with the markup above
    array = html.split("const DETAIL_TABS = [", 1)[1].split("]", 1)[0]
    assert [t.strip().strip("'") for t in array.split(",")] == list(DETAIL_TAB_NAMES)


def test_console_evidence_handoff_audit_load_lazily(client) -> None:
    """The three P1 tabs fetch on open, keeping selectEng at its 3 blocking calls."""
    html = client.get("/console").text
    assert (
        "const LAZY_TABS = {evidence: loadEvidence, handoff: renderHandoff, audit: loadAudit, retro: loadRetro};"
        in html
    )
    assert "const lazy = LAZY_TABS[name];" in html
    # tab() must be callable without an element argument, or the #t:<name> hash
    # restore path cannot activate a pane
    assert """el = el || document.querySelector(`.tab[data-tab="${name}"]`);""" in html
    # evidence and audit fetch on open; handoff renders a form and POSTs on demand
    assert "/evidence`)" in html and "/audit`)" in html
    assert "/handoff`, {method:'POST'" in html


def test_console_has_one_shared_confirmation_dialog(client) -> None:
    """force / rollback / archive / delete all route through a single dialog."""
    html = client.get("/console").text
    assert '<dialog id="dlg-action"' in html
    for el in ("dlg-action-title", "dlg-action-msg", "dlg-action-fields", "dlg-action-ok"):
        assert f'id="{el}"' in html
    assert "function openActionDialog(cfg)" in html
    for fn in ("askAdvanceForce", "askRollback", "askArchiveEng", "askDeleteEng"):
        assert f"function {fn}(" in html
        assert f"{fn}(" in html.split("function openActionDialog", 1)[0]


def test_console_row_actions_carry_data_not_interpolated_handlers(client) -> None:
    """Engagement-card buttons stop propagation and pass ``this``, never the customer name.

    Interpolating a customer name into an ``onclick`` attribute is an injection
    sink — the card already exposes ``data-eid``/``data-customer`` for the
    handler to read back.
    """
    html = client.get("/console").text
    assert 'data-eid="${escapeHtml(s.engagement_id)}" data-customer="${escapeHtml(s.customer)}"' in html
    assert "event.stopPropagation();askArchiveEng(this)" in html
    assert "event.stopPropagation();askDeleteEng(this)" in html
    assert "const card = btn.closest('.eng');" in html


def test_console_rollback_only_offers_earlier_phases(client) -> None:
    """The rollback picker slices the phase list *before* the current index.

    ``Engagement.rollback`` rejects a forward jump with a ValueError, but the UI
    should not offer one in the first place.
    """
    html = client.get("/console").text
    assert "detailPhases.slice(0, curIdx)" in html
    assert "to_phase:v.to_phase" in html
    assert "/rollback`, {method:'POST'" in html


def test_console_delete_requires_typed_customer_name(client) -> None:
    """GDPR erasure is permanent, so the dialog validates a verbatim retype."""
    html = client.get("/console").text
    assert "v.confirm === customer ? null :" in html
    assert "{method:'DELETE'" in html
    assert "URLSearchParams({confirm:customer})" in html


def test_console_states_audit_is_not_tamper_evident(client) -> None:
    """The UI must not imply a hash chain or a digital signature that does not exist.

    sha256 evidence digests are integrity checks, not signatures, and the audit
    log is a plain append-only JSONL file. Overclaiming here is a compliance
    statement, so the honest wording is pinned.
    """
    html = client.get("/console").text
    assert "摘要不是数字签名" in html
    assert "没有哈希链，也没有数字签名" in html


def test_en_console_translates_guided_tab(client) -> None:
    html = client.get("/en/console").text
    assert """tab('guided',this)">Guided</button>""" in html
    assert "What to deliver in this phase" in html


def test_en_console_translates_new_engagement_tabs(client) -> None:
    """The P1 tabs, dialogs and panes are translated, and stay honest in English."""
    html = client.get("/en/console").text
    assert """tab('evidence',this)">Evidence</button>""" in html
    assert """tab('handoff',this)">Handoff</button>""" in html
    assert """tab('audit',this)">Audit</button>""" in html
    assert "<h2>Acceptance evidence</h2>" in html
    assert "<h2>Handoff package</h2>" in html
    assert "<h2>Audit trail (append-only)</h2>" in html
    assert "Roll back phase</button>" in html
    assert "title:'Delete engagement (GDPR right to erasure)'" in html
    assert "A digest is not a digital signature" in html
    assert "no hash chain and no digital signature" in html
    # only the deliberate language switcher may still carry CJK
    import re

    leftovers = [
        ln.strip()
        for ln in html.split("\n")
        if re.search(r"[\u3400-\u4dbf\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]", ln)
    ]
    assert leftovers == ['<a class="lang" href="/console" title="中文版" aria-label="切换到中文">中文</a>']


def test_catalog_portal_served_locally(client) -> None:
    from fde_scope.web.deps import catalog_site_dir

    if catalog_site_dir() is None:
        import pytest

        pytest.skip("catalog portal not built in this checkout")
    r = client.get("/catalog/index.html")
    assert r.status_code == 200
    assert "firecrawl-search" in r.text


def test_guided_catalog_urls_are_in_app_portal_links(client) -> None:
    r = client.post("/api/engagements", data={"customer": "CatCo", "profile": "ticket"})
    eid = r.json()["engagement_id"]
    body = client.get(f"/api/engagements/{eid}/guided").json()
    pages = body["catalog_pages"]
    assert pages
    assert all(p["url"].startswith("/catalog/index.html#/") for p in pages)
    assert all(p["url_en"].startswith("/catalog/en/index.html#/") for p in pages)
    assert all("github.com" not in p["url"] for p in pages)


# ---------------------------------------------------------------------------
# guided mode: AI draft-context + goal plan（迭代 3/4）
# ---------------------------------------------------------------------------
_GOOD_DRAFT_JSON = (
    '{"stakeholders": [{"name": "张三", "role": "CTO", "is_sponsor": true, "success_metric": "首响<8s"},'
    '{"name": "李四", "role": "COO", "is_sponsor": true}],'
    ' "success_criteria": ["首响 <8s"]}'
)


def _fake_mimo(monkeypatch, reply=None, error=False):
    from fde_scope import llm as llm_mod

    monkeypatch.setattr(llm_mod.MiMoClient, "available", property(lambda self: True))

    def complete(self, prompt, **kwargs):
        if error:
            raise RuntimeError("boom")
        return reply

    monkeypatch.setattr(llm_mod.MiMoClient, "complete", complete)


def _mk(client, customer="DraftCo", profile="ticket"):
    return client.post("/api/engagements", data={"customer": customer, "profile": profile}).json()[
        "engagement_id"
    ]


def test_draft_context_endpoint(client, monkeypatch) -> None:
    _fake_mimo(monkeypatch, reply=_GOOD_DRAFT_JSON)
    eid = _mk(client)
    r = client.post(f"/api/engagements/{eid}/guided/draft-context", json={"description": "我们是茶饮连锁…"})
    assert r.status_code == 200
    body = r.json()
    assert body["used_llm"] is True
    assert len(body["draft"]["stakeholders"]) == 2
    assert body["current"]["stakeholders"] == []
    assert body["field_guide"]


def test_draft_context_never_persists(client, monkeypatch) -> None:
    _fake_mimo(monkeypatch, reply=_GOOD_DRAFT_JSON)
    eid = _mk(client)
    before = client.get(f"/api/engagements/{eid}").json()["context"]
    client.post(f"/api/engagements/{eid}/guided/draft-context", json={"description": "描述"})
    after = client.get(f"/api/engagements/{eid}").json()["context"]
    assert before == after


def test_draft_context_garbage_llm_output_is_200_null(client, monkeypatch) -> None:
    _fake_mimo(monkeypatch, reply="完全不是 JSON")
    eid = _mk(client)
    r = client.post(f"/api/engagements/{eid}/guided/draft-context", json={"description": "描述"})
    assert r.status_code == 200
    assert r.json()["draft"] is None
    assert r.json()["used_llm"] is False


def test_draft_context_llm_error_is_200_null(client, monkeypatch) -> None:
    _fake_mimo(monkeypatch, error=True)
    eid = _mk(client)
    r = client.post(f"/api/engagements/{eid}/guided/draft-context", json={"description": "描述"})
    assert r.status_code == 200
    assert r.json()["draft"] is None


def test_draft_context_rejects_blank_and_oversize(client) -> None:
    eid = _mk(client)
    assert (
        client.post(f"/api/engagements/{eid}/guided/draft-context", json={"description": "   "}).status_code
        == 422
    )
    assert (
        client.post(f"/api/engagements/{eid}/guided/draft-context", json={"description": ""}).status_code
        == 422
    )
    big = "x" * 8001
    assert (
        client.post(f"/api/engagements/{eid}/guided/draft-context", json={"description": big}).status_code
        == 422
    )


def test_draft_apply_flows_through_context_and_gate(client, monkeypatch) -> None:
    """End-to-end: draft → apply via POST /context → success_criteria gate flips to pass.

    Proves AI prefill goes through the front door and gates remain the sole
    acceptance channel (invariant 1)."""
    _fake_mimo(monkeypatch, reply=_GOOD_DRAFT_JSON)
    eid = _mk(client)
    for _ in range(2):  # qualification → stakeholder_map → success_criteria
        client.post(f"/api/engagements/{eid}/advance")
    guided = client.get(f"/api/engagements/{eid}/guided").json()
    assert guided["phase"]["slug"] == "success_criteria"
    assert guided["gates"]["success_criteria"]["passed"] is False

    draft = client.post(f"/api/engagements/{eid}/guided/draft-context", json={"description": "描述"}).json()[
        "draft"
    ]
    r = client.post(f"/api/engagements/{eid}/context", json=draft)
    assert r.status_code == 200

    guided = client.get(f"/api/engagements/{eid}/guided").json()
    assert guided["gates"]["success_criteria"]["passed"] is True
    assert guided["gates"]["success_criteria"]["next_steps"] == []


def test_draft_context_without_key_falls_back(client, monkeypatch) -> None:
    monkeypatch.delenv("FDE_SCOPE_MIMO_API_KEY", raising=False)
    eid = _mk(client)
    r = client.post(f"/api/engagements/{eid}/guided/draft-context", json={"description": "描述"})
    assert r.status_code == 200
    body = r.json()
    assert body["draft"] is None and body["used_llm"] is False
    assert body["field_guide"]  # manual fallback still served


def test_goal_plan_rule_version_persists(client, monkeypatch) -> None:
    monkeypatch.delenv("FDE_SCOPE_MIMO_API_KEY", raising=False)
    eid = _mk(client)
    gates_before = client.get(f"/api/engagements/{eid}/gates").json()
    r = client.post(f"/api/engagements/{eid}/guided/plan", json={"goal": "把首响缩到 8s 内"})
    assert r.status_code == 200
    body = r.json()
    assert body["saved"] is True and body["used_llm"] is False
    plan = body["plan"]
    assert plan["goal"] == "把首响缩到 8s 内"
    assert {i["phase_slug"] for i in plan["items"]} >= {"qualification", "disengage"}
    # persisted into assets and echoed by GET /guided
    ctx = client.get(f"/api/engagements/{eid}").json()["context"]
    assert ctx["assets"]["guided_plan"]["goal"] == plan["goal"]
    assert client.get(f"/api/engagements/{eid}/guided").json()["plan"]["goal"] == plan["goal"]
    # planning never touches the state machine
    assert client.get(f"/api/engagements/{eid}/gates").json() == gates_before


def test_goal_plan_llm_enhanced(client, monkeypatch) -> None:
    _fake_mimo(monkeypatch, reply='{"qualification": ["定制任务A"]}')
    eid = _mk(client)
    r = client.post(f"/api/engagements/{eid}/guided/plan", json={"goal": "目标"})
    body = r.json()
    assert body["used_llm"] is True
    assert any(i["title"] == "定制任务A" for i in body["plan"]["items"])


def test_goal_plan_rejects_blank(client) -> None:
    eid = _mk(client)
    assert client.post(f"/api/engagements/{eid}/guided/plan", json={"goal": "  "}).status_code == 422


def test_plan_checkbox_roundtrip_via_context(client, monkeypatch) -> None:
    monkeypatch.delenv("FDE_SCOPE_MIMO_API_KEY", raising=False)
    eid = _mk(client)
    plan = client.post(f"/api/engagements/{eid}/guided/plan", json={"goal": "目标"}).json()["plan"]
    plan["items"][0]["done"] = True
    r = client.post(f"/api/engagements/{eid}/context", json={"assets": {"guided_plan": plan}})
    assert r.status_code == 200
    echoed = client.get(f"/api/engagements/{eid}/guided").json()["plan"]
    assert echoed["items"][0]["done"] is True
    assert echoed["items"][0]["id"] == plan["items"][0]["id"]  # ids stable across save


def test_console_ships_guided_ai_and_plan_ui(client) -> None:
    html = client.get("/console").text
    for needle in ("gdDraftCtx", "gdPlan", "gdRenderGuide", "AI 起草 Context", "项目目标与任务清单"):
        assert needle in html


def test_en_console_translates_guided_ai_card(client) -> None:
    html = client.get("/en/console").text
    assert "Draft context with AI" in html
    assert "Project goal & task plan" in html


# ---------------------------------------------------------------------------
# local reading pages: /sop and the skills-handbook portal
# ---------------------------------------------------------------------------
_SOP_GITHUB = "https://github.com/ai-guru-global/fde-scope/blob/master/docs/fde_sop_full.md"
_CATALOG_GITHUB = (
    "https://github.com/ai-guru-global/fde-scope/blob/master/docs/skills-catalog/site/index.html"
)


def test_sop_rail_is_translated_and_cross_links_the_console(client) -> None:
    """The EN rail used to scrape the zh headings out of rendered HTML (plan
    §6.1); now the outline comes from the token stream and the EN rail uses
    paired literals. Both locales cross-link the console where the SOP is
    actually executed (plan §6.3)."""
    from fde_scope.web.docs_reader import render as docs_render  # noqa: F401
    from fde_scope.web.sop import _default_root, _sections_from_tokens

    text = _default_root().read_text(encoding="utf-8")
    sections = _sections_from_tokens(text)
    assert len(sections) == 7 and sections[0] == ("s01", "为什么不是 5 步")

    en = client.get("/en/sop").text
    assert "The 18 phases in detail" in en
    assert "Why not 5 steps" in en
    assert "为什么不是 5 步" not in en.split("subnav", 1)[-1].split("</div>", 1)[0]
    assert "open the console →" in en
    zh = client.get("/sop").text
    assert "打开控制台 →" in zh
    console = client.get("/console").text
    assert "阅读 SOP 全文（含 18 阶段详解）" in console


def test_sop_page_renders_the_local_document(client) -> None:
    """``/sop`` renders ``docs/fde_sop_full.md`` in-app: tables, the fenced
    zone diagram and the section rails all come from the source, and nothing
    on the page sends the reader off-site."""
    html = client.get("/sop").text
    assert "docs/fde_sop_full.md" in html  # the source is credited in-page
    assert html.count("<table") >= 4
    assert "<pre" in html and "&lt;" in html  # fenced ASCII diagram, escaped
    assert 'id="s01"' in html and 'class="subnav"' in html

    en = client.get("/en/sop").text
    assert "SOP full text" in en and "Glossary" in en
    assert "名词解释" not in en  # chrome translated
    assert "FDE full SOP — 4 zones / 18 phases" in en  # hero is paired, not the source H1
    assert "反模式" in en  # body stays the Chinese original

    for page in (html, en):
        assert _SOP_GITHUB not in page
        assert _CATALOG_GITHUB not in page


def test_sop_page_matches_its_source() -> None:
    """Drift guard: the hero title and every section the rail advertises are
    read from the document, so a renamed ``# ``/``## `` heading must show up
    (or this fails) instead of the page silently advertising stale names."""
    import html as html_mod
    import re

    from fde_scope.web.sop import _default_root

    source = _default_root().read_text(encoding="utf-8")
    lines = source.splitlines()
    title = lines[0][2:].strip()
    headings = [m.group(1).strip() for m in map(re.compile(r"^##\s+(.+)$").match, lines) if m]
    assert headings

    from fde_scope.web.app import _SOP_HTML

    assert html_mod.escape(title) in _SOP_HTML
    for heading in headings:
        assert html_mod.escape(heading) in _SOP_HTML, heading


def test_engineer_rail_links_stay_in_app(client) -> None:
    """Every reading-room shell keeps the rail in-app: SOP, skills handbook,
    repo docs and the GTM site are all local pages, and no anchor anywhere on
    these shells jumps off-site. (The certification page's provenance URLs are
    deliberately plain text, so they pass this too.)"""
    zh_pages = ("/", "/console", "/course", "/glossary", "/certification", "/sop", "/resources")
    for path in zh_pages:
        page = client.get(path).text
        assert _SOP_GITHUB not in page, path
        assert _CATALOG_GITHUB not in page, path
        assert ">SOP 全文</a>" in page, path
        assert '<a href="/catalog/index.html">技能手册库</a>' in page, path
        assert '<a href="/docs/readme">仓库文档</a>' in page, path
        assert ">GitHub 资源</a>" in page, path  # matches plain and active form
        assert '<a href="/GTM/index.html">GTM 官网</a>' in page, path
        assert 'href="http' not in page, path  # nothing jumps off-site at all
    en_pages = (
        "/en/",
        "/en/console",
        "/en/course",
        "/en/glossary",
        "/en/certification",
        "/en/sop",
        "/en/resources",
    )
    for path in en_pages:
        page = client.get(path).text
        assert _SOP_GITHUB not in page, path
        assert _CATALOG_GITHUB not in page, path
        assert ">SOP full text</a>" in page, path
        assert '<a href="/catalog/en/index.html">Skills handbook</a>' in page, path
        assert '<a href="/en/docs/readme">Repo docs</a>' in page, path
        assert ">GitHub resources</a>" in page, path
        assert '<a href="/GTM/en/index.html">GTM site</a>' in page, path
        assert 'href="http' not in page, path


def test_resources_page_zh_renders_the_harvest(client) -> None:
    """/resources renders every packaged record as a card and keeps each
    upstream GitHub URL inert. Fields are read from ``resources.yaml`` rather
    than hardcoded, so the assertion survives a re-harvest (plan step 7: the
    zh fetch test)."""
    import html as html_mod

    from fde_scope.resources.repo import load_resources

    r = client.get("/resources")
    assert r.status_code == 200
    assert '<html lang="zh">' in r.text
    assert "__ICON_SPRITE__" not in r.text  # placeholder filled by app.py
    assert 'id="res-q"' in r.text and 'oninput="resFilter()"' in r.text

    records = load_resources()
    assert r.text.count('<div class="card rcard"') == len(records)

    probe = sorted(records, key=lambda x: x.slug)[0]
    esc_url = html_mod.escape(probe.url, quote=True)
    assert f"<code>{esc_url}</code>" in r.text  # URL shown as inert text
    assert f'href="{esc_url}"' not in r.text  # ...never as a live link
    assert 'href="http' not in r.text  # nothing jumps off-site at all

    mirrored = next((x for x in records if x.mirror and x.files), None)
    assert mirrored is not None
    assert f"docs/github-resources/mirror/{mirrored.mirror_dir}" in r.text


def test_resources_page_en_keeps_chinese_out(client) -> None:
    """/en/resources is rendered from ``render('en')``, not a to_en pass, so our
    own UI chrome must not leak Chinese — above all the stored licence decision
    (translated via ``_DECISION_CLAUSES_EN``). Two things are source-language on
    purpose and are stripped first, exactly as the glossary strips its source
    ``alias``: the ``data-t`` search haystacks (machine-read, they carry the zh
    summary) and the ``.r-up`` blocks (the upstream description verbatim, which
    GitHub authors may write in Chinese)."""
    import re

    from fde_scope.web.resources import _DECISION_CLAUSES_EN

    r = client.get("/en/resources")
    assert r.status_code == 200
    assert '<html lang="en">' in r.text
    assert "permissive licence" in r.text  # a translated clause really rendered

    stripped = r.text.replace('<a class="lang" href="/resources">中文</a>', "")
    stripped = re.sub(r'data-t="[^"]*"', "", stripped)  # machine-read haystack
    stripped = re.sub(r'<p class="r-up">.*?</p>', "", stripped)  # upstream verbatim
    leaked = [ln for ln in stripped.splitlines() if re.search(r"[一-鿿]", ln)]
    assert leaked == []
    for zh_clause in _DECISION_CLAUSES_EN:
        assert zh_clause not in stripped


def test_reading_pages_are_public() -> None:
    """AGENTS.md invariant 7: new routes confirm the auth whitelist on purpose.
    All reading pages are read-only and carry no engagement data."""
    from fde_scope.web import auth

    for path in (
        "/sop",
        "/en/sop",
        "/showcase",
        "/en/showcase",
        "/resources",
        "/en/resources",
        "/catalog/index.html",
        "/catalog/en/index.html",
        "/GTM/",
        "/GTM/index.html",
        "/GTM/en/",
        "/GTM/en/index.html",
        "/gh-resources/site/index.html",
        "/gh-resources/site/en/index.html",
        "/docs/images/overview.png",
        "/docs/images/console.png",
    ):
        assert path in auth.PUBLIC_PATHS, path


def test_doc_whitelist_covers_every_reader_slug() -> None:
    """Drift guard: auth.py carries an explicit literal slug list instead of
    importing ``docs_reader`` (auditability); this pins the literal to the
    reader's actual corpus so a new document can't ship token-gated by
    accident. The GTM site's woff2 fonts and its two embedded screenshots are
    whitelisted explicitly too — by exact path, never by directory prefix."""
    from fde_scope.web import auth
    from fde_scope.web.docs_reader import SLUGS

    for slug in SLUGS:
        assert f"/docs/{slug}" in auth.PUBLIC_PATHS, slug
        assert f"/en/docs/{slug}" in auth.PUBLIC_PATHS, slug
    fonts = {p for p in auth.PUBLIC_PATHS if p.startswith("/GTM/fonts/")}
    assert len(fonts) == 8, fonts
    images = {p for p in auth.PUBLIC_PATHS if p.startswith("/GTM/images/")}
    assert images == {"/GTM/images/console.png", "/GTM/images/overview.png"}, images


# ---------------------------------------------------------------------------
# repo docs reader（/docs/{slug}）+ GTM 官网站内挂载
# ---------------------------------------------------------------------------


def test_docs_reader_serves_readme_with_local_assets(client) -> None:
    """``/docs/readme`` renders the repository README in-app: the demo
    screenshots resolve to the local image route, document citations are
    in-app deep links, and no anchor leaves the app."""
    html = client.get("/docs/readme").text
    assert 'src="/docs/images/overview.png"' in html
    assert 'src="/docs/images/console.png"' in html
    assert 'href="/sop"' in html  # the SOP citation is a local deep link
    assert 'href="/course"' in html or 'href="/course#doc-' in html
    assert 'href="http' not in html


def test_docs_reader_routes_and_locales(client) -> None:
    """Every advertised slug answers 200; unknown slugs 404; the English page
    keeps English chrome over the Chinese-authored body."""
    from fde_scope.web.docs_reader import SLUGS

    for slug in SLUGS:
        assert client.get(f"/docs/{slug}").status_code == 200, slug
        assert client.get(f"/en/docs/{slug}").status_code == 200, slug
    r = client.get("/docs/no-such-doc")
    assert r.status_code == 404
    en = client.get("/en/docs/readme").text
    assert '<html lang="en">' in en
    assert "名词解释" not in en
    assert "Repo docs" in en  # rail translated
    zh = client.get("/docs/readme").text
    assert "仓库文档" in zh


def test_docs_reader_survives_a_missing_source_tree(client) -> None:
    """A wheel install has no docs/: the reader degrades to an in-page notice
    (no crash, no GitHub link), mirroring the course's fallback."""
    from pathlib import Path

    import fde_scope.web.docs_reader as dr

    rendered = dr.render("readme", "zh", root=Path("/nonexistent/repo"))
    assert "克隆仓库后重启本页即可在这里阅读全文" in rendered
    assert 'href="http' not in rendered


def test_doc_images_route_serves_only_allowlisted_files(client) -> None:
    """The images route is allowlisted to the two demo screenshots; anything
    else (path traversal included) 404s."""
    assert client.get("/docs/images/overview.png").status_code == 200
    assert client.get("/docs/images/console.png").status_code == 200
    assert client.get("/docs/images/no-such.png").status_code == 404
    assert client.get("/docs/images/..%2Ffde_sop_full.md").status_code in (404, 400)


def test_docs_reader_active_class_follows_the_slug(client) -> None:
    """The rail's "Repo docs" link is hardcoded to /docs/readme — it may only
    carry ``class="active"`` while readme itself is open, otherwise every
    document looks like the README page."""
    from fde_scope.web.docs_reader import render

    assert 'class="active"' in render("readme")
    for slug in ("architecture", "license", "features"):
        assert 'class="active"' not in render(slug), slug


def test_docs_reader_builds_a_toc_from_heading_tokens(client) -> None:
    """Long documents get an on-this-page list built from the heading tokens
    (never scraped back out of rendered HTML), and every TOC link points at a
    heading id that really exists in the body."""
    from fde_scope.web.docs_reader import render

    html = render("architecture")
    assert '<details class="toc">' in html
    assert "本页目录" in html
    # short/sparse documents stay clean
    assert '<details class="toc">' not in render("notice")
    # every toc anchor resolves to a real heading id
    import re

    toc_hrefs = re.findall(r'class="toc-list".*?</ul>', html, re.S)
    body = html.split("toc-list", 1)[-1]
    missing = [
        hid
        for hid in re.findall(r'<a href="#([^"]+)">', toc_hrefs[0] if toc_hrefs else "")
        if f'id="{hid}"' not in body
    ]
    assert missing == []
    en = render("ontology", locale="en")
    assert "On this page" in en


def test_docs_reader_strips_unrecognized_absolute_hrefs(client) -> None:
    """A hand-written absolute href that is not a known in-app route degrades
    to its label text instead of becoming a link — same policy as external
    URLs, so a future markdown edit cannot silently grow a broken (or
    unexpected) link."""
    from fde_scope.web.docs_reader import _resolve_href

    assert _resolve_href("/console", "", set()) == "/console"
    assert _resolve_href("/docs/images/overview.png", "", set()) == "/docs/images/overview.png"
    assert _resolve_href("/catalog/index.html", "", set()) == "/catalog/index.html"
    assert _resolve_href("/admin/secret", "", set()) is None
    assert _resolve_href("/definitely/not/a/route", "", set()) is None


def test_docs_images_allowlist_is_derived_from_the_directory() -> None:
    """The allowlist is the ``docs/images/`` listing, not a hand-maintained
    tuple — dropping a file retires it, adding one serves it, and nothing
    outside the directory is reachable."""
    from fde_scope.web.docs_reader import _default_root, _repo_images, image_path

    images = _repo_images()
    assert "overview.png" in images and "console.png" in images
    assert image_path("overview.png") is not None
    assert image_path("../fde_sop_full.md") is None
    assert image_path("no-such.png") is None
    # names are files only, sorted, from that directory
    import os

    on_disk = sorted(p for p in os.listdir(_default_root() / "docs" / "images") if (p))
    assert list(images) == sorted(on_disk)


def test_gtm_site_served_locally(client) -> None:
    """The GTM landing site is mounted at /GTM: the page, its fonts and its
    assets answer locally, and the artifact carries no external anchor."""
    from fde_scope.web.deps import gtm_site_dir

    if gtm_site_dir() is None:
        import pytest

        pytest.skip("GTM site not present in this checkout")
    page = client.get("/GTM/index.html")
    assert page.status_code == 200
    assert "CASE FILE" in client.get("/GTM/en/index.html").text  # site content
    for name in (
        "big-shoulders-display-latin-900-normal.woff2",
        "public-sans-latin-400-normal.woff2",
    ):
        assert client.get(f"/GTM/fonts/{name}").status_code == 200, name
    for name in ("console.png", "overview.png"):
        assert client.get(f"/GTM/images/{name}").status_code == 200, name
    import re

    for path in ("/GTM/index.html", "/GTM/en/index.html"):
        html = client.get(path).text
        assert re.search(r'<a [^>]*href="https?://', html) is None, path
        assert 'target="_blank"' not in html, path


def test_gtm_assets_stay_public_when_auth_is_on(client, monkeypatch) -> None:
    """The portal's hero and console screenshots are embedded by the *public*
    GTM pages, so a token-gated install must still serve them — otherwise both
    locales render with two broken images. The whitelist is exact-path, so a
    gated API route and a non-whitelisted GTM asset stay behind the token."""
    from fde_scope.web.deps import gtm_site_dir

    if gtm_site_dir() is None:
        import pytest

        pytest.skip("GTM site not present in this checkout")
    monkeypatch.setenv("FDE_SCOPE_API_TOKEN", "gtm-token-123456")
    for path in ("/GTM/index.html", "/GTM/en/index.html"):
        assert client.get(path).status_code == 200, path
        assert "gtm-token-123456" not in client.get(path).text, path
    for name in ("console.png", "overview.png"):
        assert client.get(f"/GTM/images/{name}").status_code == 200, name
    assert client.get("/GTM/images/no-such.png").status_code == 401
    assert client.get("/api/engagements").status_code == 401


def test_favicon_is_served_and_public(client, monkeypatch) -> None:
    """Every HTML shell links ``/static/favicon.svg``; a missing asset makes
    browsers fall back to ``/favicon.ico`` (also absent), so both requests 404
    on every page load. The glyph is a brand asset with no engagement data, so
    it stays public when auth is on — browsers fetch it without headers."""
    r = client.get("/static/favicon.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert b"<svg" in r.content
    for shell in ("/", "/en/", "/console", "/en/console"):
        assert "/static/favicon.svg" in client.get(shell).text, shell
    monkeypatch.setenv("FDE_SCOPE_API_TOKEN", "favicon-token-123456")
    assert client.get("/static/favicon.svg").status_code == 200
    assert client.get("/static/no-such.svg").status_code == 401


def test_gtm_root_redirects_to_the_landing_page(client) -> None:
    """The rail links /GTM/index.html directly, but a bare /GTM/ must also
    land on the site (StaticFiles html=True serves the index)."""
    from fde_scope.web.deps import gtm_site_dir

    if gtm_site_dir() is None:
        import pytest

        pytest.skip("GTM site not present in this checkout")
    r = client.get("/GTM/", follow_redirects=False)
    assert r.status_code in (200, 307)


def test_gtm_anchor_labels_match_their_targets(client) -> None:
    """No GTM anchor may be labelled "GitHub" while pointing at ``/``: that is
    the console, and the artifact carries no external anchor by design, so the
    repo is reached through the in-app readers (``/docs/readme``, ``/sop``,
    ``/docs/license``). Pins both locales' labels, which ``GTM/i18n_split.py``
    regenerates from ``GTM/index.bilingual.html``."""
    import re

    from fde_scope.web.deps import gtm_site_dir

    if gtm_site_dir() is None:
        import pytest

        pytest.skip("GTM site not present in this checkout")
    expected = {
        "/GTM/index.html": ("控制台", "打开控制台", "阅读 README"),
        "/GTM/en/index.html": ("CONSOLE", "Open the console", "Read the README"),
    }
    for path, labels in expected.items():
        html = client.get(path).text
        assert re.search(r'<a [^>]*href="/"[^>]*>[^<]*GitHub', html) is None, path
        assert "Star on GitHub" not in html, path
        assert 'href="/docs/readme"' in html, path
        for label in labels:
            assert f">{label}</a>" in html, (path, label)


def test_homepage_connector_tiles_are_registry_generated(client) -> None:
    """The tiles' status pills come from the connector registry at import
    time — the hand-written "ROS2 Bag → stub" once drifted from the shipped
    code (plan §2.1), so the homepage must not carry hand-written statuses
    anymore. The KPI section states how to replace the demo numbers (§2.3)."""
    from fde_scope.connectors._registry import _MODULE_BY_TYPE, get_registry

    html = client.get("/").text
    registry = get_registry()
    assert "状态由连接器注册表在导入时生成" in html
    assert html.count("<span") >= len(_MODULE_BY_TYPE)
    for slug in _MODULE_BY_TYPE:
        ok = slug in registry
        assert ('class="status s-ok">已注册' in html) == ok or not ok, slug
    # no hand-written status vocabulary survives in the connectors section
    section = html.split('id="connectors"', 1)[1].split("</section>", 1)[0]
    assert "stub" not in section
    assert 'class="status s-stub"' not in html  # the scenario tile is fixed too
    assert "换成真实数据" in html


def test_catalog_portal_brand_is_keyboard_reachable_and_gtm_links_resolve(client) -> None:
    """The brand area was a ``<div onclick>`` (invisible to keyboards) and the
    GTM links pointed three/four levels above the served root, surviving only
    because the browser clamps at ``/`` (plan §8.2/§8.6). The search box also
    needs a label (§8.3), and the search handler must not query a ``#hero``
    id that does not exist (§8.1)."""
    site = Path(__file__).resolve().parents[1] / "docs" / "skills-catalog" / "site"
    zh = (site / "index.html").read_text(encoding="utf-8")
    en = (site / "en" / "index.html").read_text(encoding="utf-8")
    for name, html in (("index.html", zh), ("en/index.html", en)):
        assert '<a class="brand" href="#/">' in html, name
        assert '<div class="brand"' not in html, name
        assert 'aria-label="' in html and 'type="search"' in html, name
        assert "getElementById('hero')" not in html, name
    assert '"../../../GTM' not in zh and '"../../../../GTM' not in en
    assert '"../GTM/index.html"' in zh and '"../../GTM/index.html"' in en


def test_catalog_links_survive_an_install_without_docs(client) -> None:
    """A wheel install has no ``docs/``, so the portal mount is skipped and the
    rail's ``/catalog/index.html`` link must still land on an in-app notice
    rather than a 404. Exercises the else-branch of the mount (unreachable in
    this checkout, where ``docs/`` exists)."""
    import importlib

    from fastapi.testclient import TestClient

    from fde_scope.web import app as app_mod
    from fde_scope.web import deps

    real = deps.catalog_site_dir
    deps.catalog_site_dir = lambda: None  # manual restore: undo() would outlive the reload
    try:
        importlib.reload(app_mod)
        bare = TestClient(app_mod.app)
        zh = bare.get("/catalog/index.html")
        assert zh.status_code == 200
        assert "docs/skills-catalog/site" in zh.text
        en = bare.get("/catalog/en/index.html")
        assert en.status_code == 200
        en_text = en.text
        assert "docs/skills-catalog/site" in en_text and "not in this install" in en_text
    finally:
        deps.catalog_site_dir = real
        # the reload swapped the module-global app for the no-docs variant;
        # leaving it that way leaked into every later test (order-dependent
        # failures in anything inspecting the mounts)
        importlib.reload(app_mod)
        importlib.reload(app_mod)


def test_ontology_store_api_success_path(client) -> None:
    """Q3: ``GET /api/ontology/store/{id}`` had no success-path test."""
    from fde_scope.ontology.models import InstanceStore
    from fde_scope.ontology.store import OntologyStore

    OntologyStore().save_store(
        InstanceStore(id="q3-store", ontology_ref="fde-core@1.0.0", individuals=[{"curie": "ex:i1"}])
    )
    r = client.get("/api/ontology/store/q3-store")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "q3-store" and body["ontology_ref"] == "fde-core@1.0.0"
    assert len(body["individuals"]) == 1
    assert client.get("/api/ontology/store/nope").status_code == 404


def test_skill_and_journal_error_branches(client) -> None:
    """Q3: the 404/409/422 branches of skills, journal and context."""
    # unknown skill id on publish / export / archive
    for path in ("/api/skills/ghost/publish", "/api/skills/ghost/archive"):
        assert client.post(path).status_code == 404, path
    assert client.post("/api/skills/ghost/export", json={"format": "agentscope"}).status_code == 404
    # journal: unknown engagement
    assert client.get("/api/engagements/ghost/journal").status_code == 404
    eid = client.post("/api/engagements", data={"customer": "Q3"}).json()["engagement_id"]
    # context: pydantic 422 carries the field path
    bad = client.post(f"/api/engagements/{eid}/context", json={"success_criteria": "not-a-list"})
    assert bad.status_code == 422
    assert any("success_criteria" in str(e.get("loc", "")) for e in bad.json()["detail"])


def test_fallback_notices_are_wellformed(client) -> None:
    """Q3: the conditional fallback branches for a wheel install (no docs/,
    no GTM/) — the templates are import-time constants, so assert their
    content here; the routes themselves only exist on an installed app."""
    import fde_scope.web.app as webapp

    mounted = {getattr(r, "path", "") for r in webapp.app.routes}
    for prefix, names in (
        ("/catalog", ("_CATALOG_NOTICE", "_CATALOG_NOTICE_EN")),
        ("/GTM", ("_GTM_NOTICE", "_GTM_NOTICE_EN")),
    ):
        # when the install has no asset dir the else-branch registers the
        # notice routes instead of a mount; either way the notice template
        # (module-level when that branch ran) must be a well-formed shell.
        if prefix not in mounted:
            for name in names:
                notice = getattr(webapp, name, None)
                assert notice is not None and "DOCTYPE" in notice and "/static/favicon.svg" in notice, name


# ---------------------------------------------------------------------------
# course lab grading（实验判分：学习页与执行引擎共用 run_lab）
# ---------------------------------------------------------------------------
def test_course_labs_registry_endpoint(client) -> None:
    labs = client.get("/api/course/labs").json()
    assert [lab["day"] for lab in labs] == ["D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"]
    assert all(lab["gate"] and lab["deliverable"] and lab["checks"] > 0 for lab in labs)
    assert labs[0]["gate"] == "G1" and labs[-1]["gate"].startswith("G8")


def test_course_doctor_endpoint(client) -> None:
    body = client.get("/api/course/doctor").json()
    assert body["gate"] == "G0"
    assert body["exit_code"] == 0  # a healthy checkout grades nothing but passes G0
    assert body["ok"] is True
    assert body["items"] and all("id" in item for item in body["items"])


def test_course_lab_grade_unknown_day_404(client) -> None:
    r = client.post("/api/course/labs/D9/grade")
    assert r.status_code == 404


def test_course_lab_grade_d1_is_green_cold(client) -> None:
    """D1 grades no writing, so the API path must be green on a cold machine —
    same oracle the verifier's own ``run_all`` test pins (81/10/9 overall)."""
    body = client.post("/api/course/labs/D1/grade").json()
    assert body["ok"] is True, body
    assert body["failed"] == 0
    assert body["passed"] > 0
    assert all(c["status"] in ("pass", "manual") for c in body["checks"])


def test_course_page_carries_the_grading_panel(client) -> None:
    html = client.get("/course").text
    assert 'id="lab-grading"' in html
    assert "labGrade" in html and "labDoctor" in html
    assert 'data-day="D1"' in html
    en = client.get("/en/course").text
    assert "Lab grading" in en and "Day 8 · Monetise" in en


# ---------------------------------------------------------------------------
# retrospective（复盘：SLA 时钟 + 时间线 + gate 统计）
# ---------------------------------------------------------------------------
def test_retrospective_endpoint_after_web_create(client) -> None:
    r = client.post("/api/engagements", data={"customer": "RetroCo", "profile": "ticket"})
    eid = r.json()["engagement_id"]
    r = client.get(f"/api/engagements/{eid}/retrospective")
    assert r.status_code == 200
    body = r.json()
    assert body["engagement_id"] == eid
    assert body["start_source"] == "engagement.create"
    assert body["advances_ok"] == 0
    assert body["advances_blocked"] == 0
    assert body["timeline_consistent"] is True
    assert [m["key"] for m in body["sla"]] == ["first_integration", "production", "disengage"]
    assert body["data_sources"][0].startswith("audit.jsonl")


def test_retrospective_endpoint_unknown_engagement_404(client) -> None:
    r = client.get("/api/engagements/eng-ghost/retrospective")
    assert r.status_code == 404


def test_retrospective_after_advance_and_gate(client) -> None:
    eid = client.post("/api/engagements", data={"customer": "FlowCo", "profile": "ticket"}).json()[
        "engagement_id"
    ]
    assert client.post(f"/api/engagements/{eid}/advance").json()["advanced"] is True
    gate_r = client.post(f"/api/engagements/{eid}/gate/success_criteria").json()
    assert gate_r["passed"] is False  # 无 sponsor / 无标准 → 被拦
    body = client.get(f"/api/engagements/{eid}/retrospective").json()
    assert body["advances_ok"] == 1
    sc = next(g for g in body["gates"] if g["slug"] == "success_criteria")
    assert sc["source"] == "audit"
    assert sc["first_pass"] is False
    assert body["gate_first_pass_rate"] == 0.0
