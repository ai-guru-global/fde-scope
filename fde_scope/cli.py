"""fde-scope CLI — the FDE's daily driver.

Five subcommands mirror the FDE workflow: ``connect`` → ``corpus`` →
``deploy`` → ``eval`` → ``flywheel``. Scriptable output: ``deploy``, ``eval``,
``kpi``, ``engage status``/``list``/``retrospective``/``stakeholder list``/``criterion list``/
``slo list``/``site show``, ``skill list``, ``gate check`` and the
``ontology`` read/validate commands accept ``--json`` (plain JSON on stdout,
no rich markup). ``--version`` and ``--install-completion`` work app-wide.
"""

from __future__ import annotations

import json
import os
from contextlib import suppress
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.table import Table

from . import __version__, paths
from .fsutil import atomic_write_text

if TYPE_CHECKING:
    from .config import AgentSpec, TenantConfig
    from .skills.service import SkillService


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"fde-scope {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="fde-scope",
    help="FDE Scope — 72h from raw data to a deployed agent. Built on AgentScope 2.0.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@app.callback()
def _root_callback(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """FDE Scope — 72h from raw data to a deployed agent. Built on AgentScope 2.0.

    Logging is configured here (not in ``main()``) so both entry points —
    ``fde-scope`` and ``python -m fde_scope.cli`` — behave identically."""
    from .logutil import configure_logging

    configure_logging()


console = Console()


def _banner(title: str) -> None:
    console.print(f"\n[bold cyan]FDE Scope[/bold cyan] v{__version__} — {title}\n")


def _echo_json(payload: object) -> None:
    """Write a JSON document to stdout verbatim.

    ``--json`` promises "plain JSON, no rich markup" (see the module docstring):
    rich re-wraps long string values at the console width, which makes the output
    unparseable, so machine-readable payloads bypass the console entirely.
    """
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# LLM wiring (Xiaomi MiMo Token Plan — optional, env-configured)
# ---------------------------------------------------------------------------
def _maybe_llm(require: bool = False, quiet: bool = False):
    """Build the env-selected LLM client; exit cleanly when no key is configured.

    ``quiet`` suppresses the fallback notice — ``--json`` output must stay
    parseable, and the manifest itself already carries the LLM state."""
    from .llm import get_llm_client

    client = get_llm_client()
    if not client.available:
        if require:
            console.print(
                "[red]LLM not configured:[/red] set FDE_SCOPE_MIMO_API_KEY "
                "(Xiaomi MiMo Token Plan, tp-… format) or FDE_SCOPE_LLM_BASE_URL+"
                "FDE_SCOPE_LLM_API_KEY (OpenAI-compatible) to enable LLM mode."
            )
            raise typer.Exit(2)
        if not quiet:
            console.print(
                "[yellow]LLM disabled (FDE_SCOPE_MIMO_API_KEY / FDE_SCOPE_LLM_* not set)[/yellow] — "
                "falling back to rule-based mode.\n"
            )
    return client


# ---------------------------------------------------------------------------
# connect
# ---------------------------------------------------------------------------
@app.command()
def connect(
    type: str = typer.Option("csv", "--type", "-t", help="Connector type: csv|zammad|salesforce|mysql"),
    source: str = typer.Option(..., "--source", "-s", help="Path or URL of the data source"),
    sample_size: int = typer.Option(100, "--sample-size", help="Rows to extract for preview"),
    api_key: str | None = typer.Option(None, "--api-key", help="API token (zammad/salesforce)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan only; don't read data"),
) -> None:
    """[Layer 1] Connect to a data source and preview its schema + sample."""
    _banner(f"connect · {type}")
    if dry_run:
        console.print(f"[yellow]DRY-RUN[/yellow] would connect type={type} source={source}")
        raise typer.Exit(0)

    from .connectors._registry import get as get_connector

    try:
        cls = get_connector(type)
    except KeyError as exc:
        console.print(f"[red]Unknown connector type:[/red] {exc}")
        raise typer.Exit(2) from exc

    connector = cls(source, api_key=api_key) if api_key else cls(source)
    schema = connector.discover_schema()
    sample = connector.extract_sample(sample_size)

    table = Table(title=f"Schema · {schema.source}")
    table.add_column("field", style="cyan")
    table.add_column("type")
    table.add_column("nullable")
    table.add_column("PII?", style="yellow")
    for f in schema.fields:
        table.add_row(f.name, f.inferred_type, str(f.nullable), "⚠" if f.pii_candidate else "")
    console.print(table)
    console.print(
        f"\nrows≈[bold]{schema.row_count}[/bold] · "
        f"categories={schema.detected_categories} · "
        f"channels={schema.detected_channels} · "
        f"sample_size={len(sample)}"
    )

    out = paths.data_root() / "samples" / "preview.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(out, json.dumps(sample, ensure_ascii=False, indent=2))
    console.print(f"\n✅ Sample extracted → [green]{out}[/green]")


# ---------------------------------------------------------------------------
# corpus
# ---------------------------------------------------------------------------
@app.command()
def corpus(
    input: str = typer.Option(..., "--input", "-i", help="Input dir/file of raw rows (JSON) or CSV path"),
    config: str = typer.Option(
        "fde_scope/templates/corpus_config.yaml", "--config", "-c", help="CorpusConfig YAML"
    ),
    out: str | None = typer.Option(
        None, "--out", "-o", help="Output HTML report path (default: <data root>/reports/corpus_report.html)"
    ),
    llm: bool = typer.Option(
        False, "--llm", help="Synthesize gap-filling samples with MiMo (needs FDE_SCOPE_MIMO_API_KEY)"
    ),
    ontology: bool = typer.Option(False, "--ontology", help="启用本体概念注解与概念级覆盖"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan only; don't forge"),
) -> None:
    """[Layer 2] Forge a raw sample into an auditable, gap-aware corpus."""
    _banner("corpus forge")
    if dry_run:
        console.print(f"[yellow]DRY-RUN[/yellow] would forge input={input} config={config}")
        raise typer.Exit(0)

    from .config import CorpusConfig
    from .corpus import CorpusForge, save_html, save_report_json

    out = out or str(paths.reports_dir() / "corpus_report.html")
    client = _maybe_llm(require=llm) if llm else None
    cfg = CorpusConfig.from_yaml(config) if Path(config).exists() else CorpusConfig()
    rows = _load_rows(input)
    console.print(f"🔄 Loaded [bold]{len(rows)}[/bold] raw rows")

    schema = None
    if ontology:
        from .ontology.store import OntologyStore

        schema = OntologyStore().load_schema("fde-corpus-taxonomy")
        if schema is None:
            console.print("[red]Ontology schema not found:[/red] fde-corpus-taxonomy")
            raise typer.Exit(2)
        console.print(f"🧠 Ontology: [bold]{schema.id}[/bold] ({len(schema.concept_schemes)} schemes)")

    forge = CorpusForge(cfg, llm=client, ontology=schema)
    report = forge.forge_rows(rows)

    console.print(f"✅ PII entities masked: [bold]{report.pii_entities_masked}[/bold]")
    console.print(f"✅ Dropped (dedup+gate): [bold]{report.dropped}[/bold]")
    console.print(
        f"✅ Corpus forged: [bold]{report.real}[/bold] real + "
        f"[bold]{report.synthetic}[/bold] synthetic = [bold]{report.total}[/bold] total"
    )
    if report.coverage.gaps:
        console.print("[yellow]⚠ Coverage gaps:[/yellow]")
        for g in report.coverage.gaps:
            console.print(f"   • {g.category}: {g.current_count} (need ≥{g.target_count})")
    if report.coverage.concept_counts is not None:
        console.print(f"🧠 Concept coverage: [bold]{len(report.coverage.concept_counts)}[/bold] concepts")
        for cg in report.coverage.concept_gaps or []:
            console.print(f"   • {cg.concept}: {cg.current_count} (need ≥{cg.target_count})")

    save_html(report, out)
    json_out = str(Path(out).parent / "corpus_report.json")
    save_report_json(report, json_out)
    console.print(f"📊 Report → [green]{out}[/green] (+ {json_out})")


def _read_input_text(path: str, what: str) -> str:
    """Read an input file, turning OSError/UnicodeDecodeError into a clean
    message + exit 2 instead of a traceback (C7)."""
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        console.print(f"[red]Cannot read {what}:[/red] {path} ({exc.strerror})")
        raise typer.Exit(2) from None
    except UnicodeDecodeError:
        console.print(f"[red]{what} is not valid UTF-8:[/red] {path}")
        raise typer.Exit(2) from None


def _parse_agent_specs(specs: list[str] | None) -> list[AgentSpec]:
    """Parse repeatable ``name:role[:model]`` options (C10: one implementation
    for ``deploy`` and ``qwenpaw export`` — they used to be copy-pasted)."""
    from .config import AgentSpec

    agents: list[AgentSpec] = []
    for a in specs or []:
        parts = a.split(":")
        if len(parts) == 2:
            agent_name, agent_role, agent_model = parts[0], parts[1], None
        elif len(parts) == 3:
            agent_name, agent_role, agent_model = parts
        else:
            console.print(f"[red]Invalid agent spec:[/red] {a} (expected name:role[:model])")
            raise typer.Exit(2)
        agents.append(AgentSpec(name=agent_name, role=agent_role, model=agent_model))
    return agents


def _load_rows(path: str) -> list[dict]:
    """Load raw rows from a JSON array, JSONL, or CSV (delegating to CSVConnector)."""
    p = Path(path)
    if p.is_dir() or p.suffix.lower() == ".csv":
        from .connectors.csv_fallback import CSVConnector

        try:
            return CSVConnector(str(p)).extract_sample(100000)
        except FileNotFoundError:
            console.print(f"[red]CSV source not found:[/red] {path}")
            raise typer.Exit(2) from None
    text = _read_input_text(path, "input file").strip()
    try:
        if p.suffix.lower() == ".jsonl" or (text and text[0] != "["):
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        return json.loads(text)
    except json.JSONDecodeError as exc:
        console.print(f"[red]Input is not valid JSON/JSONL:[/red] {path} (line {exc.lineno})")
        raise typer.Exit(2) from None


# ---------------------------------------------------------------------------
# deploy
# ---------------------------------------------------------------------------
@app.command()
def deploy(
    tenant: str = typer.Option(..., "--tenant", "-t", help="Tenant ID"),
    name: str = typer.Option("Tenant", "--name", help="Tenant display name"),
    corpus: str | None = typer.Option(None, "--corpus", help="Path to forged corpus JSON"),
    model: str = typer.Option("qwen-max", "--model", "-m", help="Model config name"),
    agent_specs: list[str] | None = typer.Option(
        None, "--agent", "-a", help="Agent spec 'name:role[:model]' (repeatable)"
    ),
    sources: list[str] | None = typer.Option(
        None,
        "--connector-source",
        help="Bind a role connector to its physical source 'slug=value' (repeatable), "
        "e.g. --connector-source csv=data/t.csv --connector-source documents=docs/",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan only; don't assemble/start"),
    serve: bool = typer.Option(
        False,
        "--serve",
        help="Opt-in runtime: build the real AgentScope app and serve it (needs agentscope + Redis + a reachable model)",
    ),
    as_json: bool = typer.Option(False, "--json", help="Print the manifest as plain JSON (no rich markup)"),
) -> None:
    """[Layer 3] Assemble (and optionally start) a multi-tenant agent."""
    if not as_json:
        _banner(f"deploy · {tenant}")
    from .config import TenantConfig
    from .deploy import TenantDeployer

    agents = _parse_agent_specs(agent_specs)
    source_map = _parse_kv_list(sources, "--connector-source", "slug=value")
    cfg = TenantConfig(
        id=tenant, name=name, model=model, corpus_path=corpus, agents=agents or None, sources=source_map
    )
    corpus_report = None
    if corpus:
        from .corpus import CorpusReport

        try:
            corpus_report = CorpusReport.model_validate_json(Path(corpus).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            console.print(f"[red]Cannot load corpus report:[/red] {corpus} ({exc})")
            raise typer.Exit(2) from exc
    client = _maybe_llm(quiet=as_json)
    deployer = TenantDeployer()
    with console.status("assembling deploy plan…"):
        deployed = deployer.deploy(cfg, corpus_report=corpus_report, dry_run=dry_run)
    if client.available:
        deployed.manifest["llm"] = client.describe()

    if as_json:
        console.print_json(json.dumps(deployed.manifest, ensure_ascii=False, default=str))
        return
    console.print(f"🔄 Sandbox: [bold]{deployed.manifest['sandbox']['backend']}[/bold]")
    console.print(f"🔄 Corpus collection: [bold]{deployed.corpus_collection}[/bold]")
    console.print(f"🔄 Model: [bold]{deployed.manifest['model']}[/bold]")
    if client.available:
        console.print(f"🔄 LLM: [bold]{client.model}[/bold] @ {client.base_url}")
    else:
        console.print("🔄 LLM: [yellow]未配置（设 FDE_SCOPE_MIMO_API_KEY 或 FDE_SCOPE_LLM_* 启用）[/yellow]")
    console.print("🔄 Permissions:")
    console.print(f"   allow={deployed.manifest['permissions']['allow']}")
    console.print(f"   deny={deployed.manifest['permissions']['deny']}")
    if deployed.is_assembled:
        console.print("✅ Agent deployed! (runtime)")
    else:
        console.print("✅ Deployment plan assembled (dry-run / core-only)")
    for a in deployed.manifest.get("agents") or []:
        console.print(
            f"🔄 Agent: [bold]{a['name']}[/bold] · {a['role']} · model={a['model'] or 'runtime'} · connectors={a.get('connectors')}"
        )
        for tool in a.get("tools") or []:
            mark = "[green]✓[/green]" if tool["bound"] else "[yellow]·[/yellow]"
            console.print(f"   {mark} {tool['tool']:24s} {tool['note']}")
    console.print(f"📋 Manifest → [green]{json.dumps(deployed.manifest, ensure_ascii=False)}[/green]")

    if serve:
        _serve_app(cfg)


def _parse_kv_list(values: list[str] | None, flag: str, shape: str) -> dict[str, str]:
    """Parse repeatable ``--flag key=value`` options into a dict (exit 2 on junk)."""
    out: dict[str, str] = {}
    for v in values or []:
        key, sep, val = v.partition("=")
        if not sep or not key.strip() or not val.strip():
            console.print(f"[red]Invalid {flag}:[/red] {v} (expected {shape})")
            raise typer.Exit(2)
        out[key.strip()] = val.strip()
    return out


def _serve_app(cfg: TenantConfig) -> None:
    """Build the real AgentScope app for ``cfg`` and serve it (opt-in runtime).

    Kept out of the default path: constructing needs the agentscope extra, and
    serving requires a reachable Redis + model. This is the explicit
    ``deploy --serve`` step that goes beyond assembly.
    """
    from .deploy import build_app

    try:
        import uvicorn
    except ImportError:
        console.print("[red]--serve 需要 uvicorn[/red]：pip install 'fde-scope[web]' 后重试")
        raise typer.Exit(2) from None
    try:
        as_app = build_app(cfg)
    except ImportError as exc:
        console.print(
            f"[red]--serve 需要 agentscope extra[/red]：pip install 'fde-scope[agentscope]'（{exc}）"
        )
        raise typer.Exit(2) from exc
    console.print("🚀 Serving AgentScope app (Ctrl-C to stop) — needs Redis + model at run time")
    uvicorn.run(as_app, host="127.0.0.1", port=8000)


# ---------------------------------------------------------------------------
# eval
# ---------------------------------------------------------------------------
@app.command("eval")
def eval_command(
    agent: str = typer.Option(
        "mock", "--agent", "-a", help="Agent: 'mock' (rule-based) or 'mimo' (MiMo LLM)"
    ),
    test_set: str = typer.Option(..., "--test-set", help="Path to eval cases (JSON/JSONL)"),
    accuracy: float = typer.Option(0.9, "--accuracy", help="Mock agent accuracy (0-1)"),
    as_json: bool = typer.Option(False, "--json", help="Print the report as plain JSON (no rich markup)"),
) -> None:
    """[Layer 4] Run the FDE benchmark over a test set."""
    if not as_json:
        _banner(f"eval · {agent}")
    from .eval import FDEBenchmark, MiMoReplyFn, MockReplyFn, ReplyFn
    from .llm import LLMError

    cases = _load_eval_cases(test_set)
    reply_fn: ReplyFn
    if agent == "mock":
        reply_fn = MockReplyFn(accuracy=accuracy)
    elif agent == "mimo":
        client = _maybe_llm(require=True)
        reply_fn = MiMoReplyFn(client)
    else:
        console.print(f"[red]Unknown agent:[/red] {agent!r} — use 'mock' (rule-based) or 'mimo' (MiMo LLM).")
        raise typer.Exit(2)
    try:
        with console.status(f"running {len(cases)} eval case(s)…"):
            report = FDEBenchmark().run(reply_fn, cases)
    except LLMError as exc:
        # Mid-run endpoint failure: exit cleanly instead of a traceback that
        # discards all context (the benchmark has no rule path to fall back to).
        console.print(f"[red]MiMo eval failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    if as_json:
        console.print_json(report.model_dump_json())
        return
    table = Table(title="Metrics")
    table.add_column("metric", style="cyan")
    table.add_column("value", justify="right")
    table.add_column("label")
    for k, v in report.metrics.items():
        table.add_row(k, f"{v:.3f}", report.metric_labels.get(k, ""))
    console.print(table)

    if report.bad_cases.total_failures:
        console.print(f"\n[yellow]⚠ Top bad case category:[/yellow] {report.bad_cases.top_category}")
        console.print(f"💡 [green]{report.bad_cases.recommendation}[/green]")


def _load_eval_cases(path: str) -> list:
    p = Path(path)
    text = _read_input_text(path, "test set").strip()
    try:
        if p.suffix.lower() == ".jsonl" or (text and text[0] != "["):
            raw = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            raw = json.loads(text)
    except json.JSONDecodeError as exc:
        console.print(f"[red]Test set is not valid JSON/JSONL:[/red] {path} (line {exc.lineno})")
        raise typer.Exit(2) from None
    from .eval import EvalCase

    return [EvalCase.model_validate(r) for r in raw]


# ---------------------------------------------------------------------------
# flywheel
# ---------------------------------------------------------------------------
@app.command()
def flywheel(
    agent: str = typer.Option(
        ...,
        "--agent",
        "-a",
        help="Agent ID (recorded in the banner and summary; attaching to a live event stream needs the runtime)",
    ),
    events: str | None = typer.Option(
        None, "--events", help="Path to a JSON array of concept events to replay"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan only; don't collect"),
) -> None:
    """[Layer 5] Start (or replay into) the data flywheel."""
    _banner(f"flywheel · {agent}")
    if dry_run:
        console.print(f"[yellow]DRY-RUN[/yellow] would attach flywheel to agent={agent}")
        raise typer.Exit(0)

    from .flywheel import DataFlywheel

    wheel = DataFlywheel()
    if events:
        try:
            events_raw = json.loads(_read_input_text(events, "events file"))
        except json.JSONDecodeError as exc:
            console.print(f"[red]Events file is not valid JSON:[/red] {events} ({exc})")
            raise typer.Exit(2) from None
        if not isinstance(events_raw, list):
            console.print(f"[red]Events file must be a JSON array:[/red] {events}")
            raise typer.Exit(2)
        for ev in events_raw:
            handled = wheel.handle_concept_event(ev["concept"], ev.get("payload", {}))
            tag = "✓" if handled else "·"
            console.print(f"   [{ev['concept']}] {tag}")
    snap = wheel.snapshot()
    console.print(
        f"\n🔄 Flywheel state (agent={agent}): collected={snap['collected']} "
        f"(golden={snap['golden']}, labeling={snap['labeling_queued']}, "
        f"edge={snap['edge_cases']}, failures={snap['failures']})"
    )
    # These are *descriptors* for an external orchestrator: nothing in this
    # process fires them. The old line claimed "scheduled: next Mon 02:00" —
    # a scheduler that does not exist; keep the panel honest too.
    from .flywheel.retrain_scheduler import RetrainScheduler

    sched = RetrainScheduler()
    console.print("🔄 retrain jobs (descriptors only — no scheduler runs inside this CLI):")
    for job in sched.jobs:
        console.print(f"   {job.name}: cron={job.cron} min_new_samples={job.min_new_samples} kind={job.kind}")


# ===========================================================================
# Engagement SOP (the full 4-zone / 18-phase lifecycle)
# ===========================================================================
engage_app = typer.Typer(name="engage", help="[SOP] FDE engagement state machine.", no_args_is_help=True)
gate_app = typer.Typer(name="gate", help="[SOP] Phase-gate校验器.", no_args_is_help=True)
app.add_typer(engage_app)
app.add_typer(gate_app)


def _engagement_path(engagement_id: str) -> Path:
    return paths.engagements_dir() / f"{engagement_id}.json"


def _load_engagement(engagement_id: str):
    from .engagement import Engagement, EngagementContext

    path = _engagement_path(engagement_id)
    if not path.exists():
        console.print(f"[red]Engagement not found:[/red] {engagement_id}")
        raise typer.Exit(2)
    return Engagement(EngagementContext.load(path))


def _save_engagement(eng) -> None:
    _engagement_path(eng.ctx.id).parent.mkdir(parents=True, exist_ok=True)
    eng.ctx.save(_engagement_path(eng.ctx.id))


@engage_app.command("init")
def engage_init(
    customer: str = typer.Option(..., "--customer", "-c"),
    profile: str = typer.Option("ticket", "--profile", "-p", help="ticket | manufacturing"),
    engagement_id: str | None = typer.Option(None, "--id", help="Explicit engagement id"),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing engagement with the same id"),
) -> None:
    """Start a new FDE engagement."""
    _banner(f"engage init · {profile}")
    from .engagement import Engagement, EngagementContext

    eid = engagement_id or f"eng-{customer.lower().replace(' ', '-')}-{profile}"
    if _engagement_path(eid).exists() and not force:
        console.print(
            f"[red]Engagement already exists:[/red] {eid}\n"
            "Re-run with --force to overwrite it (losing its progress)."
        )
        raise typer.Exit(2)
    ctx = EngagementContext(id=eid, customer=customer, profile=profile)
    eng = Engagement(ctx)
    _save_engagement(eng)
    from . import audit

    audit.log_event(
        "engagement.create",
        actor="cli",
        detail={"engagement_id": eid, "customer": customer, "profile": profile},
    )
    console.print(f"✅ Engagement [bold]{eid}[/bold] created (profile={profile})")
    console.print(f"   phase: {eng.ctx.current_phase} · zone: {eng.ctx.current_zone.value}")
    console.print(f"   visible phases: {len(eng.ctx.visible_phases)}")


@engage_app.command("status")
def engage_status(
    engagement_id: str = typer.Argument(..., help="Engagement id"),
    as_json: bool = typer.Option(
        False, "--json", help="Print the status dict as plain JSON (no rich markup)"
    ),
) -> None:
    """Show engagement status: current phase, zone, gate state, progress."""
    eng = _load_engagement(engagement_id)
    st = eng.status()
    if as_json:
        console.print_json(json.dumps(st, ensure_ascii=False))
        return
    _banner(f"engage status · {engagement_id}")
    console.print(f"customer: [bold]{st['customer']}[/bold] · profile: {st['profile']}")
    console.print(
        f"phase: [cyan]{st['current_phase']}[/cyan] "
        f"(zone: {st['current_zone']}) → next: {st['next_phase'] or '—'}"
    )
    if st["gate"]:
        state = "✅ passed" if st["gate_passed"] else "❌ not passed"
        console.print(f"gate: {st['gate']} ({state})")
    console.print(f"progress: {st['visible_phase_count']} phases visible · complete={st['is_complete']}")
    if st["gate_records"]:
        table = Table(title="Gate records")
        table.add_column("gate")
        table.add_column("passed")
        for slug, rec in st["gate_records"].items():
            table.add_row(slug, "✅" if rec["passed"] else "❌")
        console.print(table)


@engage_app.command("advance")
def engage_advance(
    engagement_id: str = typer.Argument(...),
    force: bool = typer.Option(False, "--force", help="Record gate result but don't block"),
) -> None:
    """Advance to the next SOP phase (gate-enforced)."""
    from . import audit
    from .engagement import AdvanceBlocked

    eng = _load_engagement(engagement_id)
    try:
        nxt = eng.advance(force=force)
    except AdvanceBlocked as exc:
        console.print(f"[red]❌ ADVANCE BLOCKED[/red] — phase={eng.ctx.current_phase}")
        console.print(exc.result.summary())
        _save_engagement(eng)
        audit.log_event(
            "engagement.advance",
            actor="cli",
            detail={"engagement_id": engagement_id, "force": force, "advanced": False},
        )
        _maybe_suggest_skill(engagement_id, eng.ctx.current_phase, list(exc.result.blockers))
        raise typer.Exit(1) from exc
    except StopIteration as exc:
        console.print("[yellow]Engagement already complete.[/yellow]")
        raise typer.Exit(0) from exc
    _save_engagement(eng)
    audit.log_event(
        "engagement.advance",
        actor="cli",
        detail={"engagement_id": engagement_id, "force": force, "advanced": True},
    )
    _maybe_capture("advance", engagement_id, phase_slug=eng.ctx.current_phase)
    console.print(f"✅ Advanced → [cyan]{nxt.slug}[/cyan] ({nxt.name}) · zone={nxt.zone.value}")


@engage_app.command("rollback")
def engage_rollback(
    engagement_id: str = typer.Argument(...),
    to_phase: str = typer.Option(..., "--to", help="Target phase slug"),
) -> None:
    """Roll the engagement back to an earlier phase."""
    from . import audit

    eng = _load_engagement(engagement_id)
    from_phase = eng.ctx.current_phase
    try:
        target = eng.rollback(to_phase)
    except KeyError:
        console.print(f"[red]Unknown phase:[/red] {to_phase}")
        raise typer.Exit(2) from None
    except ValueError as exc:
        console.print(f"[red]Invalid rollback:[/red] {exc}")
        raise typer.Exit(2) from None
    _save_engagement(eng)
    audit.log_event(
        "engagement.rollback",
        actor="cli",
        detail={"engagement_id": engagement_id, "from_phase": from_phase, "to_phase": target.slug},
    )
    console.print(f"⏪ Rolled back → [cyan]{target.slug}[/cyan] ({target.name})")


@engage_app.command("retrospective")
def engage_retrospective(
    engagement_id: str = typer.Argument(..., help="Engagement id"),
    as_json: bool = typer.Option(False, "--json", help="Print the report as plain JSON (no rich markup)"),
    out: Path | None = typer.Option(None, "--out", "-o", help="同时把 Markdown 报告写到该路径"),
) -> None:
    """复盘：SLA 时钟 + 阶段时间线 + gate 统计（audit 流 + context，只读）。"""
    from rich.markdown import Markdown

    from . import audit
    from .engagement.retrospective import build_retrospective, render_markdown

    eng = _load_engagement(engagement_id)
    report = build_retrospective(eng.ctx, list(audit.read_events(engagement_id)))
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(out, render_markdown(report))
    if as_json:
        console.print_json(report.model_dump_json())
        return
    console.print(Markdown(render_markdown(report)))


@engage_app.command("list")
def engage_list(
    as_json: bool = typer.Option(False, "--json", help="Print the list as plain JSON (no rich markup)"),
) -> None:
    """List all local engagements."""
    eng_dir = paths.engagements_dir()
    rows: list[dict] = []
    for p in sorted(eng_dir.glob("*.json")) if eng_dir.exists() else []:
        from .engagement import Engagement, EngagementContext

        st = Engagement(EngagementContext.load(p)).status()
        rows.append(
            {
                "id": st["engagement_id"],
                "customer": st["customer"],
                "profile": st["profile"],
                "phase": st["current_phase"],
                "zone": st["current_zone"],
            }
        )
    if as_json:
        console.print_json(json.dumps(rows, ensure_ascii=False))
        return
    _banner("engagements")
    if not rows:
        console.print("[yellow]No engagements yet.[/yellow]")
        return
    table = Table(title="Engagements")
    for col in ("id", "customer", "profile", "phase", "zone"):
        table.add_column(col)
    for r in rows:
        table.add_row(r["id"], r["customer"], r["profile"], r["phase"], r["zone"])
    console.print(table)


@engage_app.command("journal")
def engage_journal(
    engagement_id: str = typer.Argument(..., help="Engagement id"),
    kind: str = typer.Option("research", "--kind", "-k", help="research | implementation | optimization"),
    note: str | None = typer.Option(None, "--note", "-n", help="记录内容；缺省时只查看"),
    link_skill: str | None = typer.Option(None, "--link-skill", help="关联技能 id（追加时校验存在性）"),
) -> None:
    """Record / view field notes (现场记录：调研/实施/调优)."""
    eng = _load_engagement(engagement_id)
    if note is None:  # 查看模式
        _banner(f"journal · {engagement_id}")
        if not eng.ctx.journal:
            console.print("[yellow]暂无现场记录。[/yellow]")
            console.print('  添加: fde-scope engage journal <id> --kind research --note "..."')
            return
        table = Table(title="Journal")
        for col in ("id", "ts", "kind", "note", "skill"):
            table.add_column(col)
        for e in eng.ctx.journal:
            table.add_row(e.id, e.ts, e.kind, e.note, e.skill_id or "—")
        console.print(table)
        return
    if kind not in ("research", "implementation", "optimization"):
        console.print(f"[red]Invalid kind:[/red] {kind} (research | implementation | optimization)")
        raise typer.Exit(2)
    if link_skill:
        try:
            _skill_service().get(link_skill)
        except KeyError:
            console.print(f"[red]Unknown skill:[/red] {link_skill}")
            raise typer.Exit(2) from None
    from .engagement.context import JournalEntry

    entry = JournalEntry(kind=kind, note=note, skill_id=link_skill)
    eng.ctx.journal.append(entry)
    _save_engagement(eng)
    console.print(f"✅ 已记录 [cyan]{entry.id}[/cyan] ({kind}) · {entry.note}")


# ---------------------------------------------------------------------------
# Pre-engagement inputs — the fields the Zone A gates read
#
# ``site`` / ``stakeholders`` / ``success_criteria`` / ``slos`` used to be
# writable only from the web console, so a CLI-only learner could never drive a
# Zone A gate red or green. These writers go through the same pydantic models
# and the same atomic save; they touch *facts*, never the state machine itself
# (phase / journal / gate_records stay owned by Engagement.advance).
# ---------------------------------------------------------------------------
stakeholder_app = typer.Typer(
    name="stakeholder", help="干系人地图（SuccessCriteriaGate 读取）。", no_args_is_help=True
)
criterion_app = typer.Typer(
    name="criterion", help="合同化成功标准（SuccessCriteriaGate 读取）。", no_args_is_help=True
)
slo_app = typer.Typer(name="slo", help="SLO 定义（SloGate 读取）。", no_args_is_help=True)
site_app = typer.Typer(name="site", help="现场勘察事实（SiteSurveyGate 读取）。", no_args_is_help=True)
engage_app.add_typer(stakeholder_app)
engage_app.add_typer(criterion_app)
engage_app.add_typer(slo_app)
engage_app.add_typer(site_app)


@stakeholder_app.command("add")
def stakeholder_add(
    engagement_id: str = typer.Argument(...),
    name: str = typer.Option(..., "--name", "-n"),
    role: str = typer.Option(..., "--role", "-r"),
    sponsor: bool = typer.Option(False, "--sponsor", help="标记为发起人（需要 ≥2 位才能过关）"),
    success_metric: str = typer.Option("", "--success-metric", help="这位发起人在乎的可度量指标"),
) -> None:
    """Add a stakeholder to the engagement's stakeholder map."""
    from .engagement.context import Stakeholder

    eng = _load_engagement(engagement_id)
    person = Stakeholder(name=name, role=role, is_sponsor=sponsor, success_metric=success_metric)
    eng.ctx.stakeholders.append(person)
    _save_engagement(eng)
    mark = "👑 sponsor" if person.is_sponsor else person.role
    console.print(f"✅ 干系人 [bold]{person.name}[/bold]（{mark}）已记录")
    sponsors = sum(1 for s in eng.ctx.stakeholders if s.is_sponsor)
    console.print(f"   当前发起人 {sponsors} 位（要求 ≥2，防 Sponsor Collapse）")


@stakeholder_app.command("list")
def stakeholder_list(
    engagement_id: str = typer.Argument(...),
    as_json: bool = typer.Option(False, "--json", help="Print the stakeholder list as plain JSON"),
) -> None:
    """Show the stakeholder map."""
    eng = _load_engagement(engagement_id)
    rows = [s.model_dump() for s in eng.ctx.stakeholders]
    if as_json:
        _echo_json({"engagement_id": engagement_id, "stakeholders": rows})
        return
    _banner(f"stakeholders · {engagement_id}")
    if not rows:
        console.print("[yellow]暂无干系人。[/yellow]")
        console.print('  添加: fde-scope engage stakeholder add <id> --name "..." --role "..." --sponsor')
        return
    table = Table(title="Stakeholders")
    for col in ("name", "role", "sponsor", "success_metric"):
        table.add_column(col)
    for r in rows:
        table.add_row(r["name"], r["role"], "✅" if r["is_sponsor"] else "—", r["success_metric"] or "—")
    console.print(table)


@criterion_app.command("add")
def criterion_add(
    engagement_id: str = typer.Argument(...),
    text: str = typer.Option(..., "--text", "-t", help="一条可度量成功标准（含数字 + 时间，客户能自己验收）"),
) -> None:
    """Add a contractual success criterion."""
    eng = _load_engagement(engagement_id)
    stripped = text.strip()
    if not stripped:
        console.print("[red]成功标准不能为空。[/red]")
        raise typer.Exit(2)
    if stripped in eng.ctx.success_criteria:
        console.print(f"[red]重复的成功标准:[/red] {stripped}")
        raise typer.Exit(2)
    eng.ctx.success_criteria.append(stripped)
    _save_engagement(eng)
    console.print(f"✅ 成功标准 {len(eng.ctx.success_criteria)} 条已记录")
    import re

    if not re.search(r"\d", stripped):
        console.print("[yellow]⚠️  这条没有数字——「提升体验」类形容词无法验收（门禁 G2 会打回）[/yellow]")


@criterion_app.command("list")
def criterion_list(
    engagement_id: str = typer.Argument(...),
    as_json: bool = typer.Option(False, "--json", help="Print the criteria as plain JSON"),
) -> None:
    """Show the agreed success criteria."""
    eng = _load_engagement(engagement_id)
    if as_json:
        _echo_json({"engagement_id": engagement_id, "success_criteria": eng.ctx.success_criteria})
        return
    _banner(f"success criteria · {engagement_id}")
    if not eng.ctx.success_criteria:
        console.print("[yellow]暂无成功标准（= 无限 pilot 反模式入口）。[/yellow]")
        return
    for i, c in enumerate(eng.ctx.success_criteria, 1):
        console.print(f"  {i}. {c}")


@slo_app.command("add")
def slo_add(
    engagement_id: str = typer.Argument(...),
    name: str = typer.Option(..., "--name", "-n"),
    target: str = typer.Option(..., "--target", help="目标值，例如 可用性 99.5% / P95 ≤ 2s"),
    error_budget: str = typer.Option("", "--error-budget", help="错误预算，例如 月 21.6min"),
    alert_route: str = typer.Option("", "--alert-route", help="谁 / 哪个渠道 / 多久响应"),
    window: str = typer.Option("28d", "--window", help="测量窗口"),
) -> None:
    """Define an SLO (target + error budget + alert route)."""
    from .engagement.context import SLOSpec

    eng = _load_engagement(engagement_id)
    slo = SLOSpec(name=name, target=target, error_budget=error_budget, alert_route=alert_route, window=window)
    eng.ctx.slos.append(slo)
    _save_engagement(eng)
    console.print(f"✅ SLO [bold]{slo.name}[/bold] 已定义 · target={slo.target} · window={slo.window}")
    if not slo.alert_route:
        console.print("[yellow]⚠️  未填告警路由——门禁 G6 要求「谁在什么时候被叫醒」写清楚[/yellow]")


@slo_app.command("list")
def slo_list(
    engagement_id: str = typer.Argument(...),
    as_json: bool = typer.Option(False, "--json", help="Print the SLOs as plain JSON"),
) -> None:
    """Show the defined SLOs."""
    eng = _load_engagement(engagement_id)
    rows = [s.model_dump() for s in eng.ctx.slos]
    if as_json:
        _echo_json({"engagement_id": engagement_id, "slos": rows})
        return
    _banner(f"slos · {engagement_id}")
    if not rows:
        console.print("[yellow]暂无 SLO。[/yellow]")
        return
    table = Table(title="SLOs")
    for col in ("name", "target", "window", "error_budget", "alert_route"):
        table.add_column(col)
    for r in rows:
        table.add_row(r["name"], r["target"], r["window"], r["error_budget"] or "—", r["alert_route"] or "—")
    console.print(table)


@site_app.command("set")
def site_set(
    engagement_id: str = typer.Argument(...),
    location: str | None = typer.Option(None, "--location", help="现场地址 / 勘察记录（缺失 = blocker）"),
    network: list[str] = typer.Option([], "--network", help="网络拓扑，可重复传入"),
    shift_count: int | None = typer.Option(None, "--shift-count", help="班次数（>1 而未记网络会告警）"),
    ot_it_separated: bool | None = typer.Option(None, "--ot-it-separated/--no-ot-it-separated"),
    air_gapped: bool | None = typer.Option(None, "--air-gapped/--no-air-gapped"),
    works_council: bool | None = typer.Option(
        None, "--works-council/--no-works-council", help="是否有职工代表参与（DACH 场景）"
    ),
    assets_file: str | None = typer.Option(
        None, "--assets-file", help="JSON/JSONL/CSV 资产清单（name/type/vendor/protocol/criticality）"
    ),
    notes: str | None = typer.Option(None, "--notes"),
) -> None:
    """Record / update site-survey facts gathered on the gemba walk."""
    eng = _load_engagement(engagement_id)
    site = eng.ctx.site
    changed: list[str] = []
    for field_name, value in (
        ("location", location),
        ("shift_count", shift_count),
        ("ot_it_separated", ot_it_separated),
        ("air_gapped", air_gapped),
        ("works_council_represented", works_council),
        ("notes", notes),
    ):
        if value is not None:
            setattr(site, field_name, value)
            changed.append(field_name)
    if network:
        site.networks = list(network)
        changed.append("networks")
    if assets_file:
        assets = _load_rows(assets_file)
        site.assets = [a if isinstance(a, dict) else {"name": str(a)} for a in assets]
        changed.append("assets")
    _save_engagement(eng)
    console.print(
        f"✅ 现场事实已记录（{', '.join(changed) if changed else '无字段变更'}）"
        f" · location={site.location or '(空)'} · 资产 {len(site.assets)} 项 · 班次 {site.shift_count}"
    )
    if site.shift_count > 1 and not site.networks:
        console.print("[yellow]⚠️  多班次现场但未记录网络拓扑[/yellow]")


@site_app.command("show")
def site_show(
    engagement_id: str = typer.Argument(...),
    as_json: bool = typer.Option(False, "--json", help="Print the site facts as plain JSON"),
) -> None:
    """Show the recorded site-survey facts."""
    eng = _load_engagement(engagement_id)
    if as_json:
        _echo_json({"engagement_id": engagement_id, "site": eng.ctx.site.model_dump()})
        return
    _banner(f"site · {engagement_id}")
    site = eng.ctx.site
    console.print(f"location: [bold]{site.location or '—'}[/bold]")
    console.print(
        f"OT/IT 隔离: {site.ot_it_separated} · 网闸/气隙: {site.air_gapped} · 班次: {site.shift_count}"
    )
    console.print(f"网络: {', '.join(site.networks) or '—'}")
    console.print(f"资产: {len(site.assets)} 项 · 职工代表: {site.works_council_represented}")
    if site.notes:
        console.print(f"notes: {site.notes}")


# ---------------------------------------------------------------------------
# gate subcommands
# ---------------------------------------------------------------------------
@gate_app.command("list")
def gate_list(
    profile: str = typer.Option("manufacturing", "--profile", "-p"),
) -> None:
    """List gates applicable to a profile."""
    from .engagement.engagement import default_gate_registry

    _banner(f"gates · {profile}")
    table = Table(title="Gates")
    for col in ("slug", "name", "industrial_only"):
        table.add_column(col)
    for slug, gate in default_gate_registry().items():
        table.add_row(slug, gate.name, "🏭" if gate.industrial_only else "🏢")
    console.print(table)


@gate_app.command("check")
def gate_check(
    engagement_id: str = typer.Argument(...),
    gate_slug: str | None = typer.Option(
        None, "--gate", "-g", help="Specific gate slug; omit = current phase's gate"
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Print the gate result as plain JSON (no rich markup)"
    ),
) -> None:
    """Evaluate a gate against an engagement."""
    eng = _load_engagement(engagement_id)
    slug = gate_slug or eng.phase.gate
    if not slug:
        if as_json:
            _echo_json(
                {
                    "engagement_id": engagement_id,
                    "phase": eng.ctx.current_phase,
                    "gate": None,
                    "applicable": False,
                    "passed": True,
                    "blockers": [],
                    "warnings": [],
                }
            )
        console.print(f"[yellow]Phase '{eng.ctx.current_phase}' has no gate.[/yellow]")
        raise typer.Exit(0)
    result = eng.evaluate_gate(slug)
    _save_engagement(eng)
    from . import audit

    audit.log_event(
        "engagement.gate_evaluate",
        actor="cli",
        detail={"engagement_id": engagement_id, "gate": slug, "passed": result.passed},
    )
    if as_json:
        _echo_json({"engagement_id": engagement_id, "phase": eng.ctx.current_phase, **asdict(result)})
    else:
        console.print(result.summary())
    if not result.passed:
        # The hint is a human convenience; printing it after the payload would
        # append prose to a stdout that the contract says is JSON-only.
        if not as_json:
            _maybe_suggest_skill(engagement_id, slug, list(result.blockers))
        raise typer.Exit(1)
    _maybe_capture("gate_pass", engagement_id, phase_slug=eng.ctx.current_phase)


# ---------------------------------------------------------------------------
# handoff + kpi + profile + web commands
# ---------------------------------------------------------------------------
@app.command()
def handoff(
    engagement_id: str = typer.Argument(...),
    eval_report: str | None = typer.Option(None, "--eval-report"),
    training: str | None = typer.Option(None, "--training-material"),
    boundary: str | None = typer.Option(None, "--boundary", help="G7③ 适用边界：这套方案在哪些条件下不成立"),
    termination: str | None = typer.Option(
        None, "--termination", help="G7④ 终止条件：什么情况下停用/回退，谁说了算"
    ),
    llm: bool = typer.Option(
        False, "--llm", help="Draft the runbook with MiMo (needs FDE_SCOPE_MIMO_API_KEY)"
    ),
    accept: bool = typer.Option(False, "--accept", help="Mark customer accepted"),
) -> None:
    """[Zone D] Assemble the handoff / knowledge-transfer package."""
    from .engagement import build_handoff_package, render_handoff_summary
    from .engagement.operationalization import llm_runbook, render_runbook

    eng = _load_engagement(engagement_id)
    runbook_path = paths.reports_dir() / f"runbook_{engagement_id}.md"
    # The package is built *first* because the runbook's 移交状态 section reads
    # ctx.assets["handoff_package"]: assembling it afterwards wrote a customer-
    # facing runbook that said "❌ 未签" while stdout said the customer accepted.
    build_handoff_package(
        eng.ctx,
        runbook_path=str(runbook_path),
        eval_report_path=eval_report,
        training_material=training,
        boundary=boundary,
        termination=termination,
        customer_accepted=accept,
    )
    model_name = ""
    if llm:
        client = _maybe_llm(require=True)
        model_name = client.model
        runbook_md, used_llm = llm_runbook(eng.ctx, client)
    else:
        runbook_md, used_llm = render_runbook(eng.ctx), False
    atomic_write_text(runbook_path, runbook_md)
    if used_llm:
        console.print(f"🤖 Runbook drafted by MiMo ({model_name})")
    elif llm:
        console.print("[yellow]Runbook rendered from template (MiMo draft failed)[/yellow]")
    _save_engagement(eng)
    console.print(f"✅ Handoff package assembled for [bold]{engagement_id}[/bold]")
    console.print(f"   runbook → [green]{runbook_path}[/green]")
    console.print(render_handoff_summary(eng.ctx))


@app.command()
def kpi(
    engagement_id: str = typer.Argument(...),
    samples_file: str = typer.Option(..., "--samples", "-s", help="JSON/JSONL of sample records"),
    as_json: bool = typer.Option(False, "--json", help="Print the KPIs as plain JSON (no rich markup)"),
) -> None:
    """Compute profile-specific KPIs over a sample set."""
    eng = _load_engagement(engagement_id)
    from .profiles import get_profile

    profile = get_profile(eng.ctx.profile)
    samples = _load_rows(samples_file)
    if not isinstance(samples, list):
        samples = [samples]
    kpis = profile.compute_kpis(samples)
    if as_json:
        console.print_json(json.dumps({"engagement_id": engagement_id, "kpis": kpis}, ensure_ascii=False))
        return
    _banner(f"KPIs · {engagement_id} ({profile.slug})")
    table = Table(title=f"{profile.name} KPIs")
    table.add_column("KPI", style="cyan")
    table.add_column("value", justify="right")
    table.add_column("label")
    for k, v in kpis.items():
        label = profile.kpi_catalogue.get(k, "")
        table.add_row(k, f"{v:.4f}", label)
    console.print(table)


@app.command(name="storage-migrate")
def storage_migrate(
    to: str = typer.Option(..., "--to", help="Target backend: sqlite"),
    db: str | None = typer.Option(
        None, "--db", help="SQLite file path (default: <data root>/.fde_scope/engagements.db)"
    ),
) -> None:
    """[Storage] One-way migrate engagements from the file backend to SQLite."""
    _banner(f"storage-migrate → {to}")
    if to != "sqlite":
        console.print(f"[red]Unsupported target:[/red] {to} (only 'sqlite')")
        raise typer.Exit(2)
    from .storage import migrate_file_to_sqlite

    summary = migrate_file_to_sqlite(db)
    console.print(
        f"✅ Migrated [bold]{summary['migrated']}[/bold] engagement(s) → [green]{summary['db_path']}[/green]"
    )
    if summary["skipped"]:
        console.print(
            f"[yellow]Skipped [bold]{summary['skipped']}[/bold] unreadable JSON file(s); "
            "they stay on disk.[/yellow]"
        )
    console.print("[dim]Source JSON files left in place; activate with FDE_SCOPE_STORAGE=sqlite.[/dim]")


@app.command()
def profiles() -> None:
    """List available deployment scenario profiles."""
    from .profiles import all_profiles

    _banner("profiles")
    table = Table(title="Scenario profiles")
    for col in ("slug", "name", "industrial", "connectors", "kpi_count"):
        table.add_column(col)
    for slug, p in all_profiles().items():
        table.add_row(
            slug,
            p.name,
            "🏭" if p.is_industrial else "🏢",
            ", ".join(p.primary_connectors),
            str(len(p.kpi_catalogue)),
        )
    console.print(table)


@app.command()
def web(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8080, "--port"),
    reload: bool = typer.Option(False, "--reload"),
) -> None:
    """Launch the FDE Scope Web UI (engagement dashboard + gates + reports)."""
    _banner("web ui")
    try:
        import uvicorn
    except ImportError:
        console.print("[red]Web UI needs the 'web' extra:[/red] pip install 'fde-scope[web]'")
        raise typer.Exit(2) from None
    from .web.auth import ENV_VAR, host_is_loopback, token_is_configured

    # Two independent gates on a non-loopback bind: FDE_SCOPE_ALLOW_REMOTE
    # opts into the bind itself, FDE_SCOPE_API_TOKEN makes the console safe to
    # expose. Neither implies the other, so clearing both is what serving
    # beyond loopback costs — an opt-in flag must not be able to disable auth.
    if not host_is_loopback(host):
        if os.environ.get("FDE_SCOPE_ALLOW_REMOTE") != "1":
            console.print(
                f"[red]Refusing to bind non-loopback host {host!r}.[/red] "
                "The workbench would be reachable from your network with its "
                "engagements, journals and corpus upload API.\n"
                f"[dim]Opt in only on a trusted network:[/dim] "
                f"[bold]FDE_SCOPE_ALLOW_REMOTE=1[/bold] fde-scope web --host {host}"
            )
            raise typer.Exit(2)
        if not token_is_configured():
            console.print(
                f"[red]Refusing to bind non-loopback host {host!r} without a token.[/red] "
                f"[bold]{ENV_VAR}[/bold] is unset, so every route would be served "
                "unauthenticated — customer engagements, journals and the corpus "
                "upload API included.\n"
                "[dim]Set a secret token (it is read from the environment only, never "
                "written to a file or log), then:[/dim] "
                f"[bold]export {ENV_VAR}=<token>; FDE_SCOPE_ALLOW_REMOTE=1[/bold] "
                f"fde-scope web --host {host}\n"
                "[dim]Or keep the console loopback and authenticate at a reverse "
                "proxy.[/dim]"
            )
            raise typer.Exit(2)
    console.print(f"🚀 Launching [cyan]http://{host}:{port}[/cyan]")
    uvicorn.run(
        "fde_scope.web.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


def main() -> None:
    """Entry point for ``python -m fde_scope.cli``."""
    from .logutil import configure_logging

    configure_logging()
    app()


# ---------------------------------------------------------------------------
# skills（技能/方法论沉淀库）
# ---------------------------------------------------------------------------
skill_app = typer.Typer(name="skill", help="[Skills] 技能/方法论沉淀库.", no_args_is_help=True)
app.add_typer(skill_app)


# ---------------------------------------------------------------------------
# qwenpaw（QwenPaw 集成：导出 / 校验）
# ---------------------------------------------------------------------------
qwenpaw_app = typer.Typer(
    name="qwenpaw", help="[QwenPaw] 导出 / 校验 QwenPaw 兼容产物.", no_args_is_help=True
)
app.add_typer(qwenpaw_app)


@qwenpaw_app.command("export")
def qwenpaw_export(
    tenant: str = typer.Option(..., "--tenant", "-t", help="Tenant ID"),
    name: str = typer.Option("Tenant", "--name", help="Tenant display name"),
    model: str = typer.Option("qwen-max", "--model", "-m", help="Model config name"),
    agent_specs: list[str] | None = typer.Option(
        None, "--agent", "-a", help="Agent spec 'name:role[:model]' (repeatable)"
    ),
    out: str = typer.Option(..., "--out", help="Output directory"),
    corpus: str | None = typer.Option(None, "--corpus", help="Path to forged corpus JSON (optional)"),
) -> None:
    """[QwenPaw] 导出 tenant 拓扑 + published 技能 + corpus 说明为 QwenPaw 兼容产物."""
    _banner(f"qwenpaw export · {tenant}")
    from .config import TenantConfig
    from .integrations.qwenpaw_exporter import QwenPawExporter
    from .skills.models import SkillStatus

    agents = _parse_agent_specs(agent_specs)
    cfg = TenantConfig(id=tenant, name=name, model=model, agents=agents or None)

    corpus_report = None
    if corpus:
        from .corpus import CorpusReport

        try:
            corpus_report = CorpusReport.model_validate_json(Path(corpus).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            console.print(f"[red]Cannot load corpus report:[/red] {corpus} ({exc})")
            raise typer.Exit(2) from exc

    skills = _skill_service().search(status=SkillStatus("published"))
    try:
        bundle = QwenPawExporter().export(cfg, Path(out), skills=skills, corpus_report=corpus_report)
    except ValueError as exc:
        console.print(f"[red]Cannot derive a valid QwenPaw agent id:[/red] {exc}")
        raise typer.Exit(2) from exc
    for w in bundle.written:
        console.print(f"📦 {w}")
    if bundle.report["valid"]:
        console.print(f"✅ Exported {len(bundle.written)} files → [green]{out}[/green]")
    else:
        console.print("[yellow]⚠ export contains validation errors (see qwenpaw_validate.json)[/yellow]")
    console.print(f"📋 Manifest → [green]{json.dumps(bundle.report, ensure_ascii=False)}[/green]")


@qwenpaw_app.command("validate")
def qwenpaw_validate(
    out: str = typer.Option(..., "--out", help="Export directory to validate"),
) -> None:
    """[QwenPaw] 校验导出产物（结构 + 必填字段 + agent id 规则）。"""
    _banner(f"qwenpaw validate · {out}")
    from .integrations.validator import validate_export

    report = validate_export(Path(out))
    if report["valid"]:
        console.print("✅ [green]VALID[/green] — QwenPaw-compatible bundle")
    else:
        for e in report["errors"]:
            console.print(f"[red]✗[/red] {e}")
        console.print(f"❌ [red]INVALID[/red] — {len(report['errors'])} error(s)")
        raise typer.Exit(1)


def _skill_service() -> SkillService:
    from .skills.service import SkillService
    from .skills.store import SkillStore

    return SkillService(SkillStore(paths.skills_dir()))


def _maybe_suggest_skill(engagement_id: str, gate_slug: str, blockers: list[str]) -> None:
    """gate 阻塞时生成提示草稿；失败静默（不阻塞主流程）。"""
    with suppress(OSError):
        rec = _skill_service().suggest_from_gate_block(engagement_id, gate_slug, blockers)
        console.print(
            f"💡 已把这次阻塞沉淀为草稿 [cyan]{rec.id}[/cyan] — "
            f"[bold]fde-scope skill review[/bold] 可查看并完善"
        )


def _maybe_capture(
    action: str, engagement_id: str, phase_slug: str | None = None, detail: dict | None = None
) -> None:
    """操作自动捕获；失败静默。"""
    with suppress(OSError):
        _skill_service().capture_operation(
            action=action, engagement_id=engagement_id, phase_slug=phase_slug, detail=detail
        )


@skill_app.command("add")
def skill_add(
    title: str = typer.Option(..., "--title"),
    category: str = typer.Option(..., "--category", help="research|implementation|optimization|methodology"),
    tags: str = typer.Option("", "--tags", help="逗号分隔"),
    body: str = typer.Option("", "--body"),
    body_file: str | None = typer.Option(None, "--body-file", help="从文件读正文"),
    phase: str | None = typer.Option(None, "--phase"),
    gate: str | None = typer.Option(None, "--gate"),
    profile: str = typer.Option("", "--profile", help="ticket,manufacturing 逗号分隔"),
    engagement: str | None = typer.Option(None, "--engagement"),
    source: str = typer.Option("manual", "--source", help="manual|gate_hint|auto_capture"),
) -> None:
    """创建一条技能草稿。"""
    _banner(f"skill add · {title}")
    from .skills.models import SkillCategory, SkillDraft, SkillSource

    try:
        cat = SkillCategory(category)
        src = SkillSource(source)
    except ValueError:
        console.print("[red]非法 category/source[/red]（见 --help）")
        raise typer.Exit(2) from None
    text = Path(body_file).read_text(encoding="utf-8") if body_file else body
    service = _skill_service()
    rec = service.create(
        SkillDraft(
            title=title,
            category=cat,
            tags=[t.strip() for t in tags.split(",") if t.strip()],
            body_md=text,
            phase_slug=phase,
            gate_slug=gate,
            applies_to=[p.strip() for p in profile.split(",") if p.strip()],
            source=src,
            source_engagement=engagement,
        )
    )
    console.print(f"✅ 草稿创建 [cyan]{rec.id}[/cyan] — [bold]fde-scope skill review[/bold] 可审阅")


@skill_app.command("list")
def skill_list(
    category: str | None = typer.Option(None, "--category"),
    tag: str | None = typer.Option(None, "--tag"),
    status: str | None = typer.Option(None, "--status", help="published|draft|archived（默认全部）"),
    profile: str | None = typer.Option(None, "--profile"),
    gate: str | None = typer.Option(None, "--gate"),
    phase: str | None = typer.Option(None, "--phase"),
    search: str | None = typer.Option(None, "--search"),
    concept: str | None = typer.Option(
        None, "--concept", help="按本体概念检索（含 narrower 扩展，schema=fde-core）"
    ),
    as_json: bool = typer.Option(False, "--json", help="Print the list as plain JSON (no rich markup)"),
) -> None:
    """列出/检索技能。"""
    _banner("skill list")
    from .skills.models import SkillCategory, SkillStatus

    service = _skill_service()
    try:
        cat = SkillCategory(category) if category else None
        st = SkillStatus(status) if status else None
    except ValueError:
        console.print("[red]非法 category/status[/red]")
        raise typer.Exit(2) from None
    schema = None
    if concept is not None:
        from .ontology.store import OntologyStore

        schema = OntologyStore().load_schema("fde-core")
        if schema is None:
            console.print("[red]Ontology schema not found:[/red] fde-core")
            raise typer.Exit(2) from None
        known = {c.curie for s in schema.concept_schemes for c in s.concepts}
        if concept not in known:
            console.print(f"[red]未知概念:[/red] {concept}（fde-core 未声明）")
            raise typer.Exit(2) from None
    rows = service.search(
        search,
        category=cat,
        tags=[tag] if tag else None,
        status=st,
        profile=profile,
        gate_slug=gate,
        phase_slug=phase,
        concept=concept,
        ontology_schema=schema,
    )
    if as_json:
        console.print_json(json.dumps([r.model_dump(mode="json") for r in rows], ensure_ascii=False))
        return
    if not rows:
        console.print("[yellow]无匹配技能[/yellow]")
        return
    table = Table(title=f"Skills · {len(rows)}")
    for col in ("id", "title", "category", "status", "tags", "updated"):
        table.add_column(col)
    for r in rows:
        table.add_row(
            r.id,
            r.title,
            r.category.value,
            r.status.value,
            ",".join(r.tags),
            r.updated_at.strftime("%Y-%m-%d"),
        )
    console.print(table)


@skill_app.command("show")
def skill_show(skill_id: str = typer.Argument(...)) -> None:
    """显示技能正文与元数据。"""
    try:
        rec = _skill_service().get(skill_id)
    except KeyError:
        console.print(f"[red]技能不存在:[/red] {skill_id}")
        raise typer.Exit(2) from None
    console.print(
        f"\n[bold cyan]{rec.title}[/bold cyan] · {rec.category.value} · {rec.status.value} · v{rec.version}"
    )
    console.print(
        f"tags={rec.tags} · phase={rec.phase_slug} · gate={rec.gate_slug} · "
        f"applies_to={rec.applies_to} · source={rec.source.value}"
    )
    console.print(
        f"源自: {rec.source_engagement or '—'} · 创建: {rec.created_at:%Y-%m-%d} · 更新: {rec.updated_at:%Y-%m-%d}"
    )
    console.print("\n" + rec.body_md)


@skill_app.command("edit")
def skill_edit(
    skill_id: str = typer.Argument(...),
    title: str | None = typer.Option(None, "--title"),
    tags: str | None = typer.Option(None, "--tags"),
    body: str | None = typer.Option(None, "--body"),
) -> None:
    """编辑技能（version+1）。"""
    from .skills.models import SkillPatch

    try:
        rec = _skill_service().update(
            skill_id,
            SkillPatch(
                title=title,
                tags=[t.strip() for t in tags.split(",") if t.strip()] if tags else None,
                body_md=body,
            ),
        )
    except KeyError:
        console.print(f"[red]技能不存在:[/red] {skill_id}")
        raise typer.Exit(2) from None
    console.print(f"✅ 已更新 [cyan]{rec.id}[/cyan] → v{rec.version}")


@skill_app.command("publish")
def skill_publish(skill_id: str = typer.Argument(...)) -> None:
    """发布草稿（可检索、可导出）。"""
    try:
        _skill_service().publish(skill_id)
    except KeyError:
        console.print(f"[red]技能不存在:[/red] {skill_id}")
        raise typer.Exit(2) from None
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from None
    console.print(f"✅ 已发布 [cyan]{skill_id}[/cyan]")


@skill_app.command("archive")
def skill_archive(skill_id: str = typer.Argument(...)) -> None:
    """归档技能。"""
    try:
        _skill_service().archive(skill_id)
    except (KeyError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from None
    console.print(f"✅ 已归档 [cyan]{skill_id}[/cyan]")


@skill_app.command("review")
def skill_review(limit: int = typer.Option(20, "--limit")) -> None:
    """草稿审阅队列（自动捕获/gate 提示产生的草稿）。"""
    _banner("skill review")
    rows = _skill_service().list_drafts()[:limit]
    if not rows:
        console.print("[yellow]没有待审草稿[/yellow]")
        return
    table = Table(title=f"Draft queue · {len(rows)}")
    for col in ("id", "title", "source", "engagement"):
        table.add_column(col)
    for r in rows:
        table.add_row(r.id, r.title, r.source.value, r.source_engagement or "—")
    console.print(table)


@skill_app.command("export")
def skill_export(
    skill_id: str = typer.Argument(...),
    fmt: str = typer.Option(..., "--format", help="agentscope|qwenpaw"),
    out: str | None = typer.Option(
        None, "--out", help="输出目录（默认 <data root>/.fde_scope/skills/export）"
    ),
    ontology: bool = typer.Option(False, "--ontology", help="frontmatter 附带本体概念行（schema=fde-core）"),
) -> None:
    """导出技能为 AgentScope / QwenPaw 格式。"""
    from .skills.exporters import export_skill

    schema = None
    if ontology:
        from .ontology.store import OntologyStore

        schema = OntologyStore().load_schema("fde-core")
        if schema is None:
            console.print("[red]Ontology schema not found:[/red] fde-core")
            raise typer.Exit(2) from None

    try:
        rec = _skill_service().get(skill_id)
        files = export_skill(rec, fmt, ontology=schema)
    except KeyError:
        console.print(f"[red]技能不存在:[/red] {skill_id}")
        raise typer.Exit(2) from None
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from None
    out = out or str(paths.skills_export_dir())
    out_dir = Path(out)
    for f in files:
        atomic_write_text(out_dir / f.name, f.content)
    console.print(f"✅ 导出 {len(files)} 个文件 → [green]{out_dir}[/green] ({fmt})")


# ---------------------------------------------------------------------------
# ontology（本体语义层：TBox/ABox 校验 + JSON-LD 导出）
# ---------------------------------------------------------------------------
ontology_app = typer.Typer(
    name="ontology", help="[Ontology] 本体 schema/实例库：校验与 JSON-LD 导出.", no_args_is_help=True
)
app.add_typer(ontology_app)


def _ontology_store():
    from .ontology.store import OntologyStore

    return OntologyStore()


def _print_report(prefix: str, report) -> None:
    from rich.table import Table

    if report.ok:
        console.print(f"✅ [green]VALID[/green] — {prefix}")
        return
    table = Table(title="Validation errors")
    table.add_column("code", style="red")
    table.add_column("subject")
    table.add_column("message")
    for e in report.errors:
        table.add_row(e.code, e.subject, e.message)
    console.print(table)
    console.print(f"❌ [red]INVALID[/red] — {len(report.errors)} error(s)")


@ontology_app.command("list")
def ontology_list(
    as_json: bool = typer.Option(False, "--json", help="Print schemas/stores as plain JSON (no rich markup)"),
) -> None:
    """[Ontology] 列出内置 + 工作区 schema 与实例库."""
    store = _ontology_store()
    if as_json:
        console.print_json(
            json.dumps({"schemas": store.list_schemas(), "stores": store.list_stores()}, ensure_ascii=False)
        )
        return
    _banner("ontology list")
    schemas = store.list_schemas()
    stores = store.list_stores()
    console.print(f"[bold]schemas[/bold] ({len(schemas)})")
    for s in schemas:
        console.print(
            f"  {s['id']}@{s['version']}  [{s['origin']}]  classes={s['classes']} "
            f"obj={s['object_properties']} data={s['data_properties']} schemes={s['concept_schemes']}"
        )
    console.print(f"[bold]stores[/bold] ({len(stores)})")
    for s in stores:
        console.print(f"  {s['id']}  ref={s['ontology_ref']}  individuals={s['individuals']}")
    if not schemas and not stores:
        console.print("  (empty)")


@ontology_app.command("validate")
def ontology_validate(
    schema_id: str = typer.Argument(..., help="Schema id，如 fde-core"),
    as_json: bool = typer.Option(False, "--json", help="Print the report as plain JSON (no rich markup)"),
) -> None:
    """[Ontology] 校验 TBox（含 overlay 的 import 合并视图）. exit 1 = 校验失败."""
    store = _ontology_store()
    schema = store.load_schema(schema_id)
    if schema is None:
        console.print(f"[red]Unknown schema:[/red] {schema_id}")
        raise typer.Exit(2)
    from .ontology.validation import validate_schema

    with console.status(f"validating {schema_id}…"):
        report = validate_schema(schema, loader=store.load_schema)
    if as_json:
        console.print_json(
            json.dumps({"target": f"{schema_id}@{schema.version}", **report.model_dump()}, ensure_ascii=False)
        )
    else:
        _print_report(f"{schema_id}@{schema.version}", report)
    if not report.ok:
        raise typer.Exit(1)


@ontology_app.command("check")
def ontology_check(
    store_id: str = typer.Argument(..., help="Instance store id"),
    as_json: bool = typer.Option(False, "--json", help="Print the report as plain JSON (no rich markup)"),
) -> None:
    """[Ontology] 校验 ABox 实例库（对 ontology_ref 指向的 TBox）. exit 1 = 校验失败."""
    inst = _ontology_store().load_store(store_id)
    if inst is None:
        console.print(f"[red]Unknown store:[/red] {store_id}")
        raise typer.Exit(2)
    from .ontology.validation import validate_store

    with console.status(f"checking {store_id}…"):
        report = validate_store(inst, loader=_ontology_store().load_schema)
    if as_json:
        console.print_json(
            json.dumps(
                {"target": f"{store_id} ({inst.ontology_ref})", **report.model_dump()}, ensure_ascii=False
            )
        )
    else:
        _print_report(f"{store_id} ({inst.ontology_ref})", report)
    if not report.ok:
        raise typer.Exit(1)


@ontology_app.command("export")
def ontology_export(
    target: str = typer.Argument(..., help="Schema 或 store id"),
    fmt: str = typer.Option("jsonld", "--format", help="输出格式：jsonld | mermaid（mermaid 仅 schema）"),
    out: Path | None = typer.Option(None, "--out", "-o", help="写入文件（缺省打印到 stdout）"),
) -> None:
    """[Ontology] 导出 JSON-LD（schema/store）或 Mermaid 概念模型图（仅 schema）."""
    _banner(f"ontology export · {target}")
    if fmt not in ("jsonld", "mermaid"):
        console.print(f"[red]Unsupported format:[/red] {fmt} (jsonld | mermaid)")
        raise typer.Exit(2)
    store = _ontology_store()
    schema = store.load_schema(target)
    if schema is not None:
        if fmt == "mermaid":
            from .ontology.diagram import schema_to_mermaid

            text = schema_to_mermaid(schema)
        else:
            from .ontology.jsonld import schema_to_jsonld

            text = json.dumps(schema_to_jsonld(schema), ensure_ascii=False, indent=2, sort_keys=True)
    else:
        if fmt == "mermaid":
            console.print("[red]Mermaid export is schema-only[/red]（概念模型图来自 TBox）")
            raise typer.Exit(2)
        inst = store.load_store(target)
        if inst is None:
            console.print(f"[red]Unknown target:[/red] {target}")
            raise typer.Exit(2)
        ref_id = inst.ontology_ref.split("@", 1)[0]
        ref_schema = store.load_schema(ref_id)
        if ref_schema is None:
            console.print(f"[red]Store references unknown schema:[/red] {inst.ontology_ref}")
            raise typer.Exit(2)
        from .ontology.jsonld import store_to_jsonld

        text = json.dumps(store_to_jsonld(inst, ref_schema), ensure_ascii=False, indent=2, sort_keys=True)
    if out is None:
        console.print(text)
    else:
        atomic_write_text(out, text + "\n")
        console.print(f"✅ Exported {fmt} → [green]{out}[/green]")


@ontology_app.command("diff")
def ontology_diff(
    old_id: str = typer.Argument(..., help="旧 schema id"),
    new_id: str = typer.Argument(..., help="新 schema id"),
    store_id: str | None = typer.Option(None, "--store", help="附带 ABox 影响面（个体证据清单）"),
    as_json: bool = typer.Option(False, "--json", help="Print the diff as plain JSON (no rich markup)"),
) -> None:
    """[Ontology] TBox 版本 diff：D1-D4 破坏性变更 + 可选 ABox 影响面. exit 1 = 有破坏性变更."""
    if not as_json:
        _banner(f"ontology diff · {old_id} → {new_id}")
    store = _ontology_store()
    old = store.load_schema(old_id)
    new = store.load_schema(new_id)
    if old is None or new is None:
        console.print(f"[red]Unknown schema:[/red] {old_id if old is None else new_id}")
        raise typer.Exit(2)
    from .ontology.diff import diff_schemas, store_impact

    diff = diff_schemas(old, new)
    impact: list = []
    if store_id is not None:
        inst = store.load_store(store_id)
        if inst is None:
            console.print(f"[red]Unknown store:[/red] {store_id}")
            raise typer.Exit(2)
        impact = store_impact(inst, diff)

    from dataclasses import asdict as _asdict

    from .ontology.diff import Change as _Change

    def _change(c: _Change) -> dict:
        return _asdict(c)

    if as_json:
        console.print_json(
            json.dumps(
                {
                    "from": f"{old_id}@{diff.from_version}",
                    "to": f"{new_id}@{diff.to_version}",
                    "ok": diff.ok,
                    "breaking": [_change(c) for c in diff.breaking],
                    "info": [_change(c) for c in diff.info],
                    "impact": [_change(c) for c in impact],
                },
                ensure_ascii=False,
            )
        )
    else:
        console.print(f"{old_id}@{diff.from_version} → {new_id}@{diff.to_version}")
        if diff.ok:
            console.print("✅ [green]NO BREAKING CHANGES[/green]")
        for c in diff.breaking:
            console.print(f"  [red]{c.kind}[/red] {c.subject}: {c.detail}")
        for c in diff.info:
            console.print(f"  [dim]{c.kind} {c.subject}: {c.detail}[/dim]")
        if store_id is not None:
            console.print(f"[bold]ABox impact[/bold] ({store_id}): {len(impact)} individual(s)")
            for c in impact:
                console.print(f"  {c.subject}: {c.detail}")
    if not diff.ok:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# license（离线许可：状态查看 + 签发）
# ---------------------------------------------------------------------------
@app.command("license")
def license_status() -> None:
    """Show the current license tier, expiry and effective features."""
    from .license import ENV_LICENSE_KEY, load_license

    info = load_license()
    _banner("license")
    console.print(
        f"tier: [bold cyan]{info.tier}[/bold cyan]"
        + (" [red](expired — downgraded)[/red]" if info.expired else "")
    )
    if info.customer:
        console.print(f"customer: {info.customer} · license_id: {info.license_id}")
        console.print(f"seats: {info.seats}")
        console.print(f"expires: {info.expires_at.date().isoformat() if info.expires_at else 'never'}")
    else:
        console.print(
            f"[dim]no license key ({ENV_LICENSE_KEY} / .fde_scope/license.key) — community tier[/dim]"
        )
    console.print("features: " + ", ".join(sorted(info.effective_features())))


@app.command("license-issue")
def license_issue(
    customer: str = typer.Option(..., "--customer", "-c", help="Customer name"),
    tier: str = typer.Option(..., "--tier", "-t", help="community | pro | enterprise"),
    seats: int = typer.Option(1, "--seats", help="Licensed seats"),
    expires: str | None = typer.Option(None, "--expires", help="Expiry date YYYY-MM-DD (omit = perpetual)"),
    features: str = typer.Option("", "--features", help="Extra feature grants, comma-separated"),
    out: str | None = typer.Option(None, "--out", "-o", help="Write the key to this file instead of stdout"),
) -> None:
    """Sign a license key for a customer (vendor delivery tool).

    Requires FDE_SCOPE_LICENSE_SECRET in the environment; the secret is
    never written anywhere. The issued *key* is the deliverable.
    """
    from datetime import UTC, datetime

    from .license import ENV_LICENSE_SECRET, LicenseError, issue_license

    expires_at = None
    if expires:
        try:
            expires_at = datetime.strptime(expires, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            console.print(f"[red]Invalid --expires:[/red] {expires!r} (expected YYYY-MM-DD)")
            raise typer.Exit(2) from None
    try:
        key = issue_license(
            customer=customer,
            tier=tier,  # type: ignore[arg-type]
            seats=seats,
            expires_at=expires_at,
            features=[f.strip() for f in features.split(",") if f.strip()],
        )
    except LicenseError as exc:
        console.print(f"[red]Cannot issue license:[/red] {exc}")
        raise typer.Exit(2) from None
    if out:
        atomic_write_text(Path(out), key + "\n")
        console.print(f"✅ License key for [bold]{customer}[/bold] ({tier}) → [green]{out}[/green]")
    else:
        console.print(f"license key for [bold]{customer}[/bold] ({tier}, seats={seats}):\n{key}")
    console.print(f"[dim]signed with ${ENV_LICENSE_SECRET} (never stored)[/dim]")


# ---------------------------------------------------------------------------
# course（Level-1 八天 lab：G0 环境自检 + 逐日机器判分）
# ---------------------------------------------------------------------------
course_app = typer.Typer(
    name="course",
    help="[Course] Level-1 八天 lab：G0 环境自检、逐日机器判分（判分依据 03/06）。",
    no_args_is_help=True,
)
app.add_typer(course_app)


def _print_plain(text: str) -> None:
    """Print grader output verbatim.

    Every line here carries literal ``[G1/success-criteria]`` tags. With rich
    markup on, those parse as style tags and silently vanish — a student would
    read a report whose gate names disappeared, so this path disables markup.
    """
    console.print(text, markup=False, highlight=False)


@course_app.command("doctor")
def course_doctor(
    as_json: bool = typer.Option(False, "--json", help="Print the G0 report as plain JSON"),
) -> None:
    """G0 入学门自检：解释器、包、教案目录、数据目录、可选依赖。

    退出码非 0 = 有必答项没过，lab 还跑不了。API key / Docker / AgentScope 是
    可选项，只报状态不算失败（06 §2「不需要」）。
    """
    from .course.doctor import doctor_report

    code, items, payload = doctor_report()
    if as_json:
        _echo_json(payload)
        raise typer.Exit(code)
    _banner("course doctor · G0 入学门")
    for item in items:
        _print_plain(item.line())
    counts = payload["summary"]
    tail = f"{counts['ok']} 通过 · {counts['warn']} 提醒 · {counts['info']} 可选 · {counts['fail']} 失败"
    if payload["ok"]:
        console.print(f"\n[green]✅ G0 通过[/green]（{tail}）可以开 D1。")
    else:
        console.print(
            f"\n[red]❌ G0 未通过[/red]（{tail}）阻塞项："
            + "、".join(payload["blockers"])
            + "——按上面 💡 修完再跑一次。"
        )
    raise typer.Exit(code)


@course_app.command("labs")
def course_labs() -> None:
    """列出 8 天的 lab、门禁、产出与判分项数。"""
    from .course.catalog import LABS
    from .course.checks import ManualCheck

    _banner("course labs · D1..D8")
    table = Table(title="Level-1 labs", expand=True)
    for column in ("天", "门禁", "今日产出", "机器项", "人工项", "标题"):
        table.add_column(column, overflow="fold")
    for lab in LABS:
        manual = sum(1 for check in lab.checks if isinstance(check, ManualCheck))
        table.add_row(
            lab.day,
            lab.gate,
            lab.deliverable,
            str(len(lab.checks) - manual),
            str(manual),
            lab.title,
        )
    console.print(table)
    scored = sum(1 for lab in LABS for check in lab.checks if not isinstance(check, ManualCheck))
    manual = sum(1 for lab in LABS for check in lab.checks if isinstance(check, ManualCheck))
    console.print(f"\n合计：{scored} 个机器判分项 + {manual} 个人工项（人工项不进分母）。")


@course_app.command("check")
def course_check(
    day: str = typer.Argument("all", help="D1…D8 或 all"),
    as_json: bool = typer.Option(False, "--json", help="Print results as plain JSON"),
    keep: bool = typer.Option(False, "--keep", help="保留临时工作目录并在结果里打印路径"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="逐条打印执行的命令与输出"),
) -> None:
    """跑一天的机器判分（在临时目录里，不碰你的数据目录）。

    分数只由已有 CLI 表面决定：退出码、打印原话、--json/落盘文件。
    冷跑会在「写作项」上红——starter 里 TODO 还在就是没写完，这是设计。
    """
    from .course.catalog import lab_for
    from .course.verifier import run_all, run_lab

    if day.lower() in ("all", "every", "*"):
        results = run_all(keep=keep, verbose=verbose)
    else:
        try:
            lab = lab_for(day)
        except KeyError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(2) from None
        results = [run_lab(lab, keep=keep, verbose=verbose)]

    if as_json:
        _echo_json(
            {
                "labs": [result.as_dict() for result in results],
                "passed": sum(result.passed for result in results),
                "failed": sum(result.failed for result in results),
                "manual": sum(result.manual for result in results),
                "ok": all(result.ok for result in results),
            }
        )
        raise typer.Exit(0 if all(result.ok for result in results) else 1)

    for result in results:
        for line in result.lines():
            _print_plain(line)
        console.print("")
    passed = sum(result.passed for result in results)
    failed = sum(result.failed for result in results)
    manual = sum(result.manual for result in results)
    if failed:
        console.print(
            f"[red]❌ {passed}/{passed + failed} 机器项通过[/red]，{failed} 项红 · "
            f"另有 {manual} 项人工评分（不进分母）"
        )
    else:
        console.print(
            f"[green]✅ {passed}/{passed + failed} 机器项全绿[/green] · 另有 {manual} 项人工评分（见 📝）"
        )
    raise typer.Exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
