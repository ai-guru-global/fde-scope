"""Guards for the portfolio registry — ``fde_scope.course.showcase`` and its two pages.

The registry's whole claim is that a graduate's portfolio is *re-derived from the
file on every call*, so the tests have to prove three things a mock would let
slide:

* **A pass is earned, not stored.** The shipped ``course-labs/D8/作品集索引.md``
  template must fail exactly the rules a student who has written nothing should
  fail (R1/R3/R4/R6/R9), and rewriting the file must change the verdict on the
  very next call. Same discipline as gate re-evaluation (AGENTS.md invariant 1).
* **Each rule can actually fail.** A rubric row that passes on every input is
  decoration, so the good fixture is mutated one rule at a time and each
  mutation flips exactly one rule.
* **Nothing of the document leaves the audit.** PII findings report a shape and
  a row, never the matched text (``11`` §6.1) — and the public ``/showcase`` page
  renders rules, not records.
* **The record is the enforcement point, not the wire model.** The three
  ``@field_validator``s sit on :class:`ShowcaseEntry`, so :class:`ShowcaseRegistration`
  only caps lengths and a refused request answers **400** (a ``ValidationError``
  is a ``ValueError``) instead of FastAPI's 422. That placement is what makes a
  ``entry.json`` written by an older build re-validated on load, which is why
  tests assert through :func:`register` — and why R7 re-derives the 编号 format
  at audit time instead of trusting the door.

The credential path is pinned too: the three endpoints answer 401 without a
token, 403 to a routable client when auth is off, and the token never appears in
a body. ``entry_id`` is generated server-side and cannot be set from a request
(AGENTS.md invariant 2), which is why :class:`ShowcaseRegistration` has no such
field at all.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from fde_scope import paths
from fde_scope.cli import app as cli_app
from fde_scope.course import showcase as sc
from fde_scope.web import showcase as web_showcase
from fde_scope.web.app import app

pytestmark = pytest.mark.filterwarnings("ignore")

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIPPED_TEMPLATE = REPO_ROOT / "course-labs" / "D8" / sc.DEFAULT_PORTFOLIO

TOKEN = "test-token-0123456789"
REMOTE_IP = "10.0.0.7"
API = "/api/showcase/entries"

ENTRY = {"alias": "茶客十一号", "cohort": "2026Q4", "level": "B", "cert_no": "L1-2026Q4-B-011"}

#: A 作品集索引 that satisfies every machine-decidable rule, built from the
#: lesson's own column order (``12``:856) so the row/column numbers the findings
#: quote are the ones a student sees in the file.
GOOD_INDEX = """# 作品集索引 · 茶客七号 · 第 2026Q4 期

> 全部产出基于**虚构**演示场景「茶语万象」茶饮连锁客服，示例数据一律标为示例。
> 结论口径：这条链路在当前数据下**能做**；扩到三个以上城市要先补语料。

## 索引（8 件，一行一件）

| # | 产出名 | 日期 | 证据链接（文件路径 / 命令 / 报告） | 一句话价值（客户视角） |
|---|---|---|---|---|
| 1 | 迷你链路证据包 | D1 | `out/d1/trace.jsonl` | 一次跑通 5 段链路，取证 12 个节点 |
| 2 | 客户委托单 | D2 | `out/d2/engagement.json` | 把 3 项口头要求写成可验收的 7 条 |
| 3 | 数据体检报告 | D3 | `out/d3/kpi --json` | 字段完整率 91%（380/415），缺字段 35 行定位到列 |
| 4 | 语料报告 + 客户话术 | D4 | `out/d4/corpus_report.json` | 415 条里 20 条真实话术，复用率 48%（样本 20） |
| 5 | 原型证据 + 评估结果 | D5 | `out/d5/eval_top3.html` | Top3 命中 3/5，两份失败样本留档 |
| 6 | SLO 卡 + Runbook | D6 | `out/d6/slo.md` | 值班 3 人可在 15 分钟内走完 6 步降级 |
| 7 | 交接包四件套 | D7 | `out/d7/handoff/README.md` | 4 件套 + 2 条退场条件，接手方回签 1 份 |
| 8 | 作品集三套包装 + 答辩 | D8 | `out/d8/portfolio.md` | 求职 / 汇报 / 接单 3 版各取 3–5 行 |

