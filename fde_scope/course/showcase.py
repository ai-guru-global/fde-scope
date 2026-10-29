"""The portfolio registry: a graduate's claims, recomputed from the file.

``12`` §2.14 hands out a 作品集索引 page and ``03``:75 makes it G8's second
blocker ("作品集索引完整（8 件）"), but nothing in the tool could afterwards
answer the question a reader of a portfolio actually asks: *is the thing this
person claims still the thing the file says?* A registry that stored a
client-supplied ``passed=true`` would be exactly the artifact ``10``:292 calls
数字无出处 and ``15`` §3.3 forbids — a number with no denominator and no way to
re-derive it. So :func:`audit` re-reads the on-disk 作品集索引 and re-evaluates
**every** rule on every call, the same live re-evaluation rule the engagement
engine follows for gates (AGENTS.md invariant 1: a stale pass never grants
passage).

What this is **not**, stated because the course is strict about the difference:

* It is not the 在线证书核验页. ``15``:230 records that page as 未建, and ``15``:48
  makes verification a 3-business-day human reply through the course's own
  channel. Nothing here verifies a certificate against an issuer; the registry is
  per-machine (the data root), so the one-number-one-person rule (``15``:46) is
  enforced *locally* — against re-registration on this machine — and the page says so.
* It does not grade. ``03` §2 puts 答辩 at 25% and 互助出勤 at 15%, and ``03``:75 ③④
  makes both the defence and the 等级判定 human blockers; ``23`` 附 C.2 documents
  that the book's A/B/C wording leaves a combination satisfied by no grade. The
  audit scores rules and never emits an A/B/C.

Every rule carries ``source`` (checkable in one hop) and ``confidence``, one of
the six tiers used across this project's audit documents:
``工具实测`` > ``代码原文`` / ``项目约束原文`` > ``教案原文`` > ``OFFICIAL`` > ``GAP``.
``GAP`` means the book does not actually spell the rule out and the pattern is our
reading of it — R7 is the honest example: ``15``:45 states ``<期次>-<等级>-<顺序号>``
with one example (``L1-2026Q4-B-007``) and never says how long 期次 is.

Two properties that are not negotiable, both from the course's own red lines
(``11`` §6.1–6.2, plus AGENTS.md invariants 2 and 3):

* **Nothing of the student's document is echoed back.** A finding reports the
  *kind* and a row or line number, never the matched text — an audit result is
  what a reviewer pastes into a reply, and the document is where a leaked 手机号
  would be.
* **The document is never copied into the registry.** An entry stores one
  filename under ``course-labs/D8/`` (:func:`fde_scope.course.verifier.draft_dir`).
  Copying it would duplicate the PII the red line is about and let the registry
  keep claiming something about a file the student has since edited.
"""

from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .. import fsutil, paths
from .checks import Status
from .verifier import draft_dir

__all__ = [
    "DEFAULT_PORTFOLIO",
    "PORTFOLIO_DAY",
    "RULES",
    "AuditResult",
    "Rule",
    "RuleResult",
    "ShowcaseEntry",
    "ShowcaseRegistration",
    "ShowcaseStore",
    "audit",
    "audit_entry",
    "get",
    "list_entries",
    "listing",
    "register",
    "rule_for",
]

#: ``D8`` is the only day whose deliverable this registry addresses: ``12`` §2.14
#: is the 作品集索引 page and ``03``:75 files it under G8.
PORTFOLIO_DAY = "D8"
DEFAULT_PORTFOLIO = "作品集索引.md"

#: The body has to be *writing*, not a template — the same 800-byte floor and
#: ``TODO`` ban the G8 ArtifactCheck asserts (``catalog.py:1284–1291``).
_MIN_BYTES = 800
_PLACEHOLDER = "TODO"

Confidence = Literal["工具实测", "代码原文", "项目约束原文", "教案原文", "OFFICIAL", "GAP"]
Grade = Literal["A", "B", "C"]

#: ``15``:45, read off its one example: ``L1`` programme, ``2026Q4`` 期次,
#: ``B`` 等级, ``007`` 顺序号. Our reading, hence R7's ``GAP`` label.
CERT_NO_RE = re.compile(r"^L\d{1,2}-\d{4}Q[1-4]-[ABC]-\d{3}$")

