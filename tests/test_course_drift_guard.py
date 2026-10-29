"""Course-book drift guards.

``course-level-1/`` is not prose that *describes* the tool — for a first-time FDE
it *is* the tool. Every ``fde-scope …`` line in it gets typed into a terminal
during class, and every number in it gets copied into a customer deliverable.
Before this guard a lesson could quote a command that no longer existed, a flag
nobody declared, or a gate count that had drifted from the registry, and the
suite stayed green because nothing read the book.

Two halves:

* **static** — every command-shaped token sequence in the book is resolved
  against the *live* typer command tree, and every option value against a domain
  derived from the code (gate registry, profile registry, connector registry,
  ``ExportFormat``, ``SkillCategory``, the ``--agent`` branches in ``cli.py``).
  A rename in ``fde_scope/`` fails here instead of failing in front of a class.
* **executed** — the claims the book makes about *output* (``✅ PASS`` for an
  industrial gate closed on a ticket profile, ``🚫 移交包缺失: [...]``, ``18
  phases visible``, ``grasp_success_rate=0.7931``) are re-run through the real
  console against a pristine seeded home.

Count claims are recorded as ``(file, pattern, occurrences, values)`` and the
occurrence count is asserted, so a claim that *disappears* fails as loudly as one
that changes — the failure mode silent regex scanning normally hides.
``test_scanner_reports_a_planted_broken_command`` is the meta-guard for the
static half: a scan that stops finding problems because it stopped finding
*commands* is itself a failure.

Executed baseline: fde-scope 0.1.0 · Python 3.12 · macOS arm64 · 2026-10-07.
"""

from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, get_args

import pytest
from typer.main import get_command

# `csv` registers itself on import (fallback connector), so the registry the domains
# derive from is only complete once this has run — at module scope, because _domains()
# is called by tests that do not import it themselves.
import fde_scope.connectors.csv_fallback  # noqa: F401
from fde_scope import __version__
from fde_scope.connectors.base import DataConnector
from fde_scope.course.catalog import LABS
from fde_scope.course.checks import ManualCheck
from fde_scope.engagement.context import JournalEntry
from fde_scope.engagement.engagement import _default_gate_registry
from fde_scope.engagement.phases import PHASES, Zone, phases_for_profile
from fde_scope.profiles.base import all_profiles
from fde_scope.skills.models import ExportFormat, SkillCategory

REPO_ROOT = Path(__file__).resolve().parents[1]
BOOK = REPO_ROOT / "course-level-1"
CLI = str(Path(sys.executable).with_name("fde-scope"))
SEED_SCRIPT = REPO_ROOT / "examples" / "seed_mock_engagements.py"

_COMMAND_SHAPED = re.compile(r"[a-z][a-z0-9_-]*\Z")
_HEAD = re.compile(r"(?<![A-Za-z0-9_./-])(?:fde-scope|python -m fde_scope)(?=[ \t])(?P<rest>[^\n`]*)")
_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]")
_ASCII_ALNUM = re.compile(r"[A-Za-z0-9]")
_PLACEHOLDER = re.compile(r"<[^<>]*>\Z")
_SHELL_OPS = ("&&", "||", "|", ";", ">", "<", "2>", ">>", "&")
# Options whose argument is a value from a closed code-derived domain. Booleans
# (--json, --accept) are deliberately absent: their "value" is the next token.
_VALUE_OPTIONS = (
    "--gate",
    "--profile",
    "--type",
    "--format",
    "--agent",
    "--category",
    "--kind",
)
_REF = re.compile(r"(?:examples|labs|course-level-1)/[A-Za-z0-9_.\-/]+")


def _command_tree() -> dict[tuple[str, ...], tuple[set[str], set[str]]]:
    """``{(path, ...): (declared opts, sub-command names)}`` from the live app."""
    from fde_scope.cli import app as typer_app

    def walk(cmd, prefix=()):
        opts = {o for p in cmd.params for o in getattr(p, "opts", [])}
        subs = getattr(cmd, "commands", None) or {}
        yield prefix, opts, set(subs)
        for name, sub in subs.items():
            yield from walk(sub, prefix + (name,))

    return {path: (opts, subs) for path, opts, subs in walk(get_command(typer_app))}


def _fence_langs(text: str) -> dict[int, str | None]:
    """Line number -> info string of the fence it sits in (``` → ``None``)."""
    langs: dict[int, str | None] = {}
    inside: str | None = None
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("```"):
            if inside is None:
                inside = stripped[3:].strip() or None
            else:
                inside = None
            continue
        if inside is not None:
            langs[lineno] = inside
    return langs


def _strip_trailing_comment(rest: str) -> str:
    """Drop an unquoted ``#`` comment, quote-aware."""
    out, quote = [], ""
    for ch in rest:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "'\"":
            quote = ch
        elif ch == "#":
            break
        out.append(ch)
    return "".join(out)


def _is_placeholder(tok: str) -> bool:
    """``<你的档案id>`` is a hole the student fills, not a value to validate."""
    return bool(_PLACEHOLDER.match(tok))


def _tokenize(text: str) -> tuple[list[str], str | None]:
    """Split on whitespace honouring quotes; stop at prose or a shell operator.

    The stop token is returned so prose that merely *mentions* a command
    (``fde-scope 五分钟冒烟``) or a pipeline (``… | head``) is reported as what it
    is instead of being validated as an argument list.
    """
    toks: list[str] = []
    cur, quote, i = "", "", 0
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote:
                quote = ""
            else:
                cur += ch
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            i += 1
            continue
        if ch in " \t":
            if cur:
                toks.append(cur)
                cur = ""
            i += 1
            continue
        if text.startswith("```", i):
            break
        cur += ch
        i += 1
    if cur:
        toks.append(cur)

    argv: list[str] = []
    for tok in toks:
        if not _is_placeholder(tok) and any(tok.startswith(op) for op in _SHELL_OPS):
            return argv, tok
        # pure prose: CJK with no latin/digit and not a <placeholder>
        if _CJK.search(tok) and not _ASCII_ALNUM.search(tok) and not tok.startswith("<"):
            return argv, tok
        argv.append(tok)
    return argv, None


def _candidates(root: Path) -> list[dict[str, Any]]:
    """Every command-shaped token sequence in every ``*.md`` under *root*."""
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        langs = _fence_langs(text)
        for match in _HEAD.finditer(text):
            lineno = text.count("\n", 0, match.start()) + 1
            rest = match.group("rest")
            # a trailing backslash continues onto the next source line
            nxt = lineno
            while rest.rstrip().endswith("\\") and nxt < len(lines):
                rest = rest.rstrip()[:-1] + " " + lines[nxt].strip().strip("`")
                nxt += 1
            cand = "fde-scope " + re.sub(r"\s+", " ", _strip_trailing_comment(rest).strip())
            argv, stop = _tokenize(cand)
            rows.append(
                {
                    "file": path.name,
                    "line": lineno,
                    "lang": langs.get(lineno),
                    "text": cand,
                    "argv": argv,
                    "stop": stop,
                }
            )
    return rows


