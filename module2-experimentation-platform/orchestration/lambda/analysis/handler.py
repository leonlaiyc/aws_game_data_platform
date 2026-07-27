"""Step 4: effect analysis, reading ONLY from gold_player_features (the
feature registry) joined against this experiment's assignments - never
recomputing player aggregates from Bronze/Silver directly.

Uses the last day the experiment was actually observed: the first
breached day if monitoring caught one, otherwise the last planned check
date (or as_of_date if the monitoring window was empty).
"""
import math
import os

import boto3
from athena_utils import run_athena_query, fetch_all_rows
from dynamo_utils import now_iso, to_decimal

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["EXPERIMENTS_TABLE_NAME"])


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _group_stats(experiment_id: str, metric: str, analysis_date: str) -> dict:
    sql = f"""
    SELECT ea.variant, COUNT(*) AS n, AVG(pf.{metric}) AS mean, VARIANCE(pf.{metric}) AS variance
    FROM gold_player_features pf
    JOIN gold_experiment_assignments ea ON ea.player_id = pf.player_id
    WHERE ea.experiment_id = '{experiment_id}' AND pf.snapshot_date = '{analysis_date}'
    GROUP BY ea.variant
    """
    rows = fetch_all_rows(run_athena_query(sql))
    return {
        r["variant"]: {
            "n": int(r["n"]),
            "mean": float(r["mean"]) if r["mean"] is not None else 0.0,
            "variance": float(r["variance"]) if r["variance"] is not None else 0.0,
        }
        for r in rows
    }


def handler(event, context):
    experiment_id = event["experiment_id"]
    experiment = event["assignment"]["experiment"]
    oec_metric = experiment["oec_metric"]
    guardrail_metrics = experiment.get("guardrail_metrics", [])
    monitoring_results = event.get("monitoring_results", [])

    breach = next((r for r in monitoring_results if r.get("breached")), None)
    if breach:
        analysis_date = breach["check_date"]
    elif monitoring_results:
        analysis_date = monitoring_results[-1]["check_date"]
    else:
        analysis_date = event["as_of_date"]

    oec_stats = _group_stats(experiment_id, oec_metric, analysis_date)
    control = oec_stats.get("control", {"n": 0, "mean": 0.0, "variance": 0.0})
    treatment = oec_stats.get("treatment", {"n": 0, "mean": 0.0, "variance": 0.0})

    lift_pct = ((treatment["mean"] - control["mean"]) / control["mean"] * 100) if control["mean"] else None
    se = math.sqrt(
        (treatment["variance"] / treatment["n"] if treatment["n"] else 0.0)
        + (control["variance"] / control["n"] if control["n"] else 0.0)
    )
    z_score = (treatment["mean"] - control["mean"]) / se if se > 0 else 0.0
    p_value = 2 * (1 - _norm_cdf(abs(z_score)))

    guardrail_status = []
    for g in guardrail_metrics:
        stats = _group_stats(experiment_id, g["metric"], analysis_date)
        t = stats.get("treatment", {"mean": 0.0})
        threshold = float(g["threshold"])
        breached = (g["direction"] == "min" and t["mean"] < threshold) or (g["direction"] == "max" and t["mean"] > threshold)
        guardrail_status.append({
            "metric": g["metric"],
            "treatment_mean": round(t["mean"], 4),
            "threshold": threshold,
            "direction": g["direction"],
            "status": "breached" if breached else "ok",
        })

    analysis_result = {
        "analysis_date": analysis_date,
        "oec_metric": oec_metric,
        "control_n": control["n"],
        "treatment_n": treatment["n"],
        "control_mean": round(control["mean"], 4),
        "treatment_mean": round(treatment["mean"], 4),
        "lift_pct": round(lift_pct, 2) if lift_pct is not None else None,
        "z_score": round(z_score, 4),
        "p_value": round(p_value, 6),
        "significant": p_value < 0.05,
        "guardrail_status": guardrail_status,
    }

    table.update_item(
        Key={"experiment_id": experiment_id},
        UpdateExpression="SET analysis_result = :ar, updated_at = :now",
        ExpressionAttributeValues={":ar": to_decimal(analysis_result), ":now": now_iso()},
    )

    return analysis_result
