# Module 2 — Lightweight Internal Experimentation Platform

Status: built and verified end to end (Phase 2a — priority module). Narrative pass (Pain Point ->
Reasoning -> Architecture -> Implementation -> Summary) still pending for Phase 4.

## Sub-modules

| Sub-module | Status |
|---|---|
| [feature_registry](feature_registry/) — player_features Gold table, single source of truth | Done |
| [registry](registry/) — DynamoDB experiment registry, CRUD API, Athena export | Done |
| [orchestration](orchestration/) — Step Functions lifecycle (assignment, SRM, monitoring, analysis, readout) | Done |
| [demo](demo/) — 2-3 concurrent experiments end to end (clean winner, guardrail auto-stop, SRM catch) | Done |