_EVIDENCE_HEADER = "证据链接"
_VALUE_HEADER = "价值"
_ROW = re.compile(r"^\|(.+)\|\s*$")
_SEPARATOR = re.compile(r"^\|[\s:|-]+\|$")

#: Shapes from ``11` §6.2's list. 地址 / 车牌 / 订单号 / 设备序列号 are deliberately
#: not guessed at: none has a shape that does not also match legitimate portfolio
#: text, and a false "clean" is worse than a row that says a human must look.
_PII_SHAPES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("手机号", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("邮箱", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}")),
    (
        "身份证号",
        re.compile(
            r"(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)"
        ),
    ),
    ("银行卡号", re.compile(r"(?<!\d)\d{16,19}(?!\d)")),
)

#: A 证据链接 cell must look like a pointer. Angle brackets are checked *first*,
#: because the book's own template ships ``<路径/链接>`` (``12``:858–865), which
#: contains a slash and would otherwise pass as a path.
_LINK_MARKERS = ("/", ".md", ".json", ".jsonl", ".csv", ".html", ".png", ".jpg", "http", "#")

#: ``15` §3.2's five outward metrics are ratios and ``15`:154 requires each to be
#: published with its denominator. R8 applies to *those*: the book's own sample
#: row "准确率 78% → 91%" (``12``:862) carries no denominator and must not fail.
_RATE_TOKENS = ("完整率", "完课率", "留存率", "复用率", "满意度", "NPS", "通过率")
_PERCENT = re.compile(r"\d+(?:\.\d+)?\s*%")
_DENOMINATOR = re.compile(r"\d\s*[/÷]\s*\d|[Nn]\s*=|样本")


def _now() -> datetime:
    return datetime.now(UTC)


# -- 输入与记录 ----------------------------------------------------------------


class ShowcaseRegistration(BaseModel):
    """登记输入：``entry_id``、时间戳、版本一律由 :class:`ShowcaseEntry` 生成。

    Deliberately has no ``entry_id`` field, so no request body can choose the id
    its record will be stored under (AGENTS.md invariant 2).
    """

    alias: str = Field(min_length=1, max_length=40)
    cohort: str = Field(pattern=r"^\d{4}Q[1-4]$")
    level: Grade
    cert_no: str
    portfolio: str = Field(default=DEFAULT_PORTFOLIO, min_length=1, max_length=60)


class ShowcaseEntry(BaseModel):
    """一条登记记录：一个代号、一个编号、一个作品集文件。"""

    entry_id: str = Field(default_factory=lambda: f"sc-{secrets.token_hex(4)}")
    alias: str
    cohort: str
    level: Grade
    cert_no: str
    portfolio: str = DEFAULT_PORTFOLIO
    version: int = 1
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    @field_validator("alias")
    @classmethod
    def _alias_is_a_codename(cls, value: str) -> str:
        """``11` §6.1: the public face carries a 代号, not a name or a contact.

        ``@`` and a 7-digit run are rejected because they are the two shapes that
        turn a 代号 into contact details (email, phone, order id).
        """
        value = value.strip()
        if not value:
            raise ValueError("alias 不能为空")
        if "@" in value:
            raise ValueError("alias 不能含邮箱：公开面只登记代号（11 §6.1）")
        if re.search(r"\d{7,}", value):
            raise ValueError("alias 不能含长数字串：手机 / 订单 / 卡号形态（11 §6.2）")
        return value

    @field_validator("cert_no")
    @classmethod
    def _cert_no_is_well_formed(cls, value: str) -> str:
        value = value.strip()
        if not CERT_NO_RE.match(value):
            raise ValueError(
                f"证书编号不符合 15 §1.2 的 <期次>-<等级>-<顺序号>（例 L1-2026Q4-B-007）：{value!r}"
            )
        return value

    @field_validator("portfolio")
    @classmethod
    def _portfolio_is_one_segment(cls, value: str) -> str:
        """A file *in* the D8 drafts directory — never a path that walks out of it."""
        return fsutil.safe_child(Path("."), value.strip()).name

    def touch(self) -> None:
        self.version += 1
        self.updated_at = _now()


