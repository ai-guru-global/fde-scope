---
version: 1
slug: "gtm-index-html"
primary_target: "GTM/index.html"
related_targets: []
---

# GTM board surface brief

Scope and mode: GTM/index.html, Persuade. The project's only marketing surface. Authored once in `GTM/index.bilingual.html`; `GTM/i18n_split.py` emits two monolingual artifacts, `GTM/index.html` (zh) and `GTM/en/index.html` (en). No bundler, no runtime dependencies.

Audience and job: FDE team leads evaluating a SOP engine; practicing FDEs wanting a workbench; OSS developers judging methodology; enterprise decision-makers needing compliance evidence. Job: believe "the full SOP, enforced" within seconds and take the role-appropriate action.

Action: primary pip install / Star on GitHub; secondary read SOP docs and factory walkthrough; enterprise lane reads the gate interlock panel and the ledger.

Proof: 4 zones / 18 phases / 10 executable gates (from fde_scope/engagement/phases.py); gate check semantics from README; two profiles with real connector/KPI sets; six engine-seeded demo engagements labeled DEMO DATA; zero-config install facts. No real testimonials, benchmarks, or contact channels: never fabricate.

Constraints: both languages legible; works offline (self-hosted woff2 in GTM/fonts/, platform CJK fallback); prefers-reduced-motion honored; WCAG AA contrast.

Chosen direction: Workbench (the repo's Carbon-derived enterprise workbench ramp — `fde_scope/web/layout.py` THEME_CSS, mirrored light-only here). The page is still the plant scheduling board: the profile switch re-renders board state per scenario, keys 1-0 jump to gates, and the signature motion is the three real keyframes — `set-in` slot-in, `rise`, and the `pulse` andon blink on a blocked gate.

Memorable moment: the blocked DEPLOY T-card with its red verdict "advance → REFUSED", and the profile switch that ghosts the industrial-only phases on ticket.

Unresolved: real enterprise contact channel when one exists; authorized customer case studies to replace the demo ledger.
