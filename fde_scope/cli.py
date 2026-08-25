"""fde-scope CLI — the FDE's daily driver.

Five subcommands mirror the FDE workflow: ``connect`` → ``corpus`` →
``deploy`` → ``eval`` → ``flywheel``. Every command supports ``--dry-run``
so the whole flow is walkable with zero data and zero extras installed.
"""

from __future__ import annotations

import json
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.console import Console
from rich.table import Table

from . import __version__

if TYPE_CHECKING:
    from .skills.service import SkillService

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
# LLM wiring (Xiaomi MiMo Token Plan — optional, env-configured)
# ---------------------------------------------------------------------------
def _maybe_llm(require: bool = False):
    """Build the MiMo client from env vars; exit cleanly when a key is missing."""
    from .llm import MiMoClient

    client = MiMoClient()
    if not client.available:
        if require:
            console.print(
                "[red]LLM not configured:[/red] set FDE_SCOPE_MIMO_API_KEY "
                "(Xiaomi MiMo Token Plan, tp-… format) to enable LLM mode."
            )
            raise typer.Exit(2)
        console.print(
            "[yellow]LLM disabled (FDE_SCOPE_MIMO_API_KEY not set)[/yellow] — "
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
    llm: bool = typer.Option(
        False, "--llm", help="Synthesize gap-filling samples with MiMo (needs FDE_SCOPE_MIMO_API_KEY)"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan only; don't forge"),
) -> None:
    """[Layer 2] Forge a raw sample into an auditable, gap-aware corpus."""
    _banner("corpus forge")
    if dry_run:
        console.print(f"[yellow]DRY-RUN[/yellow] would forge input={input} config={config}")
        raise typer.Exit(0)

    from .config import CorpusConfig
    from .corpus import CorpusForge, save_html, save_report_json

    client = _maybe_llm(require=llm) if llm else None
    cfg = CorpusConfig.from_yaml(config) if Path(config).exists() else CorpusConfig()
    rows = _load_rows(input)
    console.print(f"🔄 Loaded [bold]{len(rows)}[/bold] raw rows")

    forge = CorpusForge(cfg, llm=client)
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
    json_out = str(Path(out).parent / "corpus_report.json")
    save_report_json(report, json_out)
    console.print(f"📊 Report → [green]{out}[/green] (+ {json_out})")


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
    agent_specs: list[str] | None = typer.Option(
        None, "--agent", "-a", help="Agent spec 'name:role[:model]' (repeatable)"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan only; don't assemble/start"),
) -> None:
    """[Layer 3] Assemble (and optionally start) a multi-tenant agent."""
    _banner(f"deploy · {tenant}")
    from .config import AgentSpec, TenantConfig
    from .deploy import TenantDeployer

    agents = []
    for a in agent_specs or []:
        parts = a.split(":")
        if len(parts) == 2:
            agent_name, agent_role, agent_model = parts[0], parts[1], None
        elif len(parts) == 3:
            agent_name, agent_role, agent_model = parts
        else:
            console.print(f"[red]Invalid agent spec:[/red] {a} (expected name:role[:model])")
            raise typer.Exit(2)
        agents.append(AgentSpec(name=agent_name, role=agent_role, model=agent_model))
    cfg = TenantConfig(id=tenant, name=name, model=model, corpus_path=corpus, agents=agents or None)
    corpus_report = None
    if corpus:
        from .corpus import CorpusReport

        try:
            corpus_report = CorpusReport.model_validate_json(Path(corpus).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            console.print(f"[red]Cannot load corpus report:[/red] {corpus} ({exc})")
            raise typer.Exit(2) from exc
    client = _maybe_llm()
    deployer = TenantDeployer()
    deployed = deployer.deploy(cfg, corpus_report=corpus_report, dry_run=dry_run)
    if client.available:
        deployed.manifest["llm"] = client.describe()

    console.print(f"🔄 Sandbox: [bold]{deployed.manifest['sandbox']['backend']}[/bold]")
    console.print(f"🔄 Corpus collection: [bold]{deployed.corpus_collection}[/bold]")
    console.print(f"🔄 Model: [bold]{deployed.manifest['model']}[/bold]")
    if client.available:
        console.print(f"🔄 LLM: [bold]{client.model}[/bold] @ {client.base_url} (MiMo)")
    else:
        console.print("🔄 LLM: [yellow]未配置（设 FDE_SCOPE_MIMO_API_KEY 启用 MiMo）[/yellow]")
    console.print("🔄 Permissions:")
    console.print(f"   allow={deployed.manifest['permissions']['allow']}")
    console.print(f"   deny={deployed.manifest['permissions']['deny']}")
    if deployed.is_assembled:
        console.print("✅ Agent deployed! (runtime)")
    else:
        console.print("✅ Deployment plan assembled (dry-run / core-only)")
    for a in deployed.manifest.get("agents") or []:
        console.print(f"🔄 Agent: [bold]{a['name']}[/bold] · {a['role']} · model={a['model'] or 'runtime'}")
    console.print(f"📋 Manifest → [green]{json.dumps(deployed.manifest, ensure_ascii=False)}[/green]")


# ---------------------------------------------------------------------------
# eval
# ---------------------------------------------------------------------------
@app.command()
def eval(
    agent: str = typer.Option(
        "mock", "--agent", "-a", help="Agent: 'mock' (rule-based) or 'mimo' (MiMo LLM)"
    ),
    test_set: str = typer.Option(..., "--test-set", help="Path to eval cases (JSON/JSONL)"),
    accuracy: float = typer.Option(0.9, "--accuracy", help="Mock agent accuracy (0-1)"),
) -> None:
    """[Layer 4] Run the FDE benchmark over a test set."""
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
        report = FDEBenchmark().run(reply_fn, cases)
    except LLMError as exc:
        # Mid-run endpoint failure: exit cleanly instead of a traceback that
        # discards all context (the benchmark has no rule path to fall back to).
        console.print(f"[red]MiMo eval failed:[/red] {exc}")
        raise typer.Exit(1) from exc

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
        _maybe_suggest_skill(engagement_id, eng.ctx.current_phase, list(exc.result.blockers))
        raise typer.Exit(1) from exc
    except StopIteration as exc:
        console.print("[yellow]Engagement already complete.[/yellow]")
        raise typer.Exit(0) from exc
    _save_engagement(eng)
    _maybe_capture("advance", engagement_id, phase_slug=eng.ctx.current_phase)
    console.print(f"✅ Advanced → [cyan]{nxt.slug}[/cyan] ({nxt.name}) · zone={nxt.zone.value}")


@engage_app.command("rollback")
def engage_rollback(
    engagement_id: str = typer.Argument(...),
    to_phase: str = typer.Option(..., "--to", help="Target phase slug"),
) -> None:
    """Roll the engagement back to an earlier phase."""
    eng = _load_engagement(engagement_id)
    try:
        target = eng.rollback(to_phase)
    except KeyError:
        console.print(f"[red]Unknown phase:[/red] {to_phase}")
        raise typer.Exit(2) from None
    except ValueError as exc:
        console.print(f"[red]Invalid rollback:[/red] {exc}")
        raise typer.Exit(2) from None
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
    llm: bool = typer.Option(
        False, "--llm", help="Draft the runbook with MiMo (needs FDE_SCOPE_MIMO_API_KEY)"
    ),
    accept: bool = typer.Option(False, "--accept", help="Mark customer accepted"),
) -> None:
    """[Zone D] Assemble the handoff / knowledge-transfer package."""
    from .engagement import build_handoff_package, render_handoff_summary
    from .engagement.operationalization import llm_runbook, render_runbook

    eng = _load_engagement(engagement_id)
    runbook_path = f"reports/runbook_{engagement_id}.md"
    Path(runbook_path).parent.mkdir(parents=True, exist_ok=True)
    model_name = ""
    if llm:
        client = _maybe_llm(require=True)
        model_name = client.model
        runbook_md, used_llm = llm_runbook(eng.ctx, client)
    else:
        runbook_md, used_llm = render_runbook(eng.ctx), False
    Path(runbook_path).write_text(runbook_md, encoding="utf-8")
    if used_llm:
        console.print(f"🤖 Runbook drafted by MiMo ({model_name})")
    elif llm:
        console.print("[yellow]Runbook rendered from template (MiMo draft failed)[/yellow]")
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


# ---------------------------------------------------------------------------
# skills（技能/方法论沉淀库）
# ---------------------------------------------------------------------------
skill_app = typer.Typer(name="skill", help="[Skills] 技能/方法论沉淀库.", no_args_is_help=True)
app.add_typer(skill_app)


def _skill_service() -> SkillService:
    from .skills.service import SkillService
    from .skills.store import SkillStore

    return SkillService(SkillStore(Path(".fde_scope/skills")))


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
    rows = service.search(
        search,
        category=cat,
        tags=[tag] if tag else None,
        status=st,
        profile=profile,
        gate_slug=gate,
        phase_slug=phase,
    )
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
    out: str = typer.Option("exports", "--out", help="输出目录"),
) -> None:
    """导出技能为 AgentScope / QwenPaw 格式。"""
    from .skills.exporters import export_skill

    try:
        rec = _skill_service().get(skill_id)
        files = export_skill(rec, fmt)
    except KeyError:
        console.print(f"[red]技能不存在:[/red] {skill_id}")
        raise typer.Exit(2) from None
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from None
    out_dir = Path(out)
    for f in files:
        p = out_dir / f.name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f.content, encoding="utf-8")
    console.print(f"✅ 导出 {len(files)} 个文件 → [green]{out_dir}[/green] ({fmt})")


if __name__ == "__main__":
    main()
