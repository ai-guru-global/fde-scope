"""Guards for ``fde_scope.course`` — the eight-day lab registry, G0 doctor, and the two oracles.

This is the test file that makes ``course check`` a *claim* instead of a
feature. Three things could go silently wrong once the labs exist, and each has
a name here:

* **The book's numbers drift from the registry.** ``labs/README.md`` states
  "91 个判分项 + 9 个人工项" and "81 个契约项 + 10 个写作项" with a per-day
  split. Those numbers are what a student uses to decide whether their
  environment is broken or their writing is not done. So the assertion parses
  the README and compares it to the catalog: the prose *is* the test input, and
  editing one without the other fails here.
* **A writing item is a fake gate.** ``check all`` going red on ``TODO`` is only
  honest if writing the words turns it green. The warm oracle proves that.
* **The cold oracle is the documented result.** On a machine that has written
  nothing, ``check all`` must fail exactly the 10 writing items and pass all 81
  contract items — a red contract item means the tool or the lesson drifted, and
  this is the only place that distinction is enforced.

Static checks never shell out (milliseconds). The two oracles do (about 8
seconds each, measured): one CLI call is 0.06 s and a full eight-day run is
7.5 s cold, so the cost is affordable and there is no ``slow`` marker to hide
behind.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fde_scope import paths
from fde_scope.cli import app
from fde_scope.course import LABS, doctor_report, lab_for, run_all
from fde_scope.course.checks import (
    ArtifactCheck,
    Command,
    CommandCheck,
    DeterminismCheck,
    ManualCheck,
    MetricCheck,
)
from fde_scope.course.verifier import (
    LabWorkspace,
    _extract_json,
    _resolve,
    _seed_drafts,
    cli_prefix,
    draft_dir,
    labs_root,
)

# ``course/__init__`` re-exports the ``doctor`` *function*, which shadows the submodule attribute, so
# ``from fde_scope.course import doctor`` hands back a function; importlib reads sys.modules instead.
doctor_module = importlib.import_module("fde_scope.course.doctor")

REPO_ROOT = Path(__file__).resolve().parents[1]
LABS_DIR = REPO_ROOT / "course-level-1" / "labs"
DAYS = ["D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"]


# ---------------------------------------------------------------------------
# the two vocabularies: contract items vs writing items
# ---------------------------------------------------------------------------


def is_writing(check: ArtifactCheck) -> bool:
    """A writing item is an ArtifactCheck that forbids template residue.

    Derived from the registry rather than a day-by-day list on purpose: if a
    check stops forbidding ``TODO`` it stops being a writing item, and the
    per-day counts in the README then fail their own guard below.
    """
    return isinstance(check, ArtifactCheck) and bool(check.not_contains)


def machine_checks(lab) -> list:
    return [c for c in lab.checks if not isinstance(c, ManualCheck)]


def writing_checks(lab) -> list[ArtifactCheck]:
    return [c for c in lab.checks if is_writing(c)]


def contract_checks(lab) -> list:
    return [c for c in machine_checks(lab) if not is_writing(c)]


# ---------------------------------------------------------------------------
# registry shape
# ---------------------------------------------------------------------------


def test_registry_covers_d1_to_d8_in_order_with_one_gate_each() -> None:
    assert [lab.day for lab in LABS] == DAYS
    assert [lab.gate for lab in LABS] == ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8（结业门）"]
    assert len({lab.eid for lab in LABS}) == 8, (
        "two labs sharing an id would overwrite each other's engagement"
    )


def test_lab_for_accepts_every_day_and_rejects_noise() -> None:
    for day in DAYS:
        assert lab_for(day).day == day
        assert lab_for(day.lower()).day == day
        # the docstring promises the engagement id resolves back to a day, which is
        # what a student pastes from their own history (`gate check lab-d5`)
        assert lab_for(lab_for(day).eid).day == day
    with pytest.raises(KeyError, match="unknown lab"):
        lab_for("D9")
    with pytest.raises(KeyError, match="unknown lab"):
        lab_for(" D1 ")  # measured: no trimming, so a stray space is a loud error


def test_every_lab_initialises_its_own_engagement() -> None:
    """One ``engage init`` per lab, with the day's own eid and a real profile.

    Isolation is the property under test: no lab may grade against state a
    previous lab left behind (AGENTS.md invariant 1 — gates are re-evaluated
    live, so a stale engagement would still change the answer).
    """
    for lab in LABS:
        assert len(lab.setup) == 1, f"{lab.day}: expected exactly one setup command"
        argv = lab.setup[0].argv
        assert argv[:2] == ("engage", "init"), f"{lab.day} setup is {argv}"
        # the id is the *token*, not the literal — the workspace fills it per run,
        # which is why eight labs can all use a fixed eid without colliding.
        assert "{{eid}}" in argv and lab.eid and lab.profile in argv
        assert lab.setup[0].read_only is False
        assert lab.setup_hint, f"{lab.day}: a failed setup prints only setup_hint to the student"


def test_check_ids_are_unique_per_day_and_every_item_is_answerable() -> None:
    for lab in LABS:
        ids = [c.id for c in lab.checks]
        assert len(ids) == len(set(ids)), f"{lab.day} has duplicate check ids: {ids}"
        for check in lab.checks:
            assert check.ask.strip(), f"{lab.day}/{check.id}: a check with no ask cannot be audited"
            # D8's lab gate is written "G8（结业门）" while its items carry "G8"
            assert lab.gate.startswith(check.gate), (
                f"{lab.day}/{check.id} serves {check.gate}, lab serves {lab.gate}"
            )
            if isinstance(check, ManualCheck):
                assert check.rubric.strip(), f"{lab.day}/{check.id}: manual items need a rubric"
            else:
                assert check.hint.strip(), f"{lab.day}/{check.id}: machine items need a next-step hint"


def test_metric_and_command_checks_are_wired_to_something() -> None:
    for lab in LABS:
        for check in lab.checks:
            if isinstance(check, MetricCheck):
                assert check.file or check.command is not None, f"{lab.day}/{check.id} reads nothing"
            if isinstance(check, (CommandCheck, DeterminismCheck)):
                assert check.command.argv, f"{lab.day}/{check.id} runs an empty argv"
            if isinstance(check, ArtifactCheck) and check.command is not None:
                assert check.command.argv, f"{lab.day}/{check.id} generates nothing"
            if isinstance(check, Command):
                assert all(isinstance(token, str) for token in check.argv)


def test_determinism_check_bypasses_the_cache() -> None:
    """The one reproducibility item must actually run twice — caching it once
    would turn "the same command gave the same number" into tautology."""
    for lab in LABS:
        for check in lab.checks:
            if isinstance(check, DeterminismCheck):
                assert check.command.read_only is False, f"{lab.day}/{check.id} would be served from one run"


# ---------------------------------------------------------------------------
# read_only: what licenses the verifier to reuse an output
# ---------------------------------------------------------------------------

#: argv heads the verifier is allowed to reuse across checks.
CACHED_HEADS = {"connect", "engage", "eval", "gate", "kpi", "skill"}
#: sub-verbs that write engagement state — re-running them is the point, not a waste.
MUTATING_VERBS = {"add", "advance", "check", "delete", "handoff", "init", "rollback", "set", "update"}


def cached_commands() -> list[tuple[str, str, Command]]:
    rows = []
    for lab in LABS:
        for where, command in [("setup", None), *[(c.id, getattr(c, "command", None)) for c in lab.checks]]:
            if command is None:
                continue
            if command.read_only:
                rows.append((lab.day, where, command))
    return rows


def test_only_non_mutating_commands_are_cached() -> None:
    cached = cached_commands()
    assert cached, "nothing is cached — then the flag means nothing and the docs lie"
    for day, where, command in cached:
        head = command.argv[0]
        assert head in CACHED_HEADS, f"{day}/{where}: caching {head!r} is not licensed"
        bad = [token for token in command.argv if token in MUTATING_VERBS]
        assert not bad, f"{day}/{where} mutates via {bad} but is marked read_only"


def test_cached_command_output_is_stable_across_repeats() -> None:
    """``connect`` is the one cached command that *writes* — a preview file.

    So the real requirement is not "changes nothing" but "running it again
    changes nothing observable". Measured here rather than trusted: same exit
    code, byte-identical output, and the artifact untouched between runs.
    """
    source = labs_root() / "_shared" / "fixtures" / "sample_tickets.csv"
    home = Path(os.environ.get("FDE_SCOPE_HOME") or ".").resolve()
    argv = [*cli_prefix(), "connect", "--type", "csv", "--source", str(source), "--sample-size", "20"]
    env = {**os.environ, "FDE_SCOPE_HOME": str(home), "COLUMNS": "200", "NO_COLOR": "1"}
    runs = [
        subprocess.run(argv, cwd=home, env=env, capture_output=True, text=True, check=False)  # noqa: S603
        for _ in range(2)
    ]
    assert [proc.returncode for proc in runs] == [0, 0]
    assert runs[0].stdout == runs[1].stdout, "identical argv must give identical stdout, or the cache lies"
    preview = home / "samples" / "preview.json"
    if preview.is_file():
        digest = hashlib.sha256(preview.read_bytes()).hexdigest()
        subprocess.run(argv, cwd=home, env=env, capture_output=True, text=True, check=False)  # noqa: S603
        assert hashlib.sha256(preview.read_bytes()).hexdigest() == digest


# ---------------------------------------------------------------------------
# token substitution
# ---------------------------------------------------------------------------

#: tokens the workspace knows without a capture step.
STATIC_TOKENS = {"drafts", "eid", "fixtures", "home", "lab", "out", "root", "shared", "workspace"}


def tokens_in(*texts: str | tuple[str, ...] | None) -> set[str]:
    out: set[str] = set()
    for text in texts:
        if text is None:
            continue
        joined = " ".join(text) if isinstance(text, tuple) else str(text)
        out.update(re.findall(r"\{\{([a-z_]+)\}\}", joined))
    return out


def test_every_template_token_is_known_or_captured() -> None:
    captured: set[str] = set()
    for lab in LABS:
        for command in lab.setup:
            captured.update(name for name, _ in command.capture)
        for check in lab.checks:
            command = getattr(check, "command", None)
            if command is not None:
                captured.update(name for name, _ in command.capture)
    known = STATIC_TOKENS | captured
    for lab in LABS:
        commands = [lab.setup[0], *(c.command for c in lab.checks if getattr(c, "command", None))]
        for command in commands:
            stray = tokens_in(*command.argv) - known
            assert not stray, f"{lab.day}: {sorted(stray)} would reach the CLI as a literal"
        for check in lab.checks:
            stray = tokens_in(getattr(check, "file", ""), check.ask, check.hint) - known
            assert not stray, f"{lab.day}/{check.id}: {sorted(stray)} is not a token the verifier fills"


def test_captured_tokens_are_needed_by_a_later_command() -> None:
    """A capture nobody reads is dead weight; a token nobody captures is a typo.

    ``skill_id`` exists because the server generates it (AGENTS.md invariant 2),
    so the lab cannot hardcode it — but the capture is only worth having if a
    later argv actually references it.
    """
    for lab in LABS:
        commands = [lab.setup[0]] + [
            c.command for c in lab.checks if getattr(c, "command", None) is not None and c.command.argv
        ]
        for index, command in enumerate(commands):
            for name, pattern in command.capture:
                assert re.compile(pattern).groups >= 1, f"{lab.day}: {name} captures nothing"
                later = " ".join(" ".join(c.argv) for c in commands[index + 1 :])
                assert "{{" + name + "}}" in later, f"{lab.day}: {name} is captured but never used"


def test_lab_referenced_fixtures_exist_except_the_declared_negative() -> None:
    """Every ``{{fixtures}}/x`` the rubric reads is on disk — except D1's, which
    is *supposed* to be missing (the "bad input must fail loudly" item)."""
    for lab in LABS:
        referenced: set[str] = set()
        for command in [lab.setup[0], *(c.command for c in lab.checks if getattr(c, "command", None))]:
            for token in command.argv:
                for name in re.findall(r"\{\{fixtures\}\}/([A-Za-z0-9_.\-]+)", token):
                    referenced.add((name, command.exit_code))
        for check in lab.checks:
            path = getattr(check, "file", "")
            for name in re.findall(r"\{\{fixtures\}\}/([A-Za-z0-9_.\-]+)", path):
                referenced.add((name, 0))
        for name, expected_exit in referenced:
            exists = (labs_root() / lab.day / "fixtures" / name).is_file()
            if exists:
                continue
            assert expected_exit != 0, f"{lab.day}/{name} is missing but its command must exit 0"


def test_shared_fixtures_are_byte_copies_of_the_examples() -> None:
    """labs/README.md promises the lab copy and ``examples/`` are the same bytes.

    Two files that drift apart would make "same command, same data" a lie
    depending on whether you are in a checkout or running the wheel.
    """
    pairs = [
        (
            labs_root() / "_shared" / "fixtures" / "sample_tickets.csv",
            REPO_ROOT / "examples" / "quickstart_csv" / "sample_tickets.csv",
        ),
        (
            labs_root() / "_shared" / "fixtures" / "station_samples.jsonl",
            REPO_ROOT / "examples" / "quickstart_manufacturing" / "station_samples.jsonl",
        ),
    ]
    for lab_copy, original in pairs:
        assert lab_copy.is_file() and original.is_file(), f"missing {lab_copy} or {original}"
        assert lab_copy.read_bytes() == original.read_bytes(), f"{lab_copy.name} differs from examples/"


# ---------------------------------------------------------------------------
# writing items vs starter files
# ---------------------------------------------------------------------------


def test_writing_items_and_starter_files_correspond_exactly() -> None:
    """10 writing items grade 10 starter documents — no orphan, no ungraded page.

    A starter file nothing reads is a document the student writes for nobody;
    a writing item with no starter fails cold with a hint pointing at an empty
    directory.
    """
    for lab in LABS:
        wanted = {Path(c.file).name for c in writing_checks(lab)}
        starter = labs_root() / lab.day / "starter"
        on_disk = {p.name for p in starter.iterdir()} if starter.is_dir() else set()
        assert wanted == on_disk, f"{lab.day}: graded {sorted(wanted)} but starter has {sorted(on_disk)}"
        for check in writing_checks(lab):
            assert "{{drafts}}" in check.file, (
                f"{lab.day}/{check.id} grades a scratch file, not the student's page"
            )
            assert "TODO" in check.not_contains, (
                f"{lab.day}/{check.id} does not actually forbid the placeholder"
            )


def test_d1_has_no_starter_because_it_grades_no_writing() -> None:
    assert not writing_checks(lab_for("D1"))
    assert not (labs_root() / "D1" / "starter").exists()


# ---------------------------------------------------------------------------
# the README is the spec: parse it, then agree with it
# ---------------------------------------------------------------------------

README = LABS_DIR / "README.md"


def _readme_day_split(label: str, separator: str) -> dict[str, tuple[int, int]]:
    """``D1 10+1｜D2 14+1｜…`` or ``D1 10/0｜D2 13/1｜…`` out of labs/README.md.

    The parenthesised run after *label* is the unit read, because the prose
    wraps mid-list: a line-anchored regex would silently match the first two
    days and pass on the wrong totals.
    """
    text = README.read_text(encoding="utf-8")
    at = text.find(label)
    assert at >= 0, f"labs/README.md no longer contains {label!r}"
    window = text[at : at + 400]
    close = window.find("）")
    assert close > 0, f"{label!r} is no longer a parenthesised list"
    pairs = re.findall(rf"(D[1-8])\s+(\d+){re.escape(separator)}(\d+)", window[:close])
    assert len(pairs) == 8, f"{label!r} lists {len(pairs)} days, expected 8: {pairs}"
    split = {day: (int(a), int(b)) for day, a, b in pairs}
    assert len(split) == 8, f"{label!r} names a day twice: {pairs}"
    return split


def test_readme_totals_match_the_registry() -> None:
    """Both README lines are pinned: 89+9 machine/manual and 79+10 contract/writing."""
    text = README.read_text(encoding="utf-8")
    machine = sum(len(machine_checks(lab)) for lab in LABS)
    manual = sum(1 for lab in LABS for c in lab.checks if isinstance(c, ManualCheck))
    contract = sum(len(contract_checks(lab)) for lab in LABS)
    writing = sum(len(writing_checks(lab)) for lab in LABS)

    assert re.search(rf"\*\*{machine} 个判分项 \+ {manual} 个人工项\*\*", text), (
        f"README must say {machine} 判分项 + {manual} 人工项"
    )
    assert re.search(rf"\*\*{contract} 个契约项 \+ {writing} 个写作项\*\*", text), (
        f"README must say {contract} 契约项 + {writing} 写作项"
    )
    assert contract + writing == machine, "the two classes must partition the machine items"


def test_readme_per_day_split_matches_the_registry() -> None:
    scored = _readme_day_split("按天：", "+")
    for lab in LABS:
        machine, manual = scored[lab.day]
        assert machine == len(machine_checks(lab)), (
            f"README says {lab.day}={machine} 判分项, registry has {len(machine_checks(lab))}"
        )
        assert manual == sum(1 for c in lab.checks if isinstance(c, ManualCheck)), (
            f"README {lab.day} manual count is off"
        )

    classes = _readme_day_split("按天 契约/写作：", "/")
    for lab in LABS:
        contract, writing = classes[lab.day]
        assert (contract, writing) == (len(contract_checks(lab)), len(writing_checks(lab))), (
            f"README says {lab.day}={contract}契约/{writing}写作, registry says "
            f"{len(contract_checks(lab))}/{len(writing_checks(lab))}"
        )
    assert sum(a for a, _ in classes.values()) == 81, (
        "the cold-green count the README quotes is the contract total"
    )


def test_readme_cold_oracle_sentence_agrees_with_the_registry() -> None:
    """The sentence '正确结论是 **79 绿 / 10 红**' is a claim about a real run."""
    text = README.read_text(encoding="utf-8")
    contract = sum(len(contract_checks(lab)) for lab in LABS)
    writing = sum(len(writing_checks(lab)) for lab in LABS)
    assert re.search(rf"\*\*{contract} 绿 / {writing} 红\*\*", text), (
        f"README must quote the cold result as {contract} 绿 / {writing} 红"
    )


# ---------------------------------------------------------------------------
# verifier helpers
# ---------------------------------------------------------------------------


def test_cli_prefix_is_the_interpreter_under_test() -> None:
    assert cli_prefix() == (sys.executable, "-m", "fde_scope")
    assert cli_prefix()[0] == sys.executable, "a stale global fde-scope must not grade the lab"


def test_labs_root_resolves_inside_this_repo() -> None:
    root = labs_root()
    assert root.is_dir()
    assert root.name == "labs"
    assert (root / "_shared" / "fixtures" / "sample_tickets.csv").is_file()
    for day in DAYS:
        assert (root / day / "README.md").is_file(), (
            f"{day} has no README — course doctor would still call it ok"
        )


def test_draft_dir_is_absolute_and_under_the_data_root() -> None:
    """Must not inherit ``data_root()``'s relative-CWD fallback (rule 4): grading
    the same file twice from two directories has to give the same answer."""
    for lab in LABS:
        path = draft_dir(lab.day)
        assert path.is_absolute(), f"{lab.day} draft dir is relative: {path}"
        assert path.parts[-2:] == ("course-labs", lab.day), (
            f"{lab.day} drafts land in an unexpected layout: {path}"
        )
        assert path == (paths.data_root() / "course-labs" / lab.day).expanduser().resolve()


def test_seed_drafts_copies_once_and_never_overwrites(tmp_path: Path) -> None:
    target = tmp_path / "drafts"
    _seed_drafts("D6", target)
    first = {p.name: p.read_bytes() for p in target.iterdir()}
    assert first, "D6 has starter files, so seeding must produce them"
    (target / "Runbook.md").write_text("我写好的 runbook\n", encoding="utf-8")
    _seed_drafts("D6", target)
    assert (target / "Runbook.md").read_text(encoding="utf-8") == "我写好的 runbook\n", (
        "seeding clobbered the student"
    )
    assert {p.name for p in target.iterdir()} == set(first)


def test_seed_drafts_is_a_no_op_for_days_without_a_starter(tmp_path: Path) -> None:
    target = tmp_path / "d1"
    _seed_drafts("D1", target)
    assert target.is_dir() and list(target.iterdir()) == []


@pytest.mark.parametrize(
    ("payload", "path", "expected"),
    [
        ({"a": {"b": 1}}, "a.b", 1),
        ({"splits": {"train": [1, 2, 3]}}, "splits.train#len", 3),
        ({"bad_cases": {"by_category": {"门店投诉": 2}}}, "bad_cases.by_category.门店投诉", 2),
        ([{"x": 1}, {"x": 2}], "1.x", 2),
        ({"a": 1}, "a.b", None),
        ({"a": 1}, "a.b.c", None),
        ([1, 2], "9", None),
        ({"a": ["s"]}, "a#len", 1),
        ({"a": {"b": "文本"}}, "a.b#len", 2),
        ({"a": None}, "a#len", 0),
        # a key that is absent loses the walk before #len is ever reached (measured)
        ({"a": {}}, "a.b#len", None),
    ],
)
def test_resolve_paths(payload, path, expected) -> None:
    assert _resolve(payload, path) == expected


def test_resolve_len_reads_null_as_zero_and_missing_as_no_number() -> None:
    """``#len`` of a JSON null is 0, so the metric fails on its threshold with a
    number in the message instead of dying on a TypeError. A key that was never
    there reads as ``None`` — "this payload does not carry that field" is a
    different diagnosis, and the check says so rather than claiming zero rows.
    """
    assert _resolve({"a": {"b": None}}, "a.b#len") == 0
    assert _resolve({"a": 1}, "missing#len") is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"a": 1}', {"a": 1}),
        ("banner\n[1, 2]\nfooter", [1, 2]),
        ('✅ skill added\n{"id": "sk-1", "n": 2}\ndone', {"id": "sk-1", "n": 2}),
        ('{"s": "}{ still a string"}', {"s": "}{ still a string"}),
        ('{"esc": "a\\"{b"}', {"esc": 'a"{b'}),
        ("no json here", None),
        ("", None),
        ("{unbalanced", None),
    ],
)
def test_extract_json_finds_the_first_balanced_document(text, expected) -> None:
    assert _extract_json(text) == expected


def test_extract_json_skips_a_broken_candidate_and_keeps_looking() -> None:
    assert _extract_json('{oops}\n{"ok": true}') == {"ok": True}


def test_workspace_substitutes_tokens_and_reports_the_strays() -> None:
    lab = lab_for("D2")
    workspace = LabWorkspace.create(lab)
    try:
        assert workspace.sub("{{eid}}") == lab.eid
        assert workspace.sub("{{drafts}}/x.md") == str(draft_dir("D2") / "x.md")
        assert workspace.sub("{{fixtures}}/x").startswith(str(labs_root() / "D2" / "fixtures"))
        assert workspace.unresolved_tokens() == []
        # ``sub`` is silent; only ``run`` records a stray, and it records it once
        assert workspace.sub("{{nope}}") == "{{nope}}"
        assert workspace.unresolved_tokens() == []
        code, _text = workspace.run(Command(argv=("engage", "status", "{{nope}}")))
        assert code != 0, "an unsubstituted token must not quietly look up a real engagement"
        assert workspace.unresolved_tokens() == ["nope"]
        workspace.run(Command(argv=("engage", "status", "{{nope}}")))
        assert workspace.unresolved_tokens() == ["nope"]
    finally:
        workspace.dispose()


def test_workspace_runs_a_real_command_in_its_own_sandbox() -> None:
    """The subprocess env is the isolation: ``FDE_SCOPE_HOME`` points at the
    scratch dir, so a lab can neither read nor write the developer's data root."""
    lab = lab_for("D1")
    workspace = LabWorkspace.create(lab)
    status = Command(argv=("engage", "status", "{{eid}}", "--json"), read_only=True)
    try:
        code, _text = workspace.run(lab.setup[0])
        assert code == 0, "engage init must succeed before any status check"
        assert workspace.unresolved_tokens() == []
        code, text = workspace.run(status)
        assert code == 0, text
        assert Path(workspace._tokens["home"]).is_absolute()  # noqa: SLF001 — token table is the contract here
        payload = _extract_json(text)
        assert payload is not None and payload["engagement_id"] == lab.eid
        assert payload["customer"] == "西岸家电" and payload["profile"] == lab.profile
        # the engagement really lives in the scratch home, not in the test's home
        home = Path(workspace._tokens["home"])  # noqa: SLF001 — token table is the contract here
        assert str(home) != str(paths.data_root())
        record = home / paths.DATA_SUBDIR / "engagements" / f"{lab.eid}.json"
        assert record.is_file(), f"{lab.eid} was written outside the sandbox: expected {record}"
        assert not (paths.data_root() / paths.DATA_SUBDIR / "engagements" / f"{lab.eid}.json").exists()
        # cached on the *substituted* argv, so two spellings of one command share one entry
        assert workspace.run(status) == (code, text)
        assert list(workspace._cache) == [("engage", "status", lab.eid, "--json")]  # noqa: SLF001
    finally:
        workspace.dispose()