def _resolve(argv: list[str], tree) -> tuple[tuple[str, ...], list[str]]:
    path: list[str] = []
    i = 1
    subs = tree[tuple(path)][1]
    while i < len(argv):
        tok = argv[i]
        if tok.startswith("-") or tok not in subs:
            break
        path.append(tok)
        subs = tree[tuple(path)][1]
        i += 1
    return tuple(path), argv[i:]


def _classify(root: Path = BOOK):
    tree = _command_tree()
    out: dict[str, list | dict] = {
        "resolved": [],
        "unknown": [],
        "bad_flags": [],
        "non_command": [],
        "flag_values": {},
        "refs": [],
    }
    for row in _candidates(root):
        argv = row["argv"]
        head = argv[1] if len(argv) > 1 else ""
        if not _COMMAND_SHAPED.match(head):
            out["non_command"].append(row)
            continue
        path, leftover = _resolve(argv, tree)
        if not path:
            # the head token looks like a sub-command and is not one: a rename or a
            # typo, never prose — prose is already excluded by shape above.
            out["unknown"].append((row["file"], row["line"], row["text"], head))
            continue
        if path not in tree:  # pragma: no cover - _resolve only returns known paths
            raise AssertionError(f"scanner lost a path it invented: {path}")
        out["resolved"].append(row)
        # root options are unioned in: `fde-scope X --help`/`--version` style global
        # flags are legal at the top level, and forgiving that is cheaper than the
        # false positives it would otherwise produce on lesson prose.
        declared = tree[path][0] | tree[()][0] | {"--help"}
        for tok in leftover:
            if not tok.startswith("-"):
                continue
            name = tok.split("=", 1)[0]
            if name in declared:
                continue
            flag = "--" + name.lstrip("-")
            if flag not in declared:
                out["bad_flags"].append((row["file"], row["line"], row["text"], name, path))
        for j, tok in enumerate(leftover):
            for key in _VALUE_OPTIONS:
                if tok == key and j + 1 < len(leftover):
                    val = leftover[j + 1]
                elif tok.startswith(key + "="):
                    val = tok.split("=", 1)[1]
                else:
                    continue
                if _is_placeholder(val):
                    continue
                for part in val.split("|"):
                    if part:
                        out["flag_values"].setdefault(key, {}).setdefault(part, []).append(row)
        for tok in leftover:
            for m in _REF.finditer(tok):
                out["refs"].append((row["file"], row["line"], m.group(0).rstrip(".")))
    return out


def _domains() -> dict[str, set[str]]:
    """Option -> the set of values the *code* accepts, derived not transcribed."""
    agent_src = ast.parse((REPO_ROOT / "fde_scope" / "cli.py").read_text(encoding="utf-8"))
    agents = {
        comp.value
        for node in ast.walk(agent_src)
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == "agent"
        for comp in node.comparators
        if isinstance(comp, ast.Constant) and isinstance(comp.value, str)
    }
    return {
        "--gate": set(_default_gate_registry()),
        "--profile": set(all_profiles()),
        "--type": set(DataConnector.registry()),
        "--format": set(get_args(ExportFormat)),
        "--agent": agents,
        "--category": {c.value for c in SkillCategory},
        "--kind": set(get_args(JournalEntry.model_fields["kind"].annotation)),
    }


def _gate_registry() -> dict[str, Any]:
    return _default_gate_registry()


def _industrial_gates() -> set[str]:
    return {slug for slug, gate in _gate_registry().items() if gate.industrial_only}


def _general_gates() -> set[str]:
    return {slug for slug, gate in _gate_registry().items() if not gate.industrial_only}


def _book_slugs(rel: str, anchor: str) -> list[str]:
    """Backticked slugs on the line containing *anchor*, plus its soft-wrapped tail.

    The anchor has to match exactly one line: a rewrite that duplicates or deletes an
    enumeration should fail here, not quietly change which line got read. ``03``'s 🏭
    list wraps, so tail lines are collected until a blank line or the next block item —
    a one-line regex would have dropped four of its seven slugs without noticing.
    """
    lines = _read(rel).splitlines()
    hits = [i for i, line in enumerate(lines) if anchor in line]
    assert len(hits) == 1, f"anchor {anchor!r} matched {len(hits)} lines, want exactly 1"
    collected = [lines[hits[0]]]
    for nxt in lines[hits[0] + 1 :]:
        if not nxt.strip() or nxt.startswith(("- ", "> ", "|")):
            break
        collected.append(nxt)
    return [slug for line in collected for slug in re.findall(r"`([a-z_]+)`", line)]


def _read(rel: str) -> str:
    return (BOOK / rel).read_text(encoding="utf-8")


def _book_line(rel: str, anchor: str) -> str:
    """The single line in *rel* containing *anchor* — the region a claim lives in."""
    hits = [line for line in _read(rel).splitlines() if anchor in line]
    assert len(hits) == 1, f"{rel}: {anchor!r} matched {len(hits)} lines, want exactly 1"
    return hits[0]


