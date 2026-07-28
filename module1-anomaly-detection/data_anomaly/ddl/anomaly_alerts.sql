-- Written by the detector Lambda whenever an EWMA check fires. One file
-- per (client_site_id, as_of_date) that had at least one alert -
-- unpartitioned, same reasoning as module2's experiments_export/
-- gold_experiment_assignments: small volume, full-prefix scan is fine.
DROP TABLE IF EXISTS anomaly_alerts;

CREATE EXTERNAL TABLE anomaly_alerts (
    client_site_id string,
    as_of_date     string,
    alerts         array<struct<
        metric: string,
        actual: double,
        ewma_baseline: double,
        sigma: double,
        deviation: double,
        k_sigma_threshold: double
    >>,
    detected_at    string
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://$bucket/gold/anomaly_alerts/';