> 每个数字都能当场重跑；重跑不了的写「未跑」，不写结论。

## 门禁对照（用 slug）

| 工具门禁 slug | 本作品集里的证据 | 状态 |
|---|---|---|
| `success_criteria` | out/d2/engagement.json 第 7 条 | 过 |
| `slo` | out/d6/slo.md | 过 |
"""


def _statuses(result: sc.AuditResult) -> dict[str, str]:
    return {r.id: r.status for r in result.results}


def _detail(result: sc.AuditResult, rule_id: str) -> str:
    return next(r.detail for r in result.results if r.id == rule_id)


def _index(tmp_path: Path, text: str = GOOD_INDEX) -> Path:
    """Materialise a D8 draft under ``tmp_path`` and return its directory."""
    drafts = tmp_path / "drafts"
    drafts.mkdir(exist_ok=True)
    (drafts / sc.DEFAULT_PORTFOLIO).write_text(text, encoding="utf-8")
    return drafts


def _audit(tmp_path: Path, text: str = GOOD_INDEX, **fields: object) -> sc.AuditResult:
    entry = sc.ShowcaseEntry(**{**ENTRY, **fields})  # type: ignore[arg-type]
    return sc.audit_entry(entry, drafts=_index(tmp_path, text))


def _flip_only(tmp_path: Path, text: str, broken: str) -> set[str]:
    """The failing rule ids for ``text`` — which must be exactly ``{broken}``."""
    result = _audit(tmp_path, text)
    statuses = _statuses(result)
    assert statuses["M1"] == "manual", "M1 is a human call and never scores"
    failed = {rid for rid, st in statuses.items() if st == "fail"}
    assert failed == {broken}, f"expected only {broken} to fail, got {sorted(failed)}"
    return failed


def _replace(text: str, old: str, new: str) -> str:
    """One replacement, and a loud failure if the anchor is no longer there."""
    assert old in text, f"fixture drift: {old[:50]!r} is not in GOOD_INDEX"
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# 登记输入：一切在落盘之前
# ---------------------------------------------------------------------------


def test_registration_carries_no_entry_id_field() -> None:
    """Invariant 2: the record's key is not an input, so it cannot be a forgery."""
    assert "entry_id" not in sc.ShowcaseRegistration.model_fields
    assert "created_at" not in sc.ShowcaseRegistration.model_fields
    assert "version" not in sc.ShowcaseRegistration.model_fields


def test_register_generates_the_id_and_writes_one_entry(tmp_path: Path) -> None:
    store = sc.ShowcaseStore(tmp_path / "reg")
    entry = sc.register(sc.ShowcaseRegistration(**ENTRY), store)  # type: ignore[arg-type]
    assert re.fullmatch(r"sc-[0-9a-f]{8}", entry.entry_id)
    assert entry.version == 1
    assert entry.portfolio == sc.DEFAULT_PORTFOLIO  # omitted in the draft → the default file
    assert (tmp_path / "reg" / entry.entry_id / "entry.json").is_file()
    assert [e.entry_id for e in store.load_all()] == [entry.entry_id]
    # atomic_write_text renames its temp file; residue would mean a crash mid-write
    assert list((tmp_path / "reg" / entry.entry_id).iterdir()) == [
        tmp_path / "reg" / entry.entry_id / "entry.json"
    ]


def test_index_row_keeps_only_what_a_reviewer_needs_to_pick_a_row(tmp_path: Path) -> None:
    store = sc.ShowcaseStore(tmp_path / "reg")
    entry = sc.register(sc.ShowcaseRegistration(**ENTRY), store)  # type: ignore[arg-type]
    assert sc.listing(store) == [
        {
            "entry_id": entry.entry_id,
            "alias": entry.alias,
            "cohort": entry.cohort,
            "level": entry.level,
            "cert_no": entry.cert_no,
            "portfolio": entry.portfolio,
            "updated_at": entry.updated_at.isoformat(),
        }
    ]


