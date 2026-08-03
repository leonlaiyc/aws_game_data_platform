"""Scheduled anomaly detection for hourly operational KPIs, daily business
KPIs, and mature retention cohorts.

Three invocation modes share the same publication boundary:
- Hourly scheduled (``{"scheduled": true, "cadence": "hourly"}``): reads
  precomputed same-hour baselines and control limits from Gold.
- Explicit daily (``{"client_site_id", "as_of_date"}``): retains the
  historical EWMA replay used by the original PoC.
- Weekly scheduled (``{"scheduled": true, "cadence": "weekly"}``): pools
  fully matured registration cohorts by calendar week, then checks D1/D7
  retention with a two-proportion z-score. D7 cohorts are not evaluated until
  seven days of outcomes exist, and partial calendar weeks are never compared
  with complete weeks.
- Explicit ({"client_site_id", "as_of_date"}): used by the demo to replay
  a specific historical daily KPI check.

Daily method: seed an EWMA baseline (and standard deviation) from the trailing
history window (excluding the day being checked), then flag the checked
day if it deviates from the EWMA baseline by more than K_SIGMA standard
deviations. This is a simplified EWMA control chart - a textbook EWMA
chart derives control limits from a recursive variance formula that
narrows over time; here the limits are a fixed multiple of the trailing
window's plain standard deviation, which is simpler to implement and
explain and is accurate enough at this project's data volume. Documented
as a deliberate simplification, not an oversight.
"""
import json
import math
import os
import time
from datetime import date, timedelta
from decimal import Decimal
from statistics import mean, pstdev

import boto3
from athena_utils import fetch_all_rows, run_athena_query

s3 = boto3.client("s3")
sns = boto3.client("sns")
dynamodb = boto3.resource("dynamodb")
BUCKET = os.environ["LAKE_BUCKET_NAME"]
ALERTS_TOPIC_ARN = os.environ["ALERTS_TOPIC_ARN"]
INCIDENTS_TABLE_NAME = os.environ.get("INCIDENTS_TABLE_NAME", "")
incidents = dynamodb.Table(INCIDENTS_TABLE_NAME) if INCIDENTS_TABLE_NAME else None

ALPHA = 0.3  # EWMA smoothing factor
K_SIGMA = 3.0  # flag when |actual - ewma| > K_SIGMA * trailing stdev
MIN_HISTORY_DAYS = 10  # skip the check if there isn't enough trailing history yet
WINDOW_DAYS = 21
METRICS = ["dau", "ggr_usd"]
PUBLICATION_MANIFEST_KEY = "manifests/published/gold_daily_kpi.json"
CONSUMPTION_MARKER_KEY = "manifests/consumed/data_anomaly.json"
RETENTION_CONSUMPTION_MARKER_KEY = "manifests/consumed/retention_anomaly.json"
HOURLY_PUBLICATION_MANIFEST_KEY = (
    "manifests/published/gold_hourly_monitoring_features.json"
)
HOURLY_CONSUMPTION_MARKER_KEY = "manifests/consumed/hourly_data_anomaly.json"
HOURLY_METRICS = ("active_users", "sessions", "processed_events")
MIN_HOURLY_BASELINE_POINTS = 30

