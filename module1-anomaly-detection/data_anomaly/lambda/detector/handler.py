"""Batch anomaly detection: EWMA-based control limits on gold_daily_kpi's
DAU and GGR, per client_site_id.

Two invocation modes, same underlying check - the same dual-mode pattern
used by module2-experimentation-platform/orchestration/monitoring_check:
- Scheduled (event == {"scheduled": true}): the real production path, an
   EventBridge daily schedule. Discovers every known client_site_id and
   checks each against the transform's explicit publication manifest.
- Explicit ({"client_site_id", "as_of_date"}): used by the demo to replay
  a specific historical day against our fixed simulated dataset, where
  "today" doesn't literally apply.

Method: seed an EWMA baseline (and standard deviation) from the trailing
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
import os
import time
from statistics import mean, pstdev

import boto3
from athena_utils import fetch_all_rows, run_athena_query

s3 = boto3.client("s3")
sns = boto3.client("sns")
BUCKET = os.environ["LAKE_BUCKET_NAME"]
ALERTS_TOPIC_ARN = os.environ["ALERTS_TOPIC_ARN"]

ALPHA = 0.3  # EWMA smoothing factor
K_SIGMA = 3.0  # flag when |actual - ewma| > K_SIGMA * trailing stdev
MIN_HISTORY_DAYS = 10  # skip the check if there isn't enough trailing history yet
WINDOW_DAYS = 21
METRICS = ["dau", "ggr_usd"]
PUBLICATION_MANIFEST_KEY = "manifests/published/gold_daily_kpi.json"
CONSUMPTION_MARKER_KEY = "manifests/consumed/data_anomaly.json"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


def _already_processed(publication: dict) -> bool:
    try:
        obj = s3.get_object(Bucket=BUCKET, Key=CONSUMPTION_MARKER_KEY)
    except s3.exceptions.NoSuchKey:
        return False
    marker = json.loads(obj["Body"].read())
    return marker.get("published_at") == publication["published_at"]


def _mark_processed(publication: dict) -> None:
    s3.put_object(
        Bucket=BUCKET,
        Key=CONSUMPTION_MARKER_KEY,
        Body=json.dumps({
            "table": publication["table"],
            "published_at": publication["published_at"],
            "published_through": publication["published_through"],
            "processed_at": _now_iso(),
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


def handler(event, context):
    if event.get("scheduled"):
        publication = _publication_manifest()
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

    return _check_site(event["client_site_id"], event["as_of_date"])
