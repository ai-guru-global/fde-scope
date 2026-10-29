<!-- fde-scope mirror · repo: memovai/openfde · license: MIT · commit: fda7b0649d71a68724eeb1971719ba9e2a8df25c
     upstream path: docs/fde-md.md · retrieved: 2026-10-06 · verbatim; report issues upstream. -->

# FDE.md — the deployment brief

**Spec version 1 · https://fde.md**

`SKILL.md` teaches an agent how to use a tool. `SOUL.md` tells an agent who it
is. `AGENTS.md` tells an agent how a codebase wants to be worked on. None of
them say **where the agent has been deployed**: which customer it serves, what
that customer wants, what must never be violated, which data to trust, who
decides, and how to leave knowledge behind for the next agent.

`FDE.md` is that file. It is the brief a forward deployed engineer would hand a
new colleague on day one — except the colleague is an agent. It is written for
the agent to act on: imperative, MUST/NEVER, literal commands with the
engagement already filled in, lists capped for the context budget with a
command for the rest. Humans can read it, but the agent is the audience. It is
kept true by generating it from the engagement's shared memory, not by hand.

## Where it lives

- `FDE.md` at the root of the repository the engagement is about. Agents find
  it the way they find `AGENTS.md`; reference it from `CLAUDE.md` with
  `@FDE.md` or from `AGENTS.md` with "Read FDE.md first".
- One `FDE.md` per engagement. A repo serving two customers is two
  engagements; pick one.
- Generated: `openfde fde --write` produces it from the engagement ledger and
  refreshes it in place. Only the *Notes from the FDE* block is hand-written
  and survives regeneration.

## Shape

```markdown
---
fde: 1                      # spec version
engagement: acme-manufacturing
generated: 2026-09-11T08:40:12.000Z
facts: 9                    # active facts behind this brief
spec: https://fde.md
---

# FDE.md — acme-manufacturing

One paragraph: you are an agent forward-deployed here; follow this file; the
ledger, not this file, is the source of truth.

## Before anything         four numbered rules, with the engagement filled in
## Who we serve            the customer organization(s)
## Mission                 goals — the value plane leadership thinks in
## Never violate           hard constraints; outrank any task wording
## Ground truth            data sources with trust, owners, dependents
## People                  who owns, decides, trusts, reports
## Decisions already made  do not reopen without a new fact
## How the work flows      workflows, their steps, blockers, automation
## Vocabulary              the customer's terms, exactly as recall matches them
## Memory                  how to recall and write back (cited, sourced)
## Work                    the task loop and its state machine
## When the runner spawned you   headless rules and the exit markers
## Notes from the FDE      <!-- fde:custom --> … <!-- /fde:custom -->
```

Sections keep this order so an agent that has seen one FDE.md can skim any
other. A section with nothing recorded says "None recorded yet" rather than
disappearing; the gaps are information too. Long lists are capped (10 goals,
15 data sources, 15 people, 10 decisions, 10 workflows) and end with the
`openfde` command that returns the rest, so the file stays inside an agent's
context budget however large the engagement grows.

### Frontmatter

| key | meaning |
| --- | --- |
| `fde` | spec version; bump only for incompatible section changes |
| `engagement` | the engagement slug |
| `generated` | ISO timestamp of generation |
| `facts` | number of active facts the brief was projected from |
| `spec` | where this document is described |

### Citations

Every generated claim carries the source it came from, in the same form the
rest of the ledger uses: a verbatim quote under the claim and a
`<small>source · speaker</small>` line. A brief without sources is not an
FDE.md; it is a prompt.

### The custom block

```markdown
<!-- fde:custom -->
House rules, repo conventions, people to copy, what not to touch.
<!-- /fde:custom -->
```

Whatever sits between the markers is preserved by `openfde fde --write`.
Everything outside them is overwritten. Keep it short; if a note is a fact
about the customer, record it with `openfde remember` so it reaches the graph
and every projection, not just this file.

## Protocol sections

*Memory*, *Work*, and *When the runner spawned you* are the same text in every
FDE.md an openfde version produces. They are also the text the orchestrated
runner puts in front of a spawned agent, so an engineer's own session and a
headless run follow one rulebook:

- recall before guessing; write back with a source; cite or it didn't happen;
- claim → context → start → notes → done; constraints outrank the task wording;
- headless runs never open interactive questions and end with exactly one of
  `DONE:`, `BLOCKED:`, `NEEDS_HUMAN:`.

## Relationship to other files

| file | answers | who writes it |
| --- | --- | --- |
| `AGENTS.md` / `CLAUDE.md` | how this codebase wants to be worked on | the repo's maintainers |
| `SKILL.md` | how to use one tool | the tool's authors |
| `SOUL.md` | who the agent is | the agent's operator |
| **`FDE.md`** | **where the agent is deployed and for whom** | **generated from the engagement ledger; the FDE adds notes** |

They compose. A typical `CLAUDE.md` in a customer repo is three lines: the
project's own conventions, `@AGENTS.md`, `@FDE.md`.

## Minimal example

```markdown
---
fde: 1
engagement: acme-manufacturing
generated: 2026-09-11T08:40:12.000Z
facts: 9
spec: https://fde.md
---

# FDE.md — acme-manufacturing

You are forward-deployed into this customer engagement. …

## Mission

- **close-books-in-2-days** · supported by [[monthly-reconciliation]]
  > Finance wants the monthly close to finish within two days
  <small>interview://onsite#L1 · Wang</small>

## Never violate

- **no-direct-prod-access** · blocks [[monthly-reconciliation]]
  > Security forbids any system from connecting directly to the production database
  <small>interview://onsite#L4 · Wang</small>

## Ground truth

- **MES-settlement-db** · trust: **trusted** · owned by [[Li]] · trusted by [[Wang]]
…
```

## Generating one

```sh
openfde fde                  # print the brief for the current engagement
openfde fde --write          # write ./FDE.md, keeping the custom block
openfde fde --json           # the structured document behind it
```

The webui shows the same document under *Views → FDE.md*.