def test_listing_does_not_repair_the_index(tmp_path: Path) -> None:
    """A ``GET`` must not write: ``index_entries`` rebuilds, :func:`listing` reads.

    The web layer calls :func:`listing` for exactly this reason — an
    unauthenticated-looking read path is still a token-gated write otherwise.
    """
    store = sc.ShowcaseStore(tmp_path / "reg")
    sc.register(sc.ShowcaseRegistration(**ENTRY), store)  # type: ignore[arg-type]
    (tmp_path / "reg" / "index.json").unlink()
    assert len(sc.listing(store)) == 1
    assert not (tmp_path / "reg" / "index.json").exists()


def test_portfolio_traversal_is_refused(tmp_path: Path) -> None:
    """The portfolio is one filename inside ``course-labs/D8/``, never a path.

    Checked on the *record*, not the wire model: ``register`` builds
    :class:`ShowcaseEntry` before it opens the store, so a request carrying a
    path can never reach disk — and a ``entry.json`` written by an older build
    is refused on the way back in.
    """
    store = sc.ShowcaseStore(tmp_path / "reg")
    for evil in ("../../etc/passwd", "作品集索引.md/../x.md", "a/b.md", "..", "/tmp/x.md"):
        with pytest.raises(ValidationError):
            sc.register(sc.ShowcaseRegistration(**{**ENTRY, "portfolio": evil}), store)  # type: ignore[arg-type]
    assert store.load_all() == []
    assert not (tmp_path / "reg").exists()


def test_bad_cert_no_is_refused_before_anything_is_written(tmp_path: Path) -> None:
    store = sc.ShowcaseStore(tmp_path / "reg")
    for bad in ("L1-2026Q4-B-7", "L1-20264-B-007", "L-2026Q4-D-007", "2026Q4-B-007", ""):
        with pytest.raises(ValidationError):
            sc.register(sc.ShowcaseRegistration(**{**ENTRY, "cert_no": bad}), store)  # type: ignore[arg-type]
    assert store.load_all() == []


def test_alias_carrying_contact_shapes_is_refused(tmp_path: Path) -> None:
    """``11`` §6.1: the public face carries a 代号 and nothing that reaches a person."""
    store = sc.ShowcaseStore(tmp_path / "reg")
    for bad in ("kefu@chayuwuxiang.example", "茶客13800138000", "工号 202601017"):
        with pytest.raises(ValidationError):
            sc.register(sc.ShowcaseRegistration(**{**ENTRY, "alias": bad}), store)  # type: ignore[arg-type]
    assert store.load_all() == []


def test_cohort_must_be_a_quarter() -> None:
    with pytest.raises(ValidationError):
        sc.ShowcaseRegistration(**{**ENTRY, "cohort": "2026-12"})  # type: ignore[arg-type]


def test_duplicate_cert_no_is_refused_as_one_number_one_person(tmp_path: Path) -> None:
    store = sc.ShowcaseStore(tmp_path / "reg")
    first = sc.register(sc.ShowcaseRegistration(**ENTRY), store)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="一人一号"):
        sc.register(sc.ShowcaseRegistration(**{**ENTRY, "alias": "茶客八号"}), store)  # type: ignore[arg-type]
    assert [e.entry_id for e in store.load_all()] == [first.entry_id]


def test_get_raises_keyerror_for_an_unknown_entry(tmp_path: Path) -> None:
    store = sc.ShowcaseStore(tmp_path / "reg")
    with pytest.raises(KeyError):
        sc.get("sc-deadbeef", store)


def test_a_corrupt_entry_is_skipped_not_fatal(tmp_path: Path) -> None:
    """One bad record must not take the whole registry listing down."""
    store = sc.ShowcaseStore(tmp_path / "reg")
    good = sc.register(sc.ShowcaseRegistration(**ENTRY), store)  # type: ignore[arg-type]
    wreck = tmp_path / "reg" / "sc-00000000"
    wreck.mkdir()
    (wreck / "entry.json").write_text("{not json", encoding="utf-8")
    assert [e.entry_id for e in store.load_all()] == [good.entry_id]
    assert store.load("sc-00000000") is None


