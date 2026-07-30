# Project Closeout and Intentional Boundaries

Status: **portfolio-complete / latest increment locally verified and deployment
pending** (2026-07-30).

The repository now demonstrates the four operating pains it was created for
without turning into an AWS service catalogue. "Portfolio-complete" means the
code, tests, infrastructure templates, cost controls, demos, and honest
boundaries are publishable. It does not mean production-ready, and it does not
authorise a new AWS deployment.

## What is implemented

| Module | Business result represented by the PoC |
|---|---|
| 1 — anomaly and arbitrage detection | Daily DAU/GGR and weekly mature-cohort retention checks are scheduled, explainable, and connected to the same investigation path; known-rule multi-account rings are surfaced as `REVIEW_REQUIRED` |
| 2 — experimentation operations | Concurrent experiments have a central registry/view with owner and IAM-derived provenance; live-exposure SRM, guardrail monitoring, and allocation stopping are automated |
| 3 — analytics assistant | Governed, allow-listed KPI questions and an on-demand `diagnose` path handle common first-look work; alerts reuse the same diagnostic evidence; unsupported work becomes a durable ticket |
| 4 — partner support | Identity-derived game-provider and client-operator audiences receive isolated corpora; ambiguity, escalation, leakage prevention, cost quota, and machine-rate throttling are code-owned |

The latest increment deliberately adds no fixed-price AWS service. It reuses
existing Lambdas, topics, tables, logs, and request-priced APIs. The detailed
cost shape is in
[`business-pain-implementation-plan.md`](business-pain-implementation-plan.md).

## What is not implemented

These are production boundaries, not missing portfolio claims:

| Boundary | Why it remains out | Adoption trigger |
|---|---|---|
| Live product ingestion and atomic lake publication | The repository uses deterministic synthetic data; a fake connector would not demonstrate a real source contract | A real source, schema owner, freshness SLO, replay policy, and data-processing agreement |
| Unknown-arbitrage novelty model | No reviewed labels, feature stability evidence, or acceptable false-positive threshold exists; claiming unknown-technique coverage would be false | Enough adjudicated cases for backtesting, explainable feature deviations, drift checks, and a review-capacity budget |
| Hosted multi-user experiment UI, SSO, and daily push digest | The localhost signed view solves the PoC visibility pain with no idle hosting charge | Multiple regular operators or measured missed-status incidents |
| Automated feature-lineage/duplicate-feature enforcement | The shared feature registry removes current duplication, but a generic grep rule would confuse legitimate player-grain analysis with duplicate features | A measurable duplicate-feature incident and an agreed ownership/lineage schema |
| Country- and player-level external analytics | Governed dimensions and external tenant claims do not exist; widening the query surface first would weaken isolation | Governed country/player views, catalog-level filters, external federation, privacy review, and aggregate-only response policy |
| Production partner federation, local-time rendering, conversation history, and CRM delivery | Account-local IAM roles prove fail-closed audience separation but are not a partner identity system | Named IdP/claim contract, partner profile/time-zone owner, retention policy, support system, and opt-in channel |
| Redshift, EMR/Spark, OpenSearch, MSK, a vector store, or provisioned BI | Current volume and latency do not justify their idle or operating cost | The measurable scale and latency thresholds in `ARCHITECTURE.md` are crossed |

## Final deployment gate

No deployment was performed during the closeout. If the latest branch is to be
deployed later:

1. Run the offline suite and `cdk synth`.
2. Run `python scripts/verify_paid_account_controls.py`.
3. Review the CDK diff for new hourly or provisioned resources.
4. Reconfirm the USD 5 budget and alert destination.
5. Deploy only the intended stacks, run their deterministic AWS-path demos,
   and inspect settled gross cost.

This distinction is intentional: a clean local closeout is safe to publish;
creating paid account resources requires a separate, explicit decision.