def test_workspace_cleans_up_unless_keep_is_set() -> None:
    lab = lab_for("D1")
    workspace = LabWorkspace.create(lab)
    root = workspace.root
    assert root.is_dir()
    workspace.dispose()
    assert not root.exists()

    kept = LabWorkspace.create(lab, keep=True)
    kept.dispose()
    assert kept.root.exists(), "--keep is how a student sees which file the grader read"
    shutil.rmtree(kept.root, ignore_errors=True)


# ---------------------------------------------------------------------------
# G0 doctor
# ---------------------------------------------------------------------------

REQUIRED_IDS = {"python", "package", "labs", "fixtures", "data-root"}
OPTIONAL_IDS = {"entry-point", "columns", "llm", "agentscope"}


def test_doctor_reports_every_g0_row_once_in_a_fixed_order() -> None:
    items = doctor_module.doctor()
    ids = [item.id for item in items]
    assert len(ids) == len(set(ids))
    assert set(ids) >= REQUIRED_IDS and set(ids) >= OPTIONAL_IDS
    assert set(ids) == REQUIRED_IDS | OPTIONAL_IDS
    assert ids[:5] == ["python", "package", "labs", "fixtures", "data-root"], "required rows must lead"


def test_optional_rows_can_never_block_a_student() -> None:
    """No key, no Docker, no AgentScope, a narrow terminal — all survivable.

    ``06`` §2 says the bootcamp is completable zero-key; a doctor that failed on
    an optional row would tell a student their environment is broken when it is
    not.
    """
    for item in doctor_module.doctor():
        if item.id in OPTIONAL_IDS:
            assert item.required is False, f"{item.id} is optional but marked required"
        assert item.blocking == (item.required and item.status == "fail")


