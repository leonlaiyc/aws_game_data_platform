# Aurora Games — B2B Game Data Platform (AWS SA Portfolio Project)

> Status: Phase 1 (data foundation) complete. This README is a working stub and will get its final narrative pass in Phase 4.

## What this is

A simulation of acting as an AWS Solutions Architect for **Aurora Games**, a fictional B2B gaming technology
company. The project solves three real-world pain points on AWS, under strict startup cost constraints
(serverless-first, near-zero idle cost).

Fictional entities (games, client sites, player data) have no relation to any real company.

## Modules

| Module | Pain point | Status |
|---|---|---|
| [data-foundation](data-foundation/) | Multiple client sites/game providers, inconsistent metric definitions, and a data-isolation requirement need a governed platform, not just a lake | Done |
| [module1-anomaly-detection](module1-anomaly-detection/) | Silent retention/revenue drops and multi-account arbitrage go undetected; batch-only monitoring misses same-hour incidents | Not started |
| [module2-experimentation-platform](module2-experimentation-platform/) | No rigorous, guardrail-safe way to run product experiments | Done |
| module3-analytics-assistant *(was: support chatbot — repointed, see [[direction pivot]] note below)* | Execs/analysts ask cross-cut business questions no prebuilt dashboard answers, and every one interrupts an analyst for 20-40 minutes | Not started |

> **Direction note (2026-07-27):** Module 3 was repointed from a partner-support RAG chatbot to an
> NL analytics assistant (semantic layer + templated SQL, grounded, with a build-vs-buy analysis
> against Amazon Quick) to better match a Sr. Analytics Specialist SA target role. Module 1 gained
> a short-lived, cost-controlled streaming path alongside its batch detection. Full narrative
> rewrite lands in Phase 4; this line is a placeholder so the table doesn't mislead in the meantime.

## Region & cost

- Deployed in **ap-northeast-1 (Tokyo)**.
- Fully serverless (no Kinesis Data Streams, no OpenSearch Serverless, no provisioned Redshift/EMR) —
  idle cost is near $0. See [docs/cost-analysis.md](docs/cost-analysis.md) (populated in Phase 4).
- See [ARCHITECTURE.md](ARCHITECTURE.md) for per-module design rationale.

## Prerequisites (handled by the project owner, not automated here)

- AWS account with an IAM user/credentials configured for CLI (`aws configure`).
- `cdk bootstrap` run once per account/region.
- A billing alarm (this project's target: alert above $5/month).
- Bedrock access to Amazon Nova Lite and Titan Text Embeddings V2 in ap-northeast-1 (auto-enabled on
  first invocation as of 2026 — no manual model-access step needed).

## Repo layout

```
infra/                              CDK app (Python) — all infrastructure as code
data-foundation/
  event_simulator/                  Synthetic B2B gaming event generator
  lake/                             S3 Bronze/Silver/Gold layout, Glue Catalog DDL, example Athena queries
  KPI_DEFINITIONS.md                Single source of truth for GGR/DAU/ARPU/retention calculation logic
  governance/                       Client-data-isolation demo (Lake Formation row-level filters)
module1-anomaly-detection/
  data_anomaly/                     EWMA-based retention/revenue anomaly detection -> SNS
  arbitrage_detection/              Rule-based multi-account / abnormal deposit-withdraw detection
  demo/                             Scripted anomaly scenario, runnable end to end
module2-experimentation-platform/   Lightweight internal experimentation platform (priority module)
  registry/                        DynamoDB experiment registry + CRUD API
  orchestration/                   Step Functions lifecycle: assignment -> SRM check -> monitoring -> analysis -> readout
  feature_registry/                Gold-layer player_features table, single source of truth for analysis
  demo/                            2-3 concurrent experiments incl. auto-stop and clean winner
module3-support-chatbot/
  knowledge_base/                  Fictional integration guides, FAQ, maintenance calendar, release notes
  rag/                             Bedrock Knowledge Base (S3 Vectors) + Guardrails
  api/                             Chat endpoint (API Gateway + Lambda)
  demo/                            Preset conversations incl. a Guardrails-blocked attempt
docs/
  cost-analysis.md                 Observed monthly cost per module + scale-up cost projection
```

## Teardown

Every module is destroyable via `cdk destroy` from `infra/`. See each module's README for any
non-CDK cleanup steps (e.g., Athena query result objects, Bedrock Knowledge Base ingestion jobs).