def test_the_portfolio_file_is_never_copied_into_the_registry(tmp_path: Path) -> None:
    drafts = _index(tmp_path)
    store = sc.ShowcaseStore(tmp_path / "reg")
    entry = sc.register(sc.ShowcaseRegistration(**ENTRY), store)  # type: ignore[arg-type]
    audit = sc.audit_entry(entry, drafts=drafts)
    payload = json.dumps(audit.as_dict(), ensure_ascii=False)
    assert GOOD_INDEX[:60] not in payload
    assert "迷你链路证据包" not in payload  # the row's content, not just the head
    assert list((tmp_path / "reg" / entry.entry_id).iterdir()) == [
        tmp_path / "reg" / entry.entry_id / "entry.json"
    ]


def test_registry_lands_under_the_data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``FDE_SCOPE_HOME`` is the only knob, and ``audit`` reads it per call."""
    monkeypatch.setenv("FDE_SCOPE_HOME", str(tmp_path / "home"))
    root = paths.showcase_dir()
    assert root == tmp_path / "home" / paths.DATA_SUBDIR / "showcase"
    entry = sc.register(sc.ShowcaseRegistration(**ENTRY))  # type: ignore[arg-type]
    assert (root / entry.entry_id / "entry.json").is_file()
    # the same entry, audited after the data root moves, is simply not found
    monkeypatch.setenv("FDE_SCOPE_HOME", str(tmp_path / "other"))
    with pytest.raises(KeyError):
        sc.get(entry.entry_id)


# ---------------------------------------------------------------------------
# 审校：每次重算，每条规则都能失败
# ---------------------------------------------------------------------------


def test_good_fixture_passes_every_machine_rule(tmp_path: Path) -> None:
    result = _audit(tmp_path)
    statuses = _statuses(result)
    assert set(statuses) == {r.id for r in sc.RULES}
    assert len(statuses) == len(sc.RULES) == 11
    assert [rid for rid, st in statuses.items() if st == "fail"] == []
    assert statuses["M1"] == "manual"
    assert result.score == "10/10"
    assert result.ok is True
    body = result.as_dict()
    assert body["graded"] is False  # 判级是人的 blocker（03:75 ④）
    assert body["portfolio"] == f"course-labs/{sc.PORTFOLIO_DAY}/{sc.DEFAULT_PORTFOLIO}"
    assert not body["portfolio"].startswith("/")  # no home directory in the output（11 §6.2）


def test_shipped_template_fails_only_the_writing_rules() -> None:
    """The cold oracle for D8: on the untouched template, red means "write it".

    Recorded from the tool rather than asserted from wishful arithmetic — a
    contract failure here means the template and the rubric drifted apart.
    """
    entry = sc.ShowcaseEntry(**ENTRY)  # type: ignore[arg-type]
    result = sc.audit_entry(entry, drafts=SHIPPED_TEMPLATE.parent)
    statuses = _statuses(result)
    assert sorted(rid for rid, st in statuses.items() if st == "fail") == ["R1", "R3", "R4", "R6", "R9"]
    assert sorted(rid for rid, st in statuses.items() if st == "pass") == ["R10", "R2", "R5", "R7", "R8"]
    assert statuses["M1"] == "manual"
    assert result.score == "5/10" and result.ok is False
    # the index table is the 8-row one; the template's other three tables stay out
    assert _detail(result, "R2") == "索引表 8 行"


def test_missing_file_is_not_reported_as_clean(tmp_path: Path) -> None:
    """A file that cannot be read must not produce a pass anywhere it depends on it."""
    entry = sc.ShowcaseEntry(**ENTRY)  # type: ignore[arg-type]
    result = sc.audit_entry(entry, drafts=tmp_path / "nothing-here")
    statuses = _statuses(result)
    assert {rid for rid, st in statuses.items() if st == "pass"} == {"R7", "R10"}
    assert "不是「没有 PII」" in _detail(result, "R5")


def test_audit_rereads_the_file_on_every_call(tmp_path: Path) -> None:
    """No cache: the verdict is a property of the file as it is *now* (invariant 1)."""
    drafts = _index(tmp_path, GOOD_INDEX + "\n> TODO：等 D7 回签。\n")
    entry = sc.ShowcaseEntry(**ENTRY)  # type: ignore[arg-type]
    first = sc.audit_entry(entry, drafts=drafts)
    assert first.ok is False and "TODO" in _detail(first, "R1")
    (drafts / sc.DEFAULT_PORTFOLIO).write_text(GOOD_INDEX, encoding="utf-8")
    second = sc.audit_entry(entry, drafts=drafts)
    assert second.ok is True and second.score == "10/10"


def test_r1_respects_the_800_byte_floor(tmp_path: Path) -> None:
    """Same floor as G8's ArtifactCheck (``catalog.py:1284``) — a stub is not writing."""
    short = "\n".join(GOOD_INDEX.splitlines()[:2]) + "\n证据\n能做\n虚构\n"
    assert len(short.encode("utf-8")) < sc._MIN_BYTES
    assert "字节下限" in _detail(_audit(tmp_path, short), "R1")


