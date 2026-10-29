"""``/showcase`` — the portfolio registry's public face: rules, not records.

The registry itself (``fde_scope/course/showcase.py``) stores one student's
codename, certificate number and portfolio filename, and re-audits that file on
every call. This page is the *explainer* beside it: what gets checked, where
each check comes from, how far we trust it, and how to reach the endpoints.

It renders no listings on purpose. A public route that read
:class:`~fde_scope.course.showcase.ShowcaseStore` would put a cohort's codenames
and certificate numbers on an unauthenticated page — the opposite of ``11`
§6.1's red line that the public face carries a 代号 and nothing else, and
unnecessary here: the reader of this page wants the rubric, not somebody's
entry. Listing and audit live on the three token-gated endpoints instead.

Rendered from paired literals like ``sop.py``, ``course.py``, ``glossary.py``
and ``certification.py`` — ``to_en`` is an exact-substring pass and one miss
would silently ship Chinese on ``/en/showcase``. The rubric table is a special
case: its rows are compiled from :data:`fde_scope.course.showcase.RULES`, the
same tuple the auditor evaluates, so the page cannot advertise a rule the code
does not enforce. That text is authored in Chinese (it cites Chinese-language
lessons) and is **served as authored on both locales**, like the SOP document;
the English page carries a notice saying so rather than a hand-translated table
that could drift from the rules it describes.

Every string injected into HTML goes through :func:`html.escape`: the sources
contain angle brackets (``<期次>-<等级>-<顺序号>``).
"""

from __future__ import annotations

from html import escape

from .. import paths
from ..course.showcase import (
    DEFAULT_PORTFOLIO,
    PORTFOLIO_DAY,
    RULES,
)
from .layout import BASE_CSS, PROSE_CSS, SHELL_CSS, SHELL_JS, side_nav

#: The page's ``<section id>`` outline as ``(anchor, label_zh, label_en)``, in
#: document order — same contract as ``certification.py``: the rail is compiled
#: from this list and ``tests/test_rail_guard.py`` asserts every anchor lands on
#: an ``id=`` in the rendered document.
_SECTIONS: tuple[tuple[str, str, str], ...] = (
    ("what", "这是什么，不是什么", "What this is and is not"),
    ("rules", "审校规则", "The rubric"),
    ("tiers", "可信度分级", "Credibility tiers"),
    ("api", "登记与审校接口", "Register and audit"),
    ("gaps", "已知缺口", "Known gaps"),
)

#: The six tiers used across this project's audit documents, strongest first.
#: ``(tier, visual class, zh gloss, en gloss)``. The rubric table looks a rule's
#: own ``confidence`` up here, so an unlisted tier fails loudly at render time
#: instead of quietly losing its colour.
_TIERS: tuple[tuple[str, str, str, str], ...] = (
    (
        "工具实测",
        "t-strong",
        "在这台机器上跑过，输出就在下面或终端里。",
        "Executed on this machine; the output is in the terminal or below.",
    ),
    (
        "代码原文",
        "t-strong",
        "规则就是代码里那段断言，路径与行号可一跳核对。",
        "The assertion is in the code, at the cited file and line.",
    ),
    (
        "项目约束原文",
        "t-strong",
        "仓库里写死的红线（AGENTS.md、11 §6），不是我们的偏好。",
        "A red line the repository states (AGENTS.md, lesson 11 §6), not our preference.",
    ),
    (
        "教案原文",
        "t-mid",
        "课程教案里能找到原句；标号是「第几课 : 第几行」。",
        "A sentence in the course book; the citation is lesson : line.",
    ),
    (
        "OFFICIAL",
        "t-mid",
        "外部官方页面可查（本页没有这类数字，列出来是为了分级完整）。",
        "A published vendor page (this page has none; listed so the scale is complete).",
    ),
    (
        "GAP",
        "t-gap",
        "教案没写全，这是我们的读法。宁可标注，不要填空。",
        "The book stops short; this is our reading. Marked rather than filled in.",
    ),
)

_TIER_CLASS = {tier: cls for tier, cls, _zh, _en in _TIERS}

