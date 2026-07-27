-- Gold: D1/D7 retention per registration cohort (registration_date x
-- client_site_id). This is the metric module1's EWMA anomaly detector
-- watches for silent retention drops.
DROP TABLE IF EXISTS gold_cohort_retention;

CREATE TABLE gold_cohort_retention
WITH (
    format = 'PARQUET',
    external_location = 's3://$bucket/gold/cohort_retention/'
) AS
WITH registrations AS (
    SELECT player_id, client_site_id, dt AS registration_date
    FROM silver_events WHERE event_type = 'player_registered'
),
active_days AS (
    SELECT DISTINCT player_id, dt AS active_date
    FROM silver_events WHERE event_type = 'session_start'
)
SELECT
    r.registration_date,
    r.client_site_id,
    COUNT(DISTINCT r.player_id) AS cohort_size,
    COUNT(DISTINCT a1.player_id) AS d1_retained,
    COUNT(DISTINCT a7.player_id) AS d7_retained,
    ROUND(CAST(COUNT(DISTINCT a1.player_id) AS DOUBLE) / COUNT(DISTINCT r.player_id), 4) AS d1_retention_rate,
    ROUND(CAST(COUNT(DISTINCT a7.player_id) AS DOUBLE) / COUNT(DISTINCT r.player_id), 4) AS d7_retention_rate
FROM registrations r
LEFT JOIN active_days a1
    ON a1.player_id = r.player_id
    AND a1.active_date = CAST(date_add('day', 1, CAST(r.registration_date AS DATE)) AS VARCHAR)
LEFT JOIN active_days a7
    ON a7.player_id = r.player_id
    AND a7.active_date = CAST(date_add('day', 7, CAST(r.registration_date AS DATE)) AS VARCHAR)
GROUP BY r.registration_date, r.client_site_id;
