"""The Level-1 course reading room (``/course``, ``/en/course``).

The lessons are authored as Markdown in ``course-level-1/`` at the repo root,
which is the source of truth: in a checkout this page reads it directly, so a
lesson edit lands on the next restart with nothing to keep in sync. The same
directory is also shipped inside the wheel as package data
(``fde_scope/_data/course-level-1``, see ``pyproject.toml``'s
``force-include``), and :func:`_default_root` falls back to that copy when the
repo-root directory is absent — an installed app serves the same chapter set.
If neither is readable the route still renders, with an in-page notice instead
of a broken page.

Rendered from paired literals, like ``glossary.py`` and ``certification.py``
(their docstrings explain why the ``to_en`` pass is wrong for whole pages of
content): the chrome and the twenty-five chapter titles are translated here,
while the lesson bodies are Chinese-authored and are served as authored on
both locales — the English page says so in a notice, rather than pushing 5,000
lines of prose through the substring translator, which would translate a few
navigation fragments and silently leave the rest.

Markdown is rendered with ``html: False``: the lessons use angle-bracket
placeholders (``<id>``, ``<skill-id>``, ``<N 条脏数据>``) that must stay
visible, so raw HTML is escaped. Before rendering, every link and image is
rewritten to an in-app target — chapter cross-references become ``#doc-``
anchors, repo citations point at the local reader pages, and anything
unresolvable is stripped to its label — with code fences left byte-identical
(their template examples are full of markdown links). Two corrections happen
after rendering: ``<br>`` (the only in-cell line break a GFM table has) is
restored outside code blocks, and headings are demoted one level so the
document outline runs chapter (h2) → lesson section (h3).

This module also hosts the shared link-rewrite machinery — the fence walker,
path normalisation and the markdown link regexes — that ``docs_reader.py``
builds on: ``docs_reader`` imports this module, so the utilities cannot live
there without a cycle.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

from ..course.catalog import LABS as _LAB_REGISTRY
from .layout import BASE_CSS, PROSE_CSS, SHELL_CSS, SHELL_JS, side_nav
from .mdrender import (
    AUTOLINK as _AUTOLINK,
)
from .mdrender import (
    MD_IMAGE as _MD_IMAGE,
)
from .mdrender import (
    MD_LINK as _MD_LINK,
)
from .mdrender import (
    demoting_markdown,
    rewrite_outside_fences,
)
from .mdrender import (
    normalize_path as md_normalize,
)

#: The day chips' English chrome (registry titles are zh-authored; the EN page
#: translates the chrome, not the book — same policy as the chapter titles).
_LAB_TITLE_EN = {
    "D1": "Day 1 · Run the chain end to end",
    "D2": "Day 2 · Define success · the brief",
    "D3": "Day 3 · Site and data health check",
    "D4": "Day 4 · Corpus and customer script",
    "D5": "Day 5 · Validation and evaluation",
    "D6": "Day 6 · Operationalisation",
    "D7": "Day 7 · Handover and distillation",
    "D8": "Day 8 · Monetise · portfolio and defence",
}
_LAB_DELIVERABLE_EN = {
    "D1": "mini-chain evidence pack (connect sample + corpus report + 3-sentence read)",
    "D2": "customer brief (≤1 page: ≥3 measurable success criteria + dual sponsors + abandon criteria)",
    "D3": "data health report (field table + PII handling + site facts + ≥3 quality risks)",
    "D4": "corpus report + one customer script (jargon-free, synthesis ratio honestly labelled)",
    "D5": "prototype evidence + eval results + top-3 bad cases + one-page validation log",
    "D6": "SLO card (3 + error budget + alert route) + runbook + on-call handover card",
    "D7": "handover pack (four artefacts) + skill card + exit plan",
    "D8": "portfolio in three wrappers (job / briefing / freelance) + closing defence",
}

#: Grading calls only; every user-visible label arrives via the container's
#: data-* attributes (server-rendered, bilingual), so the script stays locale-free.
_LAB_JS = """
<script>
(function(){
  'use strict';
  function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){
    return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c];});}
  function call(url, opts){
    return fetch(url, opts).then(function(r){
      var denied = r.status === 401 || r.status === 403;
      return r.json().catch(function(){ return {}; }).then(function(d){
        if (!r.ok) {
          var err = new Error(d && d.detail ? d.detail : ('HTTP ' + r.status));
          err.denied = denied; throw err;
        }
        return d;
      });
    });
  }
  var out = document.getElementById('lab-out');
  function label(key){ return out.getAttribute('data-t-' + key) || key; }
  /* The verdict marks are the console's dots, not emoji: ✅❌✋ render in an
     arbitrary system font at text weight, pick up no colour from the ramp, and
     reach a screen reader as a glyph name. ``role="img"`` plus the localized
     word keeps the state in the accessibility tree, which the emoji never were. */
  var MARK = {pass:'d-ok', fail:'d-bad', manual:'d-warn'};
  function mark(st){
    var word = st === 'pass' ? label('ok') : st === 'fail' ? label('fail') : label('manual');
    return '<span class="dot ' + (MARK[st] || '') + '" role="img" aria-label="' + esc(word) + '"></span>';
  }

  window.labDoctor = function(){
    var box = document.getElementById('lab-doctor');
    box.textContent = '…';
    call('/api/course/doctor').then(function(d){
      box.innerHTML = d.ok
        ? mark('pass') + ' G0 · ' + (d.summary ? ('ok ' + d.summary.ok + ' / warn ' + d.summary.warn) : '')
        : mark('fail') + ' G0' + (d.blockers && d.blockers.length ? ' · ' + esc(d.blockers.join(', ')) : '');
    }).catch(function(e){ box.textContent = label('error') + ': ' + e.message; });
  };

  window.labGrade = function(day){
    out.innerHTML = '<div class="labres">' + esc(label('working')) + '</div>';
    call('/api/course/labs/' + encodeURIComponent(day) + '/grade', {method:'POST'})
      .then(function(d){
        var rows = (d.checks || []).map(function(c){
          return '<tr><td>' + mark(c.status) + ' <b>' + esc(c.id) + '</b></td>' +
            '<td>' + esc(c.ask) + '</td>' +
            '<td>' + esc(c.detail || '') +
              (c.hint && c.status === 'fail' ? '<br><span class="hint">' + esc(c.hint) + '</span>' : '') +
            '</td></tr>';
        }).join('');
        out.innerHTML = '<div class="labres">' +
          '<div class="labsum">' + esc(d.day) + ' · ' + esc(d.gate) + ' — ' +
            mark(d.ok ? 'pass' : 'fail') + ' ' + d.passed + '/' + d.score + ' ' + esc(label('scored')) +
            (d.manual ? ' · ' + d.manual + ' ' + esc(label('manual')) : '') + '</div>' +
          (rows ? '<table><tbody>' + rows + '</tbody></table>' : '') +
          '</div>';
      })
      .catch(function(e){
        out.innerHTML = '<div class="labres">' + mark('fail') + ' ' +
          esc(label('error')) + ': ' + esc(e.denied ? label('deny') : e.message) + '</div>';
      });
  };
})();
</script>
"""

_COURSE_DIRNAME = "course-level-1"

#: (anchor key, filename, zh title, en title, zh rail label, en rail label).
#: Titles are pinned to each file's ``# `` heading by ``tests/test_web.py``.
_CHAPTERS: list[tuple[str, str, str, str, str, str]] = [
    (
        "readme",
        "README.md",
        "小白 FDE 炼金术 · Level 1",
        "Beginner FDE Alchemy · Level 1",
        "总览",
        "Overview",
    ),
    (
        "00",
        "00-FDE方法论历史与原理.md",
        "00 · FDE 方法论、历史与原理",
        "00 · FDE methodology, history and principles",
        "00 方法论",
        "00 Method",
    ),
    (
        "01",
        "01-课程设计说明书.md",
        "01 · 课程设计说明书",
        "01 · Course design brief",
        "01 设计说明",
        "01 Design",
    ),
    (
        "02",
        "02-逐日教学大纲.md",
        "02 · 逐日教学大纲（Day 1 – Day 8）",
        "02 · Day-by-day syllabus (Day 1 – Day 8)",
        "02 教学大纲",
        "02 Syllabus",
    ),
    (
        "03",
        "03-评估体系与通关门禁.md",
        "03 · 评估体系与通关门禁",
        "03 · Assessment system and gates",
        "03 评估门禁",
        "03 Assessment",
    ),
    (
        "04",
        "04-交付实施手册.md",
        "04 · 交付实施手册",
        "04 · Delivery handbook",
        "04 交付手册",
        "04 Delivery",
    ),
    (
        "05",
        "05-讲师手册.md",
        "05 · 讲师手册（Facilitator Guide）",
        "05 · Facilitator guide",
        "05 讲师手册",
        "05 Facilitator",
    ),
    (
        "06",
        "06-学员手册与作业包.md",
        "06 · 学员手册与作业包",
        "06 · Learner handbook and homework pack",
        "06 学员手册",
        "06 Learner",
    ),
    (
        "07",
        "07-实战剧本与案例库.md",
        "07 · 实战剧本与案例库",
        "07 · Scenario scripts and case library",
        "07 剧本案例",
        "07 Scenarios",
    ),
    (
        "08",
        "08-运营手册.md",
        "08 · 运营手册",
        "08 · Operations handbook",
        "08 运营手册",
        "08 Operations",
    ),
    (
        "09",
        "09-运营指标与复盘.md",
        "09 · 运营指标与复盘",
        "09 · Operations metrics and retrospectives",
        "09 指标复盘",
        "09 Metrics",
    ),
    (
        "10",
        "10-变现路径与结营包.md",
        "10 · 变现路径与结营包",
        "10 · Monetisation paths and graduation kit",
        "10 变现结营",
        "10 Monetisation",
    ),
    (
        "11",
        "11-工具与环境准备.md",
        "11 · 工具与环境准备",
        "11 · Tools and environment setup",
        "11 工具环境",
        "11 Tooling",
    ),
    (
        "12",
        "12-附录-术语表与模板库.md",
        "12 · 附录：术语表与模板库",
        "12 · Appendix: glossary and template library",
        "12 附录",
        "12 Appendix",
    ),
    (
        "13",
        "13-GTM页面与竞品对比.md",
        "13 · GTM 页面与竞品对比",
        "13 · Go-to-market page and competitor comparison",
        "13 GTM 对比",
        "13 GTM",
    ),
    (
        "14",
        "14-课后纵深与影子项目.md",
        "14 · 课后纵深与影子项目",
        "14 · Post-course depth and shadow projects",
        "14 课后纵深",
        "14 Beyond class",
    ),
    (
        "15",
        "15-公信力与结果度量.md",
        "15 · 公信力与结果度量",
        "15 · Credibility and results measurement",
        "15 公信力",
        "15 Credibility",
    ),
    (
        "16",
        "16-D1逐节教案.md",
        "16 · D1 逐节教案：入门日",
        "16 · D1 lesson plan: orientation day",
        "16 D1 入门",
        "16 D1 Basics",
    ),
    (
        "17",
        "17-D2逐节教案.md",
        "17 · D2 逐节教案：定边界",
        "17 · D2 lesson plan: setting the boundary",
        "17 D2 定边界",
        "17 D2 Boundary",
    ),
    (
        "18",
        "18-D3逐节教案.md",
        "18 · D3 逐节教案：接数据（先看再装）",
        "18 · D3 lesson plan: data intake (look before you load)",
        "18 D3 接数据",
        "18 D3 Intake",
    ),
    (
        "19",
        "19-D4逐节教案.md",
        "19 · D4 逐节教案：造语料（把矿石炼成金属）",
        "19 · D4 lesson plan: corpus forging (ore into metal)",
        "19 D4 造语料",
        "19 D4 Forge",
    ),
    (
        "20",
        "20-D5逐节教案.md",
        "20 · D5 逐节教案：验证与评估（用证据说话）",
        "20 · D5 lesson plan: validation and evaluation (let the evidence speak)",
        "20 D5 评估",
        "20 D5 Eval",
    ),
    (
        "21",
        "21-D6逐节教案.md",
        "21 · D6 逐节教案：运维化（让东西稳得住）",
        "21 · D6 lesson plan: operationalising (make it hold)",
        "21 D6 运维",
        "21 D6 Ops",
    ),
    (
        "22",
        "22-D7逐节教案.md",
        "22 · D7 逐节教案：交接与沉淀（交得出去，带得走）",
        "22 · D7 lesson plan: handover and distillation (hand it over, carry it away)",
        "22 D7 交接",
        "22 D7 Handover",
    ),
    (
        "23",
        "23-D8逐节教案.md",
        "23 · D8 逐节教案：变现日（把 7 件产出换成职业资产）",
        "23 · D8 lesson plan: monetisation day (turn 7 artefacts into career assets)",
        "23 D8 变现",
        "23 D8 Monetise",
    ),
    (
        "24",
        "24-开源对标与来源清单.md",
        "24 · 开源对标与来源清单：GitHub 上的 FDE 教学内容，我们站在哪儿",
        "24 · Open-source benchmark and source list: where we stand among the FDE teaching repos",
        "24 开源对标",
        "24 Benchmark",
    ),
]

#: Repo-relative lesson file → chapter anchor key. Public because the docs
#: reader rewrites course citations into ``/course#doc-<key>`` deep links
#: without reaching into this module's private table.
COURSE_FILES: dict[str, str] = {f"{_COURSE_DIRNAME}/{name}": key for key, name, *_ in _CHAPTERS}

#: Rail grouping: (zh caption, en caption, chapter keys). Each group is a
#: contiguous run of ``_CHAPTERS`` order — the scroll spy walks the page top
#: to bottom, so interleaving two groups would make the rail's highlight
#: zigzag between blocks. Mirrors ``course-level-1/README.md`` §5.
_GROUPS: list[tuple[str, str, list[str]]] = [
    ("总览与底稿", "Overview & foundation", ["readme", "00"]),
    ("课程设计", "Course design", ["01", "02", "03"]),
    ("交付", "Delivery", ["04", "05", "06", "07"]),
    (
        "运营 · 变现 · 支撑",
        "Operations, monetisation & support",
        ["08", "09", "10", "11", "12", "13", "14", "15"],
    ),
    (
        "逐节教案（D1–D8）",
        "Lesson plans (D1–D8)",
        ["16", "17", "18", "19", "20", "21", "22", "23"],
    ),
    # 24 is a trailing 附卷: it is not a D-day lesson, so it does not join the
    # block above, but it still sits at the tail of _CHAPTERS order and therefore
    # stays a contiguous run.
    (
        "附卷 · 对标与来源",
        "Appendix · benchmark & sources",
        ["24"],
    ),
]

#: key → (zh rail label, en rail label); the rail renders through ``_GROUPS``.
_CHAPTER_RAIL: dict[str, tuple[str, str]] = {
    key: (rail_zh, rail_en) for key, _fn, _zh, _eng, rail_zh, rail_en in _CHAPTERS
}


def _rail_subnav(en: bool) -> tuple[str, ...]:
    """The chapter outline as ``side_nav`` entries.

    A bare ``str`` is a group caption and an ``(href, label)`` pair is a leaf,
    so one tuple carries the three-level tree the course page needs — the same
    ``_GROUPS``/``_CHAPTER_RAIL`` data that builds the body, never a second
    hand-copied list.
    """
    out: list[str | tuple[str, str]] = []
    for cap_zh, cap_en, keys in _GROUPS:
        out.append(cap_en if en else cap_zh)
        for key in keys:
            rail_zh, rail_en = _CHAPTER_RAIL[key]
            out.append((f"#doc-{key}", rail_en if en else rail_zh))
    return tuple(out)


_H1 = re.compile(r"^#\s+.*(?:\n|$)", re.M)
_TASK_ITEM = re.compile(r"^(\s*)- \[ \] ", re.M)
#: The capture group is load-bearing: ``re.split`` drops the separators
#: otherwise, which would silently delete every fenced block.
_PRE = re.compile(r"(<pre\b.*?</pre>)", re.S)


#: The shared Markdown plumbing (demoting renderer, fence walker, link
#: regexes, path normaliser) lives in :mod:`fde_scope.web.mdrender`; this
#: module keeps module-level aliases because the rest of the file predates it.
_MD = demoting_markdown()
_normalize = md_normalize


def _choose_root(repo_root: Path, packaged_root: Path) -> Path:
    """Prefer the repo checkout; fall back to the copy shipped in the wheel.

    ``repo_root`` wins whenever it exists so that editing a lesson in a
    checkout is what this page serves. ``packaged_root`` is what an installed
    app has. Returning ``repo_root`` when neither exists keeps the missing-dir
    notice pointing at the place a reader can actually fix.
    """
    if repo_root.is_dir():
        return repo_root
    if packaged_root.is_dir():
        return packaged_root
    return repo_root


def _default_root() -> Path:
    here = Path(__file__).resolve()
    return _choose_root(
        here.parents[2] / _COURSE_DIRNAME,
        here.parents[1] / "_data" / _COURSE_DIRNAME,
    )


#: every in-app target a lesson link can have. Chapter files become this
#: page's own ``#doc-`` anchors; the rest point at local pages. A path that
#: resolves to neither (``AGENTS.md``, tests/, …) strips to its label.
_COURSE_FILES = {f"{_COURSE_DIRNAME}/{name}": f"#doc-{key}" for key, name, *_ in _CHAPTERS}
_LOCAL_TARGETS = {
    "README.md": "/docs/readme",
    "docs/fde_sop_full.md": "/sop",
    "docs/fde-research.md": "/docs/fde-research",
    "docs/fde_playbook.md": "/docs/fde_playbook",
    "docs/features-en.md": "/docs/features-en",
    "examples/README.md": "/docs/examples",
    "course-level-1/en/README.md": "/docs/course-en",
}
_PAGE_ANCHORS = {f"doc-{key}" for key, *_ in _CHAPTERS}


def _resolve_course_href(href: str, base: str) -> str | None:
    """One lesson link → its in-app target, or ``None`` (the label is
    stripped). Lesson bodies render with ``base = _COURSE_DIRNAME``."""
    if href.startswith("#"):
        return href if href[1:] in _PAGE_ANCHORS else None
    if href.startswith("/"):
        return href
    if href.startswith(("http://", "https://", "mailto:")):
        return None
    path = unquote(_normalize(base, href.partition("#")[0]))
    return _COURSE_FILES.get(path) or _LOCAL_TARGETS.get(path)


def _preprocess_links(md_text: str) -> str:
    """Rewrite the lessons' links/images to their in-app form (or strip them
    to the bare label), outside code fences. Fences pass through
    byte-identical — the appendix template library is full of markdown-link
    examples that must not be touched."""
    base = _COURSE_DIRNAME

    def apply(text: str) -> str:
        def repl_image(m: re.Match[str]) -> str:
            target = _resolve_course_href(m.group(2).partition("#")[0], base)
            return f"![{m.group(1)}]({target})" if target else ""

        def repl_link(m: re.Match[str]) -> str:
            target = _resolve_course_href(m.group(2), base)
            return f"[{m.group(1)}]({target})" if target else m.group(1)

        text = _MD_IMAGE.sub(repl_image, text)
        text = _MD_LINK.sub(repl_link, text)
        return _AUTOLINK.sub(r"\1", text)

    return rewrite_outside_fences(md_text, apply)


def _prepare(md_text: str) -> str:
    """Markdown-level transforms shared by rendering and the token-stream
    stats: drop the lesson's own ``# `` heading, mark its task items, rewrite
    its links."""
    body = _H1.sub("", md_text, count=1)
    body = _TASK_ITEM.sub(r"\1- ☐ ", body)
    return _preprocess_links(body)


def _render_body(md_text: str) -> str:
    """One lesson rendered to HTML, with two post-steps: unchecked task items
    become real checkboxes (state lives in localStorage, zero backend), and
    ``<br>`` — the only in-cell line break a GFM table has — is restored
    outside code blocks."""
    html = _MD.render(_prepare(md_text))
    # `- ☐ ` task bullets become checkable list items; the box state is
    # keyed by (chapter, item index) in the page script
    html = html.replace(
        "<li>☐ ",
        '<li class="task"><input type="checkbox" class="taskbox" aria-label="practice"> ',
    )
    parts = _PRE.split(html)
    for i in range(0, len(parts), 2):
        parts[i] = parts[i].replace("&lt;br&gt;", "<br>").replace("&lt;br/&gt;", "<br>")
    return "".join(parts)


def _structured_stats(markdown_sources: list[str]) -> tuple[int, int, int]:
    """(sections, code samples, practice items) counted on the markdown token
    stream — literals inside fenced template examples can no longer inflate
    the numbers the way ``rendered.count("<h3")`` let them."""
    sections = code = tasks = 0
    for source in markdown_sources:
        for tok in _MD.parse(_prepare(source)):
            if tok.type == "heading_open" and tok.tag == "h3":
                sections += 1
            elif tok.type in ("fence", "code_block"):
                code += 1
            elif tok.type == "inline" and tok.content.startswith("☐ "):
                tasks += 1
    return sections, code, tasks


_STYLE = (
    BASE_CSS
    + PROSE_CSS
    + """
