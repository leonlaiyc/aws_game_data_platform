"""CRUD API for the experiment registry.

State machine: draft -> running -> (stopped_early | completed) -> analyzed.
This Lambda only handles the human/API-driven transitions (create, edit
while draft, manual start/stop, delete while draft). The automated
transitions - SRM result, guardrail auto-stop, analysis, readout - are
written directly to DynamoDB by the Step Functions orchestration
(module2-experimentation-platform/orchestration), not through this API.
"""
import json
import os
import random
import time
import uuid
from datetime import date, timedelta
from decimal import Decimal

import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["EXPERIMENTS_TABLE_NAME"])
sfn = boto3.client("stepfunctions")
STATE_MACHINE_ARN = os.environ["ORCHESTRATION_STATE_MACHINE_ARN"]

REQUIRED_CREATE_FIELDS = ["name", "game_id", "client_site_id", "variants", "oec_metric"]
UPDATABLE_DRAFT_FIELDS = {"name", "audience", "variants", "oec_metric", "guardrail_metrics"}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _json_default(obj):
    # DynamoDB's boto3 resource API requires Decimal for numbers, so incoming
    # request bodies are parsed with parse_float=Decimal; this undoes that
    # for outgoing responses so weights/thresholds render as JSON numbers.
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return str(obj)


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=_json_default),
    }


def create_experiment(body: dict) -> dict:
    missing = [f for f in REQUIRED_CREATE_FIELDS if f not in body]
    if missing:
        return _response(400, {"error": f"Missing required fields: {missing}"})

    experiment_id = f"exp_{uuid.uuid4().hex[:10]}"
    item = {
        "experiment_id": experiment_id,
        "name": body["name"],
        "game_id": body["game_id"],
        "client_site_id": body["client_site_id"],
        "state": "draft",
        "audience": body.get("audience", {}),
        "variants": body["variants"],
        "oec_metric": body["oec_metric"],
        "guardrail_metrics": body.get("guardrail_metrics", []),
        "created_at": _now(),
        "updated_at": _now(),
    }
    table.put_item(Item=item)
    return _response(201, item)


def get_experiment(experiment_id: str) -> dict:
    item = table.get_item(Key={"experiment_id": experiment_id}).get("Item")
    if not item:
        return _response(404, {"error": "not found"})
    return _response(200, item)


def list_experiments() -> dict:
    items = table.scan().get("Items", [])
    return _response(200, {"experiments": items})


def update_experiment(experiment_id: str, body: dict) -> dict:
    item = table.get_item(Key={"experiment_id": experiment_id}).get("Item")
    if not item:
        return _response(404, {"error": "not found"})
    if item["state"] != "draft":
        return _response(409, {"error": f"cannot edit experiment in state '{item['state']}'; only draft experiments can be edited"})

    updates = {k: v for k, v in body.items() if k in UPDATABLE_DRAFT_FIELDS}
    if not updates:
        return _response(400, {"error": f"no updatable fields provided (allowed: {sorted(UPDATABLE_DRAFT_FIELDS)})"})

    expr_names = {f"#{k}": k for k in updates}
    expr_values = {f":{k}": v for k, v in updates.items()}
    expr_values[":updated_at"] = _now()
    update_expr = "SET " + ", ".join(f"#{k} = :{k}" for k in updates) + ", updated_at = :updated_at"
    table.update_item(
        Key={"experiment_id": experiment_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )
    return get_experiment(experiment_id)


def start_experiment(experiment_id: str, body: dict) -> dict:
    as_of_date_str = body.get("as_of_date")
    duration_days = body.get("duration_days")
    if not as_of_date_str or not duration_days:
        return _response(400, {"error": "start requires 'as_of_date' (YYYY-MM-DD) and 'duration_days'"})

    as_of_date = date.fromisoformat(as_of_date_str)
    check_dates = [(as_of_date + timedelta(days=n)).isoformat() for n in range(1, int(duration_days) + 1)]

    try:
        table.update_item(
            Key={"experiment_id": experiment_id},
            UpdateExpression="SET #state = :running, started_at = :now, updated_at = :now, assignment_seed = :seed",
            ConditionExpression="#state = :draft",
            ExpressionAttributeNames={"#state": "state"},
            ExpressionAttributeValues={
                ":running": "running",
                ":draft": "draft",
                ":now": _now(),
                ":seed": random.randint(1, 2**31 - 1),
            },
        )
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return _response(409, {"error": "experiment must be in 'draft' state to start"})

    sfn.start_execution(
        stateMachineArn=STATE_MACHINE_ARN,
        name=f"{experiment_id}-{uuid.uuid4().hex[:8]}",
        input=json.dumps({
            "experiment_id": experiment_id,
            "as_of_date": as_of_date_str,
            "check_dates": check_dates,
        }),
    )
    return get_experiment(experiment_id)


def stop_experiment(experiment_id: str, body: dict) -> dict:
    final_state = body.get("final_state", "completed")
    if final_state not in ("completed", "stopped_early"):
        return _response(400, {"error": "final_state must be 'completed' or 'stopped_early'"})
    reason = body.get("reason", "manual stop")
    try:
        table.update_item(
            Key={"experiment_id": experiment_id},
            UpdateExpression="SET #state = :final_state, stopped_at = :now, updated_at = :now, stop_reason = :reason",
            ConditionExpression="#state = :running",
            ExpressionAttributeNames={"#state": "state"},
            ExpressionAttributeValues={
                ":final_state": final_state,
                ":running": "running",
                ":now": _now(),
                ":reason": reason,
            },
        )
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return _response(409, {"error": "experiment must be in 'running' state to stop"})
    return get_experiment(experiment_id)


def delete_experiment(experiment_id: str) -> dict:
    item = table.get_item(Key={"experiment_id": experiment_id}).get("Item")
    if not item:
        return _response(404, {"error": "not found"})
    if item["state"] != "draft":
        return _response(409, {"error": f"cannot delete experiment in state '{item['state']}'; only draft experiments can be deleted"})
    table.delete_item(Key={"experiment_id": experiment_id})
    return _response(204, {})


def handler(event, context):
    method = event["httpMethod"]
    resource = event["resource"]
    path_params = event.get("pathParameters") or {}
    experiment_id = path_params.get("id")
    body = json.loads(event["body"], parse_float=Decimal) if event.get("body") else {}

    if resource == "/experiments" and method == "POST":
        return create_experiment(body)
    if resource == "/experiments" and method == "GET":
        return list_experiments()
    if resource == "/experiments/{id}" and method == "GET":
        return get_experiment(experiment_id)
    if resource == "/experiments/{id}" and method == "PATCH":
        return update_experiment(experiment_id, body)
    if resource == "/experiments/{id}" and method == "DELETE":
        return delete_experiment(experiment_id)
    if resource == "/experiments/{id}/start" and method == "POST":
        return start_experiment(experiment_id, body)
    if resource == "/experiments/{id}/stop" and method == "POST":
        return stop_experiment(experiment_id, body)

    return _response(404, {"error": "route not found"})
