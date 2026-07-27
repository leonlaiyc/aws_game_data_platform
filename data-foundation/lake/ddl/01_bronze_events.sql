-- Bronze: raw events, one row per JSON line, partitioned by ingestion date.
-- Partition projection means we never need MSCK REPAIR TABLE or manual
-- ADD PARTITION calls - Athena computes valid `dt` values from the range
-- below, which costs nothing extra in Glue Catalog API calls.
DROP TABLE IF EXISTS bronze_events;

CREATE EXTERNAL TABLE bronze_events (
    event_id      string,
    event_type    string,
    event_ts      string,
    player_id     string,
    session_id    string,
    game_id       string,
    client_site_id string,
    region        string,
    platform      string,
    device_id     string,
    ip_hash       string,
    payload       struct<
        step: string,
        auth_method: string,
        fail_reason: string,
        acquisition_channel: string,
        duration_sec: int,
        game_round_id: string,
        bet_amount: double,
        win_amount: double,
        currency: string,
        amount: double,
        payment_method: string,
        status: string,
        bonus_id: string,
        bonus_amount: double
    >
)
PARTITIONED BY (dt string)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://$bucket/bronze/'
TBLPROPERTIES (
    'projection.enabled' = 'true',
    'projection.dt.type' = 'date',
    'projection.dt.range' = '$min_date,$max_date',
    'projection.dt.format' = 'yyyy-MM-dd',
    'projection.dt.interval' = '1',
    'projection.dt.interval.unit' = 'DAYS',
    'storage.location.template' = 's3://$bucket/bronze/dt=$${dt}'
);