# (file, pattern, occurrences, values the book asserts)
COUNT_CLAIMS: list[tuple[str, str, int, tuple[str, ...]]] = [
    ("01-课程设计说明书.md", r"(\d+) 条命令的 CLI", 1, ("18",)),
    ("12-附录-术语表与模板库.md", r"(\d+) 条命令", 1, ("18",)),
    ("07-实战剧本与案例库.md", r"全部 (\d+) 个门禁", 1, ("10",)),
    ("12-附录-术语表与模板库.md", r"全部 (\d+) 个门禁", 1, ("10",)),
    ("12-附录-术语表与模板库.md", r"全部 (\d+) 行", 1, ("10",)),
    ("12-附录-术语表与模板库.md", r"（共 (\d+) 个）", 1, ("10",)),
    ("12-附录-术语表与模板库.md", r"通用 (\d+) 个", 1, ("3",)),
    ("12-附录-术语表与模板库.md", r"工业专属 (\d+) 个", 1, ("7",)),
    ("12-附录-术语表与模板库.md", r"标 ⚙ 的 (\d+) 个", 1, ("3",)),
    ("12-附录-术语表与模板库.md", r"ticket 走 (\d+) 阶段", 1, ("15",)),
    ("12-附录-术语表与模板库.md", r"（(\d+) 阶段全表）", 1, ("18",)),
    ("12-附录-术语表与模板库.md", r"(\d+) 个虚构档案", 1, ("10",)),
    ("03-评估体系与通关门禁.md", r"(\d+) 个（🏢 通用 (\d+) \+ 🏭 工业专属 (\d+)）", 1, ("10", "3", "7")),
    ("03-评估体系与通关门禁.md", r"🏢 \*\*通用 (\d+) 个", 1, ("3",)),
    ("03-评估体系与通关门禁.md", r"🏭 \*\*工业专属 (\d+) 个", 1, ("7",)),
    ("03-评估体系与通关门禁.md", r"那 (\d+) 个门禁", 1, ("10",)),
    ("07-实战剧本与案例库.md", r"跳过 (\d+) 个工业专属阶段，实走 (\d+) 阶段", 1, ("3", "15")),
    ("07-实战剧本与案例库.md", r"deploy 阶段有(\w+)门禁", 1, ("三个",)),
    ("07-实战剧本与案例库.md", r"(\d+) 条 blocker", 1, ("3",)),
    ("07-实战剧本与案例库.md", r"(\d+) 个工位", 1, ("5",)),
    ("01-课程设计说明书.md", r"(\d+) 个数据连接器", 1, ("10",)),
    ("01-课程设计说明书.md", r"数据侧 (\d+) 种", 1, ("5",)),
    ("01-课程设计说明书.md", r"工业侧 (\d+) 种", 1, ("5",)),
    # 24 · 开源对标：它把课堂侧数字写进对外文案，所以这些数字也得有真值通道
    ("24-开源对标与来源清单.md", r"↔ 我们的 (\d+) 区 / (\d+) 阶段 / (\d+) 个门禁", 1, ("4", "18", "10")),
    ("24-开源对标与来源清单.md", r"合计：(\d+) 个机器判分项 \+ (\d+) 个人工项", 1, ("91", "9")),
    ("24-开源对标与来源清单.md", r"报 \*\*(\d+) 项机器判分\*\*", 1, ("91",)),
    ("24-开源对标与来源清单.md", r"表格 (\d+) 行", 1, ("10",)),
    ("24-开源对标与来源清单.md", r"⚙ = (\d+) 个工业专属阶段", 1, ("3",)),
    ("24-开源对标与来源清单.md", r"deploy 阶段有 (\d+) 个门禁", 1, ("3",)),
    ("24-开源对标与来源清单.md", r"实走 (\d+) 阶段", 1, ("15",)),
]


# --------------------------------------------------------------------------- static


def test_scanner_sees_a_substantial_command_surface() -> None:
    """Anti-vacuity, part one: the scan must still *find* commands.

    Every later assertion is conditional on there being candidates, so a scanner
    broken by a heading-format change would pass by finding nothing. 296 candidates
    across 47 lessons was the measured surface on 2026-10-08; the floors below are
    deliberately far under it so ordinary lesson edits do not trip it, but a scan
    that collapses does.
    """
    found = _classify()
    bash_fenced = [r for r in found["resolved"] if r["lang"] == "bash"]
    assert len(found["resolved"]) >= 250, f"only {len(found['resolved'])} commands resolved"
    assert len(bash_fenced) >= 100, f"only {len(bash_fenced)} commands inside ```bash fences"


def test_every_command_shaped_candidate_is_a_real_command() -> None:
    """A lesson line that looks like a command must resolve in the live CLI tree.

    Lines like ``fde-scope 冒烟 …`` or ``fde-scope v0.1.0`` are prose, excluded by
    shape (the head token is not ``[a-z][a-z0-9_-]*``) rather than by an
    allowlist, so the exemption cannot rot into hiding a real rename.
    """
    found = _classify()
    assert not found["unknown"], "unknown command in the book:\n" + "\n".join(
        f"{file}:{line} {text} -> {head}" for file, line, text, head in found["unknown"]
    )


def test_no_candidate_uses_an_undeclared_option() -> None:
    found = _classify()
    assert not found["bad_flags"], "undeclared option in the book:\n" + "\n".join(
        f"{file}:{line} {text} -> {flag} not on {' '.join(path) or 'fde-scope'}"
        for file, line, text, flag, path in found["bad_flags"]
    )


def test_option_values_come_from_the_code_domains() -> None:
    """``--gate slo`` is only correct as long as ``slo`` is in the registry.

    Domains are derived from the code (see ``_domains``) rather than pasted, so
    widening or renaming a gate, connector or export format fails here — and the
    book, not this test, is what has to change.

    ``--gate corpus`` is the one deliberate miss: D4 teaches that the console
    *refuses* an unknown gate instead of pretending to check it, so it is pinned
    to the single command that demonstrates the error.
    """
    domains = _domains()
    found = _classify()
    offenders = [
        (row["file"], row["line"], option, value)
        for option, by_value in found["flag_values"].items()
        for value, rows in by_value.items()
        for row in rows
        if value not in domains[option]
    ]
    negative_demo = [(f, ln, o, v) for f, ln, o, v in offenders if (o, v) == ("--gate", "corpus")]
    other = [x for x in offenders if x not in negative_demo]
    assert not other, "value outside its code domain:\n" + "\n".join(map(str, other))
    assert len(negative_demo) == 1, f"expected one `--gate corpus` demo, got {negative_demo}"
    assert negative_demo[0][0] == "19-D4逐节教案.md"


def test_referenced_data_paths_exist() -> None:
    """Every ``examples/`` / ``labs/`` path a command reads must be in the repo.

    Four distinct paths were the measured surface; requiring the minimum keeps a
    renamed fixture from turning a lab into a 404 mid-class.
    """
    refs = {path for _, _, path in _classify()["refs"]}
    assert len(refs) >= 4, f"scanner lost path coverage: {sorted(refs)}"
    missing = [
        path for path in sorted(refs) if not (REPO_ROOT / path).exists() and not (BOOK / path).exists()
    ]
    assert not missing, f"referenced paths do not exist: {missing}"


