# Aurora Games — B2B Game Data Platform (AWS SA Portfolio Project)

[![CI](https://github.com/leonlaiyc/aws_game_data_platform/actions/workflows/ci.yml/badge.svg)](https://github.com/leonlaiyc/aws_game_data_platform/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[**Open the bilingual interview demo →**](https://leonlaiyc.github.io/aws_game_data_platform/)

A simulation of acting as an AWS Solutions Architect for **Aurora Games**, a fictional B2B gaming
technology company serving multiple client sites. Built under a hard constraint that shaped every
design decision: **serverless-first with an explicit observability floor** — compute and data-plane
services scale down when nobody is using them; 13 CloudWatch alarms are the deliberate fixed idle
cost paid to know when the platform is broken.

The platform and its acceptance-hardening changes were deployed and exercised
against real AWS calls on 2026-07-29. This repository treats that evidence as
an operationally verified PoC, not as production workload experience. Where
something is not implemented, [ARCHITECTURE.md](ARCHITECTURE.md) names it as a
gap rather than omitting it.

*Fictional entities (games, client sites, player data) have no relation to any real company.*
No production credentials or customer/player data belong in this repository;
see [SECURITY.md](SECURITY.md).

---

## This is one system, not four demos

Follow a single real incident through it — the scripted `site_b` DAU drop the demos actually use.
Steps marked **[auto]** are wired together in code; steps marked **[human]** are where a person
decides something. The distinction matters, and blurring it is how architecture diagrams start
lying:

```
  site_b's DAU falls 55% on 2026-06-10
    │
 1. [auto]   Module 1's daily EWMA check flags it, publishes an SNS alert
    │
 2. [auto]   Module 3 is subscribed to that topic. It drills down before anyone
    │        asks: per-game GGR breakdown, 7-day baseline comparison, and a
    │        co-movement check ("DAU and GGR fell together - looks like a broad
    │        usage change, not a payout bug")
    │
 3. [human]  An analyst reads it and wants a follow-up: "what about retention?"
    │        They ask Module 3 directly instead of queueing behind an analyst
    │
 4. [human]  They form a hypothesis: "onboarding got too long"
    │        and register an experiment in Module 2
    │
 5. [auto]   Module 2 runs assignment -> SRM check -> guardrail monitoring ->
    │        analysis -> a readout whose every number is code-rendered
    │
 6. [human]  The business ships the winning variant
    │
    └──────▶ next month's gold_daily_kpi reflects it, and the loop closes
```

**The claim is not that data flows in a circle.** Steps 3, 4 and 6 are human judgement, and step 6
closes the loop through the product, not through a pipeline. What the platform automates is 1, 2
and 5 — the detection, the first-pass investigation, and the statistical rigour — which is exactly
the work that is repetitive, easy to skip under time pressure, and damaging when skipped.

Module 4 sits alongside rather than inside this loop: it absorbs inbound partner questions so that
the escalations reaching this team are the ones that actually need it.

Detection without investigation is just noise. Investigation without a way to validate a fix is
just opinion. See [`diagrams/`](diagrams/) for the rendered architecture diagrams.

### The thread that runs through all of it

Two principles applied consistently, not per-module:

**1. One definition of every metric.** `KPI_DEFINITIONS.md` governs the lake's Gold tables,
Module 3's semantic layer, and Module 2's experiment metrics. `FEATURES.md` does the same for
experiment features. A number in any output can be traced to the document that defines it.

**2. Code renders every number; the LLM only ever writes qualitative text.** Module 1's alerts,
Module 2's experiment readouts, and Module 3's answers all follow this. The model is never asked to
produce a figure, so it cannot invent one — the guarantee is structural, with automated grounding
checks as a secondary net rather than the primary defense.

---

## Modules

| Module | Pain point | Current maturity |
|---|---|---|
| [data-foundation](data-foundation/) | Multiple client sites and game providers, inconsistent metric definitions, and a hard data-isolation requirement need a governed platform, not just a lake | Deployed PoC; live ingestion and atomic publication remain |
| [module1-anomaly-detection](module1-anomaly-detection/) | Silent retention/revenue drops and multi-account arbitrage rings go undetected for weeks; batch-only monitoring misses same-hour incidents | Operationally verified PoC; explainable detector and publication-marker paths passed against AWS |
| [module2-experimentation-platform](module2-experimentation-platform/) | No central view of which concurrent experiments are live, which already tripped a guardrail, and which are on their third iteration | Operationally verified PoC; live exposure SRM, kill switch, historical lifecycle, and central view passed |
| [module3-analytics-assistant](module3-analytics-assistant/) | Analysts field cross-cut business questions no prebuilt dashboard answers, and every anomaly alert starts a drill-down from scratch | Operationally verified PoC; governed queries, durable tickets, first-look report, and delivery passed |
| [module4-partner-support-chatbot](module4-partner-support-chatbot/) | Integration engineers answer the same partner questions every week, and the questions that genuinely need an engineer queue behind the ones that don't | Operationally verified PoC; durable sessions, tickets, leakage controls, and notifications passed |

The latest cost-safe increment is locally verified and deployment-pending:
weekly mature retention detection, identity-derived experiment ownership,
on-demand “why did it drop?” diagnosis, and separate game-provider/client-
operator support corpora. See
[the business-pain implementation plan](docs/business-pain-implementation-plan.md)
for the exact scope, cost shape, and deliberately deferred boundaries.

Project-wide delivery constraints are explicit: the paid AWS account still
uses a [free-first cost policy](docs/project-constraints.md), player-risk
alerts must satisfy an explainability contract, and every finished capability
must have a deterministic operation-only demo. Recording checklists and
goal-fit review notes are maintained as local delivery documents rather than
published repository artifacts.

**Highlights worth reading the code for:**

- **Catalog-level tenant isolation** — Lake Formation row-level filters mean an analyst role is
  *physically unable* to read another client's rows — verified by assuming each role via STS and
  checking **both** directions: the Athena path returns only its own site, and a direct
  `GetObject` on the underlying Parquet is denied. Application-level filtering would be one
  forgotten `WHERE` clause from a leak.
- **Two independent signals required before flagging fraud** — device fan-out alone is a shared
  family computer; an abnormal cash-out ratio alone is a lucky winner. Only both together flag.
- **Caveats the model cannot skip** — Module 2 computes caveat flags deterministically in code and
  requires the readout to address every one. The model chooses phrasing, never whether to mention.
- **No free-form text-to-SQL** — Module 3's model picks from pre-approved SQL templates and fills
  whitelisted slots. Less capable by design; provably correct in exchange.
- **A real Guardrails false positive, documented** — `PROMPT_ATTACK` blocked 100% of requests until
  the system prompt was moved out of the user turn. See
  [module3's README](module3-analytics-assistant/README.md).
- **A leak the model actually attempted, caught by code** — told not to cite sources, it emitted an
  internal document ID anyway. A validator replaced the response before the partner saw it. The
  prompt asked; only the code enforced.
- **The same governance rule producing opposite behaviour** — Module 2 shows its citations because
  the reader is an internal analyst; Module 4 suppresses them because the reader is an external
  partner. Same philosophy, and the deciding variable is the audience.

---

## Region & cost

- Deployed in **ap-northeast-1 (Tokyo)**.
- **Steady-state gross list-price model is under $2/month**, dominated by 13 standard CloudWatch
  alarms (~$1.30/month before any free allocation), not compute. There is no always-on EC2, NAT
  Gateway, RDS, or provisioned cluster. An AWS Budgets notification fires at $5, forecast and
  actual.
- The one deliberate exception is Module 1's Kinesis streaming path, which has **no free tier and
  bills per shard-hour** (~$14/month if left running). It is excluded from the default CDK app
  behind a context flag, so `cdk deploy --all` cannot create it, and its demo script verifies
  teardown by listing streams directly rather than trusting the destroy exit code.
- **Cost Explorer snapshot on 2026-07-29: $0.1156 estimated gross usage** (fully offset by credits
  in this account). It is useful evidence, not a settled lifetime invoice; standard alarm charges
  can post later in the month. The largest line item in that snapshot was the Cost Explorer API at
  $0.04 — investigating the cost cost more than running the data plane.
- Full breakdown, verified unit prices, the Amazon Quick build-vs-buy analysis, and a 100x
  projection: [docs/cost-analysis.md](docs/cost-analysis.md). Operational responses:
  [docs/runbook.md](docs/runbook.md). Attack surface and service levels:
  [docs/threat-model.md](docs/threat-model.md).

---

## Project status and boundaries

The repository is **portfolio-complete**. The latest cost-safe increment is
locally verified and intentionally not deployed as part of closeout: deploying
to a paid account remains a separate decision behind the documented preflight.

The remaining items are explicit production boundaries, not hidden TODOs:
live ingestion, an evidence-backed unknown-arbitrage model, a hosted/SSO team
UI, external federation, governed country/player analytics, partner profiles
and CRM delivery, and scale-up services whose adoption thresholds have not
been crossed. See
[the project closeout](docs/project-closeout.md) for the exact list and
triggers, and [what I got wrong first](docs/what-i-got-wrong-first.md) for the
test-driven design corrections behind the final architecture.

---

## Running it

```bash
cd infra && cdk deploy --all
```

That deploys everything except the billable streaming stack, which needs
`-c enable_streaming=true` and should be run via
`module1-anomaly-detection/streaming/run_streaming_demo.sh` (deploy → demo → destroy → verify).

Then run the tests, which need no AWS account:

```bash
python -m pytest
```

Then the demos, each end-to-end against real deployed infrastructure and each exiting non-zero on
failure:

```bash
python data-foundation/governance/verify_isolation.py
```

```bash
python module1-anomaly-detection/demo/run_demo.py
```

```bash
python module2-experimentation-platform/demo/run_demo.py
```

```bash
python module3-analytics-assistant/demo/run_demo.py
```

```bash
python module4-partner-support-chatbot/demo/run_demo.py
```

The scripted scenarios (a site_b retention drop, a site_a six-account arbitrage ring) are baked
into the simulated data, so each demo asserts against known ground truth rather than just printing
output.

**Note:** newly created Glue tables need Lake Formation grants before a Lambda role can query them —
see [data-foundation/governance/README.md](data-foundation/governance/README.md). This trips
everyone once.

---

## Repo layout

```
infra/                              CDK app (Python) — all infrastructure as code
tests/                              pytest: CDK security assertions + unit tests, no AWS needed
.github/workflows/ci.yml            Compiles every Lambda handler, then runs the suite
site/                               Bilingual one-page interview demo, deployed by GitHub Pages
diagrams/                           Architecture diagrams (Mermaid, renders on GitHub)
docs/cost-analysis.md               Verified unit prices, observed estimate, 100x projection
docs/runbook.md                     What each alarm means and what to do about it
docs/threat-model.md                Who would attack this, whether it holds, and the SLOs
docs/project-closeout.md             Implemented scope, intentional boundaries, adoption triggers
docs/what-i-got-wrong-first.md       Five tests that changed the design

data-foundation/
  event_simulator/                  Synthetic B2B gaming event generator, with scripted scenarios
  lake/                             S3 Bronze/Silver/Gold, Glue Catalog DDL, example Athena queries
  KPI_DEFINITIONS.md                Single source of truth for GGR/DAU/ARPU/retention logic
  governance/                       Client isolation (Lake Formation row-level filters) + verifier

module1-anomaly-detection/
  data_anomaly/                     EWMA control-limit detection on DAU/GGR -> SNS
  arbitrage_detection/              Two-signal multi-account arbitrage detection
  streaming/                        Short-lived Kinesis real-time path (deploy / demo / destroy)
  demo/                             Both batch detectors against scripted ground truth

module2-experimentation-platform/
  registry/                         DynamoDB experiment registry + CRUD API
  orchestration/                    Step Functions: assignment -> SRM -> monitoring -> analysis -> readout
  feature_registry/                 gold_player_features + FEATURES.md
  demo/                             3 concurrent experiments: clean winner, guardrail stop, SRM violation

module3-analytics-assistant/
  semantic_layer/                   Pre-approved parameterized Athena SQL templates
  lambda/ask_answer/                Capability A — NL Q&A, six deterministic outcomes
  lambda/first_look_report/         Capability B — alert-triggered drill-down report
  demo/                             All six outcomes + a real alert-triggered report

module4-partner-support-chatbot/
  lambda/chat/knowledge_base/       In-context corpus (no vector store, by design)
  lambda/chat/prompts/              Versioned prompt + all code-owned fixed copy
  lambda/chat/config.py             Every classifier threshold, with its rationale
  demo/                             All four fallback categories + the leakage guard
```

---

## Prerequisites

- AWS account with CLI credentials configured (`aws configure`).
- `cdk bootstrap` run once per account/region.
- A billing alarm (this project's target: alert above $5/month).
- Bedrock access to **Amazon Nova Lite** in ap-northeast-1 (auto-enabled on first invocation as of
  2026 — no manual model-access step). No embedding model is needed; there is no vector store
  anywhere in this project, by design.
- A registered Lake Formation Data Lake Administrator. This **cannot** be done from CDK — the
  bootstrap execution role isn't an admin — so it runs as a boto3 script with the account's own
  credentials.

## Teardown

```bash
cd infra && cdk destroy --all
```

Then verify by listing resources directly rather than trusting the command's exit code — a stack
deletion that silently fails leaves a meter running. Module READMEs list any non-CDK cleanup (e.g.
Athena query result objects in S3).
