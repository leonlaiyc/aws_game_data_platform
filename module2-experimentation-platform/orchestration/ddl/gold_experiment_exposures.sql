-- Immutable product-runtime exposure events exported from DynamoDB Streams.
-- Date partition projection avoids MSCK REPAIR and lets live monitoring prune
-- the append-only prefix. Each row is an accepted EXPOSE decision; stopped
-- experiments return DO_NOT_EXPOSE and therefore produce no row.
DROP TABLE IF EXISTS gold_experiment_exposures;

CREATE EXTERNAL TABLE gold_experiment_exposures (
    experiment_id  string,
    event_id       string,
    player_id      string,
    client_site_id string,
    game_id        string,
    variant        string,
    exposed_at     string,
    recorded_at    string,
    expires_at     bigint
)
PARTITIONED BY (dt string)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://$bucket/gold/experiment_exposures/'
TBLPROPERTIES (
    'projection.enabled' = 'true',
    'projection.dt.type' = 'date',
    'projection.dt.format' = 'yyyy-MM-dd',
    'projection.dt.range' = '2026-01-01,NOW',
    'storage.location.template' = 's3://$bucket/gold/experiment_exposures/dt=$${dt}/'
);
