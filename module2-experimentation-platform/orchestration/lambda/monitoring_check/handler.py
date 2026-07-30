"""SRM and guardrail monitoring while an experiment is running.

Live mode is driven hourly by EventBridge. It uses product-recorded exposure
events for SRM and analytical cohort membership, then atomically disables
allocation before alerting and stopping the waiting Step Functions execution.

Replay mode keeps the deterministic historical demo: the Step Functions Map
invokes the same guardrail code for each simulated date, using the batch
assignment snapshot because no product runtime exists in that scenario.
"""
import math
import os
import time

import boto3
from boto3.dynamodb.conditions import Attr, Key
from dynamo_utils import now_iso, to_decimal

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["EXPERIMENTS_TABLE_NAME"])
exposures_table = dynamodb.Table(os.environ["EXPOSURES_TABLE_NAME"])
sns = boto3.client("sns")
sfn = boto3.client("stepfunctions")
TOPIC_ARN = os.environ["ALERTS_TOPIC_ARN"]

SRM_P_VALUE_THRESHOLD = 0.01
MIN_EXPOSURES_FOR_SRM = 100


def _chi2_p_value_df1(chi2: float) -> float:
    return math.erfc(math.sqrt(chi2 / 2))


def _exposure_counts(experiment_id: str) -> dict:
    player_variants = {}
    query_args = {
        "KeyConditionExpression": Key("experiment_id").eq(experiment_id),
        "ProjectionExpression": "player_id, #variant",
        "ExpressionAttributeNames": {"#variant": "variant"},
        "ConsistentRead": True,
    }
    while True:
        response = exposures_table.query(**query_args)
        for item in response.get("Items", []):
            variant = item.get("variant")
            player_id = item.get("player_id")
            if variant and player_id:
                previous = player_variants.setdefault(player_id, variant)
                if previous != variant:
                    raise ValueError(
                        f"player {player_id} has inconsistent variants "
                        f"within experiment {experiment_id}"
                    )
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        query_args["ExclusiveStartKey"] = last_key
    counts = {}
    for variant in player_variants.values():
        counts[variant] = counts.get(variant, 0) + 1
    return counts


def _check_exposure_srm(experiment: dict) -> dict:
    counts = _exposure_counts(experiment["experiment_id"])
    total = sum(counts.values())
    result = {
        "source": "product_exposures",
        "observed": counts,
        "total_exposed": total,
        "minimum_exposures": MIN_EXPOSURES_FOR_SRM,
        "threshold": SRM_P_VALUE_THRESHOLD,
    }
    if total < MIN_EXPOSURES_FOR_SRM:
        return {**result, "status": "insufficient_sample", "passed": None}

    chi2 = 0.0
    expected = {}
    for variant in experiment["variants"]:
        expected_count = total * float(variant["weight"])
        expected[variant["name"]] = round(expected_count, 2)
        if expected_count > 0:
            chi2 += (
                counts.get(variant["name"], 0) - expected_count
            ) ** 2 / expected_count
    p_value = _chi2_p_value_df1(chi2)
    passed = p_value >= SRM_P_VALUE_THRESHOLD
    return {
        **result,
        "status": "passed" if passed else "breached",
        "passed": passed,
        "expected": expected,
        "chi2": round(chi2, 4),
        "p_value": round(p_value, 6),
    }


def _check_guardrails(
    experiment_id: str,
    check_date: str,
    guardrail_metrics: list,
    cohort_table: str,
) -> list:
    breaches = []
    for guardrail in guardrail_metrics:
        metric = guardrail["metric"]
        direction = guardrail["direction"]
        threshold = float(guardrail["threshold"])
        sql = f"""
        SELECT AVG(pf.{metric}) AS value
        FROM gold_player_features pf
        JOIN (
            SELECT DISTINCT player_id
            FROM {cohort_table}
            WHERE experiment_id = '{experiment_id}' AND variant = 'treatment'
        ) cohort ON cohort.player_id = pf.player_id
        WHERE pf.snapshot_date = '{check_date}'
        """
        rows = fetch_all_rows(run_athena_query(sql))
        value = (
            float(rows[0]["value"])
            if rows and rows[0].get("value") is not None
            else None
        )
        if value is None:
            continue
        breached = (
            direction == "min" and value < threshold
        ) or (
            direction == "max" and value > threshold
        )
        if breached:
            breaches.append({
                "metric": metric,
                "direction": direction,
                "threshold": threshold,
                "value": round(value, 4),
            })
    return breaches


# Imported below the pure helpers so unit tests can load and exercise SRM
# without needing the Lambda layer to be present in their normal sys.path.
from athena_utils import fetch_all_rows, run_athena_query  # noqa: E402


def _stop_waiting_execution(experiment: dict, reason: str) -> None:
    if experiment.get("execution_mode") != "live":
        return
    execution_arn = experiment.get("execution_arn")
    if not execution_arn:
        return
    try:
        sfn.stop_execution(executionArn=execution_arn, cause=reason[:256])
    except sfn.exceptions.ExecutionDoesNotExist:
        pass