def test_doctor_exits_zero_on_a_healthy_checkout() -> None:
    code, items, payload = doctor_report()
    blockers = [item.id for item in items if item.blocking]
    assert blockers == [], [item.line() for item in items if item.status == "fail"]
    assert code == 0 and payload["ok"] is True and payload["blockers"] == []


def test_doctor_exits_one_when_a_required_row_fails(monkeypatch) -> None:
    monkeypatch.setattr(doctor_module, "labs_root", lambda: Path("/nonexistent/labs"))
    code, _items, payload = doctor_report()
    assert code == 1
    assert "labs" in payload["blockers"]


def test_doctor_data_root_row_agrees_with_paths(monkeypatch, tmp_path: Path) -> None:
    """The four-rule mirror is verified, not trusted: doctor must name the same
    directory ``paths.data_root()`` returns, and rule 1 must win when set."""
    monkeypatch.setenv("FDE_SCOPE_HOME", str(tmp_path))
    code, items, _payload = doctor_report()
    row = next(item for item in items if item.id == "data-root")
    assert code == 0, row.line()
    assert str(paths.data_root()) in row.detail
    assert row.status == "ok"
    assert "rule 1" in row.detail


def test_doctor_never_prints_a_credential(monkeypatch) -> None:
    """AGENTS.md invariant 3 — 'is the env var set' is the whole report.

    A sentinel value is asserted absent from both renderings, so a future
    'helpful' key prefix in a hint or detail line fails here instead of leaking
    into a screenshot a student posts.
    """
    sentinel = "sk-SENTINEL-do-not-print-0123456789"
    from fde_scope import llm

    monkeypatch.setenv(llm._ENV_KEY, sentinel)  # noqa: SLF001 — the env name is the contract
    code, items, payload = doctor_report()
    rendered = "\n".join(item.line() for item in items) + json.dumps(payload, ensure_ascii=False)
    assert sentinel not in rendered
    llm_row = next(item for item in items if item.id == "llm")
    assert llm_row.status == "ok" and llm_row.required is False
    assert code == 0