def test_scanner_reports_a_planted_broken_command(tmp_path: Path) -> None:
    """Anti-vacuity, part two: the scanner must still *reject* what it should.

    Origin of this meta-guard: ``tests/test_architecture_guard.py`` once asserted
    a route count from a regex that omitted ``patch``, so the number was wrong and
    the test was green. A scan is only trustworthy if a known-bad input is caught,
    so here is one.
    """
    lesson = tmp_path / "planted.md"
    lesson.write_text(
        "# planted\n\n```bash\n"
        "fde-scope frobnicate --bogus eng-x\n"
        "fde-scope gate list --bogus\n"
        "fde-scope gate check eng-x --gate not_a_gate\n"
        "```\n",
        encoding="utf-8",
    )
    found = _classify(tmp_path)
    heads = [row[3] for row in found["unknown"]]
    assert "frobnicate" in heads, f"planted unknown command not caught: {found['unknown']}"
    assert sorted(row[3] for row in found["bad_flags"]) == ["--bogus"], found["bad_flags"]
    offenders = {
        (option, value)
        for option, by_value in found["flag_values"].items()
        for value, _rows in by_value.items()
        if value not in _domains()[option]
    }
    assert ("--gate", "not_a_gate") in offenders, "planted out-of-domain gate value not caught"


def test_appendix_phase_table_is_the_state_machine() -> None:
    """§3.4's 18-row table, row by row, against ``PHASES``.

    The table is what students copy ``--phase`` values out of, so a slug in the
    wrong row is a live wrong answer. ⚙ marks the industrial-only phases, and the
    zone letters A/B/C/D are the doc's spelling of ``Zone``'s four values: the letter
    comes from ``Zone``'s declaration order, so a zone rename or a phase moved
    between zones fails here rather than quietly keeping a plausible letter.
    """
    zone_letters = ["A", "B", "C", "D"]
    assert len(zone_letters) == len(Zone)
    table = _read("12-附录-术语表与模板库.md")
    rows = [line for line in table.splitlines() if re.match(r"\|\s*\d+\s*\| [A-D] \| `", line)]
    assert len(rows) == len(PHASES) == 18, f"table has {len(rows)} rows, PHASES has {len(PHASES)}"
    industrial = {p.slug for p in PHASES if p.industrial}
    for phase, row in zip(PHASES, rows, strict=True):
        index, zone, cell = (c.strip() for c in row.split("|")[1:4])
        slug = re.search(r"`([a-z_]+)`", cell).group(1)
        assert slug == phase.slug, f"row {phase.index}: book says {slug}, code says {phase.slug}"
        assert index == str(phase.index), f"{slug}: row number {index}, code index {phase.index}"
        assert zone == zone_letters[list(Zone).index(phase.zone)], f"{slug}: zone {zone} vs {phase.zone}"
        assert ("⚙" in cell) is (slug in industrial), f"{slug}: ⚙ disagrees with Phase.industrial"
    assert len(industrial) == 3


def test_ticket_skips_exactly_the_industrial_phases() -> None:
    """``ticket 走 15 阶段`` and ``标 ⚙ 的 3 个`` both come from ``phases_for_profile``."""
    ticket = phases_for_profile(False)
    assert len(ticket) == 15
    assert {p.slug for p in PHASES} - {p.slug for p in ticket} == {p.slug for p in PHASES if p.industrial}


def test_gate_slug_lists_in_the_book_match_the_registry_as_sets() -> None:
    """The book lists general-first, the registry is industrial-first: compare sets.

    Three places enumerate the slugs (``12`` §3.2, ``03``'s table, ``07``'s
    industrial checklist). ``07`` claims 7 industrial gates; the registry's
    ``industrial_only`` flag is what makes that true.
    """
    registry = set(_gate_registry())
    general, industrial = _general_gates(), _industrial_gates()
    assert registry == general | industrial and not (general & industrial)

    assert set(_book_slugs("12-附录-术语表与模板库.md", "可用的 slug")) == general
    assert set(_book_slugs("12-附录-术语表与模板库.md", "第 3 列的 🏭")) == industrial

    assert set(_book_slugs("03-评估体系与通关门禁.md", "🏢 **通用")) == general
    assert set(_book_slugs("03-评估体系与通关门禁.md", "🏭 **工业专属")) == industrial

    seven = re.search(r"门禁全清单（(.+?)）", _book_line("07-实战剧本与案例库.md", "门禁全清单")).group(1)
    assert {s.strip(" `") for s in seven.split("/")} == industrial


def test_connector_claim_is_the_registry_split_by_profile() -> None:
    """``10 个数据连接器`` plus the 数据侧 5 / 工业侧 5 split.

    The industrial half is ``manufacturing.primary_connectors``; the data half is
    what is left of ``DataConnector.registry()`` — so ``documents`` counts as data
    side only while it stays outside every profile's primary list.
    """
    registry = set(DataConnector.registry())
    industrial = set(all_profiles()["manufacturing"].primary_connectors)
    assert len(registry) == 10
    assert len(industrial) == 5
    assert len(registry - industrial) == 5

    line = _book_line("01-课程设计说明书.md", "个数据连接器")
    halves = line.split("工业侧")
    assert len(halves) == 2, halves
    data_side = set(re.findall(r"`([a-z0-9_]+)`", halves[0].split("数据侧")[1]))
    factory_side = set(re.findall(r"`([a-z0-9_]+)`", halves[1]))
    assert data_side == registry - industrial, data_side
    assert factory_side == industrial, factory_side


def test_count_claims_appear_with_their_recorded_values() -> None:
    """Each recorded claim must be present exactly the recorded number of times.

    Asserting the *occurrence count* as well as the value is the point: a rewrite
    that deletes ``全部 10 个门禁`` must fail, not silently shrink the number of
    assertions the guard makes.
    """
    problems = []
    for rel, pattern, occurrences, expected in COUNT_CLAIMS:
        found = re.findall(pattern, _read(rel))
        got = [tuple(g) if isinstance(g, tuple) else (g,) for g in found]
        if len(got) != occurrences or got != [expected]:
            problems.append(f"{rel}: {pattern!r} -> {got or 'ABSENT'} (want {occurrences}x {expected})")
    assert not problems, "\n".join(problems)


