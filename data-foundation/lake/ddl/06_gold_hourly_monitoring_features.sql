-- Gold monitoring features: one row per site and hour with the actual values
-- and same-hour historical control limits already computed. The detector reads
-- this table; it does not repeatedly rebuild baselines inside Lambda.
DROP TABLE IF EXISTS gold_hourly_monitoring_features;

CREATE TABLE gold_hourly_monitoring_features
WITH (
    format = 'PARQUET',
    parquet_compression = 'SNAPPY',
    partitioned_by = ARRAY['dt'],
    external_location = 's3://$bucket/gold/hourly_monitoring_features/'
) AS
WITH hourly AS (
    SELECT
        event_hour,
        client_site_id,
        COUNT(DISTINCT player_id) AS active_users,
        SUM(sessions) AS sessions,
        SUM(processed_events) AS processed_events,
        CAST(date(event_hour) AS VARCHAR) AS dt
    FROM gold_hourly_kpi
    GROUP BY event_hour, client_site_id
), baselines AS (
    SELECT
        *,
        COUNT(*) OVER same_hour_history AS baseline_points,
        AVG(active_users) OVER same_hour_history AS active_users_baseline,
        STDDEV_POP(active_users) OVER same_hour_history AS active_users_sigma,
        AVG(sessions) OVER same_hour_history AS sessions_baseline,
        STDDEV_POP(sessions) OVER same_hour_history AS sessions_sigma,
        AVG(processed_events) OVER same_hour_history AS processed_events_baseline,
        STDDEV_POP(processed_events) OVER same_hour_history AS processed_events_sigma
    FROM hourly
    WINDOW same_hour_history AS (
        PARTITION BY client_site_id, hour(event_hour)
        ORDER BY event_hour
        ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
    )
)
SELECT
    event_hour,
    client_site_id,
    active_users,
    sessions,
    processed_events,
    baseline_points,
    ROUND(active_users_baseline, 4) AS active_users_baseline,
    ROUND(GREATEST(0, active_users_baseline - 3 * active_users_sigma), 4)
        AS active_users_lower_bound,
    ROUND(active_users_baseline + 3 * active_users_sigma, 4)
        AS active_users_upper_bound,
    ROUND(sessions_baseline, 4) AS sessions_baseline,
    ROUND(GREATEST(0, sessions_baseline - 3 * sessions_sigma), 4)
        AS sessions_lower_bound,
    ROUND(sessions_baseline + 3 * sessions_sigma, 4)
        AS sessions_upper_bound,
    ROUND(processed_events_baseline, 4) AS processed_events_baseline,
    ROUND(GREATEST(0, processed_events_baseline - 3 * processed_events_sigma), 4)
        AS processed_events_lower_bound,
    ROUND(processed_events_baseline + 3 * processed_events_sigma, 4)
        AS processed_events_upper_bound,
    dt
FROM baselines;