def test_doctor_summary_counts_are_the_items() -> None:
    _code, items, payload = doctor_report()
    assert payload["gate"] == "G0"
    for status in ("ok", "warn", "info", "fail"):
        assert payload["summary"][status] == sum(1 for item in items if item.status == status)
    assert len(payload["items"]) == len(items)


def test_doctor_labs_row_counts_match_the_registry() -> None:
    """The doctor prints the totals a student will be compared against."""
    _code, items, _payload = doctor_report()
    row = next(item for item in items if item.id == "labs")
    machine = sum(len(machine_checks(lab)) for lab in LABS)
    manual = sum(1 for lab in LABS for c in lab.checks if isinstance(c, ManualCheck))
    assert f"{len(LABS)} 天" in row.detail
    assert f"{machine} 个判分项 + {manual} 个人工项" in row.detail


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------

runner = CliRunner()


def test_course_doctor_cli_text_and_json_agree() -> None:
    text_run = runner.invoke(app, ["course", "doctor"])
    assert text_run.exit_code == 0, text_run.stdout
    json_run = runner.invoke(app, ["course", "doctor", "--json"])
    assert json_run.exit_code == 0
    payload = json.loads(json_run.stdout)
    assert payload["ok"] is True
    for item in payload["items"]:
        assert item["id"] in text_run.stdout, f"{item['id']} missing from the human report"