def _auto_stop(
    experiment: dict,
    check_date: str,
    reason: str,
    monitoring_status: dict,
) -> bool:
    experiment_id = experiment["experiment_id"]
    try:
        table.update_item(
            Key={"experiment_id": experiment_id},
            UpdateExpression=(
                "SET #state = :stopped, stopped_at = :now, "
                "updated_at = :now, stop_reason = :reason, "
                "allocation_enabled = :disabled, "
                "monitoring_status = :monitoring_status"
            ),
            ConditionExpression="#state = :running",
            ExpressionAttributeNames={"#state": "state"},
            ExpressionAttributeValues={
                ":stopped": "stopped_early",
                ":running": "running",
                ":now": now_iso(),
                ":reason": reason,
                ":disabled": False,
                ":monitoring_status": to_decimal(monitoring_status),
            },
        )
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return False

    _stop_waiting_execution(experiment, reason)
    sns.publish(
        TopicArn=TOPIC_ARN,
        Subject=f"Experiment {experiment_id} auto-stopped",
        Message=(
            f"Experiment {experiment_id} was auto-stopped on {check_date}.\n\n"
            f"{reason}"
        ),
    )
    return True


def _persist_monitoring_status(experiment_id: str, status: dict) -> None:
    try:
        table.update_item(
            Key={"experiment_id": experiment_id},
            UpdateExpression=(
                "SET monitoring_status = :status, updated_at = :now"
            ),
            ConditionExpression="#state = :running",
            ExpressionAttributeNames={"#state": "state"},
            ExpressionAttributeValues={
                ":status": to_decimal(status),
                ":now": now_iso(),
                ":running": "running",
            },
        )
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        pass


def _check_experiment(
    experiment_id: str, check_date: str, guardrail_metrics: list
) -> dict:
    experiment = table.get_item(
        Key={"experiment_id": experiment_id}, ConsistentRead=True
    ).get("Item")
    if not experiment or experiment.get("state") != "running":
        return {
            "experiment_id": experiment_id,
            "check_date": check_date,
            "skipped": True,
            "reason": (
                "experiment state is "
                f"'{experiment.get('state') if experiment else 'missing'}', "
                "not running"
            ),
        }

    execution_mode = experiment.get("execution_mode", "replay")
    srm_result = None
    if execution_mode == "live":
        srm_result = _check_exposure_srm(experiment)
        if srm_result["passed"] is False:
            reason = (
                "exposure_srm_violation: "
                f"observed={srm_result['observed']} "
                f"expected={srm_result['expected']} "
                f"p_value={srm_result['p_value']} "
                f"(threshold {srm_result['threshold']})"
            )
            status = {
                "checked_at": now_iso(),
                "check_date": check_date,
                "execution_mode": execution_mode,
                "srm": srm_result,
                "guardrails": {"status": "not_run_due_to_srm"},
                "allocation_enabled": False,
            }
            transitioned = _auto_stop(
                experiment, check_date, reason, status
            )
            return {
                "experiment_id": experiment_id,
                "check_date": check_date,
                "breached": True,
                "breach_type": "exposure_srm",
                "transitioned": transitioned,
                "srm": srm_result,
            }

    cohort_table = (
        "gold_experiment_exposures"
        if execution_mode == "live"
        else "gold_experiment_assignments"
    )
    breaches = _check_guardrails(
        experiment_id,
        check_date,
        guardrail_metrics,
        cohort_table,
    )
    status = {
        "checked_at": now_iso(),
        "check_date": check_date,
        "execution_mode": execution_mode,
        "cohort_source": cohort_table,
        "srm": srm_result,
        "guardrails": {
            "status": "breached" if breaches else "passed",
            "breaches": breaches,
        },
        "allocation_enabled": not bool(breaches),
    }
    if not breaches:
        _persist_monitoring_status(experiment_id, status)
        return {
            "experiment_id": experiment_id,
            "check_date": check_date,
            "breached": False,
            "srm": srm_result,
            "cohort_source": cohort_table,
        }

    reason = "guardrail_breach: " + "; ".join(
        (
            f"{breach['metric']}={breach['value']} vs "
            f"{breach['direction']} threshold {breach['threshold']}"
        )
        for breach in breaches
    )
    transitioned = _auto_stop(experiment, check_date, reason, status)
    return {
        "experiment_id": experiment_id,
        "check_date": check_date,
        "breached": True,
        "breach_type": "guardrail",
        "transitioned": transitioned,
        "breaches": breaches,
        "srm": srm_result,
        "cohort_source": cohort_table,
    }


def _running_experiments() -> list:
    items = []
    scan_args = {"FilterExpression": Attr("state").eq("running")}
    while True:
        response = table.scan(**scan_args)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_args["ExclusiveStartKey"] = last_key
    return items


def handler(event, context):
    if event.get("scheduled"):
        today = time.strftime("%Y-%m-%d", time.gmtime())
        running = _running_experiments()
        results = [
            _check_experiment(
                item["experiment_id"],
                today,
                item.get("guardrail_metrics", []),
            )
            for item in running
        ]
        return {"checked": len(running), "results": results}

    return _check_experiment(
        event["experiment_id"],
        event["check_date"],
        event.get("guardrail_metrics", []),
    )
