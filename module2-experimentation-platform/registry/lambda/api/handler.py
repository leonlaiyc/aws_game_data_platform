"""CRUD API for the experiment registry.

State machine: draft -> running -> (stopped_early | completed) -> analyzed.
This Lambda only handles the human/API-driven transitions (create, edit
while draft, manual start/stop, delete while draft). The automated
transitions - SRM result, guardrail auto-stop, analysis, readout - are
written directly to DynamoDB by the Step Functions orchestration
(module2-experimentation-platform/orchestration), not through this API.
"""
import hashlib
import json
import os
import re
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
dynamodb_client = boto3.client("dynamodb")
table = dynamodb.Table(os.environ["EXPERIMENTS_TABLE_NAME"])
exposures_table = dynamodb.Table(os.environ["EXPOSURES_TABLE_NAME"])
serializer = TypeSerializer()
sfn = boto3.client("stepfunctions")
STATE_MACHINE_ARN = os.environ["ORCHESTRATION_STATE_MACHINE_ARN"]
OPERATOR_ROLE_NAME = os.environ.get("OPERATOR_PRINCIPAL_PATTERN", "")
ALLOWED_CLIENT_SITES = {
    site.strip() for site in os.environ.get(
        "ALLOWED_CLIENT_SITES", "site_a,site_b,site_c"
    ).split(",") if site.strip()
}

REQUIRED_CREATE_FIELDS = ["name", "game_id", "client_site_id", "variants", "oec_metric"]
UPDATABLE_DRAFT_FIELDS = {"name", "audience", "variants", "oec_metric", "guardrail_metrics", "related_experiment_id"}
OPTIONAL_CREATE_FIELDS = {"audience", "guardrail_metrics", "related_experiment_id"}
ALLOWED_METRICS = {
    "sessions_7d",
    "ggr_usd_7d",
    "bet_amount_usd_7d",
    "withdrawal_to_deposit_ratio_7d",
    "bonus_claims_30d",
}
_ANALYST_ROLE_RE = re.compile(r"aurora-games-analyst-(site_[a-z0-9_]+)")
_SAFE_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
_SAFE_EVENT_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")
EXPOSURE_TTL_DAYS = 180


class ScopeResolutionError(Exception):
    """The authenticated principal is not mapped to a registry entitlement."""


def _role_name(user_arn: str) -> str:
    """Extract an exact IAM/STS role name instead of substring-matching an ARN."""
    resource = user_arn.split(":", 5)[-1] if ":" in user_arn else ""
    if resource.startswith("assumed-role/"):
        parts = resource.split("/", 2)
        return parts[1] if len(parts) >= 2 else ""
    if resource.startswith("role/"):
        return resource.rsplit("/", 1)[-1]
    return ""


def _caller_scope(event) -> str | None:
    """Return one client site for an analyst, or None for the operator.

    The request body is deliberately not consulted. An authenticated role that
    is neither the exact operator role nor an exact analyst role fails closed.
    """
    arn = (event.get("requestContext", {}).get("identity", {}) or {}).get("userArn") or ""
    role_name = _role_name(arn)
    if OPERATOR_ROLE_NAME and role_name == OPERATOR_ROLE_NAME:
        return None
    match = _ANALYST_ROLE_RE.fullmatch(role_name)
    if match and match.group(1) in ALLOWED_CLIENT_SITES:
        return match.group(1)
    raise ScopeResolutionError(
        f"caller identity is not mapped to an experiment-registry scope: {arn or '<none>'}"
    )


def _is_visible(item: dict, caller_site: str | None) -> bool:
    return caller_site is None or item.get("client_site_id") == caller_site


def _validate_variants(variants) -> str | None:
    if not isinstance(variants, list) or len(variants) != 2:
        return "variants must contain exactly control and treatment"
    if any(set(v) - {"name", "weight"} for v in variants if isinstance(v, dict)):
        return "variant objects may contain only name and weight"
    names = [v.get("name") for v in variants if isinstance(v, dict)]
    if names != ["control", "treatment"]:
        return "variants must be ordered as control then treatment"
    try:
        weights = [Decimal(str(v["weight"])) for v in variants]
    except (KeyError, TypeError, ValueError, ArithmeticError):
        return "each variant requires a numeric weight"
    if any(not weight.is_finite() for weight in weights):
        return "variant weights must be finite"
    if any(weight <= 0 for weight in weights) or sum(weights) != Decimal("1"):
        return "variant weights must be positive and sum to 1"
    return None