@pytest.mark.parametrize(
    ("case", "rule"),
    [
        ("rows", "R2"),
        ("value", "R3"),
        ("link", "R4"),
        ("pii", "R5"),
        ("verdict", "R6"),
        ("ratio", "R8"),
        ("fiction", "R9"),
    ],
)
def test_each_rule_can_fail_on_its_own(tmp_path: Path, case: str, rule: str) -> None:
    """Flip one rule at a time; the other nine must stay green.

    A rubric row that never fails is decoration, and these seven are the ones a
    student can plausibly trip by editing the file.
    """
    text = {
        "rows": _replace(
            GOOD_INDEX,
            "| 8 | 作品集三套包装 + 答辩 | D8 | `out/d8/portfolio.md` | 求职 / 汇报 / 接单 3 版各取 3–5 行 |\n",
            "",
        ),
        "value": _replace(GOOD_INDEX, "Top3 命中 3/5，两份失败样本留档", "原型命中偏低，失败样本留档"),
        "link": _replace(GOOD_INDEX, "`out/d6/slo.md`", "<路径/链接>"),
        "pii": GOOD_INDEX + "\n> 回访对接：13800138000 / kefu@chayuwuxiang.example\n",
        "verdict": _replace(GOOD_INDEX, "**能做**", "**可跑**"),
        "ratio": GOOD_INDEX + "\n> 互助完课率 78%，比上一期高。\n",
        "fiction": _replace(GOOD_INDEX, "**虚构**", "**自拟**"),
    }[case]
    _flip_only(tmp_path, text, rule)


def test_r4_treats_a_bare_description_as_an_unlinked_row(tmp_path: Path) -> None:
    """``12``:858–865 ships ``<路径/链接>``; prose that merely names a file is not a pointer."""
    text = _replace(GOOD_INDEX, "`out/d7/handoff/README.md`", "见交接包")
    assert "不像路径/链接：第 7 行" in _detail(_audit(tmp_path, text), "R4")
    _flip_only(tmp_path, text, "R4")


def test_r8_spares_metrics_that_are_not_the_outward_five(tmp_path: Path) -> None:
    """The book's own sample row (``12``:862) has no denominator and must still pass."""
    text = GOOD_INDEX + "\n> 客服意图准确率 78% → 91%。\n"
    assert _statuses(_audit(tmp_path, text))["R8"] == "pass"


def test_r7_rechecks_a_record_written_by_an_older_build(tmp_path: Path) -> None:
    """Registration validates the format, and the audit re-derives it anyway.

    ``model_construct`` stands in for an ``entry.json` put on disk before the
    regex existed — R7 is the only rule that reads a stored field rather than
    the file, so it needs a second look, not a re-validation.
    """
    entry = sc.ShowcaseEntry.model_construct(**{**ENTRY, "cert_no": "L1-26Q4-B-07"})
    result = sc.audit_entry(entry, drafts=_index(tmp_path))
    assert _statuses(result)["R7"] == "fail"
    assert "L1-26Q4-B-07" in _detail(result, "R7")


def test_r10_catches_a_self_reported_level_that_is_not_in_the_number(tmp_path: Path) -> None:
    """``15``:45–46 makes 等级 a segment of 编号, so a mismatch is a claim about two things."""
    result = _audit(tmp_path, GOOD_INDEX, level="A")  # cert says B
    assert _statuses(result)["R10"] == "fail"
    assert "等级位是 B" in _detail(result, "R10")
    assert len(result.results) == len(sc.RULES)


