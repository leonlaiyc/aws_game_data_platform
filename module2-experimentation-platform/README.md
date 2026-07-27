# Module 2 — Lightweight Internal Experimentation Platform

Status: in progress (Phase 2a — priority module). Will follow Pain Point -> Reasoning ->
Architecture -> Implementation -> Summary once all sub-modules are complete.

## Sub-modules

| Sub-module | Status |
|---|---|
| [feature_registry](feature_registry/) — player_features Gold table, single source of truth | Done |
| [registry](registry/) — DynamoDB experiment registry, CRUD API, Athena export | Done |
| [orchestration](orchestration/) — Step Functions lifecycle (assignment, SRM, monitoring, analysis, readout) | Done |
| demo — 2-3 concurrent experiments end to end | Not started |