def _validate_guardrails(guardrails) -> str | None:
    if not isinstance(guardrails, list):
        return "guardrail_metrics must be a list"
    for guardrail in guardrails:
        if not isinstance(guardrail, dict):
            return "each guardrail must be an object"
        if set(guardrail) - {"metric", "direction", "threshold"}:
            return "guardrail objects may contain only metric, direction, and threshold"
        if guardrail.get("metric") not in ALLOWED_METRICS:
            return f"unsupported guardrail metric: {guardrail.get('metric')!r}"
        if guardrail.get("direction") not in {"min", "max"}:
            return "guardrail direction must be 'min' or 'max'"
        try:
            threshold = Decimal(str(guardrail["threshold"]))
        except (KeyError, TypeError, ValueError, ArithmeticError):
            return "guardrail threshold must be numeric"
        if not threshold.is_finite():
            return "guardrail threshold must be finite"
    return None


def _validate_payload(body: dict, *, partial: bool = False) -> str | None:
    if not isinstance(body, dict):
        return "request body must be a JSON object"

    if not partial:
        missing = [field for field in REQUIRED_CREATE_FIELDS if field not in body]
        if missing:
            return f"missing required fields: {missing}"
        allowed = set(REQUIRED_CREATE_FIELDS) | OPTIONAL_CREATE_FIELDS
        unknown = set(body) - allowed
        if unknown:
            return f"unsupported create fields: {sorted(unknown)}"

    if "name" in body and (
        not isinstance(body["name"], str)
        or not body["name"].strip()
        or len(body["name"]) > 120
    ):
        return "name must be a non-empty string of at most 120 characters"
    if "client_site_id" in body and body["client_site_id"] not in ALLOWED_CLIENT_SITES:
        return f"unsupported client_site_id: {body['client_site_id']!r}"
    if "game_id" in body and not _SAFE_IDENTIFIER_RE.fullmatch(str(body["game_id"])):
        return "game_id must be a safe identifier"
    if "oec_metric" in body and body["oec_metric"] not in ALLOWED_METRICS:
        return f"unsupported oec_metric: {body['oec_metric']!r}"
    if "related_experiment_id" in body:
        related = body["related_experiment_id"]
        if related is not None and not _SAFE_IDENTIFIER_RE.fullmatch(str(related)):
            return "related_experiment_id must be a safe identifier"
    if "variants" in body:
        error = _validate_variants(body["variants"])
        if error:
            return error
    if "guardrail_metrics" in body:
        error = _validate_guardrails(body["guardrail_metrics"])
        if error:
            return error
    if "audience" in body:
        audience = body["audience"]
        if not isinstance(audience, dict):
            return "audience must be an object"
        unknown = set(audience) - {"client_site_id"}
        if unknown:
            return f"unsupported audience fields: {sorted(unknown)}"
        audience_site = audience.get("client_site_id")
        if audience_site is not None and audience_site not in ALLOWED_CLIENT_SITES:
            return f"unsupported audience client_site_id: {audience_site!r}"
        experiment_site = body.get("client_site_id")
        if experiment_site is not None and audience_site is not None and audience_site != experiment_site:
            return "audience client_site_id must match the experiment client_site_id"
    return None


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _derive_seed(experiment_id: str) -> int:
    # Deterministic (not random) on purpose: reproducible from experiment_id
    # alone, so anything that needs to know the assignment split in advance
    # (e.g. demo data setup) can replicate it without an extra round-trip.
    return int(hashlib.md5(experiment_id.encode()).hexdigest(), 16) % (2**31 - 1) + 1


