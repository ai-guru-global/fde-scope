"""Run one day's checks against the **real** CLI, in a throwaway workspace.

Why a subprocess instead of calling the Python API: the lesson tells a student
to type ``fde-scope gate check eng-…`` and to read what comes back. If the
grader imported ``evaluate_phase_gates()`` directly it could go green while the
command the student actually runs prints something else — the exact failure
mode a "course that self-grades" is most likely to hide. So every check shells
out to the same entry point the book teaches, and asserts on its exit code, its
printed text, or the JSON it writes.

Three properties the engine keeps honest:

* **Isolation.** Each lab runs in a fresh scratch directory with its own
  ``FDE_SCOPE_HOME`` (see :mod:`fde_scope.paths`: the override is rule 1), so
  ``course check D5`` works on a cold machine and a student's real engagements
  are never touched. No lab can pass because yesterday's lab left state behind.
* **Substitution, not hardcoding.** ``{{home}}``, ``{{out}}``, ``{{eid}}`` and
  ``{{skill_id}}`` (captured out of a command's own output) are filled in at run
  time, because ids are server-generated (AGENTS.md invariant 2).
* **An honest denominator.** ``ManualCheck`` results are reported and scored
  ``manual`` — excluded from the denominator, never silently counted as passed.

``CommandCheck``/``MetricCheck``/… carry no behaviour of their own; all of it
lives here, which is what lets a reader audit a rubric in
:mod:`fde_scope.course.catalog` without reading an interpreter.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .catalog import Lab, lab_for
from .checks import (  # noqa: TC001 — public re-export, see __all__
    ArtifactCheck,
    Check,
    CheckResult,
    Command,
    CommandCheck,
    DeterminismCheck,
    ManualCheck,
    MetricCheck,
    Status,
    first_missing_regex,
    first_present,
    matches_any,
)

__all__ = [
    "CheckResult",
    "LabResult",
    "Status",
    "cli_prefix",
    "draft_dir",
    "labs_root",
    "run_all",
    "run_lab",
]

#: every lab shares this so ``{{shared}}/fixtures`` stays one copy of the data
_LABS_DIRNAME = "labs"
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_TIMEOUT_EXIT = 124


def labs_root() -> Path:
    """``course-level-1/labs`` — repo checkout preferred, wheel copy fallback.

    Same resolution order as the in-app course reader
    (``fde_scope/web/course.py::_choose_root``): editing a lesson in a checkout
    must be what the verifier runs, and an installed wheel must still be able to
    grade. ``course-level-1`` is force-included in the wheel by
    ``pyproject.toml``, so the labs ship with the book.
    """
    here = Path(__file__).resolve()
    repo = here.parents[2] / "course-level-1" / _LABS_DIRNAME
    if repo.is_dir():
        return repo
    return here.parents[1] / "_data" / "course-level-1" / _LABS_DIRNAME


def cli_prefix() -> tuple[str, ...]:
    """How to invoke the CLI under test — console script only when it is ours.

    ``python -m fde_scope`` (AGENTS.md's ``fde_scope/__main__.py`` shim) is the
    default: it is guaranteed to be *this* interpreter's package, so a stale
    global ``fde-scope`` on ``PATH`` cannot grade a lab against the wrong build.
    """
    return (sys.executable, "-m", "fde_scope")


def draft_dir(day: str) -> Path:
    """Where the student's *own writing* lives: ``<data root>/course-labs/<day>``.

    Tool-produced artifacts are graded inside the throwaway workspace, because
    that is what proves the command ran. D6's Runbook and D7's 验收清单 are the
    opposite: documents a student edits over hours. Deleting them at the end of
    a run would score nothing, so they sit in the data root instead — and a cold
    run honestly fails the ``not_contains=("TODO",)`` check with a hint naming
    this directory.

    Absolute on purpose: :func:`fde_scope.paths.data_root` deliberately falls
    back to a *relative* CWD (rule 4), and a hint that said "edit
    ``course-labs/D6``" would point at whatever directory the student happened
    to be standing in. Grading the same file twice from two directories must
    give the same answer.
    """
    from .. import paths

    return (paths.data_root() / "course-labs" / day).expanduser().resolve()


def _seed_drafts(day: str, target: Path) -> None:
    """Copy ``labs/<day>/starter/`` into *target*, never overwriting a student's edits."""
    target.mkdir(parents=True, exist_ok=True)
    starter = labs_root() / day / "starter"
    if not starter.is_dir():
        return
    from .. import fsutil

    for source in sorted(starter.iterdir()):
        if source.is_file() and not (target / source.name).exists():
            fsutil.atomic_write_bytes(target / source.name, source.read_bytes())


def _strip(text: str) -> str:
    return _ANSI.sub("", text or "")


def _extract_json(text: str) -> Any | None:
    """First balanced JSON document in ``text``, or ``None``.

    Needed because several commands print a banner/table *before* their JSON
    (``skill add``, ``deploy``, ``eval``), so ``json.loads(stdout)`` is not an
    option and the labs must not grow a ``--json`` flag just to be parseable.
    """
    for index, char in enumerate(text):
        if char in "{[":
            candidate = _scan(text, index)
            if candidate is not None:
                try:
                    return json.loads(candidate)
                except ValueError:
                    continue
    return None


def _scan(text: str, start: int) -> str | None:
    """Balanced-brace slice from ``start``, honouring strings and escapes."""
    opener = text[start]
    closer = {"{": "}", "[": "]"}[opener]
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _resolve(payload: Any, path: str) -> Any:
    """Dot path with a trailing ``#len`` — dict keys may be Chinese.

    ``bad_cases.by_category.门店投诉`` and ``splits.train#len`` are the two shapes
    the lessons actually quote, so the vocabulary stays the book's.
    """
    current = payload
    segments = path.split(".")
    length = segments[-1].endswith("#len")
    if length:
        tail = segments.pop()[: -len("#len")].strip(".")
        if tail:
            segments.append(tail)
    for segment in segments:
        if not segment:
            continue
        if isinstance(current, dict):
            if segment not in current:
                return None
            current = current[segment]
        elif isinstance(current, list):
            if not segment.isdigit() or int(segment) >= len(current):
                return None
            current = current[int(segment)]
        else:
            return None
    if length:
        if isinstance(current, (list, dict, str)) or current is None:
            return 0 if current is None else len(current)
        return None
    return current


@dataclass
class LabWorkspace:
    """One scratch run: paths, token table, and the output cache."""

    lab: Lab
    root: Path
    keep: bool = False
    verbose: bool = False
    _cache: dict[tuple[str, ...], tuple[int, str]] = field(default_factory=dict, repr=False)
    _tokens: dict[str, str] = field(default_factory=dict, repr=False)
    _unresolved: list[str] = field(default_factory=list, repr=False)

    @classmethod
    def create(cls, lab: Lab, keep: bool = False, verbose: bool = False) -> LabWorkspace:
        root = Path(tempfile.mkdtemp(prefix=f"fde-lab-{lab.day}-"))
        workspace = cls(lab=lab, root=root, keep=keep, verbose=verbose)
        drafts = draft_dir(lab.day)
        workspace._tokens = {
            "root": str(root),
            "home": str(root / "data"),
            "workspace": str(root / "work"),
            "out": str(root / "out"),
            "lab": str(labs_root() / lab.day),
            "shared": str(labs_root() / "_shared"),
            "fixtures": str(labs_root() / lab.day / "fixtures"),
            "drafts": str(drafts),
            "eid": lab.eid,
        }
        for path in (root / "data", root / "work", root / "out"):
            path.mkdir(parents=True, exist_ok=True)
        _seed_drafts(lab.day, drafts)
        return workspace

    def dispose(self) -> None:
        if not self.keep:
            shutil.rmtree(self.root, ignore_errors=True)

    def sub(self, text: str) -> str:
        for name, value in self._tokens.items():
            text = text.replace("{{" + name + "}}", value)
        return text

    def unresolved_tokens(self) -> list[str]:
        return list(self._unresolved)

    def run(self, command: Command) -> tuple[int, str]:
        """Execute argv, return ``(exit code, merged output)``.

        Only commands explicitly licensed with ``read_only=True`` are cached:
        ``gate check`` records a gate result into the engagement (and can sink a
        draft skill), so re-running it is the point, not a waste.
        """
        argv = tuple(self.sub(token) for token in command.argv)
        if "{{" in " ".join(argv):
            for name in re.findall(r"\{\{([a-z_]+)\}\}", " ".join(argv)):
                if name not in self._unresolved:
                    self._unresolved.append(name)
        if command.read_only and argv in self._cache:
            return self._cache[argv]

        env = {
            **os.environ,
            "FDE_SCOPE_HOME": self._tokens["home"],
            "COLUMNS": "200",
            "NO_COLOR": "1",
            "PYTHONIOENCODING": "utf-8",
        }
        if self.verbose:
            print(f"$ {' '.join([*cli_prefix(), *argv])}")
        try:
            proc = subprocess.run(
                [*cli_prefix(), *argv],
                cwd=self._tokens["workspace"],
                env=env,
                capture_output=True,
                text=True,
                timeout=command.timeout,
            )
            code, text = proc.returncode, _strip(proc.stdout) + _strip(proc.stderr)
        except subprocess.TimeoutExpired:
            code, text = _TIMEOUT_EXIT, f"<timed out after {command.timeout}s>"
        except OSError as exc:  # pragma: no cover — a broken interpreter is not a lab failure
            code, text = 127, f"<could not run the CLI: {exc}>"
        if self.verbose:
            print(text.rstrip())
        for name, pattern in command.capture:
            match = re.search(self.sub(pattern), text)
            if match:
                self._tokens[name] = match.group(1) if match.groups() else match.group(0)
            else:
                self._unresolved.append(name)
        if command.read_only:
            self._cache[argv] = (code, text)
        return code, text

    def file(self, relative: str) -> Path:
        return Path(self.sub(relative))


@dataclass
class LabResult:
    """Everything one day's run produced — printed by default, ``--json``-able."""

    day: str
    title: str
    gate: str
    deliverable: str
    results: list[CheckResult] = field(default_factory=list)
    workspace: str = ""
    passed: int = 0
    failed: int = 0
    manual: int = 0

    @property
    def score(self) -> int:
        return self.passed + self.failed

    @property
    def ok(self) -> bool:
        return self.failed == 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "title": self.title,
            "gate": self.gate,
            "deliverable": self.deliverable,
            "workspace": self.workspace,
            "passed": self.passed,
            "failed": self.failed,
            "manual": self.manual,
            "score": self.score,
            "ok": self.ok,
            "checks": [
                {
                    "id": r.id,
                    "gate": r.gate,
                    "ask": r.ask,
                    "status": r.status,
                    "scored": r.scored,
                    "detail": r.detail,
                    "hint": r.hint,
                    "command": r.command,
                }
                for r in self.results
            ],
        }

    def lines(self) -> list[str]:
        head = [
            f"── {self.day} · {self.title}（{self.gate}）"
            + f" — {self.passed}/{self.score} 机器项"
            + (f"，另有 {self.manual} 项人工评分" if self.manual else "")
        ]
        return head + [result.line() for result in self.results]