.course-note{display:flex;gap:var(--sp2);align-items:flex-start;
background:var(--layer-02);border:1px solid var(--border);border-radius:var(--r2);
padding:var(--sp3);margin:var(--sp3) 0 0;font-size:var(--fs-sm);color:var(--muted);
max-width:820px;line-height:1.7}
.course-note .ic{color:var(--accent);margin-top:2px}
.course-note strong{color:var(--fg)}
.stats{margin-top:var(--sp4)}
.chap{padding-top:var(--sp6)}
.crbar-row{display:flex;align-items:center;gap:var(--sp2);margin:var(--sp3) 0 0;max-width:860px}
/* a meter is a data mark: square ends, radius 0. Stadium caps on a 6px bar read
   as decoration, the same call made for the certification meters. */
.crbar{flex:1;height:6px;background:var(--layer-02);border:1px solid var(--border);
border-radius:var(--r0);overflow:hidden}
/* the one place a slower duration earns its keep: a fill sweeping 860px at
   110ms reads as a jump, not as progress. The curve stays the system's. */
.crbar>div{height:100%;width:0;background:var(--accent);transition:width 240ms var(--ease)}
.csearch{display:flex;gap:var(--sp2);align-items:center;margin:var(--sp2) 0 0;max-width:860px}
/* the field's own metrics live in the canonical ``input`` rule in ``THEME_CSS`` */
.csearch input{flex:1;min-width:0}
/* no pills: 999px on a 24px-tall toggle was the capsule the rest of the app
   already refused. On-state is a fill, matching every other selected thing. */
