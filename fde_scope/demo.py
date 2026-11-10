"""`fde-scope demo` — a working workbench in one command, from a cold install.

The first five minutes decide whether someone keeps the tool. Before this
command the answer was "clone the repo, read README, work out that the console
opens empty until you run an examples/ script that a wheel does not ship". A
wheel install had no engagements, no skills and no reports, so every console
view and every rail destination the user clicked was an empty state — the
product looked broken on first contact.

`demo` seeds a small, explicitly fictional engagement using the *real*
engines: gates are evaluated by :class:`Engagement` (so the blockers are the
ones the product would really produce), the corpus is forged by
:class:`CorpusForge`, and skills go through :class:`SkillService`. Nothing is
hand-written JSON that could disagree with the engine that reads it.

Every name, metric and incident is invented. The banner says so, the seeded
engagement id says so (``eng-demo-``), and the closing guidance points at the
gates that are *meant* to be blocking — a demo that shows no red teaches the
wrong lesson about what the tool is for.
"""

from __future__ import annotations

from pathlib import Path

#: The one thing this module writes into the user's data root, listed so
#: ``--reset`` can be exact instead of "delete anything that looks like a demo".
DEMO_PREFIX = "eng-demo-"

_DISCLAIMER = (
    "全部数据为虚构演示数据，与任何真实公司无关。 / Every name, metric and incident below is fictional."
)

#: Realistic ticket rows — varied topics, no PII, long enough to clear the
#: quality gate so the corpus numbers are about the forge, not about drops.
_TICKET_ROWS: tuple[tuple[str, str], ...] = (
    ("申请退款商品质量有问题已经拍照留存希望尽快处理", "退款"),
    ("订单里多了一件商品怎么取消", "订单"),
    ("账号被锁定了怎么解锁", "账号"),
    ("咨询一下会员权益有哪些", "咨询"),
    ("收到的商品和描述不符要求退款", "退款"),
    ("优惠券无法使用结算时报错请帮忙看一下", "订单"),
    ("登录时一直提示密码错误", "账号"),
    ("物流信息三天没有更新了", "物流"),
    ("发票抬头开错了需要重开", "发票"),
    ("商品有色差想换一个颜色", "退货"),
    ("退货流程走完了什么时候能收到退款", "退货"),
    ("客服一直不回复我的问题", "咨询"),
    ("付款失败但银行卡已经扣款", "支付"),
    ("地址填写错误能否修改收货信息", "订单"),
    ("会员自动续费如何关闭", "账号"),
    ("包装破损商品有损坏", "退款"),
    ("如何申请开具电子发票", "发票"),
    ("快递显示已签收但没有收到", "物流"),
    ("尺码不合适想换货", "退货"),
    ("积分兑换的商品什么时候发货", "咨询"),
)


def _seed_engagement():
    """An engagement at ``success_criteria`` with a *failing* gate on purpose.

    The demo stops one step short of passing so the reader meets the gate
    engine doing its job: the blocker text is produced by
    ``SuccessCriteriaGate``, not written into the fixture.
    """
    from .engagement import Engagement, EngagementContext
    from .engagement.context import SiteInfo, Stakeholder

    ctx = EngagementContext(
        id=f"{DEMO_PREFIX}ticket",
        customer="北极星咖啡（虚构）",
        profile="ticket",
        site=SiteInfo(location="上海市浦东新区（虚构地址）", works_council_present=False),
    )
    ctx.stakeholders = [
        Stakeholder(name="林工", role="客服中心负责人", is_sponsor=True),
        Stakeholder(name="赵经理", role="IT 总监", is_sponsor=True),
    ]
    eng = Engagement(ctx)
    # Walk the two ungated phases so the reader lands on a *blocked* gate.
    for _ in range(2):
        eng.advance()
    eng.evaluate_gate("success_criteria")
    return eng


