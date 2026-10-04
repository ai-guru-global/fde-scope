# FDE Scope · Level 1 — English Quickstart

> **This is a quickstart, not a translation.** The lesson bodies of this course are
> written in Chinese and stay in Chinese — that is a deliberate, budgeted decision,
> not an oversight. See [§1](#1-language-policy) for exactly what is English and
> what is not, and [§7](#7-what-is-still-missing) for the honest gap list.

Level 1 is an 8-day, hands-on course that takes someone who has never been on a
client site and walks them through one complete FDE delivery chain — producing
**8 portfolio artifacts** and **8 gate checks (G1–G8)** along the way.

- **Total effort**: ~22 hours (Day 1 is a full 6-hour day; days 2–8 are ~2.25 h each)
- **Prerequisites**: install software, copy-paste terminal commands, read a table.
  No Python required. Every command ships in a copyable form.
- **Cost to start**: ¥0 — the reading room, the toolchain and the self-study path are
  permanently free. See [§5](#5-what-it-costs-l0l3).

---

## 1. Language policy

| Surface | Language | Notes |
|---|---|---|
| `/course` (web reading room) | Chinese | All lesson bodies |
| `/en/course` (web reading room) | English **chrome** + Chinese bodies | Navigation, titles, rail labels and UI strings are translated; the lessons carry `lang="zh-Hans"` so browsers and screen readers segment correctly |
| `course-level-1/` chapters (`00`–`15`) | Chinese | The source of truth; the web reader renders these files |
| This file (`en/README.md`) | English | Quickstart + orientation only |
| `examples/README.md`, CLI `--help` | English | Code-facing surfaces |
| Repo root `README.md`, `docs/features-en.md` | English | Platform-facing docs |

**Why the lessons are not translated.** Translating a whole chapter set into
English is a real one-off cost with an ongoing maintenance tail: every time a
gate changes, two texts drift apart. A quickstart is cheap to keep true, and it
answers the question an English-speaking reader actually arrives with — *what is
this, can I run it, and what do I get*. Detailed pedagogy stays in one place, in
one language, with a single owner.

---

## 2. The 8-day arc

Day 1 builds the worldview and a first working chain. Days 2–8 each end with one
gate and one artifact you can show a manager or a client.

| Day | Focus | Gate | Artifact you walk away with |
|---|---|---|---|
| D1 | Worldview + toolchain; run a miniature end-to-end chain | **G1** smoke | Artifact 1 · Mini-chain evidence + the one-page FDE worldview |
| D2 | Define the boundary — who is the client, what does success mean | **G2** boundary | Artifact 2 · Engagement Charter (profile / stakeholder map / success criteria) |
| D3 | Connect to data and profile it | **G3** data | Artifact 3 · Data health report (fields / missing / PII / distributions) |
| D4 | Forge a corpus from the raw sample | **G4** corpus | Artifact 4 · CorpusReport + a client-facing explanation with no jargon in it |
| D5 | Validate — build an eval set, find the bad cases | **G5** evidence | Artifact 5 · Demonstrable prototype + eval results + 3 bad cases |
| D6 | Make it operable | **G6** ops | Artifact 6 · Runbook + SLO card + on-call handover card |
| D7 | Hand it over and distil the reusable skill | **G7** handoff | Artifact 7 · Handoff package + 1 distilled skill |
| D8 | Portfolio + defence | **G8** graduation | Artifact 8 · Portfolio in three packagings (job search / internal report / freelance) |

There is also an entry gate, **G0**, taken before class: environment self-check
passes, the learning contract is read, and the self-assessment radar is filled in.

### How gates actually behave

- **`blocker` vs `warning`.** A blocker gate stops you — you do not advance until it
  passes. A warning gate can be passed with the miss recorded, and it costs you score.
- **Resubmission.** You get one resubmission within 24 hours at full credit.
  Later than that it is a *deferred pass* (延期通过) and the artifact is capped at grade B.
- **Waivers are recorded**, in the certificate notes. Nothing is silently granted.
- **G8 requires at least 6 of G1–G7 to have passed**, a complete 8-artifact index,
  and a live defence — where the question you will be asked is *"where is the evidence?"*

Gate semantics in full: [`03` Evaluation & gate checks](../03-评估体系与通关门禁.md) §3.
Per-gate student self-check card: [`06` Student handbook](../06-学员手册与作业包.md) §6.

---

## 3. Run it now (no API key needed)

The whole chain runs offline. The LLM step is optional and only ever an accelerator.

```bash
git clone https://github.com/ai-guru-global/fde-scope.git
cd fde-scope
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 1. Connect — profile a sample CSV
fde-scope connect --type csv --source examples/quickstart_csv/sample_tickets.csv

# 2. Forge a corpus and get an auditable HTML report
fde-scope corpus --input examples/quickstart_csv/sample_tickets.csv \
                 --out reports/corpus_report.html

# 3. Read the course in a browser
fde-scope web          # http://127.0.0.1:8080/course  and  /en/course
```

`fde-scope web` binds loopback only. Binding elsewhere is refused unless you set
`FDE_SCOPE_ALLOW_REMOTE=1` — the local workbench has no authentication by design,
so exposing it would expose your engagements and journals to the network.

**Optional, and only optional.** Adding `--llm` to `corpus` synthesizes gap-filling
samples with MiMo; it reads `FDE_SCOPE_MIMO_API_KEY` **from the environment**. Keys
are never written to manifests, reports, engagement JSON, logs or screenshots. If
you have no key, skip the flag — you lose a convenience, not a capability.

**Don't want a terminal at all?** That is supported. The course stacks a process
and gate layer on top of whatever coding or office agent you already use; it does
not require you to switch tools or to live in a shell. See
[`01` Course design](../01-课程设计说明书.md) §6.4 and
[`11` Tooling & environment](../11-工具与环境准备.md) for the no-key degraded paths.

More on the zero-dependency path: [`examples/README.md`](../../examples/README.md).

---

## 4. Honesty boundary

These five statements are load-bearing. They are repeated on the sales page, in
class and at the closing session, so that nothing you were promised at purchase
gets softened later:

1. **No employment promise, no income promise.** "变现" in this course means
   *turning capability into artifacts you can show and hand to a client* — a
   portfolio, a set of talking points, one chain you ran yourself. It does not
   mean a raise, a job, or freelance revenue.
2. **Every client case is fictional.** The cases (茶语万象, 迅捷出行, 南湾汽车, …)
   are demo data. They are not real companies, and the course requires you to
   label adapted cases as demonstrations.
3. **The certificate proves in-course completion only.** It says what you did
   inside the course, nothing about the market. Grade A includes a
   **表现信** — a factual statement of what you wrote, where the evidence is, and
   how you performed. It is **not** a referral and implies no interview.
4. **AI assistance must be declared.** Using an assistant is allowed and expected.
   Not saying so is what fails you on the honesty axis.
5. **No real client name, and no PII, anywhere** — not in the repo, not in the
   class group, not in any third-party tool.

Full statement: [`README.md`](../README.md) 诚实边界 ·
certificate scope: [`03`](../03-评估体系与通关门禁.md) §6 ·
marketing discipline: [`08` Operations](../08-运营手册.md) §11.

---

## 5. What it costs (L0–L3)

Four tiers. Three of them are priced per cohort by a published formula; one of
them is genuinely free and is not a trial.

| Tier | What it is | Includes | Excludes | Price |
|---|---|---|---|---|
| **L0** Public | The open subset of the self-study edition | All lesson text in the web reading room, the toolchain, the self-study path | Live classes, marking, defence and grading, certificate, Q&A windows | **¥0, permanently free.** No quota, no signup |
| **L1** Standard | The default product | 8 days live + teaching assistants at 1:15–20 + daily gates + defence and grading + certificate + closing pack | Shadow project, real client scenarios, invoiced billing | Break-even ÷ (1 − target margin), computed per cohort |
| **L2** Shadow project | L1 plus supervised real work | Everything in L1 + admission to a real small scenario + mentor at ≤1:3 + double-signed de-identified output | Guaranteed client adoption, guaranteed employment or income, a seat in the next cohort | L1 + mentor hours + compliance and de-identification labour |
| **L3** Corporate | Private training | 3 concentrated days + 1 week of homework + client's de-identified scenario + assessment alignment + invoicing | Seats in public cohorts, individual discounts | Per-project: day rate × headcount + hours for custom cases |

Tier definitions in full, including the cost formula and the read-this-table
discipline: [`04` Delivery handbook](../04-交付实施手册.md) §1.2.
Why L0 can be free forever: the marginal cost of one more reader is zero.

---

## 6. Where things live

| You want | Read |
|---|---|
| The history, principles and economics behind FDE | [`00` Methodology, history, principles](../00-FDE方法论历史与原理.md) |
| What the course teaches and why it is designed this way | [`01` Course design](../01-课程设计说明书.md) |
| The day-by-day schedule | [`02` Daily syllabus](../02-逐日教学大纲.md) |
| Gates, rubrics, portfolio grades, certificate rules | [`03` Evaluation & gates](../03-评估体系与通关门禁.md) |
| Pricing, scheduling, staffing, contingency, delivery acceptance | [`04` Delivery handbook](../04-交付实施手册.md) |
| Student task cards and self-check lists | [`06` Student handbook](../06-学员手册与作业包.md) |
| The 5 fictional client cases and role-play scripts | [`07` Scenarios & cases](../07-实战剧本与案例库.md) |
| Environment setup and the no-key degraded paths | [`11` Tooling & environment](../11-工具与环境准备.md) |
| Glossary and every copyable template | [`12` Glossary & templates](../12-附录-术语表与模板库.md) |
| Competitor comparison and the go-to-market page | [`13` GTM page & competitor comparison](../13-GTM页面与竞品对比.md) |
| Continuing on your own after day 8; the shadow-project track | [`14` Post-course depth & shadow projects](../14-课后纵深与影子项目.md) |
| Certification, third-party paths, results measurement | [`15` Credibility & results measurement](../15-公信力与结果度量.md) |
| The platform this course is built around | [`fde-scope` repo README](../../README.md) · [`docs/features-en.md`](../../docs/features-en.md) |

The lesson files are Chinese-named; the link text above is the gloss, the link
target is the real file.

---

## 7. What is still missing

Stated plainly, because a quickstart that oversells itself is the first
credibility failure:

- **No translated lesson bodies.** This page orients you and gets you running; it
  does not teach the 8 days. If you need to *take* the course, the lessons are
  Chinese — that is a budgeted decision, described in [§1](#1-language-policy),
  not a gap waiting to close by itself.
- **In-class deliverables are Chinese-first.** The 8 artifacts, the 5 fictional
  case companies and the client-facing talking-point scripts are all written in
  Chinese. If the client you have in mind briefs in English, the scripts need
  adapting; the course does not ship an English script bank.
- **`/en/course` is verified for chrome, not for teaching.** Its test asserts the
  navigation and titles are translated and that the page declares the lesson text
  as Chinese. Nothing asserts an English *pedagogy* exists — because it doesn't.

Already bilingual, for the record — `/en/glossary` carries all 82 terms with
English definitions, and `/en/certification` is fully paired. The vocabulary of
the domain is not gated behind Chinese; only the 8-day teaching is.

If any of these blocks you, say so in an issue — the gap list is reviewed per
cohort, and demand is what moves it.