# -- 规则 --------------------------------------------------------------------


@dataclass(frozen=True)
class Rule:
    """One line of the rubric: what must hold, where it comes from, how far we trust it."""

    id: str
    label: str
    ask: str
    source: str
    confidence: Confidence
    manual: bool = False


RULES: tuple[Rule, ...] = (
    Rule(
        id="R1",
        label="索引页实存且已填完",
        ask=f"{DEFAULT_PORTFOLIO} 存在、≥{_MIN_BYTES} 字节、不含「{_PLACEHOLDER}」",
        source="fde_scope/course/catalog.py:1284–1291（与 G8 ArtifactCheck 同一道线）",
        confidence="代码原文",
    ),
    Rule(
        id="R2",
        label="8 件齐全",
        ask="索引表至少 8 行产出（README §3 官方 8 件）",
        source="03:75 G8 blocker ②「作品集索引完整（8 件）」、12:845–865 §2.14",
        confidence="教案原文",
    ),
    Rule(
        id="R3",
        label="每行含数字",
        ask="每一行的「一句话价值」列里有一个数字（列名本身就是「一句话价值（含数字）」）",
        source="10:32 §2.0 表头、12:856 表头",
        confidence="教案原文",
    ),
    Rule(
        id="R4",
        label="证据链接非占位",
        ask=f"每一行的「{_EVIDENCE_HEADER}」已替换成可指过去的路径或链接",
        source="12:858–865（样板仍是 <路径/链接>）、10:28「证据 > 描述」",
        confidence="教案原文",
    ),
    Rule(
        id="R5",
        label="零 PII 形态",
        ask="正文不含手机号 / 邮箱 / 身份证号 / 银行卡号形态；命中只报类型与条数",
        source="11:340–348 §6.1 三条红线、11:352 §6.2 PII 识别清单",
        confidence="项目约束原文",
    ),
    Rule(
        id="R6",
        label="结论口径在场",
        ask="出现「能做」口径（能做 / 不能做 / 有条件能做 三者都含这一段），不写「建议进一步分析」",
        source="12:331 数据体检报告：结论必须明确",
        confidence="教案原文",
    ),
    Rule(
        id="R7",
        label="编号格式",
        ask=f"证书编号匹配 {CERT_NO_RE.pattern}",
        source="15:45 §1.2（格式 <期次>-<等级>-<顺序号>，例 L1-2026Q4-B-007）",
        confidence="GAP",
    ),
    Rule(
        id="R8",
        label="比率带分母",
        ask="带「完整率 / 完课率 / NPS …」的百分比，同行给出分母或样本量",
        source="15:141–147 §3.2 五项对外指标、15:154 §3.3②「永远带分母与样本量」",
        confidence="教案原文",
    ),
    Rule(
        id="R9",
        label="虚构标注在场",
        ask="写明产出基于虚构演示场景（茶饮连锁客服）",
        source="10:38 / 10:54 / 10:80③ / 10:294、12:853",
        confidence="教案原文",
    ),
    Rule(
        id="R10",
        label="等级与编号一致",
        ask="登记自报的等级 = 编号里的等级位",
        source="15:45–46（等级是编号的一段；换级是同一编号上的记录）",
        confidence="教案原文",
    ),
    Rule(
        id="M1",
        label="答辩与出勤由人判",
        ask="结业答辩（25%）、互助出勤（15%）与 A/B/C 等级判定 —— 本页不评",
        source="03:47–55 §2 权重、03:75 ③④、23 附 C.2（判级口径缺口）",
        confidence="教案原文",
        manual=True,
    ),
)


@dataclass(frozen=True)
class RuleResult:
    id: str
    label: str
    status: Status
    detail: str
    source: str
    confidence: Confidence

    def line(self) -> str:
        mark = {"pass": "✅", "fail": "❌", "manual": "📝"}[self.status]
        return "\n".join(
            [
                f"{mark} [{self.id}] {self.label}（{self.confidence}）",
                f"      {self.detail}" if self.detail else "",
                f"      依据：{self.source}",
            ]
        ).rstrip()


