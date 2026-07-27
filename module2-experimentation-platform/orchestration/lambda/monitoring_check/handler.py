"""Step 3: guardrail monitoring while an experiment is running.

Two invocation modes, same underlying check:
- From the Step Functions Map state, once per date in the experiment's
  monitoring window (module2's demo replays historical days quickly instead
  of waiting in real wall-clock time, since our data is a fixed simulation).
- From the EventBridge schedule (event == {"scheduled": true}), the real
  always-on production path: scans all currently-running experiments and
  checks each against today's date.

On a breach: auto-transition running -> stopped_early (guarded by a
ConditionExpression so a concurrent check can't double-fire) + SNS alert.
"""
import os
import time

import boto3
from boto3.dynamodb.conditions import Attr
from athena_utils import run_athena_query, fetch_all_rows
from dynamo_utils import now_iso

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["EXPERIMENTS_TABLE_NAME"])
sns = boto3.client("sns")
TOPIC_ARN = os.environ["ALERTS_TOPIC_ARN"]


def _check_guardrails(experiment_id: str, check_date: str, guardrail_metrics: list) -> list:
    breaches = []
    for g in guardrail_metrics:
        metric, direction, threshold = g["metric"], g["direction"], float(g["threshold"])
        sql = f"""
        SELECT AVG(pf.{metric}) AS value
        FROM gold_player_features pf
        JOIN gold_experiment_assignments ea ON ea.player_id = pf.player_id
        WHERE ea.experiment_id = '{experiment_id}' AND ea.variant = 'treatment'
          AND pf.snapshot_date = '{check_date}'
        """
        rows = fetch_all_rows(run_athena_query(sql))
        value = float(rows[0]["value"]) if rows and rows[0].get("value") is not None else None
        if value is None:
            continue
        breached = (direction == "min" and value < threshold) or (direction == "max" and value > threshold)
        if breached:
            breaches.append({"metric": metric, "direction": direction, "threshold": threshold, "value": round(value, 4)})
    return breaches


def _check_experiment(experiment_id: str, check_date: str, guardrail_metrics: list) -> dict:
    item = table.get_item(Key={"experiment_id": experiment_id}).get("Item")
    if not item or item.get("state") != "running":
        return {"experiment_id": experiment_id, "check_date": check_date, "skipped": True,
                "reason": f"experiment state is '{item.get('state') if item else 'missing'}', not running"}

    breaches = _check_guardrails(experiment_id, check_date, guardrail_metrics)
    if not breaches:
        return {"experiment_id": experiment_id, "check_date": check_date, "breached": False}

    reason = "guardrail_breach: " + "; ".join(
        f"{b['metric']}={b['value']} vs {b['direction']} threshold {b['threshold']}" for b in breaches
    )
    try:
        table.update_item(
            Key={"experiment_id": experiment_id},
            UpdateExpression="SET #state = :stopped, stopped_at = :now, updated_at = :now, stop_reason = :reason",
            ConditionExpression="#state = :running",
            ExpressionAttributeNames={"#state": "state"},
            ExpressionAttributeValues={
                ":stopped": "stopped_early", ":running": "running", ":now": now_iso(), ":reason": reason,
            },
        )
        sns.publish(
            TopicArn=TOPIC_ARN,
            Subject=f"Experiment {experiment_id} auto-stopped (guardrail breach)",
            Message=f"Experiment {experiment_id} was auto-stopped on {check_date}.\n\n{reason}",
        )
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        pass  # already stopped by a concurrent check or a manual action

    return {"experiment_id": experiment_id, "check_date": check_date, "breached": True, "breaches": breaches}


def handler(event, context):
    if event.get("scheduled"):
        today = time.strftime("%Y-%m-%d", time.gmtime())
        running = table.scan(FilterExpression=Attr("state").eq("running")).get("Items", [])
        results = [_check_experiment(item["experiment_id"], today, item.get("guardrail_metrics", [])) for item in running]
        return {"checked": len(running), "results": results}

    return _check_experiment(event["experiment_id"], event["check_date"], event.get("guardrail_metrics", []))
