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

## Module 3 — Support Chatbot

TBD (Phase 3).

## Deliberately excluded services

- **Kinesis Data Streams** — not needed; our SLA tolerance (minutes, not sub-second) is met by
  micro-batch ingestion straight to S3, at zero idle cost. Migration path: swap the batch writer for
  a Kinesis producer + Firehose when sub-second ingestion is required.
- **OpenSearch Serverless** — has an hourly OCU floor (~$175/month minimum) regardless of usage;
  S3 Vectors (GA Dec 2025) gives us Bedrock Knowledge Base support at near-zero idle cost instead.
- **Provisioned Redshift / EMR** — data volume (tens of MB) doesn't justify a provisioned cluster;
  Athena's per-query pricing ($5/TB scanned) costs fractions of a cent at this scale.