def test_recorded_claim_values_are_the_code_truth() -> None:
    """The literals in ``COUNT_CLAIMS`` are checked against the code, separately.

    Splitting "what the book says" from "what the code does" into two assertions is
    what keeps either one honest: if a gate is added, this fails even though the
    book and the table above still agree with each other.

    Every claim is covered by exactly one of two channels — a value derived here from
    the code, or the name of an executed test that re-runs the tool and reads the
    number off its output. The coverage assertion is what stops a claim from landing
    in whichever channel happens to be unchecked.
    """
    tree = _command_tree()
    claims = {(rel, pattern): quoted for rel, pattern, _n, quoted in COUNT_CLAIMS}

    stations = {
        json.loads(line)["station"]
        for line in (REPO_ROOT / "examples" / "quickstart_manufacturing" / "station_samples.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    }
    registry = set(DataConnector.registry())
    industrial_side = set(all_profiles()["manufacturing"].primary_connectors)
    n_commands = str(len(tree[()][1]))
    n_gates = str(len(_gate_registry()))
    n_general = str(len(_general_gates()))
    n_industrial = str(len(_industrial_gates()))
    n_phases = str(len(PHASES))
    n_ticket_phases = str(len(phases_for_profile(False)))
    # 3 ⚙ phases, 7 🏭 gates — the book quotes both and they are easy to confuse
    n_industrial_phases = str(len([p for p in PHASES if p.industrial]))
    n_deploy_gates = str(len([p for p in PHASES if p.slug == "deploy"][0].gates))
    n_zones = str(len(list(Zone)))
    # the lab ledger's split: manual items are checked by a human, so they are kept
    # out of the scored denominator — 24 quotes both halves, so both are derived here
    n_manual = str(sum(sum(1 for c in lab.checks if isinstance(c, ManualCheck)) for lab in LABS))
    n_machine = str(sum(len(lab.checks) for lab in LABS) - int(n_manual))

    derived: dict[tuple[str, str], tuple[str, ...]] = {
        ("01-课程设计说明书.md", r"(\d+) 条命令的 CLI"): (n_commands,),
        ("12-附录-术语表与模板库.md", r"(\d+) 条命令"): (n_commands,),
        ("07-实战剧本与案例库.md", r"全部 (\d+) 个门禁"): (n_gates,),
        ("12-附录-术语表与模板库.md", r"全部 (\d+) 个门禁"): (n_gates,),
        ("12-附录-术语表与模板库.md", r"全部 (\d+) 行"): (n_gates,),
        ("12-附录-术语表与模板库.md", r"（共 (\d+) 个）"): (n_gates,),
        ("03-评估体系与通关门禁.md", r"那 (\d+) 个门禁"): (n_gates,),
        ("12-附录-术语表与模板库.md", r"通用 (\d+) 个"): (n_general,),
        ("03-评估体系与通关门禁.md", r"🏢 \*\*通用 (\d+) 个"): (n_general,),
        ("12-附录-术语表与模板库.md", r"工业专属 (\d+) 个"): (n_industrial,),
        ("03-评估体系与通关门禁.md", r"🏭 \*\*工业专属 (\d+) 个"): (n_industrial,),
        ("03-评估体系与通关门禁.md", r"(\d+) 个（🏢 通用 (\d+) \+ 🏭 工业专属 (\d+)）"): (
            n_gates,
            n_general,
            n_industrial,
        ),
        ("12-附录-术语表与模板库.md", r"（(\d+) 阶段全表）"): (n_phases,),
        ("12-附录-术语表与模板库.md", r"ticket 走 (\d+) 阶段"): (n_ticket_phases,),
        ("12-附录-术语表与模板库.md", r"标 ⚙ 的 (\d+) 个"): (n_industrial_phases,),
        ("07-实战剧本与案例库.md", r"跳过 (\d+) 个工业专属阶段，实走 (\d+) 阶段"): (
            n_industrial_phases,
            n_ticket_phases,
        ),
        ("01-课程设计说明书.md", r"(\d+) 个数据连接器"): (str(len(registry)),),
        ("01-课程设计说明书.md", r"数据侧 (\d+) 种"): (str(len(registry - industrial_side)),),
        ("01-课程设计说明书.md", r"工业侧 (\d+) 种"): (str(len(industrial_side)),),
        # "三个" is the book's spelling of deploy's gate list; the numeral is the
        # claim and the list itself is pinned below, so neither side drifts alone.
        ("07-实战剧本与案例库.md", r"deploy 阶段有(\w+)门禁"): ("三个",),
        # the aggregate the lesson quotes is over the sample file's own station set
        ("07-实战剧本与案例库.md", r"(\d+) 个工位"): (str(len(stations)),),
        # 24 · 开源对标：它把课堂侧数字写进对外文案，所以每个数字都要有真值通道
        ("24-开源对标与来源清单.md", r"↔ 我们的 (\d+) 区 / (\d+) 阶段 / (\d+) 个门禁"): (
            n_zones,
            n_phases,
            n_gates,
        ),
        ("24-开源对标与来源清单.md", r"合计：(\d+) 个机器判分项 \+ (\d+) 个人工项"): (n_machine, n_manual),
        ("24-开源对标与来源清单.md", r"报 \*\*(\d+) 项机器判分\*\*"): (n_machine,),
        # "表格 10 行" is gate list's own row count, i.e. the registry again
        ("24-开源对标与来源清单.md", r"表格 (\d+) 行"): (n_gates,),
        ("24-开源对标与来源清单.md", r"⚙ = (\d+) 个工业专属阶段"): (n_industrial_phases,),
        ("24-开源对标与来源清单.md", r"deploy 阶段有 (\d+) 个门禁"): (n_deploy_gates,),
        ("24-开源对标与来源清单.md", r"实走 (\d+) 阶段"): (n_ticket_phases,),
    }
    pinned_elsewhere: dict[tuple[str, str], str] = {
        (
            "12-附录-术语表与模板库.md",
            r"(\d+) 个虚构档案",
        ): "test_appendix_engagement_table_matches_a_pristine_seed",
        ("07-实战剧本与案例库.md", r"(\d+) 条 blocker"): "test_southbay_deploy_is_blocked_on_three_gates",
    }

    uncovered = set(claims) - set(derived) - set(pinned_elsewhere)
    invented = (set(derived) | set(pinned_elsewhere)) - set(claims)
    assert not uncovered and not invented, f"claim lost its truth channel: {uncovered} / {invented}"
    stale = {k: (claims[k], derived[k]) for k in derived if claims[k] != derived[k]}
    assert not stale, "book/claims disagree with the code:\n" + "\n".join(
        f"{rel} {pattern}: book {book}, code {code}" for (rel, pattern), (book, code) in stale.items()
    )
    for key, test_name in pinned_elsewhere.items():
        assert callable(globals().get(test_name)), f"{key}: the executed guard {test_name!r} is gone"

    assert [p for p in PHASES if p.slug == "deploy"][0].gates == (
        "fat_sat",
        "functional_safety",
        "conformity",
    )
    assert len(_industrial_gates()) == 7 and len(_general_gates()) == 3


def test_lesson_census_matches_the_wheel_note() -> None:
    """``pyproject.toml`` records what ``uv build --wheel`` packs; the book must still be there.

    ``test_architecture_guard.py`` pins the ``force-include`` mapping itself; this
    pins the *count sentence* next to it, which is the half that rots silently when
    a lesson lands and nobody re-measures.
    """
    top = sorted(BOOK.glob("*.md"))
    labs = sorted((BOOK / "labs").rglob("*.md"))
    en = sorted((BOOK / "en").rglob("*.md"))
    total = sorted(BOOK.rglob("*.md"))
    assert len(total) == len(top) + len(labs) + len(en) == 47
    assert (len(top), len(labs), len(en)) == (26, 20, 1)

    note = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    claim = re.search(
        r"course-level-1/ holds (\d+) \*\.md\n# \((\d+) top-level lessons \+ (\d+) labs \+ (\d+) en\)", note
    )
    assert claim, "the wheel note is gone or reworded — re-measure it and restore the pattern"
    assert claim.groups() == ("47", "26", "20", "1"), claim.groups()


def test_every_version_claim_in_the_book_is_the_installed_release() -> None:
    """``v0.1.0`` is quoted as the measured baseline; a bump must move all of it.

    26 occurrences across 13 files carried the baseline when this guard landed. The
    floor is there so a bulk edit that *drops* the version strings (leaving the
    book unattributed, which is the thing the credibility tiers exist to prevent)
    fails as loudly as one that edits them.
    """
    versions = {
        m.group(1)
        for path in BOOK.rglob("*.md")
        for m in re.finditer(r"[vV](\d+\.\d+\.\d+)", path.read_text(encoding="utf-8"))
    }
    assert versions == {__version__}, f"book quotes {sorted(versions)}, package is {__version__}"
    count = sum(
        len(re.findall(rf"v{re.escape(__version__)}", path.read_text(encoding="utf-8")))
        for path in BOOK.rglob("*.md")
    )
    assert count >= 20, f"only {count} baseline attributions left in the book"


# -------------------------------------------------------------------------- executed


def _cli(home: Path, *args: str, columns: int = 200) -> tuple[int, str]:
    """Run the real console the way a student does, in *home*, and keep repo clean.

    ``COLUMNS`` matters: rich truncates ids at the terminal width, and several
    lessons instruct ``COLUMNS=200`` because of it.
    """
    env = {**os.environ, "FDE_SCOPE_HOME": str(home), "COLUMNS": str(columns)}
    proc = subprocess.run(
        [CLI, *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


@pytest.fixture(scope="module")
def seeded_home(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A pristine ``python examples/seed_mock_engagements.py`` home — the only evidence the appendix table may cite.

    Origin: a home polluted by earlier ``gate check --gate site_survey`` probes
    made the seed01 engagement look like it carried a fourth ``✅`` and that number
    went into the book. Fresh seed only, module scope, never mutated in place
    (mutating tests copy it).
    """
    home = tmp_path_factory.mktemp("course-seed-home")
    proc = subprocess.run(
        [sys.executable, str(SEED_SCRIPT)],
        cwd=REPO_ROOT,
        env={**os.environ, "FDE_SCOPE_HOME": str(home)},
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert len(list((home / ".fde_scope" / "engagements").glob("*.json"))) == 10
    return home


@pytest.fixture
def scratch_home(tmp_path: Path) -> Path:
    """An empty home for commands that create state."""
    home = tmp_path / "home"
    home.mkdir()
    return home


@pytest.fixture
def seeded_copy(seeded_home: Path, tmp_path: Path) -> Path:
    home = tmp_path / "seed-copy"
    shutil.copytree(seeded_home, home)
    return home


def _gate_rows(out: str) -> list[tuple[str, str]]:
    """``(slug, ✅|❌)`` from the ``Gate records`` table ``engage status`` prints."""
    return re.findall(r"│ ([a-z_]+)\s*│ (✅|❌)\s*│", out)


def test_both_documented_entry_points_print_the_quoted_version() -> None:
    """``fde-scope --version`` and ``python -m fde_scope --version``, both in the book."""
    for argv in ([CLI, "--version"], [sys.executable, "-m", "fde_scope", "--version"]):
        env = {**os.environ, "COLUMNS": "200"}
        proc = subprocess.run(argv, cwd=REPO_ROOT, env=env, capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == f"fde-scope {__version__}"


def test_gate_list_prints_ten_rows_seven_industrial_three_general(scratch_home: Path) -> None:
    """``12`` §3.2: ``gate list`` prints all 10 rows, 🏭 for 7, 🏢 for 3 — under both profiles.

    The emoji is the ``industrial_only`` *column*, not a prefix on the slug, so the
    row regex reads slug and flag from their own cells — measured shape, and the
    reason the book's own 🏭/🏢 slug lists are compared as sets instead.
    """
    registry = _gate_registry()
    for profile in ("manufacturing", "ticket"):
        rc, out = _cli(scratch_home, "gate", "list", "--profile", profile)
        assert rc == 0, out
        assert f"FDE Scope v{__version__} — gates · {profile}" in out, out.splitlines()[0]
        rows = re.findall(r"│ ([a-z_]+)\s+│ [^│]+│ (🏭|🏢)\s*│", out)
        assert [slug for slug, _ in rows] == list(registry), f"{profile}: {rows}"
        assert {slug for slug, mark in rows if mark == "🏭"} == _industrial_gates(), profile
        assert {slug for slug, mark in rows if mark == "🏢"} == _general_gates(), profile


def test_ticket_engagement_passes_an_industrial_gate_vacuously(scratch_home: Path) -> None:
    """The lesson's sharpest edge: a ticket profile reports ``✅ PASS`` for a gate it never tests.

    ``12`` §3.2 keeps the word "空过" attached to this output; if the tool ever
    starts refusing industrial gates on ticket profiles, that prose becomes wrong and
    this test is where we find out.
    """
    rc, out = _cli(scratch_home, "engage", "init", "--customer", "tmp", "--profile", "ticket")
    assert rc == 0, out
    assert "eng-tmp-ticket" in out, out  # the id formula 12 §3.4 documents
    rc, out = _cli(scratch_home, "gate", "check", "eng-tmp-ticket", "--gate", "site_survey")
    assert rc == 0, out
    assert "✅ PASS" in out and "site_survey" in out


def test_a_fresh_engagement_reports_no_gate_for_its_phase(scratch_home: Path) -> None:
    """``12`` §3.2 quotes ``Phase 'qualification' has no gate.`` as *normal* output (rc 0)."""
    _cli(scratch_home, "engage", "init", "--customer", "tmp", "--profile", "ticket")
    rc, out = _cli(scratch_home, "gate", "check", "eng-tmp-ticket")
    assert rc == 0, out
    assert "Phase 'qualification' has no gate." in out


def test_unknown_gate_is_refused_not_ignored(scratch_home: Path) -> None:
    """D4 teaches the exit code, not a failure: ``Unknown gate: 'corpus'`` must be loud."""
    _cli(scratch_home, "engage", "init", "--customer", "tmp", "--profile", "ticket")
    rc, out = _cli(scratch_home, "gate", "check", "eng-tmp-ticket", "--gate", "corpus")
    assert rc != 0, out
    assert "Unknown gate" in out and "corpus" in out


def test_southbay_deploy_is_blocked_on_three_gates(seeded_copy: Path) -> None:
    """``07`` §剧本二: three red gates, and "仅 conformity 一家就报了 3 条 blocker"."""
    eng = "eng-southbay-manufacturing-seed03"
    rc, out = _cli(seeded_copy, "gate", "check", eng)
    assert rc != 0 and "❌ BLOCKED · gate=fat_sat" in out, out
    assert "🚫 SAT (Site Acceptance Test) 未执行或未记录" in out
    rc, out = _cli(seeded_copy, "gate", "check", eng, "--gate", "functional_safety")
    assert rc != 0 and out.count("🚫") == 1, out
    rc, out = _cli(seeded_copy, "gate", "check", eng, "--gate", "conformity")
    assert rc != 0 and out.count("🚫") == 3, out
    # the three gates this lesson calls "全红" are the deploy phase's own list,
    # read from the state machine rather than inferred from the output
    assert [p for p in PHASES if p.slug == "deploy"][0].gates == (
        "fat_sat",
        "functional_safety",
        "conformity",
    )


def test_columns_80_truncates_ids_which_is_why_the_book_demands_200(seeded_copy: Path) -> None:
    """``12`` §3.2: without ``COLUMNS=200`` the ids students copy are unreadable.

    Measured against a seeded id, not a short one: ``eng-tmp-ticket`` fits inside 80
    columns and proves nothing. ``eng-adnova-ticket-seed06`` renders as
    ``eng-adnova-t…`` at the default width.
    """
    eng = "eng-adnova-ticket-seed06"
    rc, narrow = _cli(seeded_copy, "engage", "list", columns=80)
    assert rc == 0, narrow
    assert "eng-adnova-t…" in narrow, narrow
    assert eng not in narrow, f"{eng} survived an 80-column terminal"
    rc, wide = _cli(seeded_copy, "engage", "list", columns=200)
    assert eng in wide, wide


def test_progress_line_prints_15_for_ticket_and_18_for_manufacturing(seeded_copy: Path) -> None:
    """The tool itself states the phase budget the book teaches."""
    rc, out = _cli(seeded_copy, "engage", "status", "eng-teaverse-ticket-seed01")
    assert rc == 0 and "progress: 15 phases visible" in out, out
    rc, out = _cli(seeded_copy, "engage", "status", "eng-horizon-manufacturing-seed08")
    assert rc == 0 and "progress: 18 phases visible" in out, out


def test_appendix_engagement_table_matches_a_pristine_seed(seeded_copy: Path) -> None:
    """All ten rows of the ``12` §3.2 id table, verified against ``engage status`` output.

    The counting rule the appendix states — the number is the *row count* of the
    printed Gate records table, ✅ and ❌ separately — is what this implements, so
    the guard and the lesson cannot drift apart on methodology, only on facts.
    """
    table = _read("12-附录-术语表与模板库.md")
    rows = re.findall(
        r"^\| `(eng-[a-z0-9-]+)` \| [^|]*\| (\w+) \| `([a-z_]+)`[^|]*\| ([^|]*)\|",
        table,
        re.M,
    )
    assert len(rows) == 10, f"appendix table has {len(rows)} rows, expected 10"
    problems = []
    for eng, profile, phase, gate_cell in rows:
        rc, out = _cli(seeded_copy, "engage", "status", eng)
        assert rc == 0, f"{eng}: {out}"
        passed = sum(1 for _, mark in _gate_rows(out) if mark == "✅")
        blocked = sum(1 for _, mark in _gate_rows(out) if mark == "❌")
        want_pass = int(re.search(r"✅(\d+)", gate_cell).group(1)) if "✅" in gate_cell else 0
        want_fail = int(re.search(r"❌(\d+)", gate_cell).group(1)) if "❌" in gate_cell else 0
        tool_profile = re.search(r"profile: (\w+)", out).group(1)
        tool_phase = re.search(r"phase: ([a-z_]+)", out).group(1)
        if (tool_profile, tool_phase, passed, blocked) != (profile, phase, want_pass, want_fail):
            problems.append(
                f"{eng}: book {profile}/{phase} ✅{want_pass} ❌{want_fail} "
                f"but the tool says {tool_profile}/{tool_phase} ✅{passed} ❌{blocked}"
            )
    assert not problems, "\n".join(problems)


def test_the_finished_engagement_carried_exactly_the_three_general_gates(seeded_copy: Path) -> None:
    """``eng-teaverse-ticket-seed01`` ends with ✅3 = the general trio, no industrial rows.

    Origin: an earlier revision of the appendix credited this engagement with a
    vacuous ``site_survey`` pass it does not have. The distinction is the whole
    teaching point of the ⚙/空过 column, so it is pinned as a set, not a count.
    """
    rc, out = _cli(seeded_copy, "engage", "status", "eng-teaverse-ticket-seed01")
    assert rc == 0, out
    rows = _gate_rows(out)
    assert {slug for slug, mark in rows if mark == "✅"} == _general_gates()
    assert all(mark == "✅" for _, mark in rows), rows
    assert not (_industrial_gates() & {slug for slug, _ in rows}), "no vacuous industrial row"


def test_kpi_numbers_in_07_come_from_the_five_station_sample_set(scratch_home: Path) -> None:
    """``grasp_success_rate=0.7931`` aggregate, and ``0.7333`` / ``0.0321`` for one station."""
    samples = REPO_ROOT / "examples" / "quickstart_manufacturing" / "station_samples.jsonl"
    stations = {json.loads(line)["station"] for line in samples.read_text().splitlines() if line.strip()}
    assert len(stations) == 5, stations

    _cli(scratch_home, "engage", "init", "--customer", "tmp", "--profile", "manufacturing")
    rc, out = _cli(scratch_home, "kpi", "eng-tmp-manufacturing", "--samples", str(samples), "--json")
    assert rc == 0, out
    aggregate = json.loads(out)["kpis"]
    assert round(aggregate["grasp_success_rate"], 4) == 0.7931, aggregate

    one = scratch_home / "assy.jsonl"
    one.write_text(
        "\n".join(line for line in samples.read_text().splitlines() if "ASSY-HUMANOID-01" in line) + "\n",
        encoding="utf-8",
    )
    rc, out = _cli(scratch_home, "kpi", "eng-tmp-manufacturing", "--samples", str(one), "--json")
    assert rc == 0, out
    kpis = json.loads(out)["kpis"]
    assert round(kpis["grasp_success_rate"], 4) == 0.7333, kpis
    assert round(kpis["collision_intervention_rate"], 4) == 0.0321, kpis


def test_d7_handoff_signoff_progression_matches_the_lesson(seeded_copy: Path) -> None:
    """The four-beat签字演练 in ``22`` §幕2–幕4, exit codes included.

    Order matters and is asserted in one test: the gate reads live state, so the
    pass at the end only means anything if the two blocks happened first.
    """
    eng = "eng-teaverse-ticket-seed01"
    rc, out = _cli(seeded_copy, "handoff", eng)
    assert rc == 0, out
    assert "- eval report: —" in out and "- training material: —" in out
    assert "- customer accepted: ❌" in out

    rc, out = _cli(seeded_copy, "gate", "check", eng, "--gate", "handoff_signoff")
    assert rc == 1, out
    assert "🚫 移交包缺失: ['eval_report', 'training_material']" in out, out
    assert "🚫 客户尚未书面接受移交——不得退场" in out

    report = REPO_ROOT / "examples" / "quickstart_csv" / "sample_tickets.csv"
    rc, out = _cli(
        seeded_copy,
        "handoff",
        eng,
        "--eval-report",
        str(report),
        "--training-material",
        str(report),
        "--accept",
    )
    assert rc == 0, out
    assert "- customer accepted: ✅" in out
    rc, out = _cli(seeded_copy, "gate", "check", eng, "--gate", "handoff_signoff")
    assert rc == 0 and "✅ PASS · gate=handoff_signoff" in out, out


def test_the_handoff_package_is_a_snapshot_not_a_live_view(scratch_home: Path) -> None:
    """``labs/D7`` 第 1–5 项：补了 SLO 还要第二次 ``handoff``，否则第 5 项一直红。

    The whole teaching point of D7 is that the gate reads the *package*, so this walks
    the exact lab sequence and asserts the blocker text at each step. ``移交包未生成``
    before any assembly, the three-item list once a bare package exists, the single
    ``['slo_definition']`` after the other two are filled, that same single item after
    ``engage slo add`` (the snapshot has not been re-taken), and PASS only after the
    second ``handoff``. If ``HandoffSignoffGate`` ever stops reading
    ``slo_definition``, or ``build_handoff_package`` starts writing live SLO state
    instead of a snapshot, one of those five lines goes wrong.
    """
    eng = "eng-tmp-ticket"
    _cli(scratch_home, "engage", "init", "--customer", "tmp", "--profile", "ticket")

    rc, out = _cli(scratch_home, "gate", "check", eng, "--gate", "handoff_signoff")
    assert rc == 1 and "🚫 移交包未生成" in out, out

    rc, out = _cli(scratch_home, "handoff", eng)
    assert rc == 0, out
    rc, out = _cli(scratch_home, "gate", "check", eng, "--gate", "handoff_signoff")
    assert rc == 1, out
    assert "🚫 移交包缺失: ['eval_report', 'slo_definition', 'training_material']" in out, out

    report = REPO_ROOT / "examples" / "quickstart_csv" / "sample_tickets.csv"
    full = ("handoff", eng, "--eval-report", str(report), "--training-material", "店长培训包 v2", "--accept")
    rc, out = _cli(scratch_home, *full)
    assert rc == 0 and "- customer accepted: ✅" in out, out
    rc, out = _cli(scratch_home, "gate", "check", eng, "--gate", "handoff_signoff")
    assert rc == 1 and "🚫 移交包缺失: ['slo_definition']" in out, out

    rc, out = _cli(scratch_home, "engage", "slo", "add", eng, "--name", "自动解决率", "--target", ">=40%")
    assert rc == 0 and "已定义" in out, out
    rc, out = _cli(scratch_home, "gate", "check", eng, "--gate", "handoff_signoff")
    assert rc == 1 and "🚫 移交包缺失: ['slo_definition']" in out, (
        "adding the SLO must not re-take the snapshot"
    )

    rc, out = _cli(scratch_home, *full)
    assert rc == 0, out
    rc, out = _cli(scratch_home, "gate", "check", eng, "--gate", "handoff_signoff", "--json")
    assert rc == 0, out
    verdict = json.loads(out)
    assert verdict["passed"] is True and verdict["blockers"] == [], verdict
    # G7③/④ are advisory: four pieces + a signature is what blocks, so a thin
    # handoff PASSES. These two warnings are the whole counterweight — the book
    # quotes them, so they are pinned verbatim rather than by count.
    assert verdict["warnings"] == [
        "移交包未记录适用边界（G7③）：用 --boundary 写明，否则接手方无人知道边界与停手条件",
        "移交包未记录终止条件（G7④）：用 --termination 写明，否则接手方无人知道边界与停手条件",
    ], verdict
    rc, txt = _cli(scratch_home, "gate", "check", eng, "--gate", "handoff_signoff")
    assert rc == 0 and txt.count("⚠️") == 2, txt

    filled = full + (
        "--boundary",
        "新开店首周不在射程内",
        "--termination",
        "bad_case_rate 连续两窗口破线即停用",
    )
    rc, out = _cli(scratch_home, *filled)
    assert rc == 0 and "- boundary (G7③): 新开店首周不在射程内" in out, out
    rc, out = _cli(scratch_home, "gate", "check", eng, "--gate", "handoff_signoff", "--json")
    assert json.loads(out)["warnings"] == [], out

    # The plain re-assembly must not revoke the free text. ``handoff`` is re-run to
    # refresh the SLO snapshot two lines above, and silently losing G7③④ in that
    # second call is how a signed package ends up with no boundary at all.
    rc, out = _cli(scratch_home, *full)
    assert rc == 0 and "- boundary (G7③): 新开店首周不在射程内" in out, f"carry-forward broken: {out}"
    assert "- termination (G7④): bad_case_rate 连续两窗口破线即停用" in out, out


def test_corpus_report_lands_where_the_command_is_told(scratch_home: Path) -> None:
    """``corpus --input … --out …`` is CWD-relative, so the guard passes an absolute path.

    Worth pinning: the book's ``--out reports/alarm_corpus_report.html`` writes into
    whatever directory the student is standing in, and this test would otherwise
    litter the repo checkout on every run.
    """
    out = scratch_home / "reports" / "alarm_corpus_report.html"
    out.parent.mkdir()
    rc, text = _cli(
        scratch_home,
        "corpus",
        "--input",
        str(REPO_ROOT / "examples" / "quickstart_manufacturing" / "alarm_corpus.jsonl"),
        "--out",
        str(out),
    )
    assert rc == 0, text
    assert out.exists() and out.stat().st_size > 1000, out.stat().st_size