#: The three endpoints this page documents, as ``(method, path, zh, en)``.
#: Kept next to :data:`_API_ROWS`' rendering so the table and the routes in
#: ``app.py`` stay one list; ``tests/test_showcase.py`` asserts each row here
#: really exists in the app's route table.
_API_ROWS: tuple[tuple[str, str, str, str], ...] = (
    (
        "POST",
        "/api/showcase/entries",
        "登记一条：代号、期次、等级、证书编号、作品集文件名。编号若已在本机登记过即拒绝。",
        "Register one entry: codename, cohort, level, certificate number, portfolio "
        "filename. A number already registered on this machine is refused.",
    ),
    (
        "GET",
        "/api/showcase/entries",
        "列出本机登记条目（代号 / 期次 / 等级 / 编号 / 文件名 / 更新时间）。绝不公开。",
        "List this machine's entries (codename, cohort, level, number, filename, updated). Never public.",
    ),
    (
        "GET",
        "/api/showcase/entries/{entry_id}/audit",
        "重算：重新读取 course-labs/D8/ 下的作品集索引，逐条给出判定与依据。结果不含文档正文。",
        "Recompute: re-read the portfolio index under course-labs/D8/ and report every "
        "verdict with its source. The document text never appears in the result.",
    ),
)


#: The command shapes the reader pastes. They are module constants rather than
#: inline HTML because :func:`render` builds the page from one f-string, and a
#: JSON body's braces would be read as replacement fields — the curl below would
#: silently print a Python dict repr instead of the payload.
_CURL_REGISTER = """curl -X POST http://127.0.0.1:8000/api/showcase/entries \\
  -H "X-API-Key: $FDE_SCOPE_API_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"alias":"茶客七号","cohort":"2026Q4","level":"B","cert_no":"L1-2026Q4-B-007"}'

curl http://127.0.0.1:8000/api/showcase/entries \\
  -H "Authorization: Bearer $FDE_SCOPE_API_TOKEN\""""

_CURL_AUDIT = """curl http://127.0.0.1:8000/api/showcase/entries/sc-1a2b3c4d/audit \\
  -H "X-API-Key: $FDE_SCOPE_API_TOKEN\""""


def _rail_subnav(en: bool) -> tuple[tuple[str, str], ...]:
    return tuple((f"#{anchor}", en_label if en else zh_label) for anchor, zh_label, en_label in _SECTIONS)


