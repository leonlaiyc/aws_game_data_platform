-- Gold: hourly operational KPIs at event_hour x client_site_id x game_id x
-- player_id grain. Keeping the actor dimension is intentional: Module 2 can
-- join an experiment's recorded exposure cohort before aggregating a live
-- guardrail, instead of treating every eligible actor as exposed.
--
-- The table is partitioned by dt because it is materially larger than the
-- daily site summary and live checks always constrain the current date.
DROP TABLE IF EXISTS gold_hourly_kpi;

CREATE TABLE gold_hourly_kpi
WITH (
    format = 'PARQUET',
    parquet_compression = 'SNAPPY',
    partitioned_by = ARRAY['dt'],
    external_location = 's3://$bucket/gold/hourly_kpi/'
) AS
SELECT
    date_trunc('hour', event_ts) AS event_hour,
    client_site_id,
    game_id,
    player_id,
    COUNT_IF(event_type = 'session_start') AS sessions,
    COUNT_IF(event_type = 'bet_settled') AS completed_interactions,
    ROUND(SUM(CASE WHEN event_type = 'bet_settled' THEN COALESCE(bet_amount_usd, 0.0) ELSE 0.0 END), 2)
        AS gross_bets_usd,
    ROUND(SUM(CASE WHEN event_type = 'bet_settled' THEN COALESCE(win_amount_usd, 0.0) ELSE 0.0 END), 2)
        AS gross_wins_usd,
    ROUND(SUM(CASE WHEN event_type = 'bet_settled' THEN COALESCE(bet_amount_usd, 0.0) - COALESCE(win_amount_usd, 0.0) ELSE 0.0 END), 2)
        AS ggr_usd,
    ROUND(SUM(CASE WHEN event_type = 'deposit' AND payload.status = 'completed' THEN COALESCE(amount_usd, 0.0) ELSE 0.0 END), 2)
        AS deposits_usd,
    ROUND(SUM(CASE WHEN event_type = 'withdrawal' AND payload.status = 'completed' THEN COALESCE(amount_usd, 0.0) ELSE 0.0 END), 2)
        AS withdrawals_usd,
    dt
FROM silver_events
GROUP BY
    date_trunc('hour', event_ts),
    client_site_id,
    game_id,
    player_id,
    dt;
