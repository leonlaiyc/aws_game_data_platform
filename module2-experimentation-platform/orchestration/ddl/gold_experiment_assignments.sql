-- Written by the assignment Lambda: one file per experiment_id under
-- gold/experiment_assignments/, one JSON line per assigned player.
-- Unpartitioned, same reasoning as experiments_export - total row count
-- across every experiment this project will ever run is still small, and
-- experiment_id isn't a bounded/known-in-advance range the way our date
-- partitions are, so Hive partitioning would need MSCK REPAIR management
-- for no real benefit at this scale.
DROP TABLE IF EXISTS gold_experiment_assignments;

CREATE EXTERNAL TABLE gold_experiment_assignments (
    experiment_id string,
    player_id     string,
    variant       string,
    assigned_at   string
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://$bucket/gold/experiment_assignments/';