def _assign_variant(
    experiment_id: str, seed: int, player_id: str, variants: list
) -> str:
    """The product path uses the same deterministic assignment as the batch
    eligibility snapshot, so retries and multiple game servers cannot move a
    player between variants."""
    digest = hashlib.md5(
        f"{experiment_id}:{seed}:{player_id}".encode()
    ).hexdigest()
    bucket = int(digest, 16) % 10000
    cumulative = 0.0
    for variant in variants:
        cumulative += float(variant["weight"]) * 10000
        if bucket < cumulative:
            return variant["name"]
    return variants[-1]["name"]


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


def _exposure_decision(item: dict, *, idempotent: bool) -> dict:
    return _response(200 if idempotent else 201, {
        "decision": "EXPOSE",
        "experiment_id": item["experiment_id"],
        "event_id": item["event_id"],
        "player_id": item["player_id"],
        "variant": item["variant"],
        "recorded": True,
        "idempotent_replay": idempotent,
        "exposed_at": item["exposed_at"],
    })


def _do_not_expose(item: dict, reason: str) -> dict:
    """A stopped experiment fails safe to the existing product experience.

    This is a 200 decision response, not an infrastructure error: game code
    can deterministically show the control behavior without retry storms.
    """
    return _response(200, {
        "decision": "DO_NOT_EXPOSE",
        "experiment_id": item["experiment_id"],
        "fallback_variant": "control",
        "recorded": False,
        "reason": reason,
        "experiment_state": item.get("state"),
    })


def record_exposure(
    experiment_id: str, body: dict, caller_site: str | None
) -> dict:
    if not isinstance(body, dict):
        return _response(400, {"error": "request body must be a JSON object"})
    unknown = set(body) - {"event_id", "player_id"}
    if unknown:
        return _response(
            400, {"error": f"unsupported exposure fields: {sorted(unknown)}"}
        )
    event_id, player_id = body.get("event_id"), body.get("player_id")
    if not isinstance(event_id, str) or not _SAFE_EVENT_ID_RE.fullmatch(event_id):
        return _response(400, {"error": "event_id must be a safe identifier"})
    if not isinstance(player_id, str) or not _SAFE_EVENT_ID_RE.fullmatch(player_id):
        return _response(400, {"error": "player_id must be a safe identifier"})

    experiment = table.get_item(
        Key={"experiment_id": experiment_id}, ConsistentRead=True
    ).get("Item")
    if not experiment or not _is_visible(experiment, caller_site):
        return _response(404, {"error": "not found"})

    key = {"experiment_id": experiment_id, "event_id": event_id}
    existing = exposures_table.get_item(Key=key, ConsistentRead=True).get("Item")
    if existing:
        if existing.get("player_id") != player_id:
            return _response(
                409, {"error": "event_id is already bound to another player"}
            )
        return _exposure_decision(existing, idempotent=True)

    if experiment.get("state") != "running":
        return _do_not_expose(experiment, "experiment_not_running")
    if experiment.get("allocation_enabled") is not True:
        return _do_not_expose(experiment, "allocation_kill_switch_disabled")

    exposed_at = _now()
    exposure = {
        **key,
        "player_id": player_id,
        "client_site_id": experiment["client_site_id"],
        "game_id": experiment["game_id"],
        "variant": _assign_variant(
            experiment_id,
            int(experiment["assignment_seed"]),
            player_id,
            experiment["variants"],
        ),
        "exposed_at": exposed_at,
        "recorded_at": exposed_at,
        "expires_at": int(time.time()) + EXPOSURE_TTL_DAYS * 86400,
    }

    # The allocation check and immutable event insert are one transaction.
    # Therefore an hourly guardrail stop racing this request cannot return a
    # treatment decision after the kill switch has committed.
    try:
        dynamodb_client.transact_write_items(
            TransactItems=[
                {
                    "ConditionCheck": {
                        "TableName": table.name,
                        "Key": {
                            "experiment_id": serializer.serialize(experiment_id)
                        },
                        "ConditionExpression": (
                            "#state = :running AND allocation_enabled = :enabled"
                        ),
                        "ExpressionAttributeNames": {"#state": "state"},
                        "ExpressionAttributeValues": {
                            ":running": serializer.serialize("running"),
                            ":enabled": serializer.serialize(True),
                        },
                    }
                },
                {
                    "Put": {
                        "TableName": exposures_table.name,
                        "Item": {
                            name: serializer.serialize(value)
                            for name, value in exposure.items()
                        },
                        "ConditionExpression": (
                            "attribute_not_exists(experiment_id) "
                            "AND attribute_not_exists(event_id)"
                        ),
                    }
                },
            ]
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "TransactionCanceledException":
            raise
        # A client retry may have lost the conditional race to its own first
        # request. Return that immutable decision instead of making the caller
        # distinguish a harmless replay from a real allocation stop.
        existing = exposures_table.get_item(
            Key=key, ConsistentRead=True
        ).get("Item")
        if existing and existing.get("player_id") == player_id:
            return _exposure_decision(existing, idempotent=True)
        current = table.get_item(
            Key={"experiment_id": experiment_id}, ConsistentRead=True
        ).get("Item") or experiment
        if (
            current.get("state") != "running"
            or current.get("allocation_enabled") is not True
        ):
            return _do_not_expose(current, "allocation_changed_during_request")
        return _response(409, {"error": "exposure event_id conflict"})

    return _exposure_decision(exposure, idempotent=False)


def create_experiment(body: dict, caller_site: str | None) -> dict:
    error = _validate_payload(body)
    if error:
        return _response(400, {"error": error})

    requested_site = body["client_site_id"]
    if caller_site is not None and requested_site != caller_site:
        return _response(403, {"error": "cannot create an experiment for another client site"})
    audience_site = (body.get("audience") or {}).get("client_site_id", requested_site)
    if audience_site != requested_site:
        return _response(400, {"error": "audience client_site_id must match the experiment client_site_id"})

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
        # Optional link to a prior iteration of the same underlying question
        # (e.g. "payout tweak v2" pointing back at "v1") - experiments are
        # rarely one-shot, so this lets Athena trace a whole series without
        # relying on naming conventions.
        "related_experiment_id": body.get("related_experiment_id"),
        "created_at": _now(),
        "updated_at": _now(),
    }
    table.put_item(Item=item)
    return _response(201, item)


