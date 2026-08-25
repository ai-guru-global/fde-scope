"""Layer 4 — the FDE delivery evaluation framework.

An FDE doesn't ship a demo and leave; they prove value with a benchmark and
keep improving via bad-case mining. This layer is framework-agnostic: the
agent under test is just a ``str -> str`` callable, so a real AgentScope
``Agent`` and the built-in mock both plug in identically.
"""

from .bad_case_miner import BadCase, BadCaseMiner, BadCaseReport
from .benchmark import EvalReport, FDEBenchmark, MiMoReplyFn, MockReplyFn
from .metrics import METRICS, Dimension, EvalCase, ReplyFn

__all__ = [
    "FDEBenchmark",
    "EvalReport",
    "MockReplyFn",
    "MiMoReplyFn",
    "BadCaseMiner",
    "BadCase",
    "BadCaseReport",
    "METRICS",
    "Dimension",
    "EvalCase",
    "ReplyFn",
]
