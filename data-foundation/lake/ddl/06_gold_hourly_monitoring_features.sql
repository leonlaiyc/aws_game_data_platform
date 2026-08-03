-- Gold monitoring features: one row per site and hourly cutoff. Each actual
-- value is cumulative from 00:00 through that cutoff, matching what a business
-- user sees when asking "how are we doing so far today?". Baselines compare
-- that value with the previous 30 complete dates at the same cutoff. The
-- detector reads these prepared features; Lambda never rebuilds the baseline.
DROP TABLE IF EXISTS gold_hourly_monitoring_features;

CREATE TABLE gold_hourly_monitoring_features
WITH (
    format = 'PARQUET',
    parquet_compression = 'SNAPPY',
    partitioned_by = ARRAY['dt'],
    external_location = 's3://$bucket/gold/hourly_monitoring_features/'
) AS
WITH cutoffs AS (
    SELECT DISTINCT event_hour, client_site_id
    FROM gold_hourly_kpi
), cumulative AS (
    SELECT
        cutoff.event_hour,
        cutoff.client_site_id,
        COUNT(DISTINCT fact.player_id) AS active_users,
        SUM(fact.sessions) AS sessions,
        SUM(fact.processed_events) AS processed_events,
        CAST(date(cutoff.event_hour) AS VARCHAR) AS dt
    FROM cutoffs cutoff
    JOIN gold_hourly_kpi fact
      ON fact.client_site_id = cutoff.client_site_id
     AND date(fact.event_hour) = date(cutoff.event_hour)
     AND fact.event_hour <= cutoff.event_hour
    GROUP BY cutoff.event_hour, cutoff.client_site_id
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
    FROM cumulative
    WINDOW same_hour_history AS (
        PARTITION BY client_site_id, hour(event_hour)
        ORDER BY event_hour
        ROWS BETWEEN 30 PRECEDING AND 1 PRECEDING
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
