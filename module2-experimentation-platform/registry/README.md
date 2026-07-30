# Experiment Registry

DynamoDB-backed metadata store for experiments, with a CRUD API and an Athena-queryable export.
This is the state layer `orchestration/`'s Step Functions state machine drives through
`draft -> running -> (stopped_early | completed) -> analyzed`.

## Components

- **`aurora-games-experiments`** (DynamoDB, on-demand billing, PK `experiment_id`, streams
  enabled) — one item per experiment.
- **`aurora-games-experiment-exposures`** (DynamoDB on-demand, PK
  `experiment_id`, SK `event_id`, 180-day TTL) — immutable product-accepted
  exposure decisions. The table has 25 RRU/WRU per-second best-effort caps.
- **`ExperimentsApiHandler`** (Lambda behind API Gateway) — the CRUD and
  product exposure API below.
- **`ExperimentsExportHandler`** (Lambda, triggered by DynamoDB Streams) — keeps a "current state"
  JSON snapshot of every experiment in `s3://<bucket>/gold/experiments_export/<experiment_id>.json`,
  so the registry is queryable from Athena for dashboarding without a federated-query connector.
- **`ExperimentExposuresExportHandler`** (Lambda, triggered by the exposure
  stream) — appends accepted exposure events under
  `gold/experiment_exposures/dt=YYYY-MM-DD/` for Athena monitoring and
  analysis.

Automated state changes (SRM result, guardrail auto-stop, analysis, readout) are written straight
to DynamoDB by `orchestration/`'s Step Functions state machine or its Lambdas — not through this
API. API Gateway is for external/human CRUD; internal service-to-service transitions go directly
to DynamoDB, which is the more idiomatic (and cheaper, lower-latency) AWS-native pattern.

## API

Base URL: the `ExperimentsApiUrl` CDK output (`AuroraGamesRegistryStack`).

| Method | Path | Notes |
|---|---|---|
| POST | `/experiments` | Create (state=`draft`). Requires `name`, business `owner`, `game_id`, `client_site_id`, `variants`, `oec_metric`; the API derives `created_by` from the authenticated IAM principal. |
| GET | `/experiments` | Analysts list their own site; the operator role lists all. |
| GET | `/experiments/{id}` | Get one within the caller's identity-derived tenant scope. |
| PATCH | `/experiments/{id}` | Edit `name`/`owner`/`audience`/`variants`/`oec_metric`/`guardrail_metrics`/`related_experiment_id` only while `draft` (409 otherwise); `updated_by` is identity-derived. |
| DELETE | `/experiments/{id}` | Only while `draft` (409 otherwise) — history isn't deletable once an experiment has run. |
| POST | `/experiments/{id}/start` | `draft -> running`. Defaults to `mode=live`; requires 1–90 `duration_days`, while `mode=replay` also requires `as_of_date`. |
| POST | `/experiments/{id}/stop` | `running -> stopped_early \| completed`, and stops the recorded Step Functions execution. |
| POST | `/experiments/{id}/exposures` | Product decision point. Accepts `event_id` and `player_id`; returns deterministic `EXPOSE` or safe `DO_NOT_EXPOSE`. |

The exposure write is a DynamoDB transaction: it verifies that the experiment
is still `running` and `allocation_enabled=true` in the same transaction that
inserts the immutable event. A guardrail stop racing the request therefore
cannot commit a new treatment decision after the kill switch. Reusing an
`event_id` for the same player returns the prior decision; reusing it for a
different player is rejected.

### Security boundary

Every method requires API Gateway `AWS_IAM` authentication. Scope comes from the exact STS/IAM role
name: `aurora-games-analyst-site_a|b|c` maps to one tenant, while only the exact
`aurora-games-operator` role is unscoped. Similar-looking or unknown identities fail closed, and a
cross-tenant object is returned as 404 to avoid confirming its existence.

The API also validates site, game identifier, OEC/guardrail metric, variant names and weights,
guardrail direction/threshold, and audience fields against closed sets before anything can flow
into dynamically assembled Athena SQL. These hardening changes are covered offline in
`tests/test_registry_security.py`; deployed negative-path verification is still pending.

Requests must be SigV4-signed; unsigned `curl` returns 403. The runnable example uses
`demo/demo_lib.py`, which assumes the operator role and signs every request. Equivalent request
body:

```json
{
  "name": "payout-tweak-game01",
  "owner": "growth-experimentation",
  "game_id": "game_01",
  "client_site_id": "site_a",
  "variants": [{"name":"control","weight":0.5},{"name":"treatment","weight":0.5}],
  "oec_metric": "ggr_usd_7d",
  "guardrail_metrics": [{"metric":"sessions_7d","direction":"min","threshold":1}]
}
```

## Querying the export from Athena

```bash
# Registers the experiments_export table (run once, or again any time the DDL changes)
../../data-foundation/.venv/Scripts/python.exe build_registry_table.py
```

```sql
SELECT experiment_id, name, state, oec_metric, stop_reason FROM experiments_export;
```

## Iterative experiments (`related_experiment_id`)

Experiments are rarely one-shot - a payout tweak might get re-tested v1, v2, v3 before shipping.
Each iteration is still its own `experiment_id` with its own full lifecycle (the state machine
doesn't change), but an optional `related_experiment_id` on create/update points back at the prior
iteration, so a whole series can be traced in Athena without relying on naming conventions:

```sql
-- Walk a whole iteration chain starting from a known experiment_id
WITH RECURSIVE chain AS (
    SELECT experiment_id, name, related_experiment_id, state, 0 AS depth
    FROM experiments_export WHERE experiment_id = 'exp_...'
    UNION ALL
    SELECT e.experiment_id, e.name, e.related_experiment_id, e.state, c.depth + 1
    FROM experiments_export e JOIN chain c ON e.experiment_id = c.related_experiment_id
)
SELECT * FROM chain ORDER BY depth;
```

(Athena/Trino's `WITH RECURSIVE` requires engine v3 - if unavailable, a fixed-depth self-join
covers the common case of a handful of iterations.)

## A boto3/DynamoDB gotcha worth knowing

DynamoDB's Table resource API rejects native Python `float` values outright (`TypeError: Float
types are not supported. Use Decimal types instead.`) — any numeric field in a request body
(`variants[].weight`, `guardrail_metrics[].threshold`) must be parsed as `Decimal`
(`json.loads(body, parse_float=Decimal)`), and converted back for JSON responses. Both Lambdas in
this module handle this; see `handler.py`'s `_json_default`.
