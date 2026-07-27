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
| [data-foundation](data-foundation/) | No reliable single source of event truth across client sites | Done |
| [module1-anomaly-detection](module1-anomaly-detection/) | Silent retention/revenue drops and multi-account arbitrage go undetected | Not started |
| [module2-experimentation-platform](module2-experimentation-platform/) | No rigorous, guardrail-safe way to run product experiments | In progress |
| [module3-support-chatbot](module3-support-chatbot/) | Partner integration support is slow, repetitive, and inconsistent | Not started |

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