def _result(check: Check, workspace: LabWorkspace, status: str, detail: str = "") -> CheckResult:
    return CheckResult(
        id=check.id,
        gate=check.gate,
        ask=workspace.sub(check.ask),
        status=status,  # type: ignore[arg-type]
        detail=detail,
        hint=check.hint,
        command=_command_of(check, workspace),
    )


def _command_of(check: Check, workspace: LabWorkspace) -> str:
    command = getattr(check, "command", None)
    return "" if command is None else workspace.sub(command.render(cli_prefix()))


def _run_command_check(check: CommandCheck, workspace: LabWorkspace) -> CheckResult:
    code, text = workspace.run(check.command)
    if code != check.command.exit_code:
        return _result(
            check,
            workspace,
            "fail",
            f"退出码 {code}，期望 {check.command.exit_code}。输出：{_tail(text)}",
        )
    missing = matches_any(text, tuple(workspace.sub(n) for n in check.contains))
    if missing:
        return _result(check, workspace, "fail", f"输出缺少「{workspace.sub(missing)}」。输出：{_tail(text)}")
    pattern = first_missing_regex(text, tuple(workspace.sub(p) for p in check.regex))
    if pattern:
        return _result(
            check, workspace, "fail", f"输出不匹配 /{workspace.sub(pattern)}/。输出：{_tail(text)}"
        )
    return _result(check, workspace, "pass")


