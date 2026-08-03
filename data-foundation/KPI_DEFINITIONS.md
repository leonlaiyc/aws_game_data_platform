# KPI Definitions — Single Source of Truth

**Why this file exists:** the same governance problem [[FEATURES.md]] (Module 2's feature
registry) solves at the player-feature layer exists at the business-metric layer too — if every
team computes "DAU" or "retention" with a slightly different query, two dashboards showing
different numbers for the same day is not a data problem, it's a definitions problem. This file is
the one place a standard metric's calculation logic is defined. **Gold-layer tables
(`gold_daily_kpi`, `gold_hourly_kpi`, `gold_hourly_monitoring_features`, `gold_cohort_retention`) and anything built on top of them — dashboards, the
Module 3 semantic layer's SQL templates, ad hoc analysis — must compute these metrics exactly as
defined here, not re-derive them.**

Version: **v1** (2026-07-27). Any change to a calculation below is a new version; the Module 3
semantic layer cites this version number in every answer's source footer (see
`module3-analytics-assistant/README.md`) so a decision-maker knows exactly which definition of
"ARPU" produced the number they're looking at.

## Relationship to `module2-experimentation-platform/feature_registry/FEATURES.md`

Same governance philosophy, different grain and audience:

| | This file (`KPI_DEFINITIONS.md`) | `FEATURES.md` |
|---|---|---|
| Grain | daily site, hourly site/product/actor, and retention cohort | `snapshot_date x player_id` (analysis/ML) |
| Table | `gold_daily_kpi`, `gold_hourly_kpi`, `gold_hourly_monitoring_features`, `gold_cohort_retention` | `gold_player_features` |
| Consumers | Dashboards, execs, Module 3's semantic layer | Module 1 (arbitrage), Module 2 (experiment analysis) |

Both are built from the same `silver_events` — a metric defined here and a feature defined there
should never disagree about what "GGR" means, because both trace back to the same FX-normalized
`bet_amount_usd`/`win_amount_usd` columns computed once in Silver (see
`data-foundation/lake/ddl/02_silver_events.sql`).

---

## GGR (Gross Gaming Revenue)

**Definition:** `SUM(bet_amount_usd) - SUM(win_amount_usd)` across all `bet_settled` events in
the period, grouped by `date x client_site_id`.

**Computed in:** `gold_daily_kpi.ggr_usd` (`data-foundation/lake/ddl/03_gold_daily_kpi.sql`).

**Caveats:**
- FX-normalized using a **static** rate table (`event_simulator/fx.py`), not live rates — accurate
  enough to demonstrate the platform, not for real settlement. See ARCHITECTURE.md's documented
  simplifications.
- Does not net out bonus-funded wagers separately from cash wagers — a bonus-abuse-heavy day would
  inflate gross bet volume without a corresponding real-money deposit, which is exactly the kind of
  distortion Module 1's arbitrage detection is watching `gold_player_features.bonus_claims_30d` for.
- Daily GGR is inherently noisy at low-DAU sites/days (small numbers of settled rounds) — don't
  read a single day's GGR move as a trend without checking DAU moved too.

## DAU (Daily Active Users)

**Definition:** `COUNT(DISTINCT player_id)` with a `session_start` event on that date, grouped by
`date x client_site_id`.

**Computed in:** `gold_daily_kpi.dau`.

**Caveats:**
- Counts any player who starts a session, whether or not they wager — DAU is an engagement metric,
  not a revenue metric. A site with high DAU and low GGR is a distinct signal from low DAU and low
  GGR (the latter is a demand problem, the former is a monetization problem).
- No distinction between real-money and demo/bonus-only sessions in the current schema.

## ARPU (Average Revenue Per User)

**Definition:** `ggr_usd / dau` for the same `date x client_site_id`.

**Computed in:** `gold_daily_kpi.arpu_usd`.

**Caveats:**
- **Divides by DAU, not by paying users** — this is ARPU, not ARPPU (Average Revenue Per *Paying*
  User). A site with many non-paying DAU will show a structurally lower ARPU than one with fewer,
  more engaged players, even at identical GGR. Computing true ARPPU would need a "distinct
  depositing players" denominator, not currently a Gold column.
- **Small-denominator noise**: on a low-DAU day, ARPU can swing wildly from one big bettor — this
  is the same statistical issue Module 2's readout flags as `SAMPLE_IMBALANCE`/`SMALL_SAMPLE` for
  experiment analysis; the same caution applies to reading a daily ARPU number at face value.

## D1 / D7 Retention

**Definition:** for the cohort of players who registered on a given date at a given
`client_site_id`, the fraction who had a `session_start` event exactly 1 day later (D1) or 7 days
later (D7).

**Computed in:** `gold_cohort_retention.d1_retention_rate`, `.d7_retention_rate`
(`data-foundation/lake/ddl/04_gold_cohort_retention.sql`).

**Caveats:**
- Grain is `registration_date x client_site_id` only — no per-game breakdown. A retention drop
  concentrated in one game would show up as a smaller, blended drop at the site level.
- Daily registration cohorts can be small (single digits early in a site's life — see
  `data-foundation/README.md`'s note on this), making the daily retention rate itself noisy;
  a production dashboard should show a rolling/smoothed cohort view, not a raw daily line.
- Retention is defined relative to `client_site_id`, not `game_id` — a player who registers via
  one game and returns to play a different one on the same site still counts as retained.

## Hourly operational KPIs

**Definition:** metrics use the same event filters and FX-normalized Silver columns as their daily
counterparts, grouped by `event_hour x client_site_id x game_id x player_id` and partitioned by
`dt`.

**Computed in:** `gold_hourly_kpi` (`data-foundation/lake/ddl/05_gold_hourly_kpi.sql`).

**Why the actor dimension remains:** a live experiment guardrail must join only actors with a
recorded treatment exposure. Aggregating away `player_id` before that join would mix treatment,
control, and non-exposed traffic and make the hourly safety check untrustworthy.

**Caveats:** the current PoC refreshes this table during the batch lake build. A production path
would incrementally publish completed hourly partitions and advance the publication marker only
after late-arrival handling and quality checks finish.

### Hourly monitoring features

**Definition:** `active_users`, `sessions`, and `processed_events` are aggregated at
`event_hour x client_site_id`. For every hour-of-day and site, the baseline and normal range use
up to seven earlier observations at that same hour. This avoids comparing a partial hour with a
complete day or calculating history inside the alerting Lambda.

**Computed in:** `gold_hourly_monitoring_features`
(`data-foundation/lake/ddl/06_gold_hourly_monitoring_features.sql`). Module 1 reads the latest
published row and compares the prepared actual value with its prepared bounds.

---

## Adding or changing a metric

1. Update the calculation here first, bump the version, and add a one-line changelog entry below.
2. Update the corresponding Gold DDL (`data-foundation/lake/ddl/`) to match.
3. Rebuild via `data-foundation/lake/build_lake.py`.
4. If the Module 3 semantic layer has a SQL template referencing this metric, update its
   definition-version citation too.

### Changelog

- **v1.2** (2026-08-03): added site-level hourly monitoring features and same-hour baselines.
- **v1.1** (2026-08-02): added exposure-joinable hourly operational KPIs.
- **v1** (2026-07-27): initial definitions — GGR, DAU, ARPU, D1/D7 retention.
