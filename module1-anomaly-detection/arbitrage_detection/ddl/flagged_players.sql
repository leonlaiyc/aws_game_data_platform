-- Written by the detector Lambda whenever a run flags at least one
-- player. One file per (client_site_id, as_of_date) - unpartitioned,
-- same reasoning as this project's other small JSON export tables.
DROP TABLE IF EXISTS flagged_players;

CREATE EXTERNAL TABLE flagged_players (
    client_site_id string,
    as_of_date     string,
    flagged_players array<struct<
        player_id: string,
        client_site_id: string,
        shared_device_ids: array<string>,
        withdrawal_to_deposit_ratio_7d: double,
        bonus_claims_30d: int,
        reasons: array<string>
    >>,
    detected_at    string
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://$bucket/gold/flagged_players/';