@dataclass
class AuditResult:
    """One re-computed pass over one entry. Nothing here is cached."""

    entry_id: str
    alias: str
    cohort: str
    level: Grade
    cert_no: str
    portfolio: str
    checked_at: datetime = field(default_factory=_now)
    results: list[RuleResult] = field(default_factory=list)

    @property
    def scored(self) -> list[RuleResult]:
        return [r for r in self.results if r.status != "manual"]

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == "pass")

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == "fail")

    @property
    def score(self) -> str:
        """Always a fraction with its denominator (``15`:154 discipline)."""
        return f"{self.passed}/{len(self.scored)}"

    @property
    def ok(self) -> bool:
        return bool(self.scored) and self.failed == 0

    def as_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "alias": self.alias,
            "cohort": self.cohort,
            "level": self.level,
            "cert_no": self.cert_no,
            "portfolio": self.portfolio,
            "checked_at": self.checked_at.isoformat(),
            "score": self.score,
            "ok": self.ok,
            "graded": False,  # 判级是人的 blocker（03:75 ④）；这里永不出 A/B/C
            "rules": [
                {
                    "id": r.id,
                    "label": r.label,
                    "status": r.status,
                    "detail": r.detail,
                    "source": r.source,
                    "confidence": r.confidence,
                }
                for r in self.results
            ],
        }


def rule_for(rule_id: str) -> Rule:
    return next(r for r in RULES if r.id == rule_id)


# -- 文件读取 ----------------------------------------------------------------


@dataclass(frozen=True)
class _Doc:
    exists: bool
    text: str
    size: int
    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


def _cells(line: str) -> list[str]:
    match = _ROW.match(line.strip())
    return [cell.strip() for cell in match.group(1).split("|")] if match else []


def _tables(text: str) -> list[tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]]:
    """Every markdown table in ``text`` as ``(header, data rows)`` blocks.

    A block ends at the first line that is not a table row. This matters: a
    作品集索引 page ships with three *other* tables (门禁对照 / 每日机器分 / 三套包装),
    and a block that ran on until the next 证据链接 header would count their rows
    as产出 — padding ``R2``'s 「≥8 件」 with a table of gate slugs, and quoting row
    numbers in ``R3``/``R4`` that the student cannot find in the file.
    """
    blocks: list[tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]] = []
    run: list[tuple[str, ...]] = []

    def flush() -> None:
        if run:
            blocks.append((run[0], tuple(run[1:])))
            run.clear()

    for line in text.splitlines():
        if _SEPARATOR.match(line.strip()):
            continue  # ``|---|---|`` rules off the header; it is not a row
        cells = _cells(line)
        if not cells:
            flush()
            continue
        run.append(tuple(cells))
    flush()
    return blocks


def _index_table(text: str) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    """The 作品集索引 table as ``(header, data rows)``, or two empty tuples.

    Located by its header cell rather than by position: a student's page may open
    with the 虚构 note, the 一句话总结, or a different table — ``12``:851–870's order
    is a suggestion.
    """
    for header, rows in _tables(text):
        if _EVIDENCE_HEADER in "".join(header):
            return header, rows
    return (), ()


def _read_doc(path: Path) -> _Doc:
    if not path.is_file():
        return _Doc(False, "", 0, (), ())
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return _Doc(True, "", path.stat().st_size, (), ())
    header, rows = _index_table(text)
    return _Doc(True, text, path.stat().st_size, header, rows)


def _column(header: tuple[str, ...], needle: str) -> int | None:
    for i, cell in enumerate(header):
        if needle in cell:
            return i
    return None


def _is_unfilled(cell: str) -> bool:
    return not cell or cell.startswith("<") or cell in {"—", "-", "待补", _PLACEHOLDER}


def _looks_linked(cell: str) -> bool:
    return not cell.startswith("<") and any(marker in cell for marker in _LINK_MARKERS)


def _pii_kinds(text: str) -> list[str]:
    return [name for name, pattern in _PII_SHAPES if pattern.search(text)]


def _rates_without_denominator(text: str) -> list[int]:
    return [
        n
        for n, line in enumerate(text.splitlines(), start=1)
        if any(token in line for token in _RATE_TOKENS)
        and _PERCENT.search(line)
        and not _DENOMINATOR.search(line)
    ]


