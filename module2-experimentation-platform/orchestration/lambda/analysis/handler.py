"""Step 4: effect analysis, reading ONLY from gold_player_features (the
feature registry) joined against this experiment's assignments - never
recomputing player aggregates from Bronze/Silver directly.

Uses the last day the experiment was actually observed: the first
breached day if monitoring caught one, otherwise the last planned check
date (or as_of_date if the monitoring window was empty).

Also emits `flags`: deterministic, rule-based caveats (imbalanced groups,
tiny samples, a guardrail that passed but is close, a suspiciously large
effect, wide uncertainty). This is the same "code owns correctness"
principle as the numbers themselves - readout's Bedrock call is required
to address every flag here, not left to decide on its own whether a
caveat is worth mentioning. See orchestration/README.md for the full
rationale.
"""
import math
import os

import boto3
from athena_utils import run_athena_query, fetch_all_rows
from dynamo_utils import now_iso, to_decimal

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["EXPERIMENTS_TABLE_NAME"])

# Thresholds below are deliberately simple and documented here rather than
# tuned from historical variance (which we don't have at this project's
# scale) - a production system would calibrate these per-metric.
SAMPLE_IMBALANCE_MIN_MAX_RATIO = 0.7  # min(n)/max(n) below this, even if SRM passed the designed-ratio test
SMALL_SAMPLE_FLOOR = 100              # either arm below this: effect estimate is unstable
LARGE_EFFECT_PCT = 100.0              # |lift| beyond this more often signals a setup issue than a real effect
NEAR_THRESHOLD_SE_MULTIPLIER = 1.0    # "passed but close" = within 1 standard error of the breach point


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


def _compute_flags(control: dict, treatment: dict, lift_pct, diff: float, se: float, guardrail_detail: list) -> list:
    flags = []

    n_min, n_max = sorted([control["n"], treatment["n"]])
    if n_max > 0 and n_min / n_max < SAMPLE_IMBALANCE_MIN_MAX_RATIO:
        flags.append({
            "code": "SAMPLE_IMBALANCE",
            "severity": "warning",
            "message": "Control and treatment group sizes are notably unequal, which can bias the "
                       "effect estimate even though the randomization itself passed its integrity check.",
            "evidence": {"control_n": control["n"], "treatment_n": treatment["n"],
                         "ratio": round(n_min / n_max, 3), "threshold_ratio": SAMPLE_IMBALANCE_MIN_MAX_RATIO},
        })

    if control["n"] < SMALL_SAMPLE_FLOOR or treatment["n"] < SMALL_SAMPLE_FLOOR:
        flags.append({
            "code": "SMALL_SAMPLE",
            "severity": "warning",
            "message": "One or both groups are small, so the effect estimate may be unstable.",
            "evidence": {"control_n": control["n"], "treatment_n": treatment["n"], "floor": SMALL_SAMPLE_FLOOR},
        })

    if lift_pct is not None and abs(lift_pct) > LARGE_EFFECT_PCT:
        flags.append({
            "code": "SUSPICIOUSLY_LARGE_EFFECT",
            "severity": "warning",
            "message": "The measured effect size is unusually large for this kind of change, which more "
                       "often signals a data or setup issue than a genuine effect - worth verifying before acting.",
            "evidence": {"lift_pct": lift_pct, "threshold_pct": LARGE_EFFECT_PCT},
        })

    if se > 0:
        half_width = 1.96 * se
        if half_width > abs(diff):
            flags.append({
                "code": "WIDE_UNCERTAINTY",
                "severity": "info",
                "message": "The uncertainty around this estimate is wide relative to its size.",
                "evidence": {
                    "diff": round(diff, 4),
                    "ci_95_lower": round(diff - half_width, 4),
                    "ci_95_upper": round(diff + half_width, 4),
                },
            })

    for g in guardrail_detail:
        if g["status"] == "breached" or g["se"] <= 0:
            continue
        distance = (g["treatment_mean"] - g["threshold"]) if g["direction"] == "min" else (g["threshold"] - g["treatment_mean"])
        if 0 <= distance < NEAR_THRESHOLD_SE_MULTIPLIER * g["se"]:
            flags.append({
                "code": "GUARDRAIL_NEAR_THRESHOLD",
                "severity": "info",
                "message": f"The '{g['metric']}' guardrail passed but is close to its threshold.",
                "evidence": {"metric": g["metric"], "treatment_mean": g["treatment_mean"],
                             "threshold": g["threshold"], "margin_in_se": round(distance / g["se"], 3)},
            })

    return flags


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

    diff = treatment["mean"] - control["mean"]
    lift_pct = (diff / control["mean"] * 100) if control["mean"] else None
    se = math.sqrt(
        (treatment["variance"] / treatment["n"] if treatment["n"] else 0.0)
        + (control["variance"] / control["n"] if control["n"] else 0.0)
    )
    z_score = diff / se if se > 0 else 0.0
    p_value = 2 * (1 - _norm_cdf(abs(z_score)))

    guardrail_status = []
    guardrail_detail = []  # carries variance/se too, for flag computation below - not persisted as-is
    for g in guardrail_metrics:
        stats = _group_stats(experiment_id, g["metric"], analysis_date)
        t = stats.get("treatment", {"mean": 0.0, "variance": 0.0, "n": 0})
        threshold = float(g["threshold"])
        breached = (g["direction"] == "min" and t["mean"] < threshold) or (g["direction"] == "max" and t["mean"] > threshold)
        entry = {
            "metric": g["metric"],
            "treatment_mean": round(t["mean"], 4),
            "threshold": threshold,
            "direction": g["direction"],
            "status": "breached" if breached else "ok",
        }
        guardrail_status.append(entry)
        guardrail_detail.append({**entry, "se": math.sqrt(t["variance"] / t["n"]) if t["n"] else 0.0})

    flags = _compute_flags(control, treatment, lift_pct, diff, se, guardrail_detail)

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
        "flags": flags,
    }

    table.update_item(
        Key={"experiment_id": experiment_id},
        UpdateExpression="SET analysis_result = :ar, updated_at = :now",
        ExpressionAttributeValues={":ar": to_decimal(analysis_result), ":now": now_iso()},
    )

    return analysis_result