def _tail(text: str, limit: int = 240) -> str:
    flat = " ".join(text.split())
    return flat[-limit:] if len(flat) > limit else flat


def _run_metric_check(check: MetricCheck, workspace: LabWorkspace) -> CheckResult:
    payload, source = _payload_for(check, workspace)
    if payload is None:
        return _result(check, workspace, "fail", source)
    value = _resolve(payload, workspace.sub(check.path))
    if value is None:
        return _result(check, workspace, "fail", f"{check.path} 在 {source} 里取不到")
    verdict = _compare(value, check)
    if verdict:
        return _result(check, workspace, "fail", f"{check.path} = {value!r}（{verdict}）")
    return _result(check, workspace, "pass", f"{check.path} = {value!r}")


def _payload_for(check: MetricCheck, workspace: LabWorkspace) -> tuple[Any | None, str]:
    if check.file:
        path = workspace.file(check.file)
        if not path.is_file():
            return None, f"{path} 不存在"
        try:
            return json.loads(path.read_text(encoding="utf-8")), path.name
        except ValueError as exc:
            return None, f"{path.name} 不是合法 JSON（{exc}）"
    if check.command is None:
        return None, "这条检查既没有 file 也没有 command——catalog 写错了"
    code, text = workspace.run(check.command)
    if code != check.command.exit_code:
        return None, f"命令退出码 {code}（期望 {check.command.exit_code}）：{_tail(text)}"
    payload = _extract_json(text)
    return (payload, "stdout") if payload is not None else (None, f"命令输出里没有 JSON：{_tail(text)}")