_STYLE = (
    BASE_CSS
    + PROSE_CSS
    + """
/* the source line is provenance, not decoration: it carries a file path, so it
   gets ``--muted`` (6.3:1 and up) rather than ``--faint``, which falls under AA
   at 12px. Same rule as ``sop.py``. */
.src{font:500 var(--fs-xs)/1.7 var(--mono);color:var(--muted);margin:var(--sp2) 0 0;
overflow-wrap:anywhere}
/* tier is a label, not a capsule: hairline boundary, 2px corner, mono 12px.
   Three visual weights for six tiers — strongest evidence, documented claim,
   admitted gap. A 999px pill would read as decoration at 12px. */
.tier{display:inline-flex;align-items:center;font:600 var(--fs-xs)/1.7 var(--mono);
letter-spacing:var(--track-label);padding:1px 8px;border-radius:var(--r1);
border:1px solid var(--border-strong);text-transform:uppercase;white-space:nowrap}
.t-strong{color:var(--good);border-color:color-mix(in oklab,var(--good) 42%,var(--border))}
.t-mid{color:var(--accent-text);border-color:color-mix(in oklab,var(--accent) 42%,var(--border))}
.t-gap{color:var(--bad);border-color:color-mix(in oklab,var(--bad) 42%,var(--border))}
.tblwrap{overflow-x:auto;border:1px solid var(--border);border-radius:var(--r2);background:var(--panel)}
table.tbl{width:100%;border-collapse:collapse;font-size:var(--fs-sm)}
table.tbl th,table.tbl td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);vertical-align:top}
table.tbl tr:last-child td{border-bottom:0}
table.tbl th{font:600 var(--fs-xs)/1.5 var(--mono);letter-spacing:var(--track-label);
text-transform:uppercase;color:var(--muted);white-space:nowrap}
table.tbl td.id{font:700 var(--fs-sm) var(--mono);color:var(--fg);white-space:nowrap}
table.tbl td .cite{font:var(--fs-xs)/1.6 var(--mono);color:var(--muted);overflow-wrap:anywhere}
table.tbl td b{color:var(--fg)}
/* code blocks here are command shapes the reader pastes, so they keep the
   token ramp: --layer-02 ground, hairline border, --r2, mono at --fs-sm. */
pre.code{margin:var(--sp2) 0 0;padding:12px 14px;background:var(--layer-02);
border:1px solid var(--border);border-radius:var(--r2);overflow-x:auto;
font:500 var(--fs-sm)/1.7 var(--mono);color:var(--fg)}
pre.code + pre.code{margin-top:var(--sp2)}
.note{display:flex;gap:var(--sp2);align-items:flex-start;background:var(--layer-02);
border:1px solid var(--border);border-radius:var(--r2);padding:var(--sp3);
margin:var(--sp3) 0 0;font-size:var(--fs-sm);color:var(--muted);max-width:860px;line-height:1.7}
.note .ic{color:var(--accent);margin-top:2px}
.note strong{color:var(--fg)}
.prose{padding-top:var(--sp4)}
@media(max-width:640px){.stats{grid-template-columns:repeat(2,minmax(0,1fr))}.hero{padding:6px 0 24px}}
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
"""


def _rule_rows(en: bool) -> str:
    """The rubric, compiled from :data:`RULES` — one row per rule, in order."""
    head = ("Rule", "Check", "What must hold", "Source") if en else ("编号", "规则", "判定口径", "依据")
    body = []
    for r in RULES:
        cls = _TIER_CLASS.get(r.confidence)
        if cls is None:  # a tier added in the domain module without a legend row
            raise ValueError(f"unmapped confidence tier: {r.confidence!r} (rule {r.id})")
        manual = " · " + ("human judgement" if en else " · 由人判") if r.manual else ""
        body.append(
            "<tr>"
            f'<td class="id">{escape(r.id)}</td>'
            f"<td><b>{escape(r.label)}</b>{manual}</td>"
            f"<td>{escape(r.ask)}</td>"
            f'<td><span class="cite">{escape(r.source)}</span><br><span class="tier {cls}">'
            f"{escape(r.confidence)}</span></td>"
            "</tr>"
        )
    return (
        '<div class="tblwrap"><table class="tbl"><thead><tr>'
        + "".join(f"<th>{escape(h)}</th>" for h in head)
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></div>"
    )


def _tier_rows(en: bool) -> str:
    head = ("Tier", "What it means") if en else ("等级", "含义")
    rows = "".join(
        f'<tr><td class="id"><span class="tier {cls}">{escape(tier)}</span></td>'
        f"<td>{escape(en_gloss if en else zh_gloss)}</td></tr>"
        for tier, cls, zh_gloss, en_gloss in _TIERS
    )
    return (
        '<div class="tblwrap"><table class="tbl"><thead><tr>'
        + "".join(f"<th>{escape(h)}</th>" for h in head)
        + "</tr></thead><tbody>"
        + rows
        + "</tbody></table></div>"
    )


def _api_rows(en: bool) -> str:
    head = ("Method", "Path", "What it does") if en else ("方法", "路径", "作用")
    rows = "".join(
        f'<tr><td class="id">{escape(method)}</td>'
        f'<td><span class="cite">{escape(path)}</span></td>'
        f"<td>{escape(en_text if en else zh_text)}</td></tr>"
        for method, path, zh_text, en_text in _API_ROWS
    )
    return (
        '<div class="tblwrap"><table class="tbl"><thead><tr>'
        + "".join(f"<th>{escape(h)}</th>" for h in head)
        + "</tr></thead><tbody>"
        + rows
        + "</tbody></table></div>"
    )


def render(locale: str = "zh") -> str:
    """Build the portfolio-registry page. ``locale`` is ``"zh"`` or ``"en"``.

    Returns HTML with ``__ICON_SPRITE__`` still in place: the sprite lives in
    ``app.py`` (shared with every other page) and is substituted there, exactly
    like ``_OVERVIEW_HTML``. Nothing here reads the store, so the output is a
    constant of the package — no data root, no filesystem, no PII.
    """
    if locale not in ("zh", "en"):
        raise ValueError(f"unsupported locale: {locale!r}")
    en = locale == "en"

    def p(zh: str, eng: str) -> str:
        return eng if en else zh

    lang = "en" if en else "zh"
    other = "/showcase" if en else "/en/showcase"
    n_manual = sum(1 for r in RULES if r.manual)
    n_auto = len(RULES) - n_manual
    registry = f"{paths.DATA_SUBDIR}/showcase"
    draft = f"course-labs/{PORTFOLIO_DAY}/{DEFAULT_PORTFOLIO}"

    out: list[str] = []
    add = out.append
    add(
        f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{p("FDE Scope · 作品集登记", "FDE Scope · Portfolio registry")}</title>
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
    <span class="tag">{p("作品集 · 登记与审校", "portfolio · register and audit")}</span>
  </div>
  <nav class="snav">
{side_nav("showcase", en=en, subnav=_rail_subnav(en))}
  </nav>
  <div class="side-foot">
    <a class="lang" href="{other}" title="{p("切换到中文", "Switch to Chinese")}">{
            p("切换到中文", "中文")
        }</a>
    <button class="tbtn" onclick="toggleTheme()" title="{p("切换深浅主题", "Toggle theme")}" aria-label="{
            p("切换深浅主题", "Toggle theme")
        }">
      <svg class="ic when-dark"><use href="#i-sun"/></svg>
      <svg class="ic when-light"><use href="#i-moon"/></svg>
    </button>
  </div>
</aside>

<main class="main">
<div class="wrap">

<div class="hero">
  <div class="eyebrow">{p("Portfolio · registry & rubric", "Portfolio · registry & rubric")}</div>
  <h2>{p("作品集登记与审校规则", "Portfolio registration and its rubric")}</h2>
  <p>{
            p(
                f"D8 交出的那份 <code>{escape(DEFAULT_PORTFOLIO)}</code> 是 G8 的第二道 blocker（03:75）。"
                f"这一页说明工具拿到它之后<em>怎么判</em>：{len(RULES)} 条规则，每条都带教案出处与可信度等级，"
                "并且每次审校都重新读盘重算 —— 一次通过的记录不会替下一次说话。",
                f"The <code>{escape(DEFAULT_PORTFOLIO)}</code> handed in on day 8 is G8's second blocker "
                f"(03:75). This page is how the tool judges it: {len(RULES)} rules, each with its citation "
                "and a credibility tier, re-evaluated against the file on every audit — a pass once never "
                "speaks for the next run.",
            )
        }</p>
  <div class="cta">
    <a class="btn" href="#rules">{p("看审校规则", "Read the rubric")}</a>
    <a class="btn ghost" href="#tiers"><svg class="ic"><use href="#i-shield"/></svg>{
            p("可信度分级", "Credibility tiers")
        }</a>
    <a class="btn ghost" href="#api"><svg class="ic"><use href="#i-plug"/></svg>{
            p("登记接口", "The endpoints")
        }</a>
  </div>
</div>

<div class="stats">
  <div class="stat"><div class="num">{len(RULES)}</div><div class="lab">{
            p("条审校规则", "rubric rules")
        }</div></div>
  <div class="stat"><div class="num">{n_auto}</div><div class="lab">{
            p("条每次重算", "recomputed on every audit")
        }</div></div>
  <div class="stat"><div class="num">{n_manual}</div><div class="lab">{
            p("条只由人判（答辩与出勤）", "judged by people only (defence, attendance)")
        }</div></div>
  <div class="stat"><div class="num">0</div><div class="lab">{
            p("份作品集副本入库", "copies of the portfolio stored")
        }</div></div>
</div>

<section id="what">
<div class="sec-head"><svg class="ic"><use href="#i-compass"/></svg><h2>{
            p("这是什么，不是什么", "What this is and is not")
        }</h2><span class="n">01</span></div>
<p class="sec-note">{
            p(
                "课程对「是什么」很苛刻，所以这页先划边界：登记与重算在范围内；核验与判级不在。",
                "The course is strict about what a tool may claim, so the boundary comes first: "
                "registration and recomputation are in scope; verification and grading are not.",
            )
        }</p>
<div class="grid cols-3">
  <div class="tile">
    <svg class="ic"><use href="#i-folder"/></svg>
    <div class="name">{p("登记通道", "A registry")}</div>
    <div class="desc">{
            p(
                f"一条记录只有五个字段：代号、期次、等级、证书编号、作品集文件名。文件<em>不</em>复制进登记表 —— "
                f"它留在 <code>{escape(draft)}</code>，每次审校现读。存放位置是数据根下的 <code>{escape(registry)}/</code>。",
                f"An entry is five fields: codename, cohort, level, certificate number, portfolio filename. "
                f"The file is <em>not</em> copied into the registry — it stays at <code>{escape(draft)}</code> "
                f"and is re-read on every audit. Records live in <code>{escape(registry)}/</code> under the data root.",
            )
        }</div>
    <span class="src">{p("依据：11 §6.1–6.2、12 §2.14", "Source: 11 §6.1–6.2, 12 §2.14")}</span>
  </div>
  <div class="tile">
    <svg class="ic"><use href="#i-x"/></svg>
    <div class="name">{
            p("不是在线证书核验页", "Not a certificate verifier")
        } <span class="tier t-gap">GAP</span></div>
    <div class="desc">{
            p(
                "15:230 把「在线证书核验页」记为未建，15:48 把核验定义为 3 个工作日内的人工回复。"
                "这里没有对发证方核验的任何一步；编号格式（R7）也只是从 15:45 那一个示例里读出来的写法。",
                "15:230 records the online certificate-verification page as not built, and 15:48 makes "
                "verification a human reply within three business days. Nothing here checks a number against "
                "an issuer; even the number format (R7) is our reading of the single example in 15:45.",
            )
        }</div>
    <span class="src">{p("依据：15:45、15:48、15:230", "Source: 15:45, 15:48, 15:230")}</span>
  </div>
  <div class="tile">
    <svg class="ic"><use href="#i-ban"/></svg>
    <div class="name">{p("不评等级", "Not a grade")}</div>
    <div class="desc">{
            p(
                "答辩占 25%、互助出勤占 15%（03 §2），两者与 A/B/C 判级都是人的 blocker（03:75 ③④）。"
                "23 附 C.2 还记录了一个缺口：教案的 A/B/C 措辞存在任何等级都不满足的组合。"
                "所以审校输出永远是「n/m + 逐条判定」，接口里 <code>graded</code> 恒为 <code>false</code>。",
                "The defence is 25% and peer attendance 15% (03 §2); both, and the A/B/C decision itself, "
                "are human blockers (03:75 ③④). 23 appendix C.2 records that the book's A/B/C wording leaves "
                "combinations no grade covers. So an audit prints n/m plus per-rule verdicts and the API's "
                "<code>graded</code> field is always <code>false</code>.",
            )
        }</div>
    <span class="src">{p("依据：03:47–55、03:75 ③④、23 附 C.2", "Source: 03:47–55, 03:75 ③④, 23 C.2")}</span>
  </div>
</div>
</section>

<section id="rules">
<div class="sec-head"><svg class="ic"><use href="#i-check-badge"/></svg><h2>{
            p(f"审校规则 · {len(RULES)} 条", f"The rubric · {len(RULES)} rules")
        }</h2><span class="n">02</span></div>
<p class="sec-note">{
            p(
                f"下表由 <code>fde_scope/course/showcase.py</code> 里的 <code>RULES</code> 直接生成 —— "
                "审校用的就是同一份元组，所以这一页不可能宣传一条代码里没有的规则。"
                f"前 {n_auto} 条是机器判定，M1 明写交人。判定口径里的「行 / 列」指作品集索引那张表。",
                f"This table is compiled from <code>RULES</code> in "
                f"<code>fde_scope/course/showcase.py</code> — the audit evaluates the same tuple, so this page "
                "cannot advertise a rule the code does not enforce. The first "
                f"{n_auto} rows are machine-decided; M1 is explicitly a human call. “Row” and “column” below "
                "refer to the portfolio index table itself.",
            )
        }</p>
{_rule_rows(en)}
<p class="src">{
            p(
                "一条判定的机器形态：<code>✅/❌/📝 [R1] 规则名（可信度）</code> + 具体发现 + 依据行。"
                "发现只写<em>形态与行号</em>，永远不回显文档正文 —— 审校结果是会被贴进回复里的东西，"
                "而正文是可能混进手机号的地方（11 §6.1）。",
                "A verdict renders as <code>✅/❌/📝 [R1] rule (tier)</code> plus the finding plus the cited line. "
                "A finding names a <em>shape and a row</em> and never echoes document text: an audit result is "
                "something a reviewer pastes into a reply, and the body is where a leaked phone number would be "
                "(11 §6.1).",
            )
        }</p>
</section>

<section id="tiers">
<div class="sec-head"><svg class="ic"><use href="#i-shield"/></svg><h2>{
            p("可信度分级", "Credibility tiers")
        }</h2><span class="n">03</span></div>
<p class="sec-note">{
            p(
                "本项目所有审计类文档共用这六档，从强到弱。规则表里每条右侧的徽章就是它的档位 —— "
                "GAP 不是缺陷，是把「教案没写死」这件事写在脸上。R7 是本页唯一的 GAP：",
                "Six tiers, shared by every audit document in this project, strongest first. The badge at the "
                "right of each rubric row is that rule's tier — a GAP is not a defect, it is stating that the "
                "book stops short. R7 is this page's only GAP:",
            )
        } <code>&lt;期次&gt;-&lt;等级&gt;-&lt;顺序号&gt;</code>{
            p(
                " 只给了一个示例 L1-2026Q4-B-007，从没说期次几位。",
                " — one example, L1-2026Q4-B-007, and never a length for the cohort part.",
            )
        }</p>
{_tier_rows(en)}
<div class="note">
<svg class="ic"><use href="#i-bulb"/></svg>
<p>{
            p(
                "<strong>为什么不给每条都凑一个来源。</strong>10:292 把「数字无出处」列为反模式，15 §3.3 要求"
                "对外指标永远带分母与样本量。同一把尺子量自己的文档：查不到的就标 GAP，而不是编一条看起来像 "
                "教案的句子。本页因此没有第二个数字来源 —— 规则数、机判数、端点数都从代码里读。",
                "<strong>Why not attach a source to everything.</strong> 10:292 lists “numbers without "
                "provenance” as an anti-pattern and 15 §3.3 requires every outward metric to carry its "
                "denominator. The same rule applies to this page's own claims: an unfindable one is marked GAP "
                "rather than invented. That is why no figure here is typed by hand either — the rule count, the "
                "machine-decided count and the endpoint list are all read from the code.",
            )
        }</p>
</div>
</section>

<section id="api">
<div class="sec-head"><svg class="ic"><use href="#i-plug"/></svg><h2>{
            p("登记与审校接口", "Register and audit")
        }</h2><span class="n">04</span></div>
<p class="sec-note">{
            p(
                "三个端点都在 token 之后：本页是公开的，清单与判定不是（11 §6.1）。"
                "令牌只从环境变量 <code>FDE_SCOPE_API_TOKEN</code> 读，绝不进文件、日志或响应。"
                "没有 Bearer / X-API-Key 时它们返回 401；未设令牌时只对回环开放，"
                "从可路由地址到达的请求返回 403。",
                "All three sit behind a token: this page is public, the listings and verdicts are not "
                "(11 §6.1). The token is read from <code>FDE_SCOPE_API_TOKEN</code> only — never into a file, a "
                "log or a response. Without <code>Authorization: Bearer</code> or <code>X-API-Key</code> they "
                "answer 401; with no token configured they answer only over loopback, and a request arriving on "
                "a routable address gets 403.",
            )
        }</p>
{_api_rows(en)}
<pre class="code">{escape(_CURL_REGISTER)}</pre>
<pre class="code">{escape(_CURL_AUDIT)}</pre>
<div class="note">
<svg class="ic"><use href="#i-alert"/></svg>
<p>{
            p(
                "<strong>没有对应的 CLI 命令。</strong>课程把 <code>fde-scope</code> 的命令数钉在 18 条"
                "（01 课程设计说明书、12 附录），教案里的每条命令都要能跑通，所以登记通道只走 HTTP；"
                "这条边界是刻意的，不是遗漏。审校逻辑想读的话，<code>fde_scope.course.showcase</code> "
                "是可导入的 Python 模块。",
                "<strong>There is no CLI command for this.</strong> The course pins <code>fde-scope</code> at 18 "
                "commands (lesson 01's design note, lesson 12's appendix), and every command the lessons print "
                "has to run, so registration is HTTP-only. That boundary is deliberate, not a gap — the audit "
                "logic is an importable Python module, <code>fde_scope.course.showcase</code>.",
            )
        }</p>
</div>
</section>

<section id="gaps">
<div class="sec-head"><svg class="ic"><use href="#i-map"/></svg><h2>{
            p("已知缺口", "Known gaps")
        }</h2><span class="n">05</span></div>
<p class="sec-note">{
            p(
                "缺口列出来是为了不被当成已完成。每一条都指向教案里记着它的地方。",
                "The gaps are printed so nobody reads them as done. Each points at the line that records it.",
            )
        }</p>
<ul class="note-list">
  <li>{
            p(
                "<b>在线证书核验页未建</b> —— 15:230。本页与它无关；核验仍是 15:48 的人工回复。",
                "<b>The online verification page is not built</b> — 15:230. Nothing here replaces it; "
                "verification stays the human reply of 15:48.",
            )
        }</li>
  <li>{
            p(
                "<b>判级口径有洞</b> —— 23 附 C.2：A/B/C 的措辞存在谁都不满足的组合。在补齐之前，工具不出等级。",
                "<b>The grading rubric has a hole</b> — 23 appendix C.2: the A/B/C wording leaves combinations no "
                "grade covers. Until that is settled, the tool emits no grade.",
            )
        }</li>
  <li>{
            p(
                "<b>登记是本机的</b> —— 数据根按机器解析，所以「一人一号」（15:46）只在同一台机器上核对；"
                "跨机重复查不出来。",
                "<b>The registry is per machine</b> — the data root resolves locally, so “one number, one "
                "person” (15:46) is only checked on this machine; a duplicate elsewhere is invisible.",
            )
        }</li>
  <li>{
            p(
                "<b>PII 只认 4 种形态</b> —— 手机号 / 邮箱 / 身份证 / 卡号。地址、车牌、订单号、序列号不猜形状"
                "（11:352）：一个假的「干净」比一条需要人看的行更糟。",
                "<b>Four PII shapes only</b> — phone, email, national ID, card. Addresses, plates, order and "
                "serial numbers are not guessed (11:352): a false “clean” is worse than a row a human must look at.",
            )
        }</li>
  <li>{
            p(
                "<b>审校不读作品本体</b> —— 它判的是索引那张表写了什么；每一行声称的效果数字，仍然要人回原始工件核对。",
                "<b>The audit reads the index, not the artefacts</b> — it judges what the index table claims; "
                "each row's number still has to be traced back to the artefact by a person.",
            )
        }</li>
</ul>
<p class="src">{
            p(
                "本页规则源文件：fde_scope/web/showcase.py · 审校实现：fde_scope/course/showcase.py",
                "Page source: fde_scope/web/showcase.py · audit implementation: fde_scope/course/showcase.py",
            )
        }</p>
</section>

<footer>
<span>{p("FDE Scope · 作品集登记", "FDE Scope · Portfolio registry")}</span>
<span>{
            p(
                "这一页只说明规则；清单与判定都要 token",
                "This page explains the rules; listings and verdicts need a token",
            )
        }</span>
</footer>

</div>
</main>
</div>
<script>{_THEME_SCRIPT}</script>
<script>{SHELL_JS}</script>
</body>
</html>
"""
    )
    return "".join(out)