def _seed_corpus(reports_dir: Path) -> dict:
    """Forge the demo corpus with the real engine; returns the report summary."""
    from .config import CorpusConfig
    from .corpus import CorpusForge, save_html
    from .corpus.pipeline import save_report_json

    rows = [
        {"id": f"d{i}", "content": text, "category": cat} for i, (text, cat) in enumerate(_TICKET_ROWS, 1)
    ]
    cfg = CorpusConfig(min_samples_per_category=100, synth_per_gap=6)
    report = CorpusForge(cfg).forge_rows(rows)
    reports_dir.mkdir(parents=True, exist_ok=True)
    save_html(report, reports_dir / "demo_corpus.html")
    save_report_json(report, reports_dir / "demo_corpus.json")
    return {
        "total": report.total,
        "real": report.real,
        "synthetic": report.synthetic,
        "heldout_real": report.heldout_real,
        "heldout_trusted": report.heldout_trusted,
    }


def _seed_skills() -> int:
    """Three published skills so the library view is not an empty state."""
    from .paths import skills_dir
    from .skills.models import SkillCategory, SkillDraft
    from .skills.service import SkillService
    from .skills.store import SkillStore

    svc = SkillService(SkillStore(skills_dir(create=True)))
    drafts = (
        SkillDraft(
            title="现场勘察先问班组长，再问 IT",
            category=SkillCategory.RESEARCH,
            body_md="## 做法\n\n班组长知道哪台设备在半夜停过，IT 只知道网络通不通。"
            "先问班会记录，再要 IT 的接口清单。\n\n## 证据\n\n演示数据。",
            tags=["site-survey"],
        ),
        SkillDraft(
            title="门禁被拦时先看 blockers，不要 force",
            category=SkillCategory.METHODOLOGY,
            body_md="## 做法\n\n`force` 会把例外写进审计流。先读 blockers，"
            "确认是真缺失还是填错了字段。\n\n## 反例\n\n演示数据。",
            tags=["gates"],
        ),
        SkillDraft(
            title="语料留出集只用真实样本",
            category=SkillCategory.OPTIMIZATION,
            body_md="## 做法\n\n合成数据只进 train。在合成数据上量出来的准确率，"
            "量的是合成器，不是模型。\n\n## 证据\n\n`corpus_report.json` 的 `heldout_real`。",
            tags=["corpus"],
        ),
    )
    for d in drafts:
        rec = svc.create(d)
        svc.publish(rec.id)
    return len(drafts)


def _existing_demos() -> list[Path]:
    from .paths import engagements_dir

    d = engagements_dir()
    if not d.is_dir():
        return []
    return sorted(d.glob(f"{DEMO_PREFIX}*.json"))


def run(reset: bool = False) -> dict:
    """Seed (or re-seed) the demo. Idempotent: safe to run twice.

    Re-running replaces only the demo engagement — a real engagement in the
    same data root is never touched. ``reset`` removes the demo artifacts and
    stops there, so a demo can be taken out without deleting user work.
    """
    from .paths import engagements_dir, reports_dir

    removed = 0
    for path in _existing_demos():
        path.unlink(missing_ok=True)
        removed += 1
    if reset:
        for name in ("demo_corpus.html", "demo_corpus.json"):
            (reports_dir() / name).unlink(missing_ok=True)
        return {"removed": removed, "seeded": False}

    eng = _seed_engagement()
    out = engagements_dir(create=True)
    eng.ctx.save(out / f"{eng.ctx.id}.json")

    corpus = _seed_corpus(reports_dir(create=True))
    skills = _seed_skills()
    status = eng.status()
    return {
        "removed": removed,
        "seeded": True,
        "engagement_id": eng.ctx.id,
        "phase": status["current_phase"],
        "zone": status["current_zone"],
        "blockers": list(status["gate_records"].get("success_criteria", {}).get("blockers", [])),
        "corpus": corpus,
        "skills": skills,
    }