def _compare(value: Any, check: MetricCheck) -> str:
    if check.one_of:
        choices = tuple(v for v in check.one_of)
        return "" if value in choices else f"不在 {list(choices)} 里"
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return (
            "不是数字" if (check.approx is not None or check.gte is not None or check.lte is not None) else ""
        )
    if check.approx is not None and abs(float(value) - check.approx) > check.tol:
        return f"应为 {check.approx}±{check.tol}"
    if check.gte is not None and float(value) < check.gte:
        return f"应 ≥ {check.gte}"
    if check.lte is not None and float(value) > check.lte:
        return f"应 ≤ {check.lte}"
    return ""


def _run_artifact_check(check: ArtifactCheck, workspace: LabWorkspace) -> CheckResult:
    if check.command is not None:
        code, text = workspace.run(check.command)
        if code != check.command.exit_code:
            return _result(check, workspace, "fail", f"生成命令退出码 {code}：{_tail(text)}")
    path = workspace.file(check.file)
    if not path.is_file():
        return _result(check, workspace, "fail", f"{path} 不存在")
    size = path.stat().st_size
    if size < check.min_bytes:
        return _result(check, workspace, "fail", f"{path.name} 只有 {size} 字节")
    text = _strip(path.read_text(encoding="utf-8", errors="replace"))
    present = first_present(text, tuple(workspace.sub(n) for n in check.not_contains))
    if present:
        return _result(
            check,
            workspace,
            "fail",
            f"{path.name} 里还留着「{workspace.sub(present)}」——那是模板占位，要自己写完",
        )
    missing = matches_any(text, tuple(workspace.sub(n) for n in check.contains))
    if missing:
        return _result(check, workspace, "fail", f"{path.name} 缺少「{workspace.sub(missing)}」")
    pattern = first_missing_regex(text, tuple(workspace.sub(p) for p in check.regex))
    if pattern:
        return _result(check, workspace, "fail", f"{path.name} 不匹配 /{workspace.sub(pattern)}/")
    return _result(check, workspace, "pass", f"{path.name} {size} 字节")