def get_experiment(experiment_id: str, caller_site: str | None) -> dict:
    item = table.get_item(Key={"experiment_id": experiment_id}).get("Item")
    if not item or not _is_visible(item, caller_site):
        return _response(404, {"error": "not found"})
    return _response(200, item)


def list_experiments(caller_site: str | None) -> dict:
    items = []
    scan_args = {}
    while True:
        response = table.scan(**scan_args)
        items.extend(
            item for item in response.get("Items", [])
            if _is_visible(item, caller_site)
        )
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_args["ExclusiveStartKey"] = last_key
    return _response(200, {"experiments": items})


def update_experiment(experiment_id: str, body: dict, caller_site: str | None) -> dict:
    item = table.get_item(Key={"experiment_id": experiment_id}).get("Item")
    if not item or not _is_visible(item, caller_site):
        return _response(404, {"error": "not found"})
    if item["state"] != "draft":
        return _response(409, {"error": f"cannot edit experiment in state '{item['state']}'; only draft experiments can be edited"})

    updates = {k: v for k, v in body.items() if k in UPDATABLE_DRAFT_FIELDS}
    unknown = set(body) - UPDATABLE_DRAFT_FIELDS
    if unknown:
        return _response(400, {"error": f"unsupported update fields: {sorted(unknown)}"})
    if not updates:
        return _response(400, {"error": f"no updatable fields provided (allowed: {sorted(UPDATABLE_DRAFT_FIELDS)})"})
    error = _validate_payload(updates, partial=True)
    if error:
        return _response(400, {"error": error})
    audience_site = (updates.get("audience") or {}).get("client_site_id")
    if audience_site is not None and audience_site != item["client_site_id"]:
        return _response(400, {"error": "audience client_site_id must match the experiment client_site_id"})

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
    return get_experiment(experiment_id, caller_site)