def test_pii_finding_reports_a_shape_never_the_document(tmp_path: Path) -> None:
    """An audit result is pasted into a reply; the portfolio is where a leak lives."""
    result = _audit(tmp_path, GOOD_INDEX + "\n> 回访对接：13800138000 / kefu@chayuwuxiang.example\n")
    body = json.dumps(result.as_dict(), ensure_ascii=False)
    assert "13800138000" not in body
    assert "kefu@chayuwuxiang.example" not in body
    detail = _detail(result, "R5")
    assert "手机号" in detail and "邮箱" in detail
    assert "茶语万象" not in detail


def test_every_finding_carries_a_source_and_a_tier(tmp_path: Path) -> None:
    """``10``:292 数字无出处 is an anti-pattern; the tool holds itself to it."""
    tiers = {"工具实测", "代码原文", "项目约束原文", "教案原文", "OFFICIAL", "GAP"}
    for result_rule in _audit(tmp_path).results:
        assert result_rule.source, result_rule.id
        assert result_rule.confidence in tiers, result_rule.confidence
    gap_rules = [r.id for r in sc.RULES if r.confidence == "GAP"]
    assert gap_rules == ["R7"], "R7 is the admitted reading; anything else is drift"


def test_manual_rules_are_reported_but_never_scored() -> None:
    """M1 is the defence and the attendance: 25% + 15% of the book's weight, 0 of ours."""
    manual = [r for r in sc.RULES if r.manual]
    assert [r.id for r in manual] == ["M1"]
    assert "03:75" in manual[0].source
    result = sc.AuditResult(
        entry_id="sc-00000000",
        alias="a",
        cohort="2026Q4",
        level="B",
        cert_no="L1-2026Q4-B-007",
        portfolio="x.md",
        results=[sc.RuleResult("M1", "m", "manual", "ask", "src", "教案原文")],
    )
    assert result.score == "0/0"
    assert result.ok is False  # an all-manual audit scores nothing, so it never claims a pass
    assert result.as_dict()["graded"] is False


def test_rule_line_names_the_rule_and_its_tier(tmp_path: Path) -> None:
    line = _audit(tmp_path).results[0].line()
    assert line.startswith("✅ [R1] 索引页实存且已填完（代码原文）")
    assert "依据：fde_scope/course/catalog.py" in line
    assert _audit(tmp_path, GOOD_INDEX + "\n> TODO\n").results[0].line().startswith("❌")


# ---------------------------------------------------------------------------
# 公开页 /en/showcase 与三个 token 之后的端点
# ---------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FDE_SCOPE_API_TOKEN", raising=False)
    from fastapi.testclient import TestClient

    return TestClient(app)


@pytest.fixture
def authed_client(client, monkeypatch):
    monkeypatch.setenv("FDE_SCOPE_API_TOKEN", TOKEN)
    return client