def _run_determinism_check(check: DeterminismCheck, workspace: LabWorkspace) -> CheckResult:
    """Run the same command twice and require the *same* payload.

    A metric that moves between runs cannot be a gate, and the book claims the
    mock path is reproducible (``--accuracy``/``--seed`` are fixed). This is the
    check that turns that claim into something a student can falsify.
    """
    codes: list[int] = []
    payloads: list[str] = []
    for _ in range(2):
        code, text = workspace.run(check.command)
        codes.append(code)
        payload = (
            _resolve(_extract_json(text) or {}, workspace.sub(check.path))
            if check.path
            else _extract_json(text)
        )
        payloads.append(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    if len(set(codes)) > 1:
        return _result(check, workspace, "fail", f"两次退出码不同：{codes}")
    if payloads[0] != payloads[1]:
        return _result(check, workspace, "fail", f"两次结果不一致：{payloads[0]} ≠ {payloads[1]}")
    return _result(check, workspace, "pass", f"两次一致：{_tail(payloads[0], 120)}")


def _run_check(check: Check, workspace: LabWorkspace) -> CheckResult:
    if isinstance(check, ManualCheck):
        return _result(check, workspace, "manual", "人工评分项（不进分母）：见 rubric")
    if isinstance(check, CommandCheck):
        return _run_command_check(check, workspace)
    if isinstance(check, MetricCheck):
        return _run_metric_check(check, workspace)
    if isinstance(check, ArtifactCheck):
        return _run_artifact_check(check, workspace)
    if isinstance(check, DeterminismCheck):
        return _run_determinism_check(check, workspace)
    raise TypeError(f"unknown check kind: {type(check).__name__}")  # pragma: no cover


def run_lab(lab: Lab | str, keep: bool = False, verbose: bool = False) -> LabResult:
    """Score one day end to end: setup commands, then every check."""
    lab = lab_for(lab) if isinstance(lab, str) else lab
    workspace = LabWorkspace.create(lab, keep=keep, verbose=verbose)
    result = LabResult(
        day=lab.day,
        title=lab.title,
        gate=lab.gate,
        deliverable=lab.deliverable,
        workspace=str(workspace.root if keep else ""),
    )
    try:
        for command in lab.setup:
            code, text = workspace.run(command)
            if code != command.exit_code:
                result.results.append(
                    CheckResult(
                        id="setup",
                        gate=lab.gate,
                        ask=f"前置命令：{workspace.sub(command.render(cli_prefix()))}",
                        status="fail",
                        detail=f"退出码 {code}：{_tail(text)}",
                        hint=lab.setup_hint,
                        command="",
                    )
                )
                result.failed += 1
                return result
        for check in lab.checks:
            check_result = _run_check(check, workspace)
            result.results.append(check_result)
            if check_result.status == "pass":
                result.passed += 1
            elif check_result.status == "fail":
                result.failed += 1
            else:
                result.manual += 1
        stray = workspace.unresolved_tokens()
        if stray:
            result.results.append(
                CheckResult(
                    id="tokens",
                    gate=lab.gate,
                    ask="所有命令的占位符都被替换",
                    status="fail",
                    detail=f"未替换：{{{{{', '.join(stray)}}}}}",
                    hint="前置命令没有打印出可捕获的值，检查上面失败的项",
                )
            )
            result.failed += 1
    finally:
        workspace.dispose()
    return result


def run_all(keep: bool = False, verbose: bool = False) -> list[LabResult]:
    """D1..D8 in order — the self-study path, machine-checkable start to finish."""
    from .catalog import LABS

    return [run_lab(lab, keep=keep, verbose=verbose) for lab in LABS]
