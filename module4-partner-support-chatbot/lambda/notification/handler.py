"""Publish operator-approved partner operational notifications.

The default stack subscribes only an account-local SQS audit sink. It never
adds an email, SMS, webhook, or other external recipient without explicit
partner opt-in.
"""
import json
import os
import re
import uuid
from datetime import datetime, timezone

import boto3

sns = boto3.client("sns")
TOPIC_ARN = os.environ["NOTIFICATIONS_TOPIC_ARN"]
OPERATOR_ROLE_NAME = os.environ.get("OPERATOR_PRINCIPAL_PATTERN", "")

ALLOWED_TYPES = {"NEW_GAME", "MAINTENANCE"}
ALLOWED_SITES = {"site_a", "site_b", "site_c"}
ALLOWED_GAMES = {
    "game_01", "game_02", "game_03", "game_04",
    "game_05", "game_06", "game_07", "game_08",
}
_SECRET_PATTERNS = {
    "credential_assignment": re.compile(
        r"\b(?:api[_ -]?key|secret|token|password)\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
    "bearer_token": re.compile(r"\bBearer\s+\S+", re.IGNORECASE),
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "jwt": re.compile(
        r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"
    ),
}


def _role_name(user_arn: str) -> str:
    resource = user_arn.split(":", 5)[-1] if ":" in user_arn else ""
    if resource.startswith("assumed-role/"):
        parts = resource.split("/", 2)
        return parts[1] if len(parts) >= 2 else ""
    if resource.startswith("role/"):
        return resource.rsplit("/", 1)[-1]
    return ""


def _operator_authorised(event: dict) -> bool:
    arn = (
        (event.get("requestContext", {}).get("identity", {}) or {})
        .get("userArn")
        or ""
    )
    return bool(
        OPERATOR_ROLE_NAME
        and _role_name(arn) == OPERATOR_ROLE_NAME
    )


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _secret_matches(text: str) -> list[str]:
    return [
        code for code, pattern in _SECRET_PATTERNS.items()
        if pattern.search(text)
    ]


def _validate(body: dict) -> str | None:
    allowed_fields = {
        "notification_type",
        "title",
        "message",
        "effective_at",
        "client_site_ids",
        "affected_games",
    }
    unknown = set(body) - allowed_fields
    if unknown:
        return f"unsupported fields: {sorted(unknown)}"
    if body.get("notification_type") not in ALLOWED_TYPES:
        return f"notification_type must be one of {sorted(ALLOWED_TYPES)}"
    for field, limit in (("title", 120), ("message", 2000)):
        value = body.get(field)
        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value) > limit
        ):
            return f"{field} must be a non-empty string of at most {limit} characters"
    try:
        parsed = datetime.fromisoformat(
            str(body.get("effective_at", "")).replace("Z", "+00:00")
        )
        if parsed.tzinfo is None:
            return "effective_at must include a timezone"
    except ValueError:
        return "effective_at must be an ISO-8601 timestamp with timezone"
    sites = body.get("client_site_ids")
    if (
        not isinstance(sites, list)
        or not sites
        or len(sites) > len(ALLOWED_SITES)
        or not set(sites) <= ALLOWED_SITES
    ):
        return f"client_site_ids must be a non-empty subset of {sorted(ALLOWED_SITES)}"
    games = body.get("affected_games", [])
    if (
        not isinstance(games, list)
        or len(games) > len(ALLOWED_GAMES)
        or not set(games) <= ALLOWED_GAMES
    ):
        return f"affected_games must be a subset of {sorted(ALLOWED_GAMES)}"
    if body["notification_type"] == "NEW_GAME" and not games:
        return "NEW_GAME notifications require at least one affected game"
    matched = _secret_matches(f"{body['title']}\n{body['message']}")
    if matched:
        return (
            "notification contains credential-like material and was rejected: "
            f"{matched}"
        )
    return None


def handler(event, context):
    if not _operator_authorised(event):
        return _response(
            403, {"error": "only the exact operator role may publish notifications"}
        )
    try:
        body = (
            json.loads(event["body"])
            if isinstance(event.get("body"), str)
            else (event.get("body") or {})
        )
    except (json.JSONDecodeError, TypeError):
        body = None
    if not isinstance(body, dict):
        return _response(400, {"error": "request body must be a JSON object"})
    error = _validate(body)
    if error:
        return _response(400, {"error": error})

    notification = {
        "notification_id": f"NTF-{uuid.uuid4().hex[:10].upper()}",
        "notification_type": body["notification_type"],
        "title": body["title"].strip(),
        "message": body["message"].strip(),
        "effective_at": body["effective_at"],
        "client_site_ids": sorted(set(body["client_site_ids"])),
        "affected_games": sorted(set(body.get("affected_games", []))),
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    result = sns.publish(
        TopicArn=TOPIC_ARN,
        Subject=notification["title"][:100],
        Message=json.dumps(notification),
        MessageAttributes={
            "notification_type": {
                "DataType": "String",
                "StringValue": notification["notification_type"],
            },
            "client_site_ids": {
                "DataType": "String.Array",
                "StringValue": json.dumps(notification["client_site_ids"]),
            },
        },
    )
    return _response(202, {
        "status": "PUBLISHED",
        "sns_message_id": result["MessageId"],
        **notification,
    })