@pytest.fixture
def remote_client(tmp_path, monkeypatch):
    """A client whose requests arrive on a routable address (AGENTS.md invariant 7)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FDE_SCOPE_API_TOKEN", raising=False)
    from fastapi.testclient import TestClient

    return TestClient(app, base_url=f"http://{REMOTE_IP}:8000")


def test_public_pages_answer_without_a_token(client) -> None:
    for path in ("/showcase", "/en/showcase"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert "作品集登记" in r.text or "Portfolio registry" in r.text


def test_pages_render_the_rubric_from_the_same_tuple_the_auditor_uses() -> None:
    """The page cannot advertise a rule the code does not enforce."""
    for locale in ("zh", "en"):
        html = web_showcase.render(locale)
        for rule in sc.RULES:
            assert f'<td class="id">{rule.id}</td>' in html, (locale, rule.id)
            assert rule.label in html, (locale, rule.id)
        # exactly three tables carry id cells: rubric + tiers + endpoints
        assert html.count('<td class="id">') == len(sc.RULES) + len(web_showcase._TIERS) + len(
            web_showcase._API_ROWS
        )
        assert "__ICON_SPRITE__" in html  # substituted by app.py, like every other page


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/showcase/entries"),
        ("GET", "/api/showcase/entries"),
        ("GET", "/api/showcase/entries/{entry_id}/audit"),
    ],
)
def test_every_documented_endpoint_really_exists(method: str, path: str) -> None:
    """A curl on this page that 404s is worse than no page."""
    rows = {(m, p) for m, p, _zh, _en in web_showcase._API_ROWS}
    assert (method, path) in rows
    served = {(m, r.path) for r in app.routes for m in getattr(r, "methods", ()) or ()}
    assert (method, path) in served


def test_api_requires_a_token_and_the_token_never_comes_back(authed_client) -> None:
    assert authed_client.get(API).status_code == 401
    assert authed_client.get(API, headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 200
    assert authed_client.get(API, headers={"X-API-Key": TOKEN}).status_code == 200
    assert authed_client.post(API, json=ENTRY, headers={"X-API-Key": TOKEN}).status_code == 200
    assert TOKEN not in authed_client.get(API, headers={"X-API-Key": TOKEN}).text
    for response in (
        authed_client.get(API, headers={"X-API-Key": TOKEN}),
        authed_client.get("/showcase"),
        authed_client.get("/en/showcase"),
    ):
        assert TOKEN not in response.text


def test_auth_off_is_loopback_only_for_the_api_but_not_the_pages(remote_client) -> None:
    """``11` §6.1's public page stays public; the registry data does not."""
    assert remote_client.get("/showcase").status_code == 200
    assert remote_client.get("/en/showcase").status_code == 200
    for response in (
        remote_client.get(API),
        remote_client.post(API, json=ENTRY),
        remote_client.get(f"{API}/sc-00000000/audit"),
    ):
        assert response.status_code == 403, response.text
        detail = response.json()["detail"]
        assert "FDE_SCOPE_API_TOKEN" in detail
        assert REMOTE_IP in detail
        assert "reverse proxy" in detail


def test_public_pages_show_rules_not_records(authed_client) -> None:
    """Registering must change the listing, and must not change either page."""
    registered = authed_client.post(API, json=ENTRY, headers={"X-API-Key": TOKEN})
    assert registered.status_code == 200
    entry_id = registered.json()["entry_id"]
    assert authed_client.get(API, headers={"X-API-Key": TOKEN}).json()[0]["entry_id"] == entry_id
    for path in ("/showcase", "/en/showcase"):
        page = authed_client.get(path).text
        assert ENTRY["alias"] not in page
        assert ENTRY["cert_no"] not in page
        assert entry_id not in page  # only the doc's literal example id appears


def test_register_endpoint_returns_a_server_generated_id(authed_client) -> None:
    """A body cannot choose the id its own record is stored under (invariant 2)."""
    r = authed_client.post(
        API,
        json={**ENTRY, "entry_id": "sc-ffffffff", "version": 99, "created_at": "2000-01-01T00:00:00+00:00"},
        headers={"X-API-Key": TOKEN},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["entry_id"] != "sc-ffffffff"
    assert body["version"] == 1
    assert not body["created_at"].startswith("2000")


def test_register_endpoint_rejects_a_traversal_with_400_and_writes_nothing(authed_client) -> None:
    """400, not 422: the wire model deliberately carries no rules.

    ``portfolio`` is only length-capped on :class:`ShowcaseRegistration`; the
    one-segment check lives on :class:`ShowcaseEntry`, because the record — not
    the request — is the enforcement point. A ``ValidationError`` is a
    ``ValueError``, so the endpoint's one handler covers both a bad payload and
    a key that tries to walk out of the store, and nothing is written either way.
    """
    r = authed_client.post(API, json={**ENTRY, "portfolio": "../../entry.json"}, headers={"X-API-Key": TOKEN})
    assert r.status_code == 400
    assert authed_client.get(API, headers={"X-API-Key": TOKEN}).json() == []


def test_register_endpoint_refuses_a_duplicate_number(authed_client) -> None:
    assert authed_client.post(API, json=ENTRY, headers={"X-API-Key": TOKEN}).status_code == 200
    again = authed_client.post(API, json={**ENTRY, "alias": "茶客八号"}, headers={"X-API-Key": TOKEN})
    assert again.status_code == 400
    assert "一人一号" in again.json()["detail"]


def test_audit_endpoint_recomputes_and_reports_the_denominator(authed_client) -> None:
    """The draft lives under the data root (``FDE_SCOPE_HOME``, isolated per test).

    Editing that file between two ``GET``s must change the second verdict — the
    endpoint stores no pass, so a stale 10/10 cannot speak for the next call.
    """
    drafts = paths.data_root() / "course-labs" / sc.PORTFOLIO_DAY
    drafts.mkdir(parents=True, exist_ok=True)
    (drafts / sc.DEFAULT_PORTFOLIO).write_text(GOOD_INDEX, encoding="utf-8")

    entry_id = authed_client.post(API, json=ENTRY, headers={"X-API-Key": TOKEN}).json()["entry_id"]
    r = authed_client.get(f"{API}/{entry_id}/audit", headers={"X-API-Key": TOKEN})
    assert r.status_code == 200
    body = r.json()
    assert body["score"] == "10/10" and body["ok"] is True and body["graded"] is False
    assert {row["id"] for row in body["rules"]} == {row.id for row in sc.RULES}
    assert all(row["source"] and row["confidence"] for row in body["rules"])

    (drafts / sc.DEFAULT_PORTFOLIO).write_text(_replace(GOOD_INDEX, "**能做**", "**可跑**"), encoding="utf-8")
    second = authed_client.get(f"{API}/{entry_id}/audit", headers={"X-API-Key": TOKEN}).json()
    assert second["ok"] is False and second["score"] == "9/10"


def test_audit_endpoint_404s_for_an_unknown_id(authed_client) -> None:
    r = authed_client.get(f"{API}/sc-deadbeef/audit", headers={"X-API-Key": TOKEN})
    assert r.status_code == 404
    assert r.json()["detail"] == "showcase entry not found"


def test_audit_path_cannot_escape_the_registry(authed_client) -> None:
    """Two layers refuse it, and each case says which one caught it.

    A literal ``..`` or extra segment never reaches the handler: Starlette
    normalises the path and the route stops matching, so the answer is the
    router's bare ``Not Found`` — not the registry's ``showcase entry not
    found``. One percent-encoded dot-dot *does* arrive as an ``entry_id``, and
    :func:`fsutil.safe_child` refuses it with 400 before it touches the store
    (AGENTS.md invariant 2: the key is server-generated, so a caller-supplied
    one is treated as hostile input). Either way no document content is echoed.
    """
    for evil in ("..", "../../etc", "a/b"):
        r = authed_client.get(f"{API}/{evil}/audit", headers={"X-API-Key": TOKEN})
        assert r.status_code == 404, (evil, r.status_code)
        assert r.json()["detail"] == "Not Found", evil
    encoded = authed_client.get(f"{API}/%2e%2e/audit", headers={"X-API-Key": TOKEN})
    assert encoded.status_code == 400
    assert "unsafe identifier" in encoded.json()["detail"]


def test_the_registry_stores_fields_not_the_document(authed_client) -> None:
    """The student's page stays in ``course-labs/``: a copy would double the PII surface.

    ``11`` §6.1's red line is about duplicates, not just publication — so the
    registry holds nine fields and no prose, even with a real 作品集索引 on disk.
    """
    drafts = paths.data_root() / "course-labs" / sc.PORTFOLIO_DAY
    drafts.mkdir(parents=True, exist_ok=True)
    (drafts / sc.DEFAULT_PORTFOLIO).write_text(GOOD_INDEX, encoding="utf-8")
    entry_id = authed_client.post(API, json=ENTRY, headers={"X-API-Key": TOKEN}).json()["entry_id"]

    root = paths.showcase_dir()
    assert sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()) == [
        "index.json",
        f"{entry_id}/entry.json",
    ]
    stored = json.loads((root / entry_id / "entry.json").read_text(encoding="utf-8"))
    assert set(stored) == {
        "entry_id",
        "alias",
        "cohort",
        "level",
        "cert_no",
        "portfolio",
        "version",
        "created_at",
        "updated_at",
    }
    assert stored["portfolio"] == sc.DEFAULT_PORTFOLIO  # a filename, never a body
    written = "".join(p.read_text(encoding="utf-8") for p in root.rglob("*.json"))
    for marker in ("迷你链路证据包", "字段完整率", "茶语万象"):
        assert marker not in written


def test_there_is_no_cli_command_for_the_registry() -> None:
    """The page says registration is HTTP-only; the lessons pin ``fde-scope`` at 18 commands."""
    result = CliRunner().invoke(cli_app, ["showcase", "--help"])
    assert result.exit_code == 2
    assert "No such command" in result.output
