"""`fde-scope demo` — the first five minutes of an installed product.

The failure this guards is not a crash: a wheel install used to open the console
onto five empty views, with no engagements, no skills and no reports, so every
rail destination the new user clicked was an empty state. `demo` exists to make
the first screen show the product working, which means the seeded state has to
be *engine-produced*, not hand-written JSON that could drift from the gates that
read it.
"""

from __future__ import annotations

import json

import pytest

from fde_scope import demo
from fde_scope.paths import engagements_dir, reports_dir


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("FDE_SCOPE_HOME", str(tmp_path))
    return tmp_path


def test_demo_seeds_every_console_view(home) -> None:
    """engagement + skills + corpus: the three libraries the views render from."""
    result = demo.run()

    assert result["seeded"] is True
    assert result["engagement_id"].startswith(demo.DEMO_PREFIX)
    assert result["skills"] >= 1
    assert result["corpus"]["total"] > 0

    assert (engagements_dir() / f"{result['engagement_id']}.json").is_file()
    assert (reports_dir() / "demo_corpus.html").is_file()
    assert (reports_dir() / "demo_corpus.json").is_file()


def test_demo_blockers_come_from_the_real_gate(home) -> None:
    """The demo must not invent the reason it is blocked.

    ``SuccessCriteriaGate`` produces the blocker text from the context; if the
    demo hard-coded one, the first thing a new user learns about the product
    could be a sentence the engine never emits.
    """
    from fde_scope.engagement import Engagement, EngagementContext
    from fde_scope.engagement.engagement import default_gate_registry

    seeded = demo.run()
    ctx = EngagementContext.load(engagements_dir() / f"{seeded['engagement_id']}.json")
    gate_result = default_gate_registry()["success_criteria"].check(ctx)

    assert gate_result.passed is False
    assert seeded["blockers"] == gate_result.blockers
    # and the stored record agrees with what the gate says right now
    stored = Engagement(EngagementContext.load(engagements_dir() / f"{seeded['engagement_id']}.json"))
    assert stored.ctx.gate_records["success_criteria"].blockers == seeded["blockers"]


def test_demo_corpus_honours_the_heldout_rule(home) -> None:
    """Synthetic rows never reach eval/test, even in demo data."""
    demo.run()
    payload = json.loads((reports_dir() / "demo_corpus.json").read_text(encoding="utf-8"))
    assert payload["real"] > 0 and payload["synthetic"] > 0, "the demo must exercise both provenances"
    for split in ("eval", "test"):
        assert all(i["provenance"] == "real" for i in payload[split]["items"]), split


def test_demo_is_idempotent(home) -> None:
    first = demo.run()
    second = demo.run()

    assert second["removed"] == 1, "the re-run reports what it replaced"
    assert second["engagement_id"] == first["engagement_id"]
    assert len(list(engagements_dir().glob(f"{demo.DEMO_PREFIX}*.json"))) == 1


def test_demo_never_touches_a_real_engagement(home) -> None:
    """A demo in the same data root must not delete the user's work."""
    from fde_scope.engagement import Engagement, EngagementContext

    real = Engagement(EngagementContext(id="eng-real-work", customer="Real Co", profile="ticket"))
    engagements_dir(create=True)
    real.ctx.save(engagements_dir() / "eng-real-work.json")

    demo.run()
    demo.run()
    demo.run(reset=True)

    assert (engagements_dir() / "eng-real-work.json").is_file()
    assert not list(engagements_dir().glob(f"{demo.DEMO_PREFIX}*.json"))


def test_demo_reset_removes_only_its_own_reports(home) -> None:
    demo.run()
    reports = reports_dir(create=True)
    mine = reports / "user_corpus.html"
    mine.write_text("my work", encoding="utf-8")

    out = demo.run(reset=True)

    assert out["seeded"] is False
    assert not (reports / "demo_corpus.html").exists()
    assert not (reports / "demo_corpus.json").exists()
    assert mine.is_file(), "reset deleted a report it did not create"


def test_demo_is_offline_and_keyless(home, monkeypatch) -> None:
    """No API key, no network: the demo must work on a plane."""
    monkeypatch.delenv("FDE_SCOPE_MIMO_API_KEY", raising=False)
    monkeypatch.delenv("FDE_SCOPE_LLM_API_KEY", raising=False)
    result = demo.run()
    assert result["seeded"] is True


def test_demo_data_is_declared_fictional() -> None:
    """The disclaimer is the contract that this is not customer data."""
    assert "虚构" in demo._DISCLAIMER
    assert "fictional" in demo._DISCLAIMER.lower()
    # and the seeded customer carries the marker, so a screenshot of the console
    # cannot be mistaken for a real engagement
    eng = demo._seed_engagement()
    assert "虚构" in eng.ctx.customer
    assert eng.ctx.id.startswith(demo.DEMO_PREFIX)
