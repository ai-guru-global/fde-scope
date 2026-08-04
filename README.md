# FDE Scope

> **The complete on-site operating system for a Forward Deployed Engineer.**
> From first gemba walk to signed-off handoff — across software/SaaS *and*
> embodied-robotics / manufacturing. Built on [AgentScope 2.0](https://github.com/agentscope-ai/agentscope).

FDE is 2026's hottest AI role (OpenAI, Anthropic, Google, Palantir all build FDE
teams; listings up ~7× YoY). But every FDE shows up to a customer site and
rebuilds the same workflow from scratch — and most teams only model the "build"
half, skipping the pre-engagement, operationalization, and handoff zones that
actually decide whether the engagement produces value.

**FDE Scope codifies the *full* FDE standard operating procedure** — 4 zones,
18 phases — into an executable, gate-enforced state machine, with a parallel
**industrial overlay** (FAT/SAT, functional safety, CE/EU-AI-Act, works council,
air-gap, shift handover) for manufacturing/robotics deployments.

```
Zone A · Pre-engagement  →  Zone B · Build  →  Zone C · Operationalization  →  Zone D · Handoff
 qualification               connect             slo / on-call                   ops handoff
 site survey (🏭)            corpus              runbook                         knowledge transfer
 stakeholder map             prototype-real       monitoring / drift              disengage (signed off)
 success criteria            deploy (🏭 FAT/SAT)  change-mgmt (🏭 works council)
                             eval                flywheel → productize
```

It is **not** an agent application — it's an FDE's workbench: a CLI, a Web UI,
and a Python library that turns the SOP from a checklist into enforced engineering.

---

## ✨ What makes it different

1. **Full SOP, not just "5 steps".** The naive connect→corpus→deploy→eval→flywheel
   model covers only the Build zone. FDE Scope adds the 4 pre-engagement phases,
   5 operationalization phases, and 3 handoff phases that most teams skip — and
   enforces them with phase gates. See [`docs/fde_sop_full.md`](docs/fde_sop_full.md).
2. **A real industrial overlay.** Manufacturing/robotics engagements hit gates
   that SaaS never does: FAT/SAT acceptance, functional safety
   (ISO 13849 / IEC 61508 / ISO 10218), CE/EU-AI-Act conformity, German works-council
   co-determination (BetrVG §87), air-gapped deployment, shift handover. Each is
   an executable `Gate.check()` — it blocks advancement when blockers are present.
3. **Scenario profiles.** `ticket` (customer service) and `manufacturing`
   (embodied-robotics factory) share one engine but differ in connectors, KPIs,
   and which gates apply. Manufacturing reports real production KPIs: OEE, MTBF/
   MTTR, FPY/DPMO, grasp success rate, collision/intervention rate.
4. **Built on real AgentScope 2.0.** The runtime layer maps to the *actual* 2.0.5
   API — not the fictional `HarnessAgent`/`SequentialPipeline`/`EventSystem.on`
   that appear in many design docs. See
   [`docs/agentscope_api_mapping.md`](docs/agentscope_api_mapping.md).
5. **Zero-config runnable.** The core data + engagement layers have **no**
   AgentScope dependency — no LLM key, no Docker. `pip install -e ".[dev]"` and
   `pytest` is green. The Web UI is one extra.

---

## 🚀 Quick start

```bash
# install (core + dev + web; no agentscope/docker/api-key needed)
pip install -e ".[dev]"

# ── Scenario 1: customer-service tickets (the original) ──
fde-scope connect --type csv --source examples/quickstart_csv/sample_tickets.csv
fde-scope corpus --input examples/quickstart_csv/sample_tickets.csv --out reports/corpus_report.html

# ── Scenario 2: embodied-robotics factory (the new one) ──
fde-scope profiles                                    # see ticket + manufacturing
fde-scope engage init --customer "BMW Spartanburg" --profile manufacturing
fde-scope kpi <engagement-id> --samples examples/quickstart_manufacturing/station_samples.jsonl
fde-scope gate list --profile manufacturing           # 10 gates, 6 industrial-only

# ── Walk the full 18-phase SOP with gate enforcement ──
fde-scope engage advance <id>          # gate fails → refuses, shows blockers
fde-scope engage status <id>           # phase / zone / gate state / progress
fde-scope handoff <id> --accept        # Zone D: assemble the handoff package

# ── Or do it all in the browser ──
fde-scope web                          # → http://127.0.0.1:8080
```

### Web UI

```bash
pip install -e ".[web]"
fde-scope web
```

A single-page engagement console: create engagements, advance through the 18-phase
SOP (gates block in red when unmet), inspect every gate's blockers/warnings,
upload a CSV to forge a corpus and view the HTML report, and compute profile-specific
KPIs. All interactive, backed by JSON APIs.

---

## 🏗 Architecture

| Layer | Module | Role | agentscope? |
|---|---|---|---|
| **SOP** | `engagement/` | 18-phase state machine + 10 enforceable gates + handoff | ❌ |
| **Profiles** | `profiles/` | Scenario selector (ticket / manufacturing) | ❌ |
| 1 | `connectors/` | CSV★, Zammad, Salesforce, MySQL + OPC UA, MQTT-Sparkplug, ROS2, MES, Historian | ❌ |
| 2 | `corpus/` | PII scrub, dedup, quality gate, coverage, synthesis, report | ❌ |
| 3 | `deploy/` | DockerWorkspace + PermissionEngine + KnowledgeBase assembly | ✅ lazy |
| 4 | `eval/` | Ticket metrics + manufacturing KPIs (OEE/MTBF/FPY/…) + bad-case miner | ❌ |
| 5 | `flywheel/` | Concept→real event mapping + collectors + retrain scheduler | ✅ lazy |
| **Web** | `web/` | FastAPI engagement console | ❌ |

See [`docs/architecture.md`](docs/architecture.md) and
[`docs/fde_sop_full.md`](docs/fde_sop_full.md).

---

## 🧪 Tests

```bash
pip install -e ".[dev]"
pytest            # 91+ passed — core + engagement + gates + web, no agentscope needed
```

---

## 📦 Installation

```bash
pip install -e "."                 # core only
pip install -e ".[dev]"            # + pytest + web test client
pip install -e ".[web]"            # + FastAPI/uvicorn console
pip install -e ".[agentscope]"    # + real AgentScope 2.0 runtime layer
pip install -e ".[full]"           # everything
```

---

## 📄 Documentation

- [`docs/fde_sop_full.md`](docs/fde_sop_full.md) — the 18-phase SOP, 12 anti-patterns, sources
- [`docs/manufacturing_scenario.md`](docs/manufacturing_scenario.md) — embodied-robotics factory end-to-end walkthrough
- [`docs/architecture.md`](docs/architecture.md) — layered design + data flow
- [`docs/agentscope_api_mapping.md`](docs/agentscope_api_mapping.md) — design-doc fiction vs. real 2.0.5 API
- [`docs/fde_playbook.md`](docs/fde_playbook.md) — on-site 72h playbook

---

## 🗺 Roadmap

- [ ] Real industrial protocol I/O (OPC UA via asyncua, MQTT via paho-mqtt, rosbag2 via rosbags)
- [ ] Real LLM corpus synthesis & quality scoring (drop-in behind existing signatures)
- [ ] Real AgentScope agent startup (Docker workspace + model wiring)
- [ ] Full Zammad / Salesforce / MES / Historian HTTP/SQL implementations
- [ ] AgentScope Studio (npm `@agentscope/studio`) integration
- [ ] Category-stratified train/eval/test split

---

## 📄 License

MIT.
