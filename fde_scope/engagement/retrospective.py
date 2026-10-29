"""Engagement 复盘：SLA 时钟 + 时间线 + gate 统计（纯读，零持久化）。

把已存在的两类记录聚合起来，不需要任何新写入：

- ``audit.jsonl`` 事件流（``engagement.create/advance/rollback/gate_evaluate``）
  重放成阶段时间线——advance 事件不带阶段名，重放从初始阶段 ``qualification``
  起、按 ``next_phase`` 顺序推导，rollback 事件携带显式 to_phase；
- ``EngagementContext``：契约时限覆盖（``assets["success_criteria_sla"]``）、
  gate_records 的最新状态、journal 分类计数。

诚实性约定（与 gate 哲学一致）：

- 重放终态与 ``ctx.current_phase`` 不一致（审计缺失/截断）时**不猜**，
  置 ``timeline_consistent=False``，报告照常返回但携带该标志；
- 无任何审计事件时（历史项目 / CLI 早期项目），SLA 退化为 journal 时间锚，
  gate 统计退化为 context-only（评估次数未知，不编造）；
- 时限只从 ``assets["success_criteria_sla"]`` 读取显式覆盖，其余用
  ``build_success_criteria_template()`` 的行业默认值，来源逐里程碑标注。
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from .context import EngagementContext
from .phases import next_phase, phase_by_slug
from .pre_engagement import build_success_criteria_template

# 里程碑 → (assets 覆盖键, 目标阶段, 中文说明)。进入目标阶段 = 里程碑达成：
# 离开 connect（进入 corpus）= 首次数据集成；离开 deploy（进入 eval）= 上线；
# 进入 disengage = 退场启动。
_MILESTONES: tuple[tuple[str, str, str, str], ...] = (
    ("first_integration", "time_to_first_integration_days", "corpus", "首次数据集成"),
    ("production", "time_to_production_days", "eval", "部署上线"),
    ("disengage", "disengage_after_days", "disengage", "退场"),
)

_RISK_RATIO = 0.8  # 未达成的里程碑：超过 80% 时限进入 at_risk


class PhaseTiming(BaseModel):
    """一个阶段的进入/离开与累计停留。"""

    slug: str
    name: str
    zone: str
    visits: int = 0
    total_days: float | None = None  # None = 有访问但时长不可知（缺时间锚）
    first_entered_at: str | None = None
    last_entered_at: str | None = None
    current: bool = False


class SlaMilestone(BaseModel):
    """一个契约时限的达成状态。"""

    key: str
    label: str
    deadline_days: int
    deadline_source: str  # assets | defaults
    target_phase: str
    reached: bool
    reached_at: str | None = None
    elapsed_days: float | None = None
    status: str  # met | missed | on_track | at_risk | unknown
    note: str = ""


class GateStat(BaseModel):
    """一个 gate 的评估统计。"""

    slug: str
    evaluations: int | None = None  # None = 审计流缺失，不编造
    first_pass: bool | None = None
    passes: int | None = None
    latest_passed: bool | None = None  # ctx.gate_records 最新一次
    source: str  # audit | context-only


class RetrospectiveReport(BaseModel):
    """一份 engagement 复盘报告（JSON 可序列化）。"""

    engagement_id: str
    customer: str
    profile: str
    generated_at: str
    started_at: str | None = None
    start_source: str | None = None  # engagement.create | earliest-audit-event | earliest-journal
    elapsed_days: float | None = None
    current_phase: str
    phases: list[PhaseTiming] = Field(default_factory=list)
    sla: list[SlaMilestone] = Field(default_factory=list)
    gates: list[GateStat] = Field(default_factory=list)
    gate_first_pass_rate: float | None = None
    advances_ok: int = 0
    advances_forced: int = 0
    advances_blocked: int = 0
    rollbacks: int = 0
    journal_counts: dict[str, int] = Field(default_factory=dict)
    timeline_consistent: bool = True
    audit_event_count: int = 0
    data_sources: list[str] = Field(default_factory=list)


def build_retrospective(
    ctx: EngagementContext,
    events: list[dict],
    now: datetime | None = None,
) -> RetrospectiveReport:
    """从 context + 审计事件流构建复盘报告（纯函数）。

    ``events`` 应为已按 engagement 过滤的审计记录（``audit.read_events(eid)``）。
    时间戳无法解析的记录整条忽略（与 ``audit.read_events`` 跳过坏行的哲学一致）。
    """
    now = now or datetime.now(UTC)
    usable = [e for e in events if _parse_ts(e.get("ts")) is not None]
    usable.sort(key=lambda e: _parse_ts(e["ts"]) or datetime.min.replace(tzinfo=UTC))

    timeline, replay_current, counts = _replay_timeline(usable, ctx.is_industrial)
    timeline_consistent = replay_current == ctx.current_phase

    started_at, start_source = _find_start(usable, ctx)
    elapsed_raw = _days_between(started_at, now) if started_at else None
    elapsed_days = round(elapsed_raw, 2) if elapsed_raw is not None else None

    sla = _sla_milestones(ctx, timeline, started_at, elapsed_days, now)
    gates = _gate_stats(ctx, usable)
    known_first_pass = [g.first_pass for g in gates if g.first_pass is not None]
    first_pass_rate = (
        round(sum(1 for p in known_first_pass if p) / len(known_first_pass), 4) if known_first_pass else None
    )

    sources = ["context"]
    if usable:
        sources.insert(0, f"audit.jsonl ({len(usable)} events)")
    elif ctx.journal:
        sources.append("journal (audit trail absent)")

    return RetrospectiveReport(
        engagement_id=ctx.id,
        customer=ctx.customer,
        profile=ctx.profile,
        generated_at=now.isoformat(),
        started_at=started_at,
        start_source=start_source,
        elapsed_days=elapsed_days,
        current_phase=ctx.current_phase,
        phases=_ordered_phase_timings(timeline, replay_current if timeline_consistent else None, now),
        sla=sla,
        gates=gates,
        gate_first_pass_rate=first_pass_rate,
        advances_ok=counts["advances_ok"],
        advances_forced=counts["advances_forced"],
        advances_blocked=counts["advances_blocked"],
        rollbacks=counts["rollbacks"],
        journal_counts=dict(Counter(e.kind for e in ctx.journal)),
        timeline_consistent=timeline_consistent,
        audit_event_count=len(usable),
        data_sources=sources,
    )


# ---------------------------------------------------------------------------
# 时间线重放
# ---------------------------------------------------------------------------
def _replay_timeline(
    events: list[dict], is_industrial: bool
) -> tuple[dict[str, dict[str, Any]], str, dict[str, int]]:
    """按序重放审计事件 → (阶段访问表, 重放终态, 计数)。

    advance 事件不带阶段名：从初始阶段 ``qualification`` 起按 ``next_phase``
    推导（EngagementContext 的初始相恒为 qualification，与 create 事件是否
    在场无关）；rollback 事件携带显式 ``to_phase``。
    """
    current = "qualification"
    visits: dict[str, dict[str, Any]] = {}
    counts = {"advances_ok": 0, "advances_forced": 0, "advances_blocked": 0, "rollbacks": 0}

    def _open(slug: str, ts: str) -> None:
        v = visits.setdefault(
            slug, {"visits": 0, "days": 0.0, "days_known": True, "first": None, "last": None, "open": None}
        )
        v["visits"] += 1
        v["open"] = ts
        if v["last"] is None:
            v["last"] = ts
        if v["first"] is None:
            v["first"] = ts

    def _close(slug: str, ts: str) -> None:
        v = visits.get(slug)
        if v is None or v["open"] is None:
            return
        days = _days_between(v["open"], ts)
        if days is None:
            v["days_known"] = False
        else:
            v["days"] += days
        v["open"] = None

    # 初始访问只在有 create 事件时才建立——没有时间锚就宁可缺席该阶段，
    # 不伪造一条 0 天的记录。
    create_ts = next((e["ts"] for e in events if e.get("action") == "engagement.create"), None)
    if create_ts:
        _open(current, create_ts)

    for e in events:
        action, ts = e.get("action", ""), e["ts"]
        detail = e.get("detail") or {}
        if action == "engagement.create":
            continue  # 初始访问已在上面锚定
        if action == "engagement.advance":
            if detail.get("advanced") is False:
                if detail.get("reason") == "complete":
                    continue  # 已在终点的推进尝试不是“被拦”
                counts["advances_blocked"] += 1
                continue
            nxt = next_phase(current, is_industrial)
            if nxt is None:
                continue
            _close(current, ts)
            current = nxt.slug
            counts["advances_ok"] += 1
            if detail.get("force"):
                counts["advances_forced"] += 1
            _open(current, ts)
        elif action == "engagement.rollback":
            counts["rollbacks"] += 1
            target = detail.get("to_phase")
            if not isinstance(target, str):
                continue
            try:
                phase_by_slug(target)
            except KeyError:
                continue
            _close(current, ts)
            current = target
            _open(current, ts)

    # 仍在当前阶段的访问不关闭（无离开时间）。
    return visits, current, counts


def _ordered_phase_timings(
    visits: dict[str, dict[str, Any]], current_slug: str | None, now: datetime
) -> list[PhaseTiming]:
    """访问表 → 按首次进入排序的 PhaseTiming 列表。

    仍在进行中的访问把 elapsed(enter→now) 计入 total_days（"当前阶段已停留
    X 天"是最有用的读数）；时间锚缺失时 total_days=None，不伪造数字。
    """
    out: list[PhaseTiming] = []
    for slug, v in visits.items():
        if v["visits"] == 0:
            continue
        days, known = v["days"], v["days_known"]
        if v["open"] is not None:
            extra = _days_between(v["open"], now)
            if extra is None:
                known = False
            else:
                days += extra
        out.append(
            PhaseTiming(
                slug=slug,
                name=phase_by_slug(slug).name,
                zone=phase_by_slug(slug).zone.value,
                visits=v["visits"],
                total_days=round(days, 2) if known else None,
                first_entered_at=v["first"],
                last_entered_at=v["last"],
                current=slug == current_slug,
            )
        )
    out.sort(key=lambda t: t.first_entered_at or t.last_entered_at or "")
    return out


# ---------------------------------------------------------------------------
# SLA 里程碑
# ---------------------------------------------------------------------------
def _sla_milestones(
    ctx: EngagementContext,
    visits: dict[str, dict[str, Any]],
    started_at: str | None,
    elapsed_days: float | None,
    now: datetime,
) -> list[SlaMilestone]:
    overrides = ctx.assets.get("success_criteria_sla")
    overrides = overrides if isinstance(overrides, dict) else {}
    defaults = build_success_criteria_template()
    out: list[SlaMilestone] = []
    for key, deadline_key, target_phase, label in _MILESTONES:
        override = overrides.get(deadline_key)
        if isinstance(override, (int, float)) and not isinstance(override, bool) and override > 0:
            deadline, source = int(override), "assets"
        else:
            deadline, source = int(defaults[deadline_key]), "defaults"

        entry = visits.get(target_phase, {}).get("first")
        if started_at is None:
            status, note = "unknown", "无时间锚（审计流与 journal 均为空）"
            reached, reached_at, milestone_days = bool(entry), entry, None
        elif entry:
            reached, reached_at = True, entry
            milestone_days = _days_between(started_at, entry)
            if milestone_days is None:
                status, note = "unknown", "达成时间不可解析"
            elif milestone_days <= deadline:
                status, note = "met", f"用时 {milestone_days:.1f}d / 限 {deadline}d"
            else:
                status, note = "missed", f"用时 {milestone_days:.1f}d，超出契约 {deadline}d"
        else:
            reached, reached_at, milestone_days = False, None, elapsed_days
            if elapsed_days is None:
                status, note = "unknown", "无时间锚"
            elif elapsed_days > deadline:
                status, note = "missed", f"已 {elapsed_days:.1f}d，超出契约 {deadline}d"
            elif elapsed_days > _RISK_RATIO * deadline:
                status, note = "at_risk", f"已 {elapsed_days:.1f}d / 限 {deadline}d"
            else:
                status, note = "on_track", f"已 {elapsed_days:.1f}d / 限 {deadline}d"
        out.append(
            SlaMilestone(
                key=key,
                label=label,
                deadline_days=deadline,
                deadline_source=source,
                target_phase=target_phase,
                reached=reached,
                reached_at=reached_at,
                elapsed_days=round(milestone_days, 2) if milestone_days is not None else None,
                status=status,
                note=note,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Gate 统计
# ---------------------------------------------------------------------------
def _gate_stats(ctx: EngagementContext, events: list[dict]) -> list[GateStat]:
    """审计流给评估次数与首过；context 给最新状态；两者来源分开标注。"""
    per_slug: dict[str, list[bool]] = {}
    for e in events:
        if e.get("action") != "engagement.gate_evaluate":
            continue
        detail = e.get("detail") or {}
        slug, passed = detail.get("gate"), detail.get("passed")
        if isinstance(slug, str) and isinstance(passed, bool):
            per_slug.setdefault(slug, []).append(passed)

    slugs = list(dict.fromkeys([*per_slug.keys(), *ctx.gate_records.keys()]))
    out: list[GateStat] = []
    for slug in slugs:
        seq = per_slug.get(slug)
        if seq:
            out.append(
                GateStat(
                    slug=slug,
                    evaluations=len(seq),
                    first_pass=seq[0],
                    passes=sum(1 for p in seq if p),
                    latest_passed=ctx.gate_passed(slug),
                    source="audit",
                )
            )
        else:
            rec = ctx.gate_records.get(slug)
            out.append(
                GateStat(
                    slug=slug,
                    latest_passed=bool(rec.passed) if rec else None,
                    source="context-only",
                )
            )
    return out


# ---------------------------------------------------------------------------
# 时间锚与工具
# ---------------------------------------------------------------------------
def _find_start(events: list[dict], ctx: EngagementContext) -> tuple[str | None, str | None]:
    """started_at + 来源标注：create > 最早审计事件 > 最早 journal。"""
    for e in events:
        if e.get("action") == "engagement.create":
            return e["ts"], "engagement.create"
    if events:
        return events[0]["ts"], "earliest-audit-event"
    journal_ts = sorted(j.ts for j in ctx.journal if _parse_ts(j.ts))
    if journal_ts:
        return journal_ts[0], "earliest-journal"
    return None, None


def _parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        ts = datetime.fromisoformat(value)
    except ValueError:
        return None
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=UTC)


def _days_between(start: str | datetime | None, end: str | datetime | None) -> float | None:
    s, e = (
        _parse_ts(start) if isinstance(start, str) else start,
        _parse_ts(end) if isinstance(end, str) else end,
    )
    if s is None or e is None:
        return None
    return (e - s).total_seconds() / 86400


# ---------------------------------------------------------------------------
# Markdown 渲染（CLI / 分享页导出）
# ---------------------------------------------------------------------------
def render_markdown(report: RetrospectiveReport) -> str:
    """渲染人类可读的复盘报告（对话式导出用，不替代 JSON）。"""
    title = f"复盘报告 · {report.engagement_id}（{report.customer}）"
    elapsed_note = f" · 已历时 {report.elapsed_days:.1f}d" if report.elapsed_days is not None else ""
    lines = [
        f"# {title}",
        "",
        f"- 生成时间（UTC）: {report.generated_at}",
        f"- profile: {report.profile} · 当前阶段: {report.current_phase}",
        f"- started: {report.started_at or '—'}（来源: {report.start_source or '—'}）{elapsed_note}",
        f"- 推进 {report.advances_ok} 次（强制 {report.advances_forced} · 被拦 {report.advances_blocked}）"
        f" · 回滚 {report.rollbacks} 次 · gate 首过率 "
        f"{f'{report.gate_first_pass_rate:.0%}' if report.gate_first_pass_rate is not None else '—'}",
        f"- 数据源: {', '.join(report.data_sources)}",
        "",
    ]
    if not report.timeline_consistent:
        lines += [
            "> ⚠️ 审计流重放终态与当前阶段不一致——时间线可能缺失早期事件，以下阶段/SLA 数据仅供参考。",
            "",
        ]
    lines += ["## SLA 里程碑", "", "| 里程碑 | 契约 | 状态 | 说明 |", "|---|---|---|---|"]
    for m in report.sla:
        status_icon = {"met": "✅", "missed": "❌", "at_risk": "⚠️", "on_track": "🟢"}.get(m.status, "❔")
        lines.append(
            f"| {m.label} | ≤{m.deadline_days}d（{m.deadline_source}）| {status_icon} {m.status} | {m.note} |"
        )
    lines += [
        "",
        "## 阶段时间线",
        "",
        "| 阶段 | 访问 | 累计天数 | 首次进入 | 当前 |",
        "|---|---|---|---|---|",
    ]
    for p in report.phases:
        days = f"{p.total_days:.1f}" if p.total_days is not None else "—"
        lines.append(
            f"| {p.slug}（{p.name}）| {p.visits} | {days} | {p.first_entered_at or '—'} | {'●' if p.current else ''} |"
        )
    lines += [
        "",
        "## Gate 统计",
        "",
        "| gate | 评估 | 首过 | 通过 | 最新 | 来源 |",
        "|---|---|---|---|---|---|",
    ]
    for g in report.gates:
        fp = "✅" if g.first_pass else ("❌" if g.first_pass is False else "—")
        lp = {True: "✅", False: "❌", None: "—"}.get(g.latest_passed, "—")
        lines.append(
            f"| {g.slug} | {g.evaluations if g.evaluations is not None else '—'} | {fp} "
            f"| {g.passes if g.passes is not None else '—'} | {lp} | {g.source} |"
        )
    if report.journal_counts:
        lines += [
            "",
            "## 现场记录",
            "",
            "```",
            *[f"{k}: {v}" for k, v in sorted(report.journal_counts.items())],
            "```",
        ]
    return "\n".join(lines) + "\n"
