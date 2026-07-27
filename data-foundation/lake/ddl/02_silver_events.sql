-- Silver: same grain as bronze, but columnar (Parquet/Snappy) and with FX
-- normalized to USD exactly once here, so every Gold query and every module
-- downstream reads a ready-to-sum amount_usd instead of re-deriving it.
-- Cross-currency accuracy isn't the point being demonstrated, so a static
-- rate table is a deliberate simplification (see ARCHITECTURE.md).
DROP TABLE IF EXISTS silver_events;

CREATE TABLE silver_events
WITH (
    format = 'PARQUET',
    parquet_compression = 'SNAPPY',
    partitioned_by = ARRAY['dt'],
    external_location = 's3://$bucket/silver/events/'
) AS
SELECT
    event_id,
    event_type,
    CAST(from_iso8601_timestamp(event_ts) AS TIMESTAMP) AS event_ts,
    player_id,
    session_id,
    game_id,
    client_site_id,
    region,
    platform,
    device_id,
    ip_hash,
    payload,
    CASE payload.currency WHEN 'BRL' THEN 0.18 WHEN 'EUR' THEN 1.08 WHEN 'USD' THEN 1.0 END AS fx_rate,
    payload.bet_amount * (CASE payload.currency WHEN 'BRL' THEN 0.18 WHEN 'EUR' THEN 1.08 WHEN 'USD' THEN 1.0 END) AS bet_amount_usd,
    payload.win_amount * (CASE payload.currency WHEN 'BRL' THEN 0.18 WHEN 'EUR' THEN 1.08 WHEN 'USD' THEN 1.0 END) AS win_amount_usd,
    payload.amount * (CASE payload.currency WHEN 'BRL' THEN 0.18 WHEN 'EUR' THEN 1.08 WHEN 'USD' THEN 1.0 END) AS amount_usd,
    dt
FROM bronze_events;
