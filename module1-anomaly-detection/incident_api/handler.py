"""IAM-protected incident status API for the anomaly monitoring console."""

import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import unquote

import boto3


table = boto3.resource("dynamodb").Table(os.environ["INCIDENTS_TABLE_NAME"])
OPERATOR_PRINCIPAL_PATTERN = os.environ.get("OPERATOR_PRINCIPAL_PATTERN", "")
VALID_STATUS = {"DETECTED", "INVESTIGATING", "RESOLVED"}
VALID_TRANSITIONS = {
    "DETECTED": {"INVESTIGATING"},
    "INVESTIGATING": {"RESOLVED"},
    "RESOLVED": set(),
}


def _json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=_json_default),
    }


def _role_name(event: dict) -> str:
    arn = (
        (event.get("requestContext", {}).get("identity", {}) or {}).get("userArn")
        or ""
    )
    resource = arn.split(":", 5)[-1] if ":" in arn else ""
    if resource.startswith("assumed-role/"):
        parts = resource.split("/", 2)
        return parts[1] if len(parts) >= 2 else ""
    if resource.startswith("role/"):
        return resource.rsplit("/", 1)[-1]
    return ""


def _authorised(event: dict) -> bool:
    return bool(OPERATOR_PRINCIPAL_PATTERN) and _role_name(event) == OPERATOR_PRINCIPAL_PATTERN


def _parse_body(event: dict) -> dict | None:
    try:
        body = json.loads(event["body"]) if isinstance(event.get("body"), str) else event.get("body")
    except (json.JSONDecodeError, TypeError):
        return None
    return body if isinstance(body, dict) else None


def handler(event, context):
    if not _authorised(event):
        return _response(403, {"error": "operator identity required"})

    method = event.get("httpMethod", "GET")
    if method == "GET":
        items = table.scan(Limit=100).get("Items", [])
        items.sort(key=lambda item: item.get("detected_at", ""), reverse=True)
        return _response(200, {"incidents": items})

    incident_id = unquote((event.get("pathParameters") or {}).get("incident_id") or "")
    body = _parse_body(event)
    requested = body.get("status") if body else None
    if not incident_id or requested not in VALID_STATUS:
        return _response(400, {"error": "incident_id and a valid status are required"})

    current = table.get_item(Key={"incident_id": incident_id}, ConsistentRead=True).get("Item")
    if not current:
        return _response(404, {"error": "incident not found"})
    previous = current.get("status")
    if requested not in VALID_TRANSITIONS.get(previous, set()):
        return _response(409, {"error": f"invalid transition: {previous} -> {requested}"})

    now = datetime.now(timezone.utc).isoformat()
    response = table.update_item(
        Key={"incident_id": incident_id},
        UpdateExpression="SET #status = :status, updated_at = :updated_at, updated_by = :updated_by",
        ConditionExpression="#status = :previous",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":status": requested,
            ":previous": previous,
            ":updated_at": now,
            ":updated_by": _role_name(event),
        },
        ReturnValues="ALL_NEW",
    )
    return _response(200, {"incident": response["Attributes"]})
