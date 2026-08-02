# Data Foundation

## Pain Point

Aurora Games isn't one game — it's a B2B platform serving **multiple client sites** (independent
operators, each embedding our games) across **multiple game providers**, in **different regions
and currencies**. That combination creates three concrete problems a modern data platform has to
solve, not just a lake:

1. **Inconsistent data, one source of truth needed.** Every client site and every game emits
   events through the same pipeline, but "DAU", "ARPU", and "retention" mean nothing unless
   everyone — dashboards, analysts, an executive glancing at a report — agrees on exactly how
   they're computed. Two teams computing "ARPU" differently isn't a data quality bug, it's a
   definitions bug, and it erodes trust in every number after the first mismatch is discovered.
2. **Clients must only ever see their own data.** Client sites are separate business customers.
   A dashboard or ad hoc query must never be able to surface one client's numbers to another —
   and that boundary can't depend on every future SQL query happening to include the right
   `WHERE` clause.
3. **Self-service, not a queue behind an analyst.** As more sites and games onboard, "email the
   data team and wait" doesn't scale. The platform needs to make standard metrics queryable
   without an analyst rewriting the same aggregation for the fifth client.

This module — the shared Bronze/Silver/Gold lake every other module reads from — is the
foundation for solving all three, with two concrete artifacts on top of the pipeline itself:

- **[`KPI_DEFINITIONS.md`](KPI_DEFINITIONS.md)** — the single source of truth for what GGR, DAU,
  ARPU, and D1/D7 retention mean, with explicit calculation logic and caveats. Same governance
  philosophy as Module 2's `feature_registry/FEATURES.md`, one layer up (business metrics, not
  player-level features) — see that file for how the two relate.
- **[`governance/`](governance/)** — a working demonstration that one client site can only query
  its own rows, enforced by an AWS Lake Formation row-level filter, not by application code that
  a future bug could omit.

## Pipeline

```
event_simulator/  --(local JSONL)-->  S3 bronze/  --(Athena CTAS)-->  S3 silver/  --(Athena CTAS)-->  S3 gold/
                                       (JSON, gzip)                   (Parquet)                       (Parquet)
```

1. **`event_simulator/`** generates synthetic B2B gaming events (funnel, sessions, bets,
   deposits/withdrawals, bonuses, registrations) for a fictional platform ("Aurora Games"),
   including two scripted scenarios with known ground truth written to `scenario_manifest.json`:
   - a one-week retention/revenue drop on `site_b`
   - a 6-account arbitrage ring sharing device/IP fingerprints on `site_a`
2. **Bronze** (`s3://<bucket>/bronze/dt=YYYY-MM-DD/events.jsonl.gz`): raw events, one JSON object
   per line, gzip-compressed, Hive-style date partitions. Table uses **partition projection**
   (see `lake/ddl/01_bronze_events.sql`) so Athena computes valid partitions from a date range
   instead of requiring `MSCK REPAIR TABLE` or per-day `ADD PARTITION` calls.
3. **Silver** (`s3://<bucket>/silver/events/`): same grain as Bronze, but Parquet/Snappy, with
   `event_ts` parsed to a real timestamp and FX converted to USD **once** (`bet_amount_usd`,
   `win_amount_usd`, `amount_usd`) so every downstream query reuses it instead of re-deriving it.
4. **Gold**: purpose-built aggregate tables. The small daily and cohort summaries are not
   partitioned; the larger hourly actor-level table is partitioned by `dt` so scheduled checks
   can prune old data. Column-by-column definitions live in `KPI_DEFINITIONS.md`, not repeated here:
   - `gold_daily_kpi` — dt x client_site_id grain: DAU, sessions, new players, GGR, deposits,
     withdrawals, ARPU (all USD). Also the table `governance/`'s client-isolation demo filters.
   - `gold_cohort_retention` — registration_date x client_site_id grain: D1/D7 retention.
   - `gold_hourly_kpi` — event_hour x client_site_id x game_id x player_id grain: hourly sessions
     and normalized value metrics used by exposure-aware live experiment guardrails.

## Running it

```bash
# 1. Generate events (writes under event_simulator/output/, gitignored)
py -m event_simulator.cli

# 2. Deploy the lake infra (from infra/, once)
cd ../infra && cdk deploy

# 3. Upload bronze, build silver/gold, run example queries
cd ../data-foundation && ./.venv/Scripts/python.exe lake/build_lake.py
```

`build_lake.py` is idempotent: it clears the previous Silver/Gold S3 output before rebuilding, so
re-running after a simulator change or scenario tweak just works.

## Example queries (`lake/queries/`)

- `dau_and_ggr_by_site.sql` — daily KPIs, most recent days first.
- `retention_drop_check.sql` — D1/D7 retention by cohort for `site_b`.
- `arbitrage_ring_check.sql` — devices shared across an abnormal number of distinct players.

### A note on signal strength

Querying `gold_daily_kpi` for `site_b` around the drop window shows DAU falling from the
190-234 baseline to 91-118 for exactly the scripted week, then recovering — a clean signal at
this event volume. `gold_cohort_retention` shows the same effect but noisily: daily cohorts are
only ~15-30 players, too small a sample for a daily rate to be a reliable alarm signal. This is
why module 1's EWMA anomaly detector will watch **DAU and GGR from `gold_daily_kpi`** as the
primary daily signal; retention cohorts are better reviewed at a coarser (weekly) cadence, not
alarmed on day-to-day like DAU/GGR are.

## Known simplifications (see ARCHITECTURE.md for full rationale)

- FX rates are a static table (`event_simulator/fx.py`), not live — cross-currency accuracy isn't
  what this project demonstrates.
- No real balance ledger: deposit/withdrawal amounts are independently sampled, not reconciled
  against a running player balance.
- `player_features` (the per-player feature registry used by modules 1 and 2) is **not** built
  here — it's owned by `module2-experimentation-platform/feature_registry/` since that's the
  module responsible for the "single source of truth" narrative around it.
- The client-isolation demo in `governance/` filters `gold_daily_kpi` only, and its analyst IAM
  roles use a simplified (account-root) trust policy — see that module's README for exact scope.