def test_course_labs_cli_totals_match_the_registry() -> None:
    result = runner.invoke(app, ["course", "labs"])
    assert result.exit_code == 0
    machine = sum(len(machine_checks(lab)) for lab in LABS)
    manual = sum(1 for lab in LABS for c in lab.checks if isinstance(c, ManualCheck))
    assert f"合计：{machine} 个机器判分项 + {manual} 个人工项" in re.sub(
        r"\s+", " ", result.stdout.replace("｜", " ")
    )


@pytest.mark.parametrize("bad", ["D9", "bogus", "D0"])
def test_course_check_rejects_an_unknown_day_with_exit_two(bad: str) -> None:
    result = runner.invoke(app, ["course", "check", bad])
    assert result.exit_code == 2
    # rich wraps at the runner's 80 columns; the message is one sentence, not one line
    assert "unknown lab" in re.sub(r"\s+", " ", result.stdout)


# ---------------------------------------------------------------------------
# the two oracles — real runs, real CLI, the documented numbers
# ---------------------------------------------------------------------------


def test_cold_run_all_fails_exactly_the_writing_items() -> None:
    """A machine that has written nothing: 81 green, 10 red, 9 manual, exit 1.

    This is the run labs/README.md quotes. The red set must equal the writing
    set — a red contract item means the tool or the lesson drifted, and it is
    that distinction (not a green board) the course is selling.
    """
    results = run_all()
    passed = sum(r.passed for r in results)
    failed = sum(r.failed for r in results)
    manual = sum(r.manual for r in results)
    assert (passed, failed, manual) == (81, 10, 9), [r.lines() for r in results if not r.ok]

    assert all(r.ok for r in results if r.day == "D1"), "D1 grades no writing, so it must be green cold"
    for r in results:
        assert r.score == r.passed + r.failed
        assert r.ok is (r.failed == 0)
        red = {c["id"] for c in r.as_dict()["checks"] if c["status"] == "fail"}
        assert red == {c.id for c in writing_checks(lab_for(r.day))}, f"{r.day}: unexpected red {red}"

    for r in results:
        for check in r.results:
            if check.status == "fail":
                assert "TODO" in check.detail or "占位" in check.detail, (
                    f"{r.day}/{check.id} red without naming the placeholder"
                )
                assert check.hint, f"{r.day}/{check.id} red with no next step for a self-studying reader"