# -- 十条可机检规则 -----------------------------------------------------------


def _r1(doc: _Doc, entry: ShowcaseEntry) -> tuple[Status, str]:
    if not doc.exists:
        return (
            "fail",
            f"读不到 {entry.portfolio}：在 course-labs/{PORTFOLIO_DAY}/ 写完后重跑（catalog.py:1288）",
        )
    if doc.size < _MIN_BYTES:
        return "fail", f"{doc.size} 字节 < {_MIN_BYTES} 字节下限"
    if _PLACEHOLDER in doc.text:
        return "fail", f"正文仍有「{_PLACEHOLDER}」占位（{doc.size} 字节）"
    if "证据" not in doc.text:
        return "fail", "正文没有「证据」二字：G8 的 ArtifactCheck 认这一列（catalog.py:1290）"
    return "pass", f"{doc.size} 字节，占位已清"


def _r2(doc: _Doc, entry: ShowcaseEntry) -> tuple[Status, str]:
    if not doc.header:
        return "fail", f"找不到带「{_EVIDENCE_HEADER}」列的索引表（模板见 12:856）"
    if len(doc.rows) >= 8:
        return "pass", f"索引表 {len(doc.rows)} 行"
    return "fail", f"索引表 {len(doc.rows)} 行，要求 ≥8 行（03:75 G8 ②）"


def _r3(doc: _Doc, entry: ShowcaseEntry) -> tuple[Status, str]:
    """The *value* column, not "any cell": a row's 日期 is digits too, so a
    whole-row search would pass an empty 一句话价值 on every single line.
    """
    col = _column(doc.header, _VALUE_HEADER)
    if col is None:
        return "fail", f"表头没有「{_VALUE_HEADER}」列，数字要求无从核对（12:856）"
    if not doc.rows:
        return "fail", "没有可检的数据行"
    cells = [row[col] if col < len(row) else "" for row in doc.rows]
    missing = [i for i, cell in enumerate(cells, start=1) if not re.search(r"\d", cell)]
    if missing:
        return (
            "fail",
            f"第 {', '.join(map(str, missing))} 行的价值句没有数字（列名本身要求「含数字」— 12:856）",
        )
    return "pass", f"{len(cells)} 行的价值句全部含数字"


def _r4(doc: _Doc, entry: ShowcaseEntry) -> tuple[Status, str]:
    col = _column(doc.header, _EVIDENCE_HEADER)
    if col is None or not doc.rows:
        return "fail", f"表头找不到「{_EVIDENCE_HEADER}」列（12:856）"
    cells = [row[col] if col < len(row) else "" for row in doc.rows]
    unfilled = [i for i, cell in enumerate(cells, start=1) if _is_unfilled(cell)]
    shapeless = [
        i for i, cell in enumerate(cells, start=1) if not _is_unfilled(cell) and not _looks_linked(cell)
    ]
    if unfilled or shapeless:
        parts = []
        if unfilled:
            parts.append(f"仍是占位：第 {', '.join(map(str, unfilled))} 行")
        if shapeless:
            parts.append(f"不像路径/链接：第 {', '.join(map(str, shapeless))} 行")
        return "fail", "；".join(parts) + "（原则：证据 > 描述 — 10:28）"
    return "pass", f"{len(cells)} 行的证据链接都能指到别处"


def _r5(doc: _Doc, entry: ShowcaseEntry) -> tuple[Status, str]:
    if not doc.exists:
        return "fail", "文件读不到，PII 无从检查（不是「没有 PII」）"
    kinds = _pii_kinds(doc.text)
    if kinds:
        return "fail", f"检出 {'、'.join(kinds)} 形态 —— 正文不回显，请就地脱敏（11 §6.1）"
    return "pass", "未见手机号 / 邮箱 / 身份证 / 银行卡形态（地址、车牌、订单号仍需人看 — 11 §6.2）"


