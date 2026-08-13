"""CorpusReport rendering — HTML deliverable for the FDE ↔ customer handoff.

The report is the tangible output of the forge. An FDE walks a customer
through it line by line: how many real samples survived, where the gaps
were, how many were synthesized and why, and how the data was split.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .types import CorpusReport

# Templates ship inside the package so the rendered report works regardless
# of the caller's CWD.
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def _env() -> Environment:
    # The templates are named *.html.j2 / *.md.j2, so suffix-based autoescape
    # selection would miss them entirely — force it on for every template.
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(default_for_string=True, default=True),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_html(report: CorpusReport) -> str:
    """Render a CorpusReport to a self-contained HTML string."""
    env = _env()
    template = env.get_template("corpus_report.html.j2")
    return template.render(report=report)


def save_html(report: CorpusReport, path: str | Path) -> Path:
    """Render and write the report to ``path``."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render_html(report), encoding="utf-8")
    return p