RETENTION_METRICS = {
    "d1_retention_rate": "d1_retained",
    "d7_retention_rate": "d7_retained",
}
RETENTION_MATURITY_DAYS = 7
RETENTION_BASELINE_WEEKS = 6
RETENTION_MIN_BASELINE_WEEKS = 4
RETENTION_MIN_COHORT_SIZE = 50
RETENTION_Z_THRESHOLD = -2.0
RETENTION_MIN_ABSOLUTE_DROP = 0.08
RETENTION_DETECTOR_ID = "weekly_mature_cohort_retention"
RETENTION_DETECTOR_VERSION = "1.0"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _dynamodb_numbers(value):
    """Convert JSON-shaped float values to DynamoDB's native Decimal type."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, list):
        return [_dynamodb_numbers(item) for item in value]
    if isinstance(value, dict):
        return {key: _dynamodb_numbers(item) for key, item in value.items()}
    return value


def _ewma(series: list, alpha: float) -> float:
    e = series[0]
    for x in series[1:]:
        e = alpha * x + (1 - alpha) * e
    return e


def _discover_sites() -> list:
    rows = fetch_all_rows(run_athena_query("SELECT DISTINCT client_site_id FROM gold_daily_kpi"))
    return [r["client_site_id"] for r in rows]


def _publication_manifest() -> dict:
    """Read the build-success marker; never infer completeness from MAX(dt)."""
    obj = s3.get_object(Bucket=BUCKET, Key=PUBLICATION_MANIFEST_KEY)
    manifest = json.loads(obj["Body"].read())
    if manifest.get("table") != "gold_daily_kpi":
        raise ValueError(f"unexpected publication manifest: {manifest}")
    published_through = manifest.get("published_through")
    if not published_through or not manifest.get("published_at"):
        raise ValueError("gold_daily_kpi publication manifest is incomplete")
    return manifest


def _already_processed(
    publication: dict, marker_key: str = CONSUMPTION_MARKER_KEY
) -> bool:
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=marker_key)
    except s3.exceptions.NoSuchKey:
        return False
    marker = json.loads(obj["Body"].read())
    return marker.get("published_at") == publication["published_at"]


def _mark_processed(
    publication: dict,
    marker_key: str = CONSUMPTION_MARKER_KEY,
    **extra,
) -> None:
    s3.put_object(
        Bucket=BUCKET,
        Key=marker_key,
        Body=json.dumps({
            "table": publication["table"],
            "published_at": publication["published_at"],
            "published_through": publication["published_through"],
            "processed_at": _now_iso(),
            **extra,
        }).encode("utf-8"),
        ContentType="application/json",
    )


def _fetch_window(site: str, as_of_date: str) -> list:
    sql = f"""
    SELECT dt, dau, ggr_usd FROM gold_daily_kpi
    WHERE client_site_id = '{site}' AND dt <= '{as_of_date}'
    ORDER BY dt DESC
    LIMIT {WINDOW_DAYS}
    """
    rows = fetch_all_rows(run_athena_query(sql))
    rows.reverse()  # back to chronological order
    return rows


def _check_site(site: str, as_of_date: str) -> dict:
    rows = _fetch_window(site, as_of_date)
    if not rows or rows[-1]["dt"] != as_of_date:
        return {"client_site_id": site, "as_of_date": as_of_date, "skipped": "no data for as_of_date"}
    if len(rows) < MIN_HISTORY_DAYS + 1:
        return {"client_site_id": site, "as_of_date": as_of_date, "skipped": "insufficient trailing history"}

    history, today = rows[:-1], rows[-1]
    alerts = []
    for metric in METRICS:
        series = [float(r[metric]) for r in history]
        actual = float(today[metric])
        baseline = _ewma(series, ALPHA)
        sigma = pstdev(series)
        deviation = actual - baseline
        if sigma > 0 and abs(deviation) > K_SIGMA * sigma:
            alerts.append({
                "metric": metric,
                "actual": round(actual, 4),
                "ewma_baseline": round(baseline, 4),
                "sigma": round(sigma, 4),
                "deviation": round(deviation, 4),
                "k_sigma_threshold": K_SIGMA,
            })

    result = {"client_site_id": site, "as_of_date": as_of_date, "alerts": alerts}
    if alerts:
        _publish_alert(result)
    return result


def _publish_alert(result: dict):
    key = f"gold/anomaly_alerts/{result['client_site_id']}_{result['as_of_date']}.json"
    body = {**result, "detected_at": _now_iso()}
    s3.put_object(Bucket=BUCKET, Key=key, Body=json.dumps(body).encode("utf-8"), ContentType="application/json")

    lines = [f"- {a['metric']}: actual={a['actual']} vs EWMA baseline={a['ewma_baseline']} "
             f"(deviation={a['deviation']}, {a['k_sigma_threshold']}-sigma threshold={round(a['k_sigma_threshold'] * a['sigma'], 4)})"
             for a in result["alerts"]]
    sns.publish(
        TopicArn=ALERTS_TOPIC_ARN,
        Subject=f"Anomaly detected: {result['client_site_id']} on {result['as_of_date']}",
        Message=f"EWMA anomaly detection flagged {result['client_site_id']} on {result['as_of_date']}:\n\n"
                + "\n".join(lines),
        # Structured, non-breaking addition alongside the human-readable Message
        # above: module3-analytics-assistant's first_look_report subscribes to
        # this same topic and needs client_site_id/as_of_date without parsing
        # free text.
        MessageAttributes={
            # alert_type is the discriminator subscribers filter on; both
            # publishers on this topic now send it, and schema_version exists
            # so a future field change is additive rather than breaking.
            "alert_type": {"DataType": "String", "StringValue": "data_anomaly"},
            "schema_version": {"DataType": "String", "StringValue": "1"},
            "client_site_id": {"DataType": "String", "StringValue": result["client_site_id"]},
            "as_of_date": {"DataType": "String", "StringValue": result["as_of_date"]},
        },
    )


def _hourly_publication_manifest() -> dict:
    obj = s3.get_object(Bucket=BUCKET, Key=HOURLY_PUBLICATION_MANIFEST_KEY)
    manifest = json.loads(obj["Body"].read())
    if manifest.get("table") != "gold_hourly_monitoring_features":
        raise ValueError(f"unexpected hourly publication manifest: {manifest}")
    if not manifest.get("published_through") or not manifest.get("published_at"):
        raise ValueError("hourly monitoring publication manifest is incomplete")
    return manifest


def _discover_hourly_sites() -> list:
    rows = fetch_all_rows(run_athena_query(
        "SELECT DISTINCT client_site_id FROM gold_hourly_monitoring_features"
    ))
    return [row["client_site_id"] for row in rows]


def _fetch_hourly_feature(site: str, event_hour: str | None = None) -> dict | None:
    hour_filter = f"AND event_hour = TIMESTAMP '{event_hour}'" if event_hour else ""
    rows = fetch_all_rows(run_athena_query(f"""
        SELECT *
        FROM gold_hourly_monitoring_features
        WHERE client_site_id = '{site}' {hour_filter}
        ORDER BY event_hour DESC
        LIMIT 1
    """))
    return rows[0] if rows else None


def _publish_hourly_alert(result: dict) -> None:
    compact_hour = result["event_hour"].replace(" ", "T").replace(":00:00.000", "")
    key = f"gold/anomaly_alerts/{result['client_site_id']}_{compact_hour}.json"
    body = {**result, "detected_at": _now_iso(), "evidence_s3_key": key}
    encoded = json.dumps(body).encode("utf-8")
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=encoded,
        ContentType="application/json",
    )
    incident_id = f"{result['client_site_id']}#{compact_hour}"
    if incidents is not None:
        incidents.update_item(
            Key={"incident_id": incident_id},
            UpdateExpression=(
                "SET client_site_id = :site, event_hour = :event_hour, "
                "#status = if_not_exists(#status, :detected), "
                "detected_at = if_not_exists(detected_at, :detected_at), "
                "updated_at = if_not_exists(updated_at, :detected_at), "
                "evidence_s3_key = :evidence, alerts = :alerts"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":site": result["client_site_id"],
                ":event_hour": result["event_hour"],
                ":detected": "DETECTED",
                ":detected_at": body["detected_at"],
                ":evidence": key,
                ":alerts": _dynamodb_numbers(result["alerts"]),
            },
        )
    sns.publish(
        TopicArn=ALERTS_TOPIC_ARN,
        Subject=f"Hourly anomaly: {result['client_site_id']} at {compact_hour}",
        Message=encoded.decode("utf-8"),
        MessageAttributes={
            "alert_type": {
                "DataType": "String",
                "StringValue": "hourly_data_anomaly",
            },
            "schema_version": {"DataType": "String", "StringValue": "1"},
            "client_site_id": {
                "DataType": "String",
                "StringValue": result["client_site_id"],
            },
            "as_of_date": {
                "DataType": "String",
                "StringValue": result["event_hour"][:10],
            },
            "event_hour": {
                "DataType": "String",
                "StringValue": result["event_hour"],
            },
            "incident_id": {
                "DataType": "String",
                "StringValue": incident_id,
            },
        },
    )


def _check_hourly_site(site: str, event_hour: str | None = None) -> dict:
    feature = _fetch_hourly_feature(site, event_hour)
    if not feature:
        return {"client_site_id": site, "event_hour": event_hour, "skipped": "no hourly data"}
    result_hour = feature["event_hour"]
    baseline_points = int(feature.get("baseline_points") or 0)
    if baseline_points < MIN_HOURLY_BASELINE_POINTS:
        return {
            "client_site_id": site,
            "event_hour": result_hour,
            "skipped": "insufficient same-hour history",
            "baseline_points": baseline_points,
        }
    alerts = []
    for metric in HOURLY_METRICS:
        actual = float(feature[metric])
        baseline = float(feature[f"{metric}_baseline"])
        lower = float(feature[f"{metric}_lower_bound"])
        upper = float(feature[f"{metric}_upper_bound"])
        if actual < lower or actual > upper:
            alerts.append({
                "metric": metric,
                "actual": round(actual, 4),
                "baseline": round(baseline, 4),
                "lower_bound": round(lower, 4),
                "upper_bound": round(upper, 4),
                "deviation_pct": (
                    round((actual - baseline) / baseline * 100, 2)
                    if baseline else None
                ),
            })
    result = {
        "client_site_id": site,
        "event_hour": result_hour,
        "baseline_points": baseline_points,
        "alerts": alerts,
    }
    if alerts:
        _publish_hourly_alert(result)
    return result


def _run_hourly() -> dict:
    publication = _hourly_publication_manifest()
    if _already_processed(publication, HOURLY_CONSUMPTION_MARKER_KEY):
        return {
            "checked": [],
            "skipped": "publication already processed",
            "published_at": publication["published_at"],
            "cadence": "hourly",
        }
    checked = [_check_hourly_site(site) for site in _discover_hourly_sites()]
    _mark_processed(
        publication,
        HOURLY_CONSUMPTION_MARKER_KEY,
        cadence="hourly",
    )
    return {"checked": checked, "cadence": "hourly"}


def _latest_complete_retention_week(published_through: str) -> tuple[str, str]:
    """Return the latest Monday-Sunday cohort week with mature D7 outcomes."""
    latest_mature_day = (
        date.fromisoformat(published_through)
        - timedelta(days=RETENTION_MATURITY_DAYS)
    )
    days_since_sunday = (latest_mature_day.weekday() + 1) % 7
    week_end = latest_mature_day - timedelta(days=days_since_sunday)
    week_start = week_end - timedelta(days=6)
    return week_start.isoformat(), week_end.isoformat()


def _fetch_retention_weeks(site: str, eligible_through: str) -> list:
    """Fetch complete weekly cohorts, newest bounded by ``eligible_through``."""
    sql = f"""
    WITH weekly AS (
        SELECT
            CAST(date_trunc('week', CAST(registration_date AS DATE)) AS VARCHAR)
                AS cohort_week_start,
            client_site_id,
            SUM(cohort_size) AS cohort_size,
            SUM(d1_retained) AS d1_retained,
            SUM(d7_retained) AS d7_retained
        FROM gold_cohort_retention
        WHERE client_site_id = '{site}'
          AND registration_date <= '{eligible_through}'
        GROUP BY 1, 2
    )
    SELECT cohort_week_start, cohort_size, d1_retained, d7_retained
    FROM weekly
    ORDER BY cohort_week_start DESC
    LIMIT {RETENTION_BASELINE_WEEKS + 1}
    """
    rows = fetch_all_rows(run_athena_query(sql))
    rows.reverse()
    return rows


def _retention_signal(
    rows: list,
    metric: str,
    target_week_start: str,
) -> dict:
    """Compare one weekly cohort against a pooled, sample-weighted baseline."""
    if not rows or rows[-1].get("cohort_week_start") != target_week_start:
        return {"skipped": "no complete cohort for target week"}

    current = rows[-1]
    history = rows[:-1]
    if len(history) < RETENTION_MIN_BASELINE_WEEKS:
        return {"skipped": "insufficient baseline weeks"}

    retained_field = RETENTION_METRICS[metric]
    current_n = int(current.get("cohort_size") or 0)
    current_retained = int(current.get(retained_field) or 0)
    baseline_n = sum(int(row.get("cohort_size") or 0) for row in history)
    baseline_retained = sum(
        int(row.get(retained_field) or 0) for row in history
    )
    if (
        current_n < RETENTION_MIN_COHORT_SIZE
        or baseline_n < RETENTION_MIN_COHORT_SIZE
    ):
        return {
            "skipped": "insufficient cohort size",
            "current_cohort_size": current_n,
            "baseline_cohort_size": baseline_n,
        }

    actual = current_retained / current_n
    baseline = baseline_retained / baseline_n
    pooled = (current_retained + baseline_retained) / (current_n + baseline_n)
    standard_error = math.sqrt(
        pooled * (1 - pooled) * ((1 / current_n) + (1 / baseline_n))
    )
    z_score = (actual - baseline) / standard_error if standard_error else 0.0
    absolute_drop = baseline - actual
    signal = {
        "metric": metric,
        "actual": round(actual, 4),
        "baseline": round(baseline, 4),
        "absolute_drop": round(absolute_drop, 4),
        "z_score": round(z_score, 4),
        "z_threshold": RETENTION_Z_THRESHOLD,
        "minimum_absolute_drop": RETENTION_MIN_ABSOLUTE_DROP,
        "current_cohort_size": current_n,
        "baseline_cohort_size": baseline_n,
        "baseline_weeks": len(history),
        "alert": (
            z_score <= RETENTION_Z_THRESHOLD
            and absolute_drop >= RETENTION_MIN_ABSOLUTE_DROP
        ),
    }
    if signal["alert"]:
        signal["reason_code"] = "MATURE_RETENTION_RATE_DROP"
    return signal


def _publish_retention_alert(result: dict) -> None:
    key = (
        "gold/anomaly_alerts/"
        f"retention_{result['client_site_id']}_{result['cohort_week_start']}.json"
    )
    body = {**result, "detected_at": _now_iso(), "evidence_s3_key": key}
    encoded = json.dumps(body).encode("utf-8")
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=encoded,
        ContentType="application/json",
    )
    sns.publish(
        TopicArn=ALERTS_TOPIC_ARN,
        Subject=(
            f"Retention anomaly: {result['client_site_id']} "
            f"week {result['cohort_week_start']}"
        ),
        Message=encoded.decode("utf-8"),
        MessageAttributes={
            "alert_type": {
                "DataType": "String",
                "StringValue": "retention_anomaly",
            },
            "schema_version": {"DataType": "String", "StringValue": "1"},
            "client_site_id": {
                "DataType": "String",
                "StringValue": result["client_site_id"],
            },
            "as_of_date": {
                "DataType": "String",
                "StringValue": result["cohort_week_end"],
            },
        },
    )


def _check_retention_site(
    site: str,
    cohort_week_start: str,
    cohort_week_end: str,
    publication: dict | None = None,
) -> dict:
    rows = _fetch_retention_weeks(site, cohort_week_end)
    signals = [
        _retention_signal(rows, metric, cohort_week_start)
        for metric in RETENTION_METRICS
    ]
    alerts = [signal for signal in signals if signal.get("alert")]
    result = {
        "detector_id": RETENTION_DETECTOR_ID,
        "detector_version": RETENTION_DETECTOR_VERSION,
        "decision": "REVIEW_REQUIRED" if alerts else "NO_ALERT",
        "client_site_id": site,
        "cohort_week_start": cohort_week_start,
        "cohort_week_end": cohort_week_end,
        "reason_codes": sorted({
            signal["reason_code"]
            for signal in alerts
        }),
        "signals": signals,
        "alerts": alerts,
        "data_publication": (
            {
                "table": publication.get("table"),
                "published_at": publication.get("published_at"),
                "published_through": publication.get("published_through"),
            }
            if publication
            else None
        ),
        "explanation": (
            "One or more mature weekly retention rates fell below both the "
            "statistical and minimum practical-drop thresholds. Human review "
            "is required; this does not prove a product defect."
            if alerts
            else "No mature weekly retention rate crossed both alert thresholds."
        ),
        "recommended_checks": [
            "Review onboarding, release, acquisition-channel, and payment changes for the cohort week.",
            "Segment the cohort before changing detector thresholds.",
        ] if alerts else [],
    }
    if alerts:
        _publish_retention_alert(result)
    return result


def _run_weekly_retention(publication: dict) -> dict:
    if _already_processed(publication, RETENTION_CONSUMPTION_MARKER_KEY):
        return {
            "checked": [],
            "skipped": "publication already processed",
            "published_at": publication["published_at"],
            "cadence": "weekly",
        }
    week_start, week_end = _latest_complete_retention_week(
        publication["published_through"]
    )
    checked = [
        _check_retention_site(site, week_start, week_end, publication)
        for site in _discover_sites()
    ]
    _mark_processed(
        publication,
        RETENTION_CONSUMPTION_MARKER_KEY,
        cadence="weekly",
        cohort_week_start=week_start,
        cohort_week_end=week_end,
    )
    return {
        "checked": checked,
        "cadence": "weekly",
        "cohort_week_start": week_start,
        "cohort_week_end": week_end,
    }


def handler(event, context):
    if event.get("scheduled"):
        if event.get("cadence") == "hourly":
            return _run_hourly()
        publication = _publication_manifest()
        if event.get("cadence") == "weekly":
            return _run_weekly_retention(publication)
        if _already_processed(publication):
            return {
                "checked": [],
                "skipped": "publication already processed",
                "published_at": publication["published_at"],
            }
        checked = []
        as_of_date = publication["published_through"]
        for site in _discover_sites():
            checked.append(_check_site(site, as_of_date))
        _mark_processed(publication)
        return {"checked": checked}

    if event.get("event_hour"):
        return _check_hourly_site(event["client_site_id"], event["event_hour"])
    return _check_site(event["client_site_id"], event["as_of_date"])
