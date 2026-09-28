"""Guided-mode JSON API (router included by ``fde_scope.web.app``).

Read-only guidance over the same engine the expert console uses: the guided
payload re-checks the current phase's gates live and never records outcomes
or advances the state machine (AGENTS.md invariant 1).

Write semantics, by route:
- ``draft-context`` never persists — it returns a draft the user reviews and
  then applies through the existing ``POST /api/engagements/{eid}/context``
  (gates stay the sole acceptance channel).
- ``plan`` persists the task breakdown into ``ctx.assets["guided_plan"]``
  (free-form per-phase outputs; checkbox updates go through the same
  existing context PATCH). Single-user workbench: the assets key is
  replaced wholesale, concurrent writers would clobber each other.

Note: ``pawapp/backend/main.py`` mirrors the engagement helpers but not
these routes; the domain layer (``fde_scope.engagement.guided``) is pure and
can be imported directly if the PawApp grows a guided mode.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from ..engagement.guided import (
    context_field_guide,
    guided_view,
    llm_draft_context,
    llm_goal_plan,
)
from .deps import _load, _save, catalog_site_dir, engagement_lock

router = APIRouter()


class DraftContextRequest(BaseModel):
    description: str = Field(min_length=1, max_length=8000)


class PlanRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=2000)


@router.get("/api/engagements/{eid}/guided")
def engagement_guided(eid: str) -> dict:
    eng = _load(eid)
    return guided_view(eng.ctx, catalog_local=catalog_site_dir() is not None)


@router.post("/api/engagements/{eid}/guided/draft-context")
async def draft_context(eid: str, body: DraftContextRequest) -> dict:
    """AI-draft context cards from a free-text description. Pure draft:
    nothing is persisted until the user applies it via POST .../context."""
    eng = _load(eid)
    description = body.description.strip()
    if not description:
        raise HTTPException(status_code=422, detail="'description' must not be blank") from None
    from ..llm import get_llm_client

    # LLM calls are blocking (up to ~60s) — keep the event loop live.
    draft, used_llm = await run_in_threadpool(llm_draft_context, eng.ctx, description, get_llm_client())
    ctx = eng.ctx
    return {
        "draft": draft,
        "used_llm": used_llm,
        "current": {
            "site": ctx.site.model_dump(),
            "stakeholders": [s.model_dump() for s in ctx.stakeholders],
            "success_criteria": list(ctx.success_criteria),
            "slos": [s.model_dump() for s in ctx.slos],
        },
        "field_guide": context_field_guide(ctx.is_industrial),
    }


@router.post("/api/engagements/{eid}/guided/plan")
async def goal_plan(eid: str, body: PlanRequest) -> dict:
    """Break a project goal into a per-phase task plan, persisted to
    ``ctx.assets["guided_plan"]``. Rule skeleton first; the LLM only
    rewrites task wording when available. Never touches gates/phases."""
    eng = _load(eid)
    goal = body.goal.strip()
    if not goal:
        raise HTTPException(status_code=422, detail="'goal' must not be blank") from None
    from ..llm import get_llm_client

    plan, used_llm = await run_in_threadpool(llm_goal_plan, eng.ctx, goal, get_llm_client())
    with engagement_lock(eid):
        eng = _load(eid)
        eng.ctx.assets["guided_plan"] = plan
        _save(eng)
    return {"plan": plan, "used_llm": used_llm, "saved": True}
