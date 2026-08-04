# Examples

## quickstart_csv — CSV cold start

The most common FDE first-day scenario: the customer hands you a CSV export and
nothing else. This example walks the full 5-step FDE workflow against a tiny
20-row sample.

### Run it

```bash
# 1. install (core layer only — no agentscope, no docker, no API key)
pip install -e ".[dev]"

# 2. connect — preview the schema + sample
fde-scope connect --type csv --source examples/quickstart_csv/sample_tickets.csv

# 3. forge — turn raw rows into an auditable corpus report
fde-scope corpus \
  --input examples/quickstart_csv/sample_tickets.csv \
  --config fde_scope/templates/corpus_config.yaml \
  --out reports/corpus_report.html

# 4. deploy — assemble a tenant agent (dry-run; no docker needed)
fde-scope deploy --tenant client_a --dry-run

# 5. eval — benchmark a (mock) agent over an eval set
fde-scope eval --agent mock --test-set <path-to-eval.jsonl>

# 6. flywheel — replay sample concept events into the data flywheel
fde-scope flywheel --agent client_a --events <path-to-events.json>
```

Open `reports/corpus_report.html` to see the auditable deliverable: real vs
synthetic counts, coverage gaps, PII masked, and the train/eval/test split.

### What this proves

- The **core data layer** (connect / corpus / eval) runs with **zero** external
  dependencies — no LLM, no Docker, no AgentScope.
- The Corpus Engine is genuinely functional in rule-based v0: PII scrubbing,
  dedup, quality gate, coverage-gap detection, and targeted synthesis all
  produce real output.
- The **runtime layer** (deploy / flywheel) is assembled against the *real*
  AgentScope 2.0 API — see `docs/agentscope_api_mapping.md`.