def test_warm_run_all_is_fully_green() -> None:
    """Every writing item is satisfiable — finish the prose and it goes green.

    Without this, '冷跑在写作项上必然红' is unfalsifiable: a check that no amount
    of writing could pass is a fake gate, which is the诚信 problem the course
    says is a one-vote veto.
    """
    _complete_all_drafts()
    results = run_all()
    assert sum(r.failed for r in results) == 0, [r.lines() for r in results if not r.ok]
    assert sum(r.passed for r in results) == 91
    assert sum(r.manual for r in results) == 9
    assert all(r.ok for r in results)


def test_check_one_day_json_is_parseable_and_scores_only_machine_items() -> None:
    """``course check D2 --json`` is the machine-readable verdict a grader wants."""
    result = runner.invoke(app, ["course", "check", "D2", "--json"])
    assert result.exit_code == 1, result.stdout  # cold: 委托单 is not written yet
    payload = json.loads(result.stdout)
    assert payload["failed"] == 1 and payload["manual"] == 1
    assert [lab["day"] for lab in payload["labs"]] == ["D2"]
    assert payload["ok"] is False
    lab = payload["labs"][0]
    assert lab["score"] == lab["passed"] + lab["failed"] == len(machine_checks(lab_for("D2")))
    by_id = {check.id: check for check in lab_for("D2").checks}
    for item in lab["checks"]:
        assert item["scored"] is (item["status"] != "manual")
        if item["status"] == "manual":
            continue
        check = by_id[item["id"]]
        command = getattr(check, "command", None)
        if command is not None and command.argv:
            assert item["command"], f"D2/{item['id']} ran something but the report hides the command"
        else:
            # no command means the evidence is a file, so the file is the lead it gives away
            named = " ".join(item[key] for key in ("ask", "detail", "hint"))
            assert Path(check.file).name in named, f"D2/{item['id']} grades a file without saying which"


def _complete_all_drafts() -> None:
    """Write each starter into ``{{drafts}}`` with its item's own rules satisfied.

    Content comes from the catalog (``contains``/``not_contains``/``min_bytes``)
    rather than a hand-kept copy, so the test asks only "can this be passed" —
    it cannot paper over an item by knowing the magic words offline.
    """
    for lab in LABS:
        target = draft_dir(lab.day)
        _seed_drafts(lab.day, target)
        for check in writing_checks(lab):
            banned = set(check.not_contains)
            body = [f"# {Path(check.file).name}"]
            for phrase in check.contains:
                if phrase not in banned:
                    body.append(f"- {phrase}：已按课上要求写完。")
            body.append("适用边界、终止条件与签字栏均已填写；证据链接逐条可点。")
            text = "\n".join(body) + "\n"
            for pad in range(200):
                if len(text.encode()) >= check.min_bytes:
                    break
                text += f"第 {pad} 行：值班期间观察到的现象、影响面与下一步都记录在此。\n"
            assert not any(word in text for word in banned), f"{lab.day}/{check.id} cannot be satisfied"
            (target / Path(check.file).name).write_text(text, encoding="utf-8")
