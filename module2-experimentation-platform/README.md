# Module 2 — Lightweight Internal Experimentation Platform

Status: **operationally verified PoC** as of 2026-07-29. Product-recorded
exposures, exposure-based SRM, the allocation kill switch, wall-clock live
lifecycle, historical replay, and the central operations snapshot all passed
against the deployed AWS path.

Latest local increment (deployment pending): every new experiment requires a
business owner, the API records identity-derived `created_by`/`updated_by`,
and the central operations view exposes that responsibility alongside state
and monitoring health.

## Sub-modules

| Sub-module | Status |
|---|---|
| [feature_registry](feature_registry/) — player_features Gold table, shared feature source | Deployed PoC |
| [registry](registry/) — experiment registry, product exposure API, Athena exports | Operationally verified PoC |
| [orchestration](orchestration/) — replay/live lifecycle, SRM, monitoring, analysis, readout | Operationally verified PoC |
| [demo](demo/) — concurrent historical scenarios | AWS-path demo passed |
| [Central operations view](dashboard/) | Signed AWS snapshot passed; deterministic recording path documented |