def start_experiment(experiment_id: str, body: dict, caller_site: str | None) -> dict:
    item = table.get_item(Key={"experiment_id": experiment_id}).get("Item")
    if not item or not _is_visible(item, caller_site):
        return _response(404, {"error": "not found"})

    execution_mode = body.get("mode", "live")
    if execution_mode not in {"live", "replay"}:
        return _response(400, {"error": "mode must be 'live' or 'replay'"})
    unknown = set(body) - {"mode", "as_of_date", "duration_days"}
    if unknown:
        return _response(400, {"error": f"unsupported start fields: {sorted(unknown)}"})

    as_of_date_str = body.get("as_of_date")
    duration_days = body.get("duration_days")
    if execution_mode == "live" and not as_of_date_str:
        as_of_date_str = datetime.now(timezone.utc).date().isoformat()
    if not as_of_date_str or not duration_days:
        return _response(
            400,
            {
                "error": (
                    "start requires 'duration_days'; replay mode also requires "
                    "'as_of_date' (YYYY-MM-DD)"
                )
            },
        )

    try:
        as_of_date = date.fromisoformat(as_of_date_str)
        duration_days = int(duration_days)
    except (TypeError, ValueError):
        return _response(400, {"error": "as_of_date must be YYYY-MM-DD and duration_days must be an integer"})
    if not 1 <= duration_days <= 90:
        return _response(400, {"error": "duration_days must be between 1 and 90"})
    check_dates = [(as_of_date + timedelta(days=n)).isoformat() for n in range(1, duration_days + 1)]
    planned_end_at = (
        datetime.now(timezone.utc) + timedelta(days=duration_days)
    ).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    try:
        table.update_item(
            Key={"experiment_id": experiment_id},
            UpdateExpression=(
                "SET #state = :running, started_at = :now, updated_at = :now, "
                "assignment_seed = :seed, allocation_enabled = :enabled, "
                "execution_mode = :mode, planned_end_at = :end_at"
            ),
            ConditionExpression="#state = :draft",
            ExpressionAttributeNames={"#state": "state"},
            ExpressionAttributeValues={
                ":running": "running",
                ":draft": "draft",
                ":now": _now(),
                ":seed": _derive_seed(experiment_id),
                ":enabled": True,
                ":mode": execution_mode,
                ":end_at": planned_end_at,
            },
        )
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return _response(409, {"error": "experiment must be in 'draft' state to start"})

    try:
        execution = sfn.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=f"{experiment_id}-{uuid.uuid4().hex[:8]}",
            input=json.dumps({
                "experiment_id": experiment_id,
                "as_of_date": as_of_date_str,
                "check_dates": check_dates,
                "execution_mode": execution_mode,
                "planned_end_at": planned_end_at,
            }),
        )
    except Exception:
        # Do not leave the registry claiming "running" when no execution
        # exists. The conditional rollback avoids clobbering a concurrent stop.
        table.update_item(
            Key={"experiment_id": experiment_id},
            UpdateExpression=(
                "SET #state = :draft, updated_at = :now, "
                "allocation_enabled = :disabled REMOVE started_at, "
                "assignment_seed, execution_mode, planned_end_at"
            ),
            ConditionExpression="#state = :running",
            ExpressionAttributeNames={"#state": "state"},
            ExpressionAttributeValues={
                ":draft": "draft",
                ":running": "running",
                ":now": _now(),
                ":disabled": False,
            },
        )
        raise
    try:
        table.update_item(
            Key={"experiment_id": experiment_id},
            UpdateExpression="SET execution_arn = :arn, updated_at = :now",
            ConditionExpression="#state = :running",
            ExpressionAttributeNames={"#state": "state"},
            ExpressionAttributeValues={":arn": execution["executionArn"], ":running": "running", ":now": _now()},
        )
    except Exception:
        # The execution exists but the registry cannot point to it. Stop it
        # before rolling back the state; an untracked execution is worse than
        # a start request the caller can safely retry.
        sfn.stop_execution(
            executionArn=execution["executionArn"],
            cause="registry failed to persist execution ARN",
        )
        table.update_item(
            Key={"experiment_id": experiment_id},
            UpdateExpression=(
                "SET #state = :draft, updated_at = :now, "
                "allocation_enabled = :disabled REMOVE started_at, "
                "assignment_seed, execution_mode, planned_end_at"
            ),
            ConditionExpression="#state = :running",
            ExpressionAttributeNames={"#state": "state"},
            ExpressionAttributeValues={
                ":draft": "draft",
                ":running": "running",
                ":now": _now(),
                ":disabled": False,
            },
        )
        raise
    return get_experiment(experiment_id, caller_site)


