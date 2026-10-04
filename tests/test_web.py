"""Tests for the Web UI FastAPI app."""

from __future__ import annotations

import pytest

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
    assert r.text.count('<div class="card">') == len(GLOSSARY_ZH)  # no duplicates


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
    assert r.text.count('<div class="card">') == len(GLOSSARY_EN)

    stripped = r.text.replace('<a class="lang" href="/glossary">中文</a>', "")
    stripped = re.sub(r'<span class="alias">[^<]*</span>', "", stripped)
    leaked = [ln for ln in stripped.splitlines() if re.search(r"[\u4e00-\u9fff]", ln)]
    assert leaked == []


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
        assert f'<div class="sgrp">{eng}</div>' in en


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
    """``- [ ]`` renders as ☐ so the homework lists read as checkboxes; the
    count is derived from the sources, not hand-maintained."""
    from fde_scope.web.course import _CHAPTERS, _default_root

    root = _default_root()
    sources = [((root / fn).read_text(encoding="utf-8")) for _key, fn, *_ in _CHAPTERS]
    expected = sum(text.count("- [ ] ") for text in sources) + sum(text.count("☐") for text in sources)
    html = client.get("/course").text
    assert html.count("☐") == expected
    assert "- [ ]" not in html


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
    """A wheel install has no ``course-level-1/``: the page must explain that
    and keep its anchors, not raise."""
    from fde_scope.web.course import _CHAPTERS, render

    html = render("zh", root=tmp_path)
    assert "course-level-1" in html
    assert "读不到课程文件" in html
    assert html.count('id="doc-') == len(_CHAPTERS)
    assert html.count("这一章读不到") == len(_CHAPTERS)


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


# ---------------------------------------------------------------------------
# deploy plan API（角色 → 连接器 → 工具绑定）
# ---------------------------------------------------------------------------
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
    # the original 7 tabs are untouched
    for name in ("overview", "sop", "gates", "context", "forge", "kpi", "journal"):
        assert f"""tab('{name}',this)""" in html


def test_en_console_translates_guided_tab(client) -> None:
    html = client.get("/en/console").text
    assert """tab('guided',this)">Guided</button>""" in html
    assert "What to deliver in this phase" in html


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
    zh_pages = ("/", "/console", "/course", "/glossary", "/certification", "/sop")
    for path in zh_pages:
        page = client.get(path).text
        assert _SOP_GITHUB not in page, path
        assert _CATALOG_GITHUB not in page, path
        assert ">SOP 全文</a>" in page, path
        assert '<a href="/catalog/index.html">技能手册库</a>' in page, path
        assert '<a href="/docs/readme">仓库文档</a>' in page, path
        assert '<a href="/GTM/index.html">GTM 官网</a>' in page, path
        assert 'href="http' not in page, path  # nothing jumps off-site at all
    en_pages = ("/en/", "/en/console", "/en/course", "/en/glossary", "/en/certification", "/en/sop")
    for path in en_pages:
        page = client.get(path).text
        assert _SOP_GITHUB not in page, path
        assert _CATALOG_GITHUB not in page, path
        assert ">SOP full text</a>" in page, path
        assert '<a href="/catalog/en/index.html">Skills handbook</a>' in page, path
        assert '<a href="/en/docs/readme">Repo docs</a>' in page, path
        assert '<a href="/GTM/en/index.html">GTM site</a>' in page, path
        assert 'href="http' not in page, path


def test_reading_pages_are_public() -> None:
    """AGENTS.md invariant 7: new routes confirm the auth whitelist on purpose.
    All reading pages are read-only and carry no engagement data."""
    from fde_scope.web import auth

    for path in (
        "/sop",
        "/en/sop",
        "/catalog/index.html",
        "/catalog/en/index.html",
        "/GTM/",
        "/GTM/index.html",
        "/GTM/en/",
        "/GTM/en/index.html",
        "/docs/images/overview.png",
        "/docs/images/console.png",
    ):
        assert path in auth.PUBLIC_PATHS, path


def test_doc_whitelist_covers_every_reader_slug() -> None:
    """Drift guard: auth.py carries an explicit literal slug list instead of
    importing ``docs_reader`` (auditability); this pins the literal to the
    reader's actual corpus so a new document can't ship token-gated by
    accident. The GTM site's woff2 fonts are whitelisted explicitly too."""
    from fde_scope.web import auth
    from fde_scope.web.docs_reader import SLUGS

    for slug in SLUGS:
        assert f"/docs/{slug}" in auth.PUBLIC_PATHS, slug
        assert f"/en/docs/{slug}" in auth.PUBLIC_PATHS, slug
    fonts = {p for p in auth.PUBLIC_PATHS if p.startswith("/GTM/fonts/")}
    assert len(fonts) == 8, fonts


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
    import re

    for path in ("/GTM/index.html", "/GTM/en/index.html"):
        html = client.get(path).text
        assert re.search(r'<a [^>]*href="https?://', html) is None, path
        assert 'target="_blank"' not in html, path


def test_gtm_root_redirects_to_the_landing_page(client) -> None:
    """The rail links /GTM/index.html directly, but a bare /GTM/ must also
    land on the site (StaticFiles html=True serves the index)."""
    from fde_scope.web.deps import gtm_site_dir

    if gtm_site_dir() is None:
        import pytest

        pytest.skip("GTM site not present in this checkout")
    r = client.get("/GTM/", follow_redirects=False)
    assert r.status_code in (200, 307)


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
        assert "docs/skills-catalog/site" in en.text and "not in this install" in en.text
    finally:
        deps.catalog_site_dir = real
        importlib.reload(app_mod)