def _r6(doc: _Doc, entry: ShowcaseEntry) -> tuple[Status, str]:
    if not doc.exists:
        return "fail", "文件读不到"
    if "能做" in doc.text:
        return "pass", "「能做」口径在场（三种结论都含这一段）"
    return "fail", "三种结论口径都没出现 —— 12:331 不许写「建议进一步分析」"


def _r7(doc: _Doc, entry: ShowcaseEntry) -> tuple[Status, str]:
    if CERT_NO_RE.match(entry.cert_no):
        return "pass", f"{entry.cert_no} 符合格式；格式本身是我们的读法，非教案逐字（15:45 只给了一个例子）"
    return "fail", f"{entry.cert_no} 不符合 15 §1.2 的示例格式"


def _r8(doc: _Doc, entry: ShowcaseEntry) -> tuple[Status, str]:
    if not doc.exists:
        return "fail", "文件读不到"
    bad = _rates_without_denominator(doc.text)
    if bad:
        return "fail", f"第 {', '.join(map(str, bad))} 行的比率没有分母或样本量（15:154）"
    return "pass", "对外口径的比率都带分母（n < 20 只做定性这条是人的线 — 15:152）"


def _r9(doc: _Doc, entry: ShowcaseEntry) -> tuple[Status, str]:
    if not doc.exists:
        return "fail", "文件读不到"
    if "虚构" in doc.text or "演示案例" in doc.text:
        return "pass", "虚构 / 演示标注在场 —— 10:80③ 规定这行不许删"
    return "fail", "没有虚构标注：把虚构案例写成真实项目是 10:294 的「过度包装」反模式"


def _r10(doc: _Doc, entry: ShowcaseEntry) -> tuple[Status, str]:
    grade_in_number = entry.cert_no.split("-")[-2]
    if grade_in_number == entry.level:
        return "pass", f"自报等级 {entry.level} = 编号等级位 {grade_in_number}"
    return "fail", f"自报等级 {entry.level}，但编号 {entry.cert_no} 的等级位是 {grade_in_number}（15:45–46）"


_CHECKS = {
    "R1": _r1,
    "R2": _r2,
    "R3": _r3,
    "R4": _r4,
    "R5": _r5,
    "R6": _r6,
    "R7": _r7,
    "R8": _r8,
    "R9": _r9,
    "R10": _r10,
}


# -- 存储 --------------------------------------------------------------------


