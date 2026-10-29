"""Check vocabulary for the course labs — six dataclasses, no behaviour.

A check states *one* thing a day's deliverable must satisfy, in the same
language the tool already speaks (exit codes and ``--json`` payloads). Keeping
the vocabulary here, separate from the D1..D8 registry in
:mod:`fde_scope.course.catalog` and the execution engine in
:mod:`fde_scope.course.verifier`, is what lets a reader audit a lab's rubric
without reading an interpreter.

Five machine-checkable kinds and one honest escape hatch:

``CommandCheck``     a command ran, exited as expected, and said something
``MetricCheck``      a number inside a ``--json`` payload has this value
``ArtifactCheck``    this file exists (and contains this / no longer contains this)
``DeterminismCheck`` the same command twice yields the same value — G5's 可复现
``ManualCheck``      authored prose — graded by the human rubric, never by us

The last kind is not a gap in the design. D2's 委托单, D4's 客户话术 and D7's
技能卡 are writing; a string match on them would score *vocabulary*, not
quality, and the course's own 诚实标注 rule (`03` §4) forbids dressing an
ungraded artifact up as a passed gate. ``ManualCheck`` therefore reports
``manual`` and is **excluded from the score denominator** — a lab scoring
``7/7`` means seven machine-checked facts, not "everything about today".
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

Status = Literal["pass", "fail", "manual"]


@dataclass(frozen=True)
class Command:
    """One CLI invocation, expressed as argv *after* the ``fde-scope`` prefix.

    Tokens like ``{{fixtures}}`` are substituted by the verifier at run time
    (see :mod:`fde_scope.course.verifier`), which is what lets the same argv
    work from a repo checkout, an installed wheel, and a CI job.

    ``capture`` pairs a token name with a regex containing one group, matched
    against this command's merged output; the group is then available to later
    commands as ``{{<name>}}``. D7 needs it because ``skill add`` returns a
    server-generated id (AGENTS.md invariant 2 — the student cannot choose it,
    so the lab cannot hard-code it either). Kept as a tuple of pairs, not a
    dict, so ``Command`` stays hashable and the registry stays a literal.

    ``read_only`` licenses the verifier to run the command once and reuse the
    output across checks, and the property that earns that name is
    **idempotence**, not "touches no files": ``connect`` is cached and does write
    ``<data root>/samples/preview.json`` (measured v0.1.0 — byte-identical stdout
    across three runs, nothing into the working directory, same preview digest),
    which is exactly why reusing its output is safe. Anything whose *result*
    depends on the world it sees — ``engage *add``, ``gate check`` (it records the
    outcome and can sink a draft skill) — must stay False, so a later check reads
    the world as it is now rather than as it was earlier in the run.
    """

    argv: tuple[str, ...] = ()
    exit_code: int = 0
    timeout: int = 90
    capture: tuple[tuple[str, str], ...] = ()
    read_only: bool = False

    def render(self, prefix: tuple[str, ...] = ("fde-scope",)) -> str:
        """The line a student would type — used in reports and in ``check.sh``."""
        return " ".join([*prefix, *self.argv])


@dataclass(frozen=True)
class Check:
    """Common identity for every check: what it asks, and which gate it serves."""

    id: str
    gate: str
    ask: str
    hint: str = ""


@dataclass(frozen=True)
class CommandCheck(Check):
    """The command itself is the evidence.

    ``contains`` matches against merged stdout+stderr with rich markup
    stripped and ``COLUMNS=200`` set, so a table cell can't break a substring
    the way it does at the default 80 columns.
    """

    command: Command = field(default_factory=Command)
    contains: tuple[str, ...] = ()
    regex: tuple[str, ...] = ()


@dataclass(frozen=True)
class MetricCheck(Check):
    """One number out of a JSON payload.

    The payload comes from the command's stdout, or from ``file`` when the
    tool writes the JSON to disk instead of printing it — which is what
    ``corpus`` (``<out>.json``) and ``connect`` (``<data root>/samples/
    preview.json``) do. Reading those files rather than adding ``--json``
    flags keeps the lab on the contract the CLI already has.

    ``path`` is dot-separated, and dict keys may be Chinese
    (``bad_cases.by_category.门店投诉``). ``#len`` as the final segment scores
    the length of a list or dict. ``approx`` is compared with ``tol``, which
    defaults to 1e-4 — the same precision ``fde-scope kpi`` prints (``cli.py``
    formats with ``.4f``), so the number in the lesson and the number in the
    lab are the same literal.
    """

    command: Command | None = None
    file: str = ""
    path: str = ""
    approx: float | None = None
    tol: float = 1e-4
    gte: float | None = None
    lte: float | None = None
    one_of: tuple[float | str | bool, ...] = ()


@dataclass(frozen=True)
class ArtifactCheck(Check):
    """A file the student must be able to point at afterwards.

    ``not_contains`` carries the other half of honesty: D7's 四件套 includes two
    documents the student writes, shipped as a ``starter/`` template full of
    ``TODO``. Asserting the file *exists* would grade a copy of a template, so
    the check asserts the placeholders are gone. A cold lab run therefore fails
    that check on purpose — and the hint says which file to open.
    """

    command: Command | None = None
    file: str = ""
    contains: tuple[str, ...] = ()
    regex: tuple[str, ...] = ()
    not_contains: tuple[str, ...] = ()
    min_bytes: int = 1


@dataclass(frozen=True)
class DeterminismCheck(Check):
    """G5 ①: "同命令同结果可复现" is a property, not a number.

    The command runs twice and ``path`` (dot-separated, same grammar as
    :class:`MetricCheck`) is compared between the runs; with no ``path`` the
    whole stripped output is compared. Mock eval is seeded
    (``MockReplyFn(accuracy=0.9, seed=0)`` → ``random.Random(seed)``), so a
    drifting value here means the *pipeline* is not reproducible — the exact
    failure a demo-only portfolio hides.
    """

    command: Command = field(default_factory=Command)
    path: str = ""


@dataclass(frozen=True)
class ManualCheck(Check):
    """Authored deliverable — the human rubric owns it, and says so."""

    rubric: str = ""


@dataclass
class CheckResult:
    """Outcome of one check, written for a reader who has to fix it."""

    id: str
    gate: str
    ask: str
    status: Status
    detail: str = ""
    hint: str = ""
    command: str = ""

    @property
    def scored(self) -> bool:
        return self.status in ("pass", "fail")

    def line(self) -> str:
        mark = {"pass": "✅", "fail": "❌", "manual": "📝"}[self.status]
        out = [f"{mark} [{self.gate}/{self.id}] {self.ask}"]
        if self.detail:
            out.append(f"      {self.detail}")
        if self.command:
            out.append(f"      $ {self.command}")
        if self.status == "fail" and self.hint:
            out.append(f"      💡 {self.hint}")
        return "\n".join(out)


def matches_any(text: str, needles: tuple[str, ...]) -> str | None:
    """Return the first needle missing from ``text`` (``None`` if all present)."""
    for needle in needles:
        if needle not in text:
            return needle
    return None


def first_missing_regex(text: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        if not re.search(pattern, text):
            return pattern
    return None


def first_present(text: str, needles: tuple[str, ...]) -> str | None:
    """Return the first needle found in ``text`` (``None`` if none are).

    The inverse of :func:`matches_any`, used by ``not_contains``: a template
    placeholder that is still there *is* the failure, and naming it is the fix.
    """
    for needle in needles:
        if needle in text:
            return needle
    return None
