"""fde-scope CLI — the FDE's daily driver.

Five subcommands mirror the FDE workflow: ``connect`` → ``corpus`` →
``deploy`` → ``eval`` → ``flywheel``. Every command supports ``--dry-run``
so the whole flow is walkable with zero data and zero extras installed.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import __version__

app = typer.Typer(
    name="fde-scope",
    help="FDE Scope — 72h from raw data to a deployed agent. Built on AgentScope 2.0.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


def _banner(title: str) -> None:
    console.print(f"\n[bold cyan]FDE Scope[/bold cyan] v{__version__} — {title}\n")


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

    out = Path("samples/preview.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")
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
    out: str = typer.Option("reports/corpus_report.html", "--out", "-o", help="Output HTML report path"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan only; don't forge"),
) -> None:
    """[Layer 2] Forge a raw sample into an auditable, gap-aware corpus."""
    _banner("corpus forge")
    if dry_run:
        console.print(f"[yellow]DRY-RUN[/yellow] would forge input={input} config={config}")
        raise typer.Exit(0)

    from .config import CorpusConfig
    from .corpus import CorpusForge, save_html, save_report_json

    cfg = CorpusConfig.from_yaml(config) if Path(config).exists() else CorpusConfig()
    rows = _load_rows(input)
    console.print(f"🔄 Loaded [bold]{len(rows)}[/bold] raw rows")

    forge = CorpusForge(cfg)
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

    save_html(report, out)
    save_report_json(report, "reports/corpus_report.json")
    console.print(f"📊 Report → [green]{out}[/green]")


def _load_rows(path: str) -> list[dict]:
    """Load raw rows from a JSON array, JSONL, or CSV (delegating to CSVConnector)."""
    p = Path(path)
    if p.is_dir():
        # treat as CSV dir
        from .connectors.csv_fallback import CSVConnector

        c = CSVConnector(str(p))
        return c.extract_sample(100000)
    if p.suffix.lower() == ".csv":
        from .connectors.csv_fallback import CSVConnector

        return CSVConnector(str(p)).extract_sample(100000)
    text = p.read_text(encoding="utf-8").strip()
    if p.suffix.lower() == ".jsonl" or (text and text[0] != "["):
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return json.loads(text)


# ---------------------------------------------------------------------------
# deploy
# ---------------------------------------------------------------------------
@app.command()
def deploy(
    tenant: str = typer.Option(..., "--tenant", "-t", help="Tenant ID"),
    name: str = typer.Option("Tenant", "--name", help="Tenant display name"),
    corpus: str | None = typer.Option(None, "--corpus", help="Path to forged corpus JSON"),
    model: str = typer.Option("qwen-max", "--model", "-m", help="Model config name"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan only; don't assemble/start"),
) -> None:
    """[Layer 3] Assemble (and optionally start) a multi-tenant agent."""
    _banner(f"deploy · {tenant}")
    from .config import TenantConfig
    from .deploy import TenantDeployer

    cfg = TenantConfig(id=tenant, name=name, model=model, corpus_path=corpus)
    deployer = TenantDeployer()
    deployed = deployer.deploy(cfg, dry_run=dry_run)

    console.print(f"🔄 Sandbox: [bold]{deployed.manifest['sandbox']['backend']}[/bold]")
    console.print(f"🔄 Corpus collection: [bold]{deployed.corpus_collection}[/bold]")
    console.print("🔄 Permissions:")
    console.print(f"   allow={deployed.manifest['permissions']['allow']}")
    console.print(f"   deny={deployed.manifest['permissions']['deny']}")
    if deployed.is_assembled:
        console.print("✅ Agent deployed! (runtime)")
    else:
        console.print("✅ Deployment plan assembled (dry-run / core-only)")
    console.print(f"📋 Manifest → [green]{json.dumps(deployed.manifest, ensure_ascii=False)}[/green]")


# ---------------------------------------------------------------------------
# eval
# ---------------------------------------------------------------------------
@app.command()
def eval(
    agent: str = typer.Option("mock", "--agent", "-a", help="Agent ID ('mock' uses the rule-based reply fn)"),
    test_set: str = typer.Option(..., "--test-set", help="Path to eval cases (JSON/JSONL)"),
    accuracy: float = typer.Option(0.9, "--accuracy", help="Mock agent accuracy (0-1)"),
) -> None:
    """[Layer 4] Run the FDE benchmark over a test set."""
    _banner(f"eval · {agent}")
    from .eval import FDEBenchmark, MockReplyFn

    cases = _load_eval_cases(test_set)
    reply_fn = MockReplyFn(accuracy=accuracy) if agent == "mock" else MockReplyFn(accuracy=accuracy)
    report = FDEBenchmark().run(reply_fn, cases)

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
    text = p.read_text(encoding="utf-8").strip()
    if p.suffix.lower() == ".jsonl" or (text and text[0] != "["):
        raw = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        raw = json.loads(text)
    from .eval import EvalCase

    return [EvalCase.model_validate(r) for r in raw]


# ---------------------------------------------------------------------------
# flywheel
# ---------------------------------------------------------------------------
@app.command()
def flywheel(
    agent: str = typer.Option(..., "--agent", "-a", help="Agent ID"),
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
        for ev in json.loads(Path(events).read_text(encoding="utf-8")):
            handled = wheel.handle_concept_event(ev["concept"], ev.get("payload", {}))
            tag = "✓" if handled else "·"
            console.print(f"   [{ev['concept']}] {tag}")
    snap = wheel.snapshot()
    console.print(
        f"\n🔄 Flywheel state: collected={snap['collected']} "
        f"(golden={snap['golden']}, labeling={snap['labeling_queued']}, "
        f"edge={snap['edge_cases']}, failures={snap['failures']})"
    )
    console.print("🔄 weekly_retrain scheduled: next Mon 02:00")


# ===========================================================================
# Engagement SOP (the full 4-zone / 18-phase lifecycle)
# ===========================================================================
engage_app = typer.Typer(name="engage", help="[SOP] FDE engagement state machine.", no_args_is_help=True)
gate_app = typer.Typer(name="gate", help="[SOP] Phase-gate校验器.", no_args_is_help=True)
app.add_typer(engage_app)
app.add_typer(gate_app)

_ENGAGEMENTS_DIR = Path(".fde_scope/engagements")


def _engagement_path(engagement_id: str) -> Path:
    return _ENGAGEMENTS_DIR / f"{engagement_id}.json"


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
) -> None:
    """Start a new FDE engagement."""
    _banner(f"engage init · {profile}")
    from .engagement import Engagement, EngagementContext

    eid = engagement_id or f"eng-{customer.lower().replace(' ', '-')}-{profile}"
    ctx = EngagementContext(id=eid, customer=customer, profile=profile)
    eng = Engagement(ctx)
    _save_engagement(eng)
    console.print(f"✅ Engagement [bold]{eid}[/bold] created (profile={profile})")
    console.print(f"   phase: {eng.ctx.current_phase} · zone: {eng.ctx.current_zone.value}")
    console.print(f"   visible phases: {len(eng.ctx.visible_phases)}")


@engage_app.command("status")
def engage_status(
    engagement_id: str = typer.Argument(..., help="Engagement id"),
) -> None:
    """Show engagement status: current phase, zone, gate state, progress."""
    eng = _load_engagement(engagement_id)
    st = eng.status()
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
    from .engagement import AdvanceBlocked

    eng = _load_engagement(engagement_id)
    try:
        nxt = eng.advance(force=force)
    except AdvanceBlocked as exc:
        console.print(f"[red]❌ ADVANCE BLOCKED[/red] — phase={eng.ctx.current_phase}")
        console.print(exc.result.summary())
        _save_engagement(eng)
        raise typer.Exit(1) from exc
    except StopIteration as exc:
        console.print("[yellow]Engagement already complete.[/yellow]")
        raise typer.Exit(0) from exc
    _save_engagement(eng)
    console.print(f"✅ Advanced → [cyan]{nxt.slug}[/cyan] ({nxt.name}) · zone={nxt.zone.value}")


@engage_app.command("rollback")
def engage_rollback(
    engagement_id: str = typer.Argument(...),
    to_phase: str = typer.Option(..., "--to", help="Target phase slug"),
) -> None:
    """Roll the engagement back to an earlier phase."""
    eng = _load_engagement(engagement_id)
    target = eng.rollback(to_phase)
    _save_engagement(eng)
    console.print(f"⏪ Rolled back → [cyan]{target.slug}[/cyan] ({target.name})")


@engage_app.command("list")
def engage_list() -> None:
    """List all local engagements."""
    _banner("engagements")
    if not _ENGAGEMENTS_DIR.exists():
        console.print("[yellow]No engagements yet.[/yellow]")
        return
    table = Table(title="Engagements")
    for col in ("id", "customer", "profile", "phase", "zone"):
        table.add_column(col)
    for p in sorted(_ENGAGEMENTS_DIR.glob("*.json")):
        from .engagement import Engagement, EngagementContext

        eng = Engagement(EngagementContext.load(p))
        st = eng.status()
        table.add_row(
            st["engagement_id"], st["customer"], st["profile"], st["current_phase"], st["current_zone"]
        )
    console.print(table)


# ---------------------------------------------------------------------------
# gate subcommands
# ---------------------------------------------------------------------------
@gate_app.command("list")
def gate_list(
    profile: str = typer.Option("manufacturing", "--profile", "-p"),
) -> None:
    """List gates applicable to a profile."""
    from .engagement.engagement import _default_gate_registry

    _banner(f"gates · {profile}")
    table = Table(title="Gates")
    for col in ("slug", "name", "industrial_only"):
        table.add_column(col)
    for slug, gate in _default_gate_registry().items():
        table.add_row(slug, gate.name, "🏭" if gate.industrial_only else "🏢")
    console.print(table)


@gate_app.command("check")
def gate_check(
    engagement_id: str = typer.Argument(...),
    gate_slug: str | None = typer.Option(
        None, "--gate", "-g", help="Specific gate slug; omit = current phase's gate"
    ),
) -> None:
    """Evaluate a gate against an engagement."""
    eng = _load_engagement(engagement_id)
    slug = gate_slug or eng.phase.gate
    if not slug:
        console.print(f"[yellow]Phase '{eng.ctx.current_phase}' has no gate.[/yellow]")
        raise typer.Exit(0)
    result = eng.evaluate_gate(slug)
    _save_engagement(eng)
    console.print(result.summary())
    if not result.passed:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# handoff + kpi + profile + web commands
# ---------------------------------------------------------------------------
@app.command()
def handoff(
    engagement_id: str = typer.Argument(...),
    eval_report: str | None = typer.Option(None, "--eval-report"),
    training: str | None = typer.Option(None, "--training-material"),
    accept: bool = typer.Option(False, "--accept", help="Mark customer accepted"),
) -> None:
    """[Zone D] Assemble the handoff / knowledge-transfer package."""
    from .engagement import build_handoff_package, render_handoff_summary
    from .engagement.operationalization import render_runbook

    eng = _load_engagement(engagement_id)
    runbook_path = f"reports/runbook_{engagement_id}.md"
    Path(runbook_path).parent.mkdir(parents=True, exist_ok=True)
    Path(runbook_path).write_text(render_runbook(eng.ctx), encoding="utf-8")
    build_handoff_package(
        eng.ctx,
        runbook_path=runbook_path,
        eval_report_path=eval_report,
        training_material=training,
        customer_accepted=accept,
    )
    _save_engagement(eng)
    console.print(f"✅ Handoff package assembled for [bold]{engagement_id}[/bold]")
    console.print(f"   runbook → [green]{runbook_path}[/green]")
    console.print(render_handoff_summary(eng.ctx))


@app.command()
def kpi(
    engagement_id: str = typer.Argument(...),
    samples_file: str = typer.Option(..., "--samples", "-s", help="JSON/JSONL of sample records"),
) -> None:
    """Compute profile-specific KPIs over a sample set."""
    eng = _load_engagement(engagement_id)
    from .profiles import get_profile

    profile = get_profile(eng.ctx.profile)
    samples = _load_rows(samples_file)
    if not isinstance(samples, list):
        samples = [samples]
    kpis = profile.compute_kpis(samples)
    _banner(f"KPIs · {engagement_id} ({profile.slug})")
    table = Table(title=f"{profile.name} KPIs")
    table.add_column("KPI", style="cyan")
    table.add_column("value", justify="right")
    table.add_column("label")
    for k, v in kpis.items():
        label = profile.kpi_catalogue.get(k, "")
        table.add_row(k, f"{v:.4f}", label)
    console.print(table)


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
    app()


if __name__ == "__main__":
    main()