def stop_experiment(experiment_id: str, body: dict, caller_site: str | None) -> dict:
    item = table.get_item(Key={"experiment_id": experiment_id}).get("Item")
    if not item or not _is_visible(item, caller_site):
        return _response(404, {"error": "not found"})

    final_state = body.get("final_state", "completed")
    if final_state not in ("completed", "stopped_early"):
        return _response(400, {"error": "final_state must be 'completed' or 'stopped_early'"})
    reason = body.get("reason", "manual stop")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        return _response(400, {"error": "reason must be a non-empty string of at most 500 characters"})
    if item.get("state") != "running":
        return _response(409, {"error": "experiment must be in 'running' state to stop"})
    execution_arn = item.get("execution_arn")
    if execution_arn:
        try:
            sfn.stop_execution(executionArn=execution_arn, cause=f"manual stop: {reason}")
        except sfn.exceptions.ExecutionDoesNotExist:
            pass
    try:
        table.update_item(
            Key={"experiment_id": experiment_id},
            UpdateExpression=(
                "SET #state = :final_state, stopped_at = :now, "
                "updated_at = :now, stop_reason = :reason, "
                "allocation_enabled = :disabled"
            ),
            ConditionExpression="#state = :running",
            ExpressionAttributeNames={"#state": "state"},
            ExpressionAttributeValues={
                ":final_state": final_state,
                ":running": "running",
                ":now": _now(),
                ":reason": reason,
                ":disabled": False,
            },
        )
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return _response(409, {"error": "experiment must be in 'running' state to stop"})
    return get_experiment(experiment_id, caller_site)


def delete_experiment(experiment_id: str, caller_site: str | None) -> dict:
    item = table.get_item(Key={"experiment_id": experiment_id}).get("Item")
    if not item or not _is_visible(item, caller_site):
        return _response(404, {"error": "not found"})
    if item["state"] != "draft":
        return _response(409, {"error": f"cannot delete experiment in state '{item['state']}'; only draft experiments can be deleted"})
    table.delete_item(Key={"experiment_id": experiment_id})
    return _response(204, {})


def handler(event, context):
    try:
        caller_site = _caller_scope(event)
    except ScopeResolutionError as error:
        return _response(403, {"error": str(error)})

    method = event["httpMethod"]
    resource = event["resource"]
    path_params = event.get("pathParameters") or {}
    experiment_id = path_params.get("id")
    try:
        body = json.loads(event["body"], parse_float=Decimal) if event.get("body") else {}
    except (json.JSONDecodeError, TypeError):
        return _response(400, {"error": "request body must be valid JSON"})

    if resource == "/experiments" and method == "POST":
        return create_experiment(body, caller_site)
    if resource == "/experiments" and method == "GET":
        return list_experiments(caller_site)
    if resource == "/experiments/{id}" and method == "GET":
        return get_experiment(experiment_id, caller_site)
    if resource == "/experiments/{id}" and method == "PATCH":
        return update_experiment(experiment_id, body, caller_site)
    if resource == "/experiments/{id}" and method == "DELETE":
        return delete_experiment(experiment_id, caller_site)
    if resource == "/experiments/{id}/start" and method == "POST":
        return start_experiment(experiment_id, body, caller_site)
    if resource == "/experiments/{id}/stop" and method == "POST":
        return stop_experiment(experiment_id, body, caller_site)
    if resource == "/experiments/{id}/exposures" and method == "POST":
        return record_exposure(experiment_id, body, caller_site)

    return _response(404, {"error": "route not found"})
