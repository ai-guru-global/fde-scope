"""G0 入学门 — the 开营前 15 分钟 self-check from ``06`` §2, as one command.

The book lists five rows and expects a student to type each one. Two problems
that creates: a reader who is *almost* set up gets a green-looking output from
four of them and discovers the fifth at 02:00 AM while debugging a lab, and
"装包成功" says nothing about *which* install the lab will then run against.
This module turns the table into a single command whose exit code means
something: ``course doctor`` exits non-zero exactly when a required item is
missing, so "环境 OK" is a claim the machine checked.

What is deliberately *not* here:

* **No key requirement.** ``06`` §2 says so in words — API key, Docker and
  AgentScope are all optional because every link in the chain has a zero-key
  path. They are reported as ``info`` so a student knows whether the LLM branch
  of a lesson will run, and never as a failure.
* **No credential values.** Only "is the env var set" is reported
  (AGENTS.md invariant 3), never a prefix of the key.
* **No fixes applied.** Doctor reads and names the next step; it does not
  install packages, create directories or chmod anything.

The data-root item mirrors :func:`fde_scope.paths.data_root`'s four rules
because a path alone does not explain behaviour: rule 2 (a CWD that carries its
own ``.fde_scope``) is what makes the *same* command write to a different place
in two directories, and rule 4 deliberately returns a **relative** path. The
mirror is verified, not trusted — if the two disagree the item fails loudly,
which is the only way a duplicated rule order stays honest.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .checks import ManualCheck
from .verifier import cli_prefix, labs_root

Status = Literal["ok", "fail", "warn", "info"]

#: ``06`` §2 row 1 — the book promises 3.11+, so that is the gate.
MIN_PYTHON = (3, 11)

_DATA_SUBDIR_NOTE = (
    "rule 2/4 返回的是相对路径：换目录就换数据。跑 lab 前固定在一个目录，"
    "或显式设 FDE_SCOPE_HOME 指到可写位置。"
)


@dataclass(frozen=True)
class DoctorItem:
    """One G0 row: what it proves, what it found, whether the lab can start."""

    id: str
    ask: str
    status: Status
    detail: str = ""
    hint: str = ""
    required: bool = True

    @property
    def blocking(self) -> bool:
        return self.required and self.status == "fail"

    def line(self) -> str:
        mark = {"ok": "✅", "fail": "❌", "warn": "⚠️ ", "info": "ℹ️ "}[self.status]
        out = [f"{mark} [{self.id}] {self.ask}"]
        if self.detail:
            out.append(f"      {self.detail}")
        if self.hint and self.status != "info":
            out.append(f"      💡 {self.hint}")
        return "\n".join(out)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "ask": self.ask,
            "status": self.status,
            "required": self.required,
            "detail": self.detail,
            "hint": self.hint,
        }


def _python_item() -> DoctorItem:
    version = sys.version_info
    running = f"{version.major}.{version.minor}.{version.micro}"
    want = ".".join(str(part) for part in MIN_PYTHON)
    if version < MIN_PYTHON:
        return DoctorItem(
            "python",
            f"Python ≥ {want}（G0 第 1 行）",
            "fail",
            f"当前解释器 {running} — {sys.executable}",
            "按 11-工具与环境准备.md 第 2 节装 3.11+；注意用哪个解释器 pip install。",
        )
    return DoctorItem(
        "python",
        f"Python ≥ {want}（G0 第 1 行）",
        "ok",
        f"{running} · {sys.executable}",
    )


def _package_item() -> DoctorItem:
    from .. import __version__

    graded_by = " ".join(cli_prefix())
    return DoctorItem(
        "package",
        "fde_scope 可导入且有版本（G0 第 2 行「装包成功」）",
        "ok",
        f"fde-scope {__version__} · 评分器调用方式：{graded_by}",
    )


def _entry_point_item() -> DoctorItem:
    """``fde-scope`` on PATH vs the interpreter under test — a stale script is the
    classic "I ran the command in the book and got different output" cause.

    Reported as ``warn``/``info`` and never ``fail``: the labs shell out to
    ``python -m fde_scope`` (:func:`fde_scope.course.verifier.cli_prefix`)
    precisely so a global script cannot grade a run against the wrong build.
    But a student typing ``fde-scope …`` from the book is typing the script, so
    the mismatch is worth naming.
    """
    script = shutil.which("fde-scope")
    if script is None:
        return DoctorItem(
            "entry-point",
            "`fde-scope` 命令是否在 PATH 上",
            "info",
            "没有 fde-scope 脚本；课内命令请用 `python -m fde_scope …`（评分器就是这么跑的）",
            "`pip install -e .` 会装上脚本；不装也能完成全部 lab。",
            required=False,
        )
    try:
        proc = subprocess.run([script, "--version"], capture_output=True, text=True, timeout=15, check=False)
        printed = (proc.stdout + proc.stderr).strip().splitlines()
        found = printed[0] if printed else "<no output>"
    except (OSError, subprocess.SubprocessError) as exc:
        return DoctorItem(
            "entry-point",
            "`fde-scope` 命令是否在 PATH 上",
            "warn",
            f"{script} 无法执行：{exc}",
            "装坏了；重跑 pip install -e .[dev]，lab 期间改用 python -m fde_scope。",
            required=False,
        )
    from .. import __version__

    if __version__ not in found:
        return DoctorItem(
            "entry-point",
            "`fde-scope` 命令是否在 PATH 上",
            "warn",
            f"{script} 报 {found!r}，与本地包 {__version__} 不一致",
            "PATH 上装的是另一份（全局/旧 venv）。要么激活正确 venv，要么把教案里的 "
            "`fde-scope` 换成 `python -m fde_scope`——两者输出不同时报错很难查。",
            required=False,
        )
    return DoctorItem(
        "entry-point",
        "`fde-scope` 命令是否在 PATH 上",
        "ok",
        f"{script} · {found}",
        required=False,
    )


def _resolve_rule() -> tuple[Path, str]:
    """Which of the four :func:`fde_scope.paths.data_root` rules fired.

    Branch conditions are copied from ``paths.py`` verbatim (env override → CWD
    carrying ``.fde_scope`` → the app's install dir → relative CWD). ``doctor()``
    cross-checks the result against the real ``data_root()`` and fails if they
    ever diverge.
    """
    from .. import paths

    override = os.environ.get("FDE_SCOPE_HOME")
    if override:
        return Path(override).expanduser(), "rule 1 · FDE_SCOPE_HOME"
    cwd = Path()
    if (cwd / paths.DATA_SUBDIR).is_dir():
        return cwd, f"rule 2 · 当前目录带 {paths.DATA_SUBDIR}/"
    app_dir = paths.app_data_dir()
    if app_dir.is_dir():
        return app_dir, "rule 3 · ~/Documents/FDE Scope（App 安装目录）"
    return cwd, "rule 4 · 回落到当前目录（相对路径）"


def _writable(root: Path) -> tuple[bool, str]:
    """Touch a probe file in ``<root>/.fde_scope`` — the dir the labs actually write.

    A ``.fde_scope/`` the student cannot write is the single most common cold-start
    failure on a machine that previously ran the macOS app, so the probe is made
    under that subdirectory rather than next to it. Side effect, stated plainly:
    this creates ``<root>/.fde_scope`` if it is missing — the same directory the
    first ``engage init`` would create — and removes only the probe file.
    """
    target = root / ".fde_scope"
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = Path(tempfile.mkstemp(prefix=".doctor-probe-", dir=str(target))[1])
    except OSError as exc:
        return False, f"{target}: {exc}"
    probe.unlink(missing_ok=True)
    return True, ""


def _data_root_item() -> DoctorItem:
    from .. import paths

    root, rule = _resolve_rule()
    actual = paths.data_root()
    if str(actual) != str(root):
        return DoctorItem(
            "data-root",
            "数据目录落在哪、能不能写",
            "fail",
            f"诊断说 {rule} → {root}，但 paths.data_root() 返回 {actual}（两者应当一致）",
            "这是本仓库的问题，不是环境的：把这条输出贴给助教/issue。",
        )
    ok, error = _writable(root)
    if not ok:
        return DoctorItem(
            "data-root",
            "数据目录落在哪、能不能写",
            "fail",
            f"{rule} → {root}（不可写：{error or '未知原因'}）",
            "换一个可写目录：export FDE_SCOPE_HOME=~/fde-data。",
        )
    return DoctorItem(
        "data-root",
        "数据目录落在哪、能不能写",
        "ok",
        f"{rule} → {root}（{'绝对' if root.is_absolute() else '相对'}路径 · 可写）",
        hint=_DATA_SUBDIR_NOTE,
        required=True,
    )


def _labs_item() -> DoctorItem:
    root = labs_root()
    if not root.is_dir():
        return DoctorItem(
            "labs",
            "lab 目录是否存在（course-level-1/labs/）",
            "fail",
            f"{root} 不存在",
            "装的是不含教案的 wheel？pip install -e .（仓库根目录），或看 pyproject 的 "
            "package-data 是否把 course-level-1 打进去。",
        )
    from .catalog import LABS

    missing = [lab.day for lab in LABS if not (root / lab.day / "README.md").is_file()]
    if missing:
        return DoctorItem(
            "labs",
            "lab 目录是否存在（course-level-1/labs/）",
            "fail",
            f"{root} 缺少 {'、'.join(missing)} 的 README.md",
            "教案目录被改坏了：git status 看看 labs/ 有没有本地删除。",
        )
    checks = [check for lab in LABS for check in lab.checks]
    manual = sum(1 for check in checks if isinstance(check, ManualCheck))
    return DoctorItem(
        "labs",
        "lab 目录是否存在（course-level-1/labs/）",
        "ok",
        f"{root} · {len(LABS)} 天 · {len(checks) - manual} 个判分项 + {manual} 个人工项",
        required=True,
    )


def _fixtures_item() -> DoctorItem:
    """The two smoke-test files ``06`` §2 rows 3–4 name, plus the lab fixtures.

    Looked up under the repo root *and* the wheel's ``_data`` copy (same two bases
    :func:`fde_scope.course.verifier.labs_root` uses), then relative to CWD last —
    ``06`` prints the paths as CWD-relative, so a student standing in the repo root
    must get a green light for the reason the book gives, not by accident.
    """
    wanted = (
        Path("examples") / "quickstart_csv" / "sample_tickets.csv",
        Path("examples") / "quickstart_manufacturing" / "station_samples.jsonl",
    )
    here = Path(__file__).resolve()
    bases = [here.parents[2], here.parents[1] / "_data", Path()]
    missing = [rel for rel in wanted if not any((base / rel).is_file() for base in bases)]
    if missing:
        return DoctorItem(
            "fixtures",
            "冒烟数据是否在场（examples/quickstart_*）",
            "fail",
            f"找不到 {'、'.join(str(rel) for rel in missing)}",
            "G0 第 3–4 行的冒烟命令要用它。确认在仓库根目录跑，或重装含 examples/ 的包。",
        )
    days = ("D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8")
    with_fixtures = sum(1 for day in days if (labs_root() / day / "fixtures").is_dir())
    shared = "在" if (labs_root() / "_shared").is_dir() else "不在"
    return DoctorItem(
        "fixtures",
        "冒烟数据是否在场（examples/quickstart_*）",
        "ok",
        f"两个 examples 文件在场 · labs/_shared {shared} · {with_fixtures}/8 天自带 fixtures/",
        required=True,
    )


def _columns_item() -> DoctorItem:
    """A table wrapped at 80 columns splits the sentence a student is told to grep.

    The verifier pins ``COLUMNS=200`` for its own subprocesses, so a *graded* run
    is safe; a human following the book in a terminal is not. Warn, don't fail:
    nothing is wrong with the install, the reading is.
    """
    raw = os.environ.get("COLUMNS", "")
    if not raw:
        return DoctorItem(
            "columns",
            "终端宽度是否够读表格",
            "warn",
            "COLUMNS 未设置（rich 默认按 80 列折行）",
            "export COLUMNS=200——否则课里印的『输出应包含 X』会被折行打断，看着像命令没跑对。",
            required=False,
        )
    try:
        width = int(raw)
    except ValueError:
        return DoctorItem(
            "columns",
            "终端宽度是否够读表格",
            "warn",
            f"COLUMNS={raw!r} 不是数字",
            "设成 200：export COLUMNS=200。",
            required=False,
        )
    if width < 120:
        return DoctorItem(
            "columns",
            "终端宽度是否够读表格",
            "warn",
            f"COLUMNS={width}",
            "export COLUMNS=200（评分器内部用的就是这个值）。",
            required=False,
        )
    return DoctorItem("columns", "终端宽度是否够读表格", "ok", f"COLUMNS={width}", required=False)


def _llm_item() -> DoctorItem:
    """Zero-key or not — never the value (AGENTS.md invariant 3)."""
    from ..llm import _ENV_KEY, _ENV_OAI_KEY  # noqa: PLC0415 — env names, not a client

    mimo = bool(os.environ.get(_ENV_KEY, "").strip())
    openai = bool(os.environ.get(_ENV_OAI_KEY, "").strip())
    if not (mimo or openai):
        return DoctorItem(
            "llm",
            "LLM 是否配置（可选）",
            "info",
            f"未设 {_ENV_KEY} / {_ENV_OAI_KEY} → 走零 key 规则路径",
            "G0 明说不需要 key：D1–D8 全部判分项在零 key 下可跑。只有教案标了「LLM」的小节会退化。",
            required=False,
        )
    which = _ENV_KEY if mimo else _ENV_OAI_KEY
    return DoctorItem(
        "llm",
        "LLM 是否配置（可选）",
        "ok",
        f"{which} 已设置（值不打印）",
        required=False,
    )


def _agentscope_item() -> DoctorItem:
    found = importlib.util.find_spec("agentscope") is not None
    if not found:
        return DoctorItem(
            "agentscope",
            "AgentScope extra 是否在场（可选）",
            "info",
            "未安装 agentscope → 部署链路走 mock；`pytest -m agentscope` 会 skip",
            "需要真运行时：pip install -e '.[agentscope]'（版本窗口以 pyproject 的 "
            "agentscope extra 为准，接口对照见 docs/agentscope_api_mapping.md）",
            required=False,
        )
    try:
        from importlib.metadata import version

        installed = version("agentscope")
    except Exception:  # noqa: BLE001 — metadata lookup failing is not a lab blocker
        installed = "已安装（版本号取不到）"
    return DoctorItem(
        "agentscope",
        "AgentScope extra 是否在场（可选）",
        "ok",
        f"agentscope {installed}",
        required=False,
    )


def doctor() -> list[DoctorItem]:
    """Run every G0 row in a fixed order — required items first, optional last."""
    return [
        _python_item(),
        _package_item(),
        _labs_item(),
        _fixtures_item(),
        _data_root_item(),
        _entry_point_item(),
        _columns_item(),
        _llm_item(),
        _agentscope_item(),
    ]


def blocker_ids(items: list[DoctorItem]) -> list[str]:
    return [item.id for item in items if item.blocking]


def payload_for(items: list[DoctorItem]) -> dict[str, Any]:
    """The ``--json`` document — same facts as the human report, no colour."""
    blockers = blocker_ids(items)
    return {
        "gate": "G0",
        "ok": not blockers,
        "blockers": blockers,
        "summary": {
            "ok": sum(1 for i in items if i.status == "ok"),
            "warn": sum(1 for i in items if i.status == "warn"),
            "info": sum(1 for i in items if i.status == "info"),
            "fail": sum(1 for i in items if i.status == "fail"),
        },
        "items": [item.as_dict() for item in items],
    }


def doctor_report() -> tuple[int, list[DoctorItem], dict[str, Any]]:
    """Return ``(exit code, items, payload)``: non-zero iff a required item failed.

    The exit code is what makes ``course doctor`` usable as a gate: a bootcamp
    operator can put it in a checklist and a student's CI can fail on it, instead
    of a human squinting at a table. Items are returned alongside the payload so
    the text and JSON renderings come from one run — probing twice would mean
    creating the data directory twice and could disagree with itself.
    """
    items = doctor()
    payload = payload_for(items)
    return (0 if payload["ok"] else 1), items, payload