.readbtn{margin-left:auto;font:600 var(--fs-xs)/1.4 var(--font);color:var(--muted);
background:none;border:1px solid var(--border-strong);border-radius:var(--r1);
padding:var(--sp1) var(--sp2);cursor:pointer;transition:background-color var(--dur) var(--ease),
border-color var(--dur) var(--ease),color var(--dur) var(--ease)}
.readbtn:hover{color:var(--fg)}
.readbtn.on{color:var(--good);background:var(--good-fill);border-color:var(--good)}
.chap.read>.sec-head h2{color:var(--muted)}
li.task{list-style:none;margin-left:-1.2em}
li.task .taskbox{accent-color:var(--accent);margin-right:6px}
.src{font:500 var(--fs-xs)/1.7 var(--mono);color:var(--muted);margin:var(--sp2) 0 0;
overflow-wrap:anywhere}
@media(max-width:960px){.stats{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:640px){.stats{grid-template-columns:repeat(2,minmax(0,1fr))}}
"""
    + SHELL_CSS
)

_THEME_SCRIPT = """
function toggleTheme(){
  var h = document.documentElement;
  var n = h.dataset.theme === 'light' ? 'dark' : 'light';
  h.dataset.theme = n;
  try { localStorage.setItem('fde-theme', n); } catch(e) {}
}
// -- read progress / practice checkboxes / chapter filter (all client-side) --
function _store(k){ try { return JSON.parse(localStorage.getItem(k)||'{}'); } catch(e){ return {}; } }
function _save(k,v){ try { localStorage.setItem(k, JSON.stringify(v)); } catch(e){} }
function toggleRead(key){
  var m = _store('fde-course-read');
  if (m[key]) delete m[key]; else m[key] = true;
  _save('fde-course-read', m);
  refreshProgress();
}
function refreshProgress(){
  var m = _store('fde-course-read');
  var btns = document.querySelectorAll('.readbtn[data-ch]');
  var done = 0;
  btns.forEach(function(b){
    var on = !!m[b.dataset.ch];
    b.classList.toggle('on', on);
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
    b.textContent = on ? '✓ ' + b.dataset.done : b.dataset.todo;
    if (on) done++;
    var sec = document.getElementById('doc-' + b.dataset.ch);
    if (sec) sec.classList.toggle('read', on);
  });
  var bar = document.getElementById('cr-bar'), lab = document.getElementById('cr-lab');
  if (bar && btns.length) bar.style.width = Math.round(100*done/btns.length) + '%';
  if (lab) lab.textContent = done + ' / ' + btns.length;
}
document.addEventListener('change', function(e){
  if (!e.target.classList.contains('taskbox')) return;
  var li = e.target.closest('li.task');
  var sec = e.target.closest('section.chap');
  if (!li || !sec) return;
  var m = _store('fde-course-tasks');
  var k = sec.id + '::' + Array.prototype.indexOf.call(sec.querySelectorAll('li.task'), li);
  if (e.target.checked) m[k] = true; else delete m[k];
  _save('fde-course-tasks', m);
});
function restoreTasks(){
  var m = _store('fde-course-tasks');
  document.querySelectorAll('section.chap').forEach(function(sec){
    sec.querySelectorAll('li.task').forEach(function(li, i){
      var box = li.querySelector('.taskbox');
      if (box) box.checked = !!m[sec.id + '::' + i];
    });
  });
}
function courseFilter(q){
  q = q.trim().toLowerCase();
  var shown = 0, total = 0;
  document.querySelectorAll('section.chap').forEach(function(s){
    total++;
    var hit = !q || s.textContent.toLowerCase().indexOf(q) !== -1;
    s.hidden = !hit;
    if (hit) shown++;
  });
  var c = document.getElementById('cr-count'); if (c) c.textContent = q ? (shown + ' / ' + total) : '';
  var e = document.getElementById('cr-empty'); if (e) e.hidden = shown !== 0;
}
window.addEventListener('DOMContentLoaded', function(){ refreshProgress(); restoreTasks(); });
"""


def render(locale: str = "zh", root: Path | None = None) -> str:
    """The course as one long page. ``locale`` is ``"zh"`` or ``"en"``.

    ``root`` overrides the ``course-level-1/`` directory (tests use it to
    exercise the missing-directory and unreadable-file notices).
    """
    if locale not in ("zh", "en"):
        raise ValueError(f"unsupported locale: {locale!r}")
    en = locale == "en"

    def p(zh: str, eng: str) -> str:
        return eng if en else zh

    directory = root if root is not None else _default_root()
    bodies: list[tuple[tuple[str, str, str, str, str, str], str | None]] = []
    sources: list[str] = []
    for chapter in _CHAPTERS:
        filename = chapter[1]
        try:
            text = (directory / filename).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            bodies.append((chapter, None))
        else:
            sources.append(text)
            bodies.append((chapter, _render_body(text)))

    served = [(chapter, body) for chapter, body in bodies if body is not None]
    sections, code, tasks = _structured_stats(sources)
    stats = (
        (len(served), p("篇文档", "documents")),
        (sections, p("个小节", "sections")),
        (code, p("段代码", "code samples")),
        (tasks, p("项练习", "practice items")),
    )

    lang = "en" if en else "zh"
    other = "/course" if en else "/en/course"
    lang_label = "中文" if en else "EN"

    out: list[str] = []
    add = out.append
    add(
        f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{p("入门课程 · FDE Scope", "Intro course · FDE Scope")}</title>
<link rel="icon" href="/static/favicon.svg">
<script>(function(){{var t=null,q=null;try{{t=localStorage.getItem('fde-theme')}}catch(e){{}}try{{q=new URLSearchParams(location.search).get('theme')}}catch(e){{}}if(q==='dark'||q==='light'){{t=q}}else if(!t){{t='light'}}document.documentElement.dataset.theme=t}})();</script>
<style>{_STYLE}</style>
</head>
<body>
__ICON_SPRITE__
<div class="shell">
<aside class="side">
<div class="brand">
<div class="logo">FDE <span>Scope</span></div>
<span class="tag">{p("入门课程 · Level 1", "intro course · level 1")}</span>
</div>
<nav class="snav">
{side_nav("course", en=en, subnav=_rail_subnav(en))}
</nav>
<div class="side-foot">
<a class="lang" href="{other}">{lang_label}</a>
<button class="tbtn" onclick="toggleTheme()" aria-label="{
            p("切换深浅主题", "Toggle light/dark theme")
        }" title="{p("切换深浅主题", "Toggle light/dark theme")}">
<svg class="ic when-light" aria-hidden="true"><use href="#i-moon"/></svg>
<svg class="ic when-dark" aria-hidden="true"><use href="#i-sun"/></svg>
</button>
</div>
</aside>
<main class="main"><div class="wrap">
<div class="hero">
<p class="eyebrow">{p("入门课程 · Level 1 · 一天入门 · 七天变现", "Intro course · Level 1")}</p>
<h2>{
            p(
                "小白 FDE 炼金术：一天入门，七天变现",
                "Beginner FDE alchemy: one day to get started, seven days to monetise",
            )
        }</h2>
<p>{
            p(
                "把 4 个区、18 个阶段的完整交付链路，压缩成 8 天能亲手走完的一遍：第 1 天装上世界观与工具箱，"
                "第 2–8 天每天过一道门禁、交出一件拿得出手的产出。建议总投入约 22 小时"
                "（D1 全天 6 小时，D2–D8 每天约 2.25 小时），全程零 API key 可跑通。",
                "The whole four-zone, eighteen-phase delivery chain, compressed into eight days "
                "you walk yourself: day 1 installs the worldview and the toolbox; days 2–8 clear "
                "one gate a day and hand over one presentable artefact. Suggested effort is about "
                "22 hours (6 h on day 1, then about 2.25 h a day), and nothing on the path needs "
                "an API key.",
            )
        }</p>
</div>
<div class="course-note">
<svg class="ic" aria-hidden="true"><use href="#i-bulb"/></svg>
<p>{
            p(
                "<strong>「变现」指什么</strong>：把能力变成可展示、可检验、可对客交付的产出"
                "（作品集 + 话术 + 一条亲手跑通的链路）——<strong>不承诺就业、不承诺收入</strong>；"
                "所有客户案例均为虚构演示数据。",
                "<strong>What “monetise” means here</strong>: turning capability into presentable, "
                "checkable, customer-deliverable output (a portfolio, a script, and one chain you "
                "ran yourself) — <strong>not a promise of employment or income</strong>. Every "
                "customer case is fictional demo data.",
            )
        }</p>
</div>
<div class="course-note">
<svg class="ic" aria-hidden="true"><use href="#i-book"/></svg>
<p>{
            p(
                f"整门课就是这一页：{len(_CHAPTERS)} 篇文档按顺序排在下面，左侧章节栏随滚动高亮，每章末尾的"
                "文件名指向仓库里的源文件（<code>course-level-1/</code>）。",
                "These lessons are authored in Chinese and are served as authored; this page "
                "translates the chapter titles, the rail and the chrome, not the lesson text. "
                "Each chapter names its source file under <code>course-level-1/</code>.",
            )
        }</p>
</div>
<div class="crbar-row">
<div class="crbar" role="progressbar" aria-label="{
            p("阅读进度", "Reading progress")
        }"><div id="cr-bar"></div></div>
<span id="cr-lab" class="meta">0 / {len(_CHAPTERS)}</span>
</div>
<div class="csearch">
<input id="cr-q" type="search" aria-label="{p("搜索课程内容", "Search the course")}"
 placeholder="{
            p(f"在 {len(_CHAPTERS)} 篇课程文档中搜索…", f"Search across the {len(_CHAPTERS)} chapters…")
        }" oninput="courseFilter(this.value)">
<span id="cr-count" class="meta" aria-live="polite"></span>
</div>
<p id="cr-empty" class="course-note" hidden>{p("没有匹配的章节。", "No matching chapters.")}</p>
<div class="stats">"""
    )
    for num, label in stats:
        add(f'<div class="stat"><div class="num">{num}</div><div class="lab">{label}</div></div>')
    add("""</div>""")

    # -- 实验判分面板：学习页与执行引擎共用一个真相 -----------------------------
    # 芯片在这里服务端渲染（双语走 p()）；判分按钮的 JS 只调
    # /api/course/labs/{day}/grade，与 CLI `fde-scope course check` 同一 run_lab。
    chips: list[str] = []
    for lab in _LAB_REGISTRY:
        chips.append(
            f"""<div class="labchip">
<div class="labhead"><b>{lab.day}</b> <span class="tag">{lab.gate}</span> {p(lab.title, _LAB_TITLE_EN[lab.day])}</div>
<div class="labmeta">{p("产出：", "Deliverable: ")}{p(lab.deliverable, _LAB_DELIVERABLE_EN[lab.day])}
 · {p("判分项", "checks")} {len(lab.checks)}</div>
<button class="btn ghost" type="button" data-day="{lab.day}"
 onclick="labGrade(this.dataset.day)">{p("判分", "Grade")}</button>
</div>"""
        )
    add(
        f"""
<section class="chap lab-sec" id="lab-grading">
<style>
.labbar{{display:flex;gap:var(--sp2);align-items:center;margin:var(--sp2) 0;flex-wrap:wrap}}
/* no .labbtn rule: 判分 and 环境自检 are secondary actions, so they take the
   system's ``btn ghost`` pair rather than a fork with hex fallbacks that pinned
   light-mode borders and a stale #2563eb hover onto this block in dark mode. */
.lablist{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:var(--sp2);margin:var(--sp3) 0}}
.labchip{{border:1px solid var(--border);border-radius:var(--r2);padding:var(--sp2) var(--sp3);
 display:flex;flex-direction:column;gap:var(--sp2)}}
.labmeta{{color:var(--muted);font-size:var(--fs-xs)}}
.labres{{border:1px solid var(--border);border-radius:var(--r2);padding:var(--sp3);margin-top:var(--sp3)}}
.labres table{{width:100%;border-collapse:collapse;font-size:var(--fs-sm)}}
.labres td,.labres th{{text-align:left;padding:var(--sp1) var(--sp2);border-bottom:1px solid var(--border);
 vertical-align:top}}
.labsum{{font-weight:600;margin-bottom:var(--sp2)}}
</style>
<div class="sec-head">
<svg class="ic" aria-hidden="true"><use href="#i-bulb"/></svg>
<h2>{p("实验判分 · 在真实引擎里过关", "Lab grading · clear the gate on the real engine")}</h2>
<span class="n">LAB</span>
</div>
<p class="src">fde_scope/course/verifier.py · POST /api/course/labs/{{day}}/grade</p>
<div class="prose">
<p>{
            p(
                "每一天的「过关」不是自评：判分在一次性工作区里对<strong>真实 CLI</strong> 跑这一天门禁的全部"
                "检查——命令不存在、输出不对、报告缺字段都过不去；你的真实 engagement 永远不被触碰"
                "（判分用独立的 FDE_SCOPE_HOME）。人工评分项单独列出，不进分母。",
                "A day's gate is not self-assessed: grading runs every check for that day against the "
                "<strong>real CLI</strong> inside a throwaway workspace — a missing command, wrong output "
                "or an absent report field fails. Your real engagements are never touched (grading uses a "
                "private FDE_SCOPE_HOME). Manually-scored items are listed separately and never enter "
                "the denominator.",
            )
        }</p>
<div class="labbar">
<button class="btn ghost" type="button" onclick="labDoctor()">{p("G0 环境自检", "G0 environment check")}</button>
<span id="lab-doctor" class="meta" aria-live="polite"></span>
</div>
<div class="lablist">{"".join(chips)}</div>
<div id="lab-out" aria-live="polite"
 data-t-working="{p("判分中…（真实命令，可能要几秒）", "Grading… (real commands, may take seconds)")}"
 data-t-ok="{p("通过", "passed")}" data-t-fail="{p("未过", "failed")}"
 data-t-manual="{p("人工评分", "manual")}" data-t-scored="{p("机器项", "machine-checked")}"
 data-t-deny="{
            p(
                "需要 API token（本页是公开页，判分接口不是）：设置 FDE_SCOPE_API_TOKEN 后再试。",
                "This needs the API token (the page is public; the grading API is not): set FDE_SCOPE_API_TOKEN and retry.",
            )
        }"
 data-t-error="{p("判分失败", "Grading failed")}"></div>
</div>
</section>"""
    )

    for chapter, body in bodies:
        key, filename, zh_title, en_title, *_ = chapter
        number = "README" if key == "readme" else key
        add(
            f"""
<section class="chap" id="doc-{key}">
<div class="sec-head">
<svg class="ic" aria-hidden="true"><use href="#i-book"/></svg>
<h2>{en_title if en else zh_title}</h2>
<span class="n">{number}</span>
<button class="readbtn" type="button" data-ch="{key}" data-done="{p("已读", "read")}" data-todo="{p("标记已读", "mark read")}" onclick="toggleRead(this.dataset.ch)" aria-pressed="false">{p("标记已读", "mark read")}</button>
</div>
<p class="src">{_COURSE_DIRNAME}/{filename}</p>"""
        )
        if body is None:
            add(
                f"""<div class="course-note">
<svg class="ic" aria-hidden="true"><use href="#i-alert"/></svg>
<p>{
                    p(
                        f"这一章读不到：仓库里没有 <code>{_COURSE_DIRNAME}/{filename}</code>"
                        "（或是文件编码不是 UTF-8）。",
                        f"This chapter is unavailable: <code>{_COURSE_DIRNAME}/{filename}</code> "
                        "is missing from this checkout (or is not UTF-8).",
                    )
                }</p>
</div>
</section>"""
            )
            continue
        lang = ' lang="zh-Hans"' if en else ""  # the body is Chinese on both locales
        add(f'<div class="prose"{lang}>{body}</div>\n</section>')

    if not served:
        add(
            f"""
<div class="course-note">
<svg class="ic" aria-hidden="true"><use href="#i-alert"/></svg>
<p>{
                p(
                    "这台机器上读不到课程文件：仓库根目录和已安装的包数据里都没有 "
                    f"<code>{_COURSE_DIRNAME}/</code> 目录。课程全文是仓库里 "
                    f"<code>{_COURSE_DIRNAME}/</code> 下的 {len(_CHAPTERS)} 篇 Markdown；"
                    "克隆仓库后重启本页，或重新安装 fde-scope，即可在这里阅读。",
                    "The course files are not on this machine: there is no "
                    f"<code>{_COURSE_DIRNAME}/</code> directory at the repo root, and none in the "
                    f"installed package data. The lessons are {len(_CHAPTERS)} Markdown files in "
                    f"<code>{_COURSE_DIRNAME}/</code> in the repository; clone it and reopen this "
                    "page — or reinstall fde-scope — to read them here.",
                )
            }</p>
</div>"""
        )

    add(
        f"""
<footer>
<span>{p("FDE Scope · 入门课程 Level 1", "FDE Scope · Intro course, Level 1")}</span>
<span>{
            p(
                "课程正文为准，本页是它的阅读视图",
                "The Markdown lessons are authoritative; this page is their reading view",
            )
        }</span>
</footer>

</div>
</main>
</div>
<script>{_THEME_SCRIPT}</script>
<script>{SHELL_JS}</script>
{_LAB_JS}
</body>
</html>
"""
    )
    return "".join(out)