class ShowcaseStore:
    """``<root>/.fde_scope/showcase/<id>/entry.json`` + 可重建的 ``index.json``。

    The same shape as :class:`fde_scope.skills.store.SkillStore`: the directory
    *is* the record, ``index.json`` is a convenience that :meth:`rebuild_index`
    can regenerate, and one corrupt entry is skipped rather than taking the whole
    listing down.
    """

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root is not None else paths.showcase_dir()
        self._index_path = self.root / "index.json"

    def _dir_for(self, entry_id: str) -> Path:
        return fsutil.safe_child(self.root, entry_id)

    def _entry_path(self, entry_id: str) -> Path:
        return self._dir_for(entry_id) / "entry.json"

    def save(self, entry: ShowcaseEntry) -> None:
        d = self._dir_for(entry.entry_id)
        d.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(entry.model_dump(mode="json"), ensure_ascii=False, indent=2)
        fsutil.atomic_write_text(self._entry_path(entry.entry_id), payload)
        self._touch_index(entry)

    def load(self, entry_id: str) -> ShowcaseEntry | None:
        path = self._entry_path(entry_id)
        if not path.exists():
            return None
        try:
            return ShowcaseEntry.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except (ValueError, OSError):
            return None  # 损坏条目跳过，不炸整张名录

    def delete(self, entry_id: str) -> None:
        d = self._dir_for(entry_id)
        if d.is_dir():
            for p in sorted(d.iterdir()):
                p.unlink()
            d.rmdir()
        self.rebuild_index()

    def load_all(self) -> list[ShowcaseEntry]:
        if not self.root.exists():
            return []
        rows = [self.load(p.name) for p in sorted(self.root.iterdir()) if p.is_dir()]
        return sorted((r for r in rows if r is not None), key=lambda e: e.updated_at, reverse=True)

    def find_by_cert(self, cert_no: str) -> ShowcaseEntry | None:
        return next((e for e in self.load_all() if e.cert_no == cert_no), None)

    def index_entries(self) -> list[dict]:
        if not self._index_path.exists():
            self.rebuild_index()
            return json.loads(self._index_path.read_text(encoding="utf-8"))
        try:
            return json.loads(self._index_path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            self.rebuild_index()
        return json.loads(self._index_path.read_text(encoding="utf-8"))

    def rebuild_index(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        rows = [_index_row(e) for e in self.load_all()]
        fsutil.atomic_write_text(self._index_path, json.dumps(rows, ensure_ascii=False, indent=2))

    def _touch_index(self, entry: ShowcaseEntry) -> None:
        rows = [r for r in self.index_entries() if r["entry_id"] != entry.entry_id]
        rows.append(_index_row(entry))
        fsutil.atomic_write_text(self._index_path, json.dumps(rows, ensure_ascii=False, indent=2))


def _index_row(entry: ShowcaseEntry) -> dict:
    """The listing keeps only what a reviewer needs to pick a row worth auditing."""
    return {
        "entry_id": entry.entry_id,
        "alias": entry.alias,
        "cohort": entry.cohort,
        "level": entry.level,
        "cert_no": entry.cert_no,
        "portfolio": entry.portfolio,
        "updated_at": entry.updated_at.isoformat(),
    }


# -- 门面 --------------------------------------------------------------------


def register(draft: ShowcaseRegistration, store: ShowcaseStore | None = None) -> ShowcaseEntry:
    """登记一条记录；``entry_id`` 在这里生成，外部无法指定。"""
    s = store or ShowcaseStore()
    entry = ShowcaseEntry(**draft.model_dump())
    clash = s.find_by_cert(entry.cert_no)
    if clash is not None:
        # 一人一号（15:46）。The registry is one machine's data root, so this is a
        # local dedupe, not issuer-side uniqueness — see the module docstring.
        raise ValueError(f"该编号已登记（{clash.entry_id}）—— 15:46 一人一号")
    s.save(entry)
    return entry


def get(entry_id: str, store: ShowcaseStore | None = None) -> ShowcaseEntry:
    entry = (store or ShowcaseStore()).load(entry_id)
    if entry is None:
        raise KeyError(entry_id)
    return entry


def list_entries(store: ShowcaseStore | None = None) -> list[ShowcaseEntry]:
    return (store or ShowcaseStore()).load_all()


def listing(store: ShowcaseStore | None = None) -> list[dict]:
    """The reviewer's table, derived from the entries on disk.

    Not :meth:`ShowcaseStore.index_entries`, which rebuilds ``index.json`` when
    it is missing or corrupt: a ``GET`` must not repair the registry.
    """
    return [_index_row(e) for e in list_entries(store)]


def audit(entry_id: str, store: ShowcaseStore | None = None) -> AuditResult:
    return audit_entry(get(entry_id, store))


def audit_entry(entry: ShowcaseEntry, *, drafts: Path | None = None) -> AuditResult:
    """Re-evaluate every rule against the file as it is *now*.

    ``drafts`` overrides the D8 drafts directory (tests); production resolves it
    through :func:`fde_scope.course.verifier.draft_dir`, so a ``FDE_SCOPE_HOME``
    change is picked up on the next call rather than at import.
    """
    base = drafts if drafts is not None else draft_dir(PORTFOLIO_DAY)
    doc = _read_doc(base / entry.portfolio)
    results: list[RuleResult] = []
    for rule in RULES:
        if rule.manual:
            results.append(RuleResult(rule.id, rule.label, "manual", rule.ask, rule.source, rule.confidence))
            continue
        status, detail = _CHECKS[rule.id](doc, entry)
        results.append(RuleResult(rule.id, rule.label, status, detail, rule.source, rule.confidence))
    return AuditResult(
        entry_id=entry.entry_id,
        alias=entry.alias,
        cohort=entry.cohort,
        level=entry.level,
        cert_no=entry.cert_no,
        # named below the data root: an absolute path carries the home
        # directory, and ``11`` §6.2 counts identifying detail as PII.
        portfolio=f"course-labs/{PORTFOLIO_DAY}/{entry.portfolio}",
        results=results,
    )
