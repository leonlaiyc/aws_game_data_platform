# Architecture

Status: stub — will be populated incrementally as each module is built, with a final polish pass in Phase 4.

Each module section below follows: Pain -> Reasoning -> Architecture -> Trade-offs -> Cost -> Scale-up path.

## data-foundation

See [data-foundation/README.md](data-foundation/README.md).

## Module 1 — Anomaly & Arbitrage Detection

TBD (Phase 2b).

## Module 2 — Experimentation Platform

TBD (Phase 2a). Must document two deliberate substitutions: SageMaker Feature Store -> lake-based
feature registry, and Amazon Q Business -> direct Bedrock (Nova Lite) report generation.

## Module 3 — Analytics NL Assistant *(repointed 2026-07-27, was "Support Chatbot")*

TBD (Phase 3). Semantic layer + parameterized Athena SQL templates (no free-form text-to-SQL),
grounded in `KPI_DEFINITIONS.md`; must document build-vs-buy against Amazon Quick with a
usage-volume cost crossover, and the templates-vs-text-to-SQL trade-off. The original
document-RAG/support-chatbot concept is dropped, not deferred — no vector store (S3 Vectors) is
needed for this design.

## Deliberately excluded services

- **Kinesis Data Streams** — not needed for the steady-state architecture; our SLA tolerance
  (minutes, not sub-second) is met by micro-batch ingestion straight to S3, at zero idle cost.
  **Exception**: Module 1 includes one short-lived, separately-stacked streaming path (explicit
  teardown after its demo) purely to demonstrate the capability — this doesn't change the
  steady-state batch default. Migration path if sub-second ingestion were ever a permanent need:
  swap the batch writer for a Kinesis producer + Firehose.
- **OpenSearch Serverless** — has an hourly OCU floor (~$175/month minimum) regardless of usage;
  S3 Vectors (GA Dec 2025) gives us Bedrock Knowledge Base support at near-zero idle cost instead.
- **Provisioned Redshift / EMR** — data volume (tens of MB) doesn't justify a provisioned cluster;
  Athena's per-query pricing ($5/TB scanned) costs fractions of a cent at this scale.
