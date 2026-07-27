-- Athena view over the experiment registry's "current state" export
-- (one JSON file per experiment_id, kept in sync by the DynamoDB
-- Streams-triggered export Lambda). Not partitioned - this is a small,
-- full-refresh snapshot table for dashboarding, not an event log.
--
-- srm_result / analysis_result / readout columns are added later by
-- orchestration once those fields exist (see module2 orchestration DDL).
DROP TABLE IF EXISTS experiments_export;

CREATE EXTERNAL TABLE experiments_export (
    experiment_id     string,
    name              string,
    state             string,
    game_id           string,
    client_site_id    string,
    audience          map<string, string>,
    variants          array<struct<name: string, weight: double>>,
    oec_metric        string,
    guardrail_metrics array<struct<metric: string, direction: string, threshold: double>>,
    related_experiment_id string,
    assignment_seed   bigint,
    created_at        string,
    updated_at        string,
    started_at        string,
    stopped_at        string,
    stop_reason       string
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
LOCATION 's3://$bucket/gold/experiments_export/';
