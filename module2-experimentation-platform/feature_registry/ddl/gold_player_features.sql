-- Gold: player_features, a daily snapshot of per-player rolling-window
-- behavior. This is the single source of truth both module1 (arbitrage
-- detection) and module2 (experiment analysis) read from - nobody computes
-- their own player-level aggregates. See FEATURES.md for definitions.
--
-- Grain: snapshot_date x player_id. Partitioned by snapshot_date (unlike
-- data-foundation's small daily_kpi/cohort_retention tables) because this
-- one has ~300K rows (players x days-since-registration).
DROP TABLE IF EXISTS gold_player_features;

CREATE TABLE gold_player_features
WITH (
    format = 'PARQUET',
    partitioned_by = ARRAY['snapshot_date'],
    external_location = 's3://$bucket/gold/player_features/'
) AS
WITH date_spine AS (
    SELECT CAST(date_add('day', seq, DATE '$min_date') AS VARCHAR) AS dt
    FROM UNNEST(sequence(0, $num_days_minus_1)) AS t(seq)
),
players AS (
    SELECT player_id, client_site_id, region, dt AS registration_date
    FROM silver_events WHERE event_type = 'player_registered'
),
player_day_spine AS (
    SELECT p.player_id, p.client_site_id, p.region, p.registration_date, d.dt
    FROM players p
    JOIN date_spine d ON d.dt >= p.registration_date
),
daily_sessions AS (
    SELECT player_id, dt, COUNT(*) AS sessions
    FROM silver_events WHERE event_type = 'session_start' GROUP BY player_id, dt
),
daily_bets AS (
    SELECT player_id, dt, SUM(bet_amount_usd) AS bet_amount_usd, SUM(win_amount_usd) AS win_amount_usd
    FROM silver_events WHERE event_type = 'bet_settled' GROUP BY player_id, dt
),
daily_deposits AS (
    SELECT player_id, dt, SUM(amount_usd) AS deposit_amount_usd
    FROM silver_events WHERE event_type = 'deposit' AND payload.status = 'completed' GROUP BY player_id, dt
),
daily_withdrawals AS (
    SELECT player_id, dt, SUM(amount_usd) AS withdrawal_amount_usd
    FROM silver_events WHERE event_type = 'withdrawal' AND payload.status = 'completed' GROUP BY player_id, dt
),
daily_bonuses AS (
    SELECT player_id, dt, COUNT(*) AS bonus_claims
    FROM silver_events WHERE event_type = 'bonus_claimed' GROUP BY player_id, dt
),
daily_devices AS (
    SELECT player_id, dt, ARRAY_AGG(DISTINCT device_id) AS device_ids
    FROM silver_events WHERE device_id IS NOT NULL GROUP BY player_id, dt
),
daily_ips AS (
    SELECT player_id, dt, ARRAY_AGG(DISTINCT ip_hash) AS ip_hashes
    FROM silver_events WHERE ip_hash IS NOT NULL GROUP BY player_id, dt
),
daily AS (
    SELECT
        s.player_id, s.client_site_id, s.region, s.registration_date, s.dt,
        COALESCE(sess.sessions, 0) AS sessions,
        COALESCE(bet.bet_amount_usd, 0.0) AS bet_amount_usd,
        COALESCE(bet.win_amount_usd, 0.0) AS win_amount_usd,
        COALESCE(dep.deposit_amount_usd, 0.0) AS deposit_amount_usd,
        COALESCE(wd.withdrawal_amount_usd, 0.0) AS withdrawal_amount_usd,
        COALESCE(bon.bonus_claims, 0) AS bonus_claims,
        COALESCE(dev.device_ids, CAST(ARRAY[] AS ARRAY(VARCHAR))) AS device_ids,
        COALESCE(ip.ip_hashes, CAST(ARRAY[] AS ARRAY(VARCHAR))) AS ip_hashes
    FROM player_day_spine s
    LEFT JOIN daily_sessions sess ON sess.player_id = s.player_id AND sess.dt = s.dt
    LEFT JOIN daily_bets bet ON bet.player_id = s.player_id AND bet.dt = s.dt
    LEFT JOIN daily_deposits dep ON dep.player_id = s.player_id AND dep.dt = s.dt
    LEFT JOIN daily_withdrawals wd ON wd.player_id = s.player_id AND wd.dt = s.dt
    LEFT JOIN daily_bonuses bon ON bon.player_id = s.player_id AND bon.dt = s.dt
    LEFT JOIN daily_devices dev ON dev.player_id = s.player_id AND dev.dt = s.dt
    LEFT JOIN daily_ips ip ON ip.player_id = s.player_id AND ip.dt = s.dt
)
SELECT
    player_id,
    client_site_id,
    region,
    date_diff('day', CAST(registration_date AS DATE), CAST(dt AS DATE)) AS days_since_registration,

    SUM(sessions) OVER w1 AS sessions_1d,
    SUM(sessions) OVER w7 AS sessions_7d,
    SUM(sessions) OVER w30 AS sessions_30d,

    ROUND(SUM(bet_amount_usd) OVER w1, 2) AS bet_amount_usd_1d,
    ROUND(SUM(bet_amount_usd) OVER w7, 2) AS bet_amount_usd_7d,
    ROUND(SUM(bet_amount_usd) OVER w30, 2) AS bet_amount_usd_30d,

    ROUND(SUM(win_amount_usd) OVER w7, 2) AS win_amount_usd_7d,
    ROUND(SUM(bet_amount_usd) OVER w7 - SUM(win_amount_usd) OVER w7, 2) AS ggr_usd_7d,

    ROUND(SUM(deposit_amount_usd) OVER w1, 2) AS deposit_amount_usd_1d,
    ROUND(SUM(deposit_amount_usd) OVER w7, 2) AS deposit_amount_usd_7d,
    ROUND(SUM(deposit_amount_usd) OVER w30, 2) AS deposit_amount_usd_30d,

    ROUND(SUM(withdrawal_amount_usd) OVER w1, 2) AS withdrawal_amount_usd_1d,
    ROUND(SUM(withdrawal_amount_usd) OVER w7, 2) AS withdrawal_amount_usd_7d,
    ROUND(SUM(withdrawal_amount_usd) OVER w30, 2) AS withdrawal_amount_usd_30d,

    ROUND(
        -- Guard against near-zero floating point residue in the denominator
        -- (a window that truly has no deposits can still sum to a tiny
        -- nonzero epsilon rather than exact 0.0) by treating anything under
        -- one cent as "no deposits this week" -> NULL, not an astronomical ratio.
        CASE WHEN SUM(deposit_amount_usd) OVER w7 > 0.01
            THEN SUM(withdrawal_amount_usd) OVER w7 / SUM(deposit_amount_usd) OVER w7
            ELSE NULL
        END, 4
    ) AS withdrawal_to_deposit_ratio_7d,

    SUM(bonus_claims) OVER w30 AS bonus_claims_30d,

    CARDINALITY(ARRAY_DISTINCT(FLATTEN(ARRAY_AGG(device_ids) OVER w30))) AS distinct_devices_30d,
    CARDINALITY(ARRAY_DISTINCT(FLATTEN(ARRAY_AGG(ip_hashes) OVER w7))) AS distinct_ip_7d,

    ROUND(SUM(deposit_amount_usd) OVER w_life - SUM(withdrawal_amount_usd) OVER w_life, 2) AS net_deposit_lifetime_usd,

    dt AS snapshot_date

FROM daily
WINDOW
    w1 AS (PARTITION BY player_id ORDER BY dt ROWS BETWEEN 0 PRECEDING AND CURRENT ROW),
    w7 AS (PARTITION BY player_id ORDER BY dt ROWS BETWEEN 6 PRECEDING AND CURRENT ROW),
    w30 AS (PARTITION BY player_id ORDER BY dt ROWS BETWEEN 29 PRECEDING AND CURRENT ROW),
    w_life AS (PARTITION BY player_id ORDER BY dt ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW);
