"""fde_scope.course — the Level-1 course's runnable labs.

The course documents an 8-day path with a gate per day (``course-level-1/06``),
but a task card is not a lab: nothing told a self-studying reader whether the
command they pasted actually did what the lesson says it does. This package
turns each day into a machine-scored run.

It deliberately adds **no new grading language**. The CLI already grades:
``gate check`` exits 1 on a blocker, ``kpi``/``eval``/``engage status`` print
``--json`` payloads. A check here is one assertion against that existing
surface, so a lab can never pass while the tool the student is being taught
says something different.

Public surface:
    run_lab / run_all      execute one day's checks in a scratch workspace
    doctor / doctor_report  report the environment before day 1 starts
    LABS                   the D1..D8 registry
    Status                 a check's verdict (pass/fail/manual) — distinct from
                           ``doctor.DoctorItem.status`` (ok/fail/warn/info),
                           because an environment row and a rubric row do not
                           fail in the same way.
"""

from .catalog import LABS, lab_for
from .checks import ArtifactCheck, Command, CommandCheck, ManualCheck, MetricCheck, Status
from .doctor import DoctorItem, doctor, doctor_report
from .verifier import CheckResult, LabResult, run_all, run_lab

__all__ = [
    "LABS",
    "ArtifactCheck",
    "CheckResult",
    "Command",
    "CommandCheck",
    "DoctorItem",
    "LabResult",
    "ManualCheck",
    "MetricCheck",
    "Status",
    "doctor",
    "doctor_report",
    "lab_for",
    "run_all",
    "run_lab",
]
