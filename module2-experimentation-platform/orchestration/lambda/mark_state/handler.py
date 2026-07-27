"""Small reusable state transition used at two points in the Step Functions
flow that don't need any other business logic: SRM hard-fail
(running -> stopped_early) and natural completion after the monitoring loop
finishes without a breach (running -> completed). Guarded by a
ConditionExpression, so calling this after monitoring_check already flipped
the state to stopped_early is a safe no-op, not an error.
"""
import os

import boto3
from dynamo_utils import now_iso

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["EXPERIMENTS_TABLE_NAME"])
sns = boto3.client("sns")
TOPIC_ARN = os.environ["ALERTS_TOPIC_ARN"]


def handler(event, context):
    experiment_id = event["experiment_id"]
    from_state = event.get("from_state", "running")
    to_state = event["to_state"]
    reason = event.get("reason")
    notify = event.get("notify", False)

    update_expr = "SET #state = :to_state, updated_at = :now"
    values = {":to_state": to_state, ":from_state": from_state, ":now": now_iso()}
    if to_state == "stopped_early":
        update_expr += ", stopped_at = :now, stop_reason = :reason"
        values[":reason"] = reason
    elif to_state == "completed":
        update_expr += ", stopped_at = :now"

    try:
        table.update_item(
            Key={"experiment_id": experiment_id},
            UpdateExpression=update_expr,
            ConditionExpression="#state = :from_state",
            ExpressionAttributeNames={"#state": "state"},
            ExpressionAttributeValues=values,
        )
        transitioned = True
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        transitioned = False

    if transitioned and notify:
        sns.publish(
            TopicArn=TOPIC_ARN,
            Subject=f"Experiment {experiment_id} -> {to_state}",
            Message=f"Experiment {experiment_id} transitioned to '{to_state}'.\n\nReason: {reason}",
        )

    return {"transitioned": transitioned, "to_state": to_state}
