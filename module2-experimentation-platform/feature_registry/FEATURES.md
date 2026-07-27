# player_features — Feature Registry

**Owner:** data-foundation / module2-experimentation-platform (this table is the shared source of
truth; do not compute player-level aggregates anywhere else).

**Table:** `gold_player_features` (Glue Catalog, `aurora_games_lake` database). Grain: one row per
`(snapshot_date, player_id)`. Partitioned by `snapshot_date`.

**Built by:** `ddl/gold_player_features.sql`, a CTAS over `silver_events` (see
`data-foundation/README.md` for the Bronze/Silver/Gold pipeline this sits on top of). Every window
below is a *trailing* window ending on `snapshot_date` inclusive, computed with SQL window
functions over a dense per-player daily spine (so windows represent calendar days, not "last N
active days").

**Who reads this table:**
- `module1-anomaly-detection/arbitrage_detection` — the fraud-pattern features below.
- `module2-experimentation-platform/orchestration` (analysis step) — the revenue/engagement
  features below, for OEC and guardrail metrics. Experiment analysis **must** read from here,
  never recompute its own player aggregates from Bronze/Silver.

## Columns

| Column | Definition | Primary consumer |
|---|---|---|
| `snapshot_date` | The day this row's rolling windows end on (inclusive). Partition key. | all |
| `player_id`, `client_site_id`, `region` | Identity / dimension columns. | all |
| `days_since_registration` | `snapshot_date - registration_date`, in days. | experiment audience filters |
| `sessions_1d` / `_7d` / `_30d` | Count of `session_start` events in the trailing window. | engagement guardrails |
| `bet_amount_usd_1d` / `_7d` / `_30d` | Sum of `bet_settled.bet_amount`, FX-normalized. | OEC (revenue) |
| `win_amount_usd_7d` | Sum of `bet_settled.win_amount` over 7d, FX-normalized. | GGR calc |
| `ggr_usd_7d` | `bet_amount_usd_7d - win_amount_usd_7d`. | OEC (revenue) |
| `deposit_amount_usd_1d` / `_7d` / `_30d` | Sum of completed deposits, FX-normalized. | OEC, guardrails |
| `withdrawal_amount_usd_1d` / `_7d` / `_30d` | Sum of completed withdrawals, FX-normalized. | guardrails |
| `withdrawal_to_deposit_ratio_7d` | `withdrawal_amount_usd_7d / deposit_amount_usd_7d` (NULL if no deposits in window). | **arbitrage detection** |
| `bonus_claims_30d` | Count of `bonus_claimed` events in 30d. | **arbitrage detection** (bonus abuse) |
| `distinct_devices_30d` | Count of distinct `device_id`s this player used in 30d. | **arbitrage detection** (account takeover / sharing) |
| `distinct_ip_7d` | Count of distinct `ip_hash`es this player used in 7d. | **arbitrage detection** |
| `net_deposit_lifetime_usd` | Cumulative `deposits - withdrawals` since registration (not windowed). | OEC (LTV proxy) |

## Important: this table doesn't catch multi-account rings by itself

`distinct_devices_30d` / `distinct_ip_7d` describe **one player's own** device/IP footprint — they
catch account takeover or credential sharing, not a ring of *separate* player_ids coordinating on
shared hardware. The scripted arbitrage ring in the simulator (see
`data-foundation/event_simulator/config.py`) is a **device/IP fan-out** pattern instead: few
devices mapped to many distinct player_ids. That signal comes from a device-centric query (see
`data-foundation/lake/queries/arbitrage_ring_check.sql`), not from this table's per-player columns.
`module1-anomaly-detection/arbitrage_detection` combines both: the fan-out query to find candidate
rings, joined against this table's `withdrawal_to_deposit_ratio_7d` and `bonus_claims_30d` to score
how suspicious each candidate's behavior looks.

## Deliberate substitution: SageMaker Feature Store → lake-based registry

We considered **Amazon SageMaker Feature Store** for this role and chose a plain Glue-Catalog
table instead.

- SageMaker Feature Store's main value is a low-latency **online store** for real-time
  inference (e.g. a fraud-scoring API serving p99 < 10ms). Nothing in this project serves
  features online — arbitrage scoring and experiment analysis are both batch/daily jobs reading
  from Athena, so the online store buys us nothing.
- Feature Store's offline store still bills for the S3 storage plus a per-GB-month charge on top,
  and adds an extra service (with its own IAM, its own console, its own concepts) to operate and
  explain — for a batch-only workload, a Glue table is strictly less to pay for and less to learn.
- **Migration path:** if a future module needed sub-second feature lookups (e.g. a real-time
  bonus-abuse check at deposit time), we'd introduce SageMaker Feature Store (or a DynamoDB table
  populated by a stream from this Gold table) as an online store *in addition to* this offline
  table — this table would remain the batch source of truth either way.
