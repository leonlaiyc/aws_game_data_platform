"""Capability B: first-look report, auto-generated when a Module 1
anomaly alert fires (SNS), so an analyst gets a pre-investigated report
instead of a raw alert. Same division of labor as everywhere else in this
project: every number here is code-rendered from Gold/Silver query
results; Bedrock writes exactly one short qualitative headline sentence,
with no figures in it.

Drill-down sequence:
1. Site-level baseline comparison (gold_daily_kpi): today's DAU/GGR/
   sessions/new_players/deposits/withdrawals vs. the trailing 7-day
   average, excluding today.
2. Per-game breakdown (silver_events, NOT Gold): gold_daily_kpi has no
   per-game grain, so this one query deliberately reads Silver directly -
   a documented, narrow exception to "always read from Gold", justified
   because this is a one-off investigative drill-down, not a repeated
   dashboard metric that needs KPI_DEFINITIONS.md-level governance.
3. Co-movement check: did engagement metrics (DAU/sessions) move with the
   OEC metric (GGR), or is GGR moving alone? The former suggests a
   broad, real usage change; the latter suggests something narrower (a
   payout/math issue) worth a different kind of investigation.
"""
import json
import os
import re
from datetime import datetime, timezone

import boto3
from athena_utils import fetch_all_rows, run_athena_query

bedrock = boto3.client("bedrock-runtime")
s3 = boto3.client("s3")
sns = boto3.client("sns")
MODEL_ID = "amazon.nova-lite-v1:0"
BUCKET = os.environ["LAKE_BUCKET_NAME"]
REPORTS_TOPIC_ARN = os.environ.get("REPORTS_TOPIC_ARN", "")

BASELINE_WINDOW_DAYS = 7
SITE_METRICS = ["dau", "ggr_usd", "sessions", "new_players", "deposits_usd", "withdrawals_usd"]
_NUMERIC_HEADLINE_RE = re.compile(
    r"\d|\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|"
    r"forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|"
    r"first|second|third|quarter|half|double|triple)\b",
    re.IGNORECASE,
)
_HEADLINE_FALLBACK = "Anomaly detected - see the breakdown below for details."


def _site_baseline_comparison(site: str, as_of_date: str) -> dict:
    sql = f"""
    SELECT dt, dau, ggr_usd, sessions, new_players, deposits_usd, withdrawals_usd
    FROM gold_daily_kpi
    WHERE client_site_id = '{site}' AND dt <= '{as_of_date}'
    ORDER BY dt DESC
    LIMIT {BASELINE_WINDOW_DAYS + 1}
    """
    rows = fetch_all_rows(run_athena_query(sql))
    if not rows or rows[0]["dt"] != as_of_date:
        return {}
    today, history = rows[0], rows[1:]
    comparison = {}
    for metric in SITE_METRICS:
        today_val = float(today[metric])
        hist_vals = [float(r[metric]) for r in history if r.get(metric) is not None]
        baseline_avg = sum(hist_vals) / len(hist_vals) if hist_vals else None
        pct_change = ((today_val - baseline_avg) / baseline_avg * 100) if baseline_avg else None
        comparison[metric] = {
            "actual": round(today_val, 4),
            "baseline_avg_7d": round(baseline_avg, 4) if baseline_avg is not None else None,
            "pct_change": round(pct_change, 2) if pct_change is not None else None,
        }
    return comparison


def _game_breakdown(site: str, as_of_date: str) -> list:
    sql = f"""
    WITH today AS (
        SELECT game_id, SUM(bet_amount_usd) - SUM(win_amount_usd) AS ggr_usd
        FROM silver_events
        WHERE client_site_id = '{site}' AND event_type = 'bet_settled' AND dt = '{as_of_date}'
        GROUP BY game_id
    ),
    baseline AS (
        SELECT game_id, (SUM(bet_amount_usd) - SUM(win_amount_usd)) / {BASELINE_WINDOW_DAYS}.0 AS ggr_usd_avg
        FROM silver_events
        WHERE client_site_id = '{site}' AND event_type = 'bet_settled'
          AND dt BETWEEN CAST(date_add('day', -{BASELINE_WINDOW_DAYS}, DATE '{as_of_date}') AS VARCHAR)
                      AND CAST(date_add('day', -1, DATE '{as_of_date}') AS VARCHAR)
        GROUP BY game_id
    )
    SELECT COALESCE(t.game_id, b.game_id) AS game_id,
           COALESCE(t.ggr_usd, 0.0) AS ggr_usd_today,
           COALESCE(b.ggr_usd_avg, 0.0) AS ggr_usd_baseline_avg
    FROM today t FULL OUTER JOIN baseline b ON t.game_id = b.game_id
    """
    rows = fetch_all_rows(run_athena_query(sql))
    breakdown = []
    for r in rows:
        today_v, base_v = float(r["ggr_usd_today"]), float(r["ggr_usd_baseline_avg"])
        pct_change = ((today_v - base_v) / base_v * 100) if base_v else None
        breakdown.append({
            "game_id": r["game_id"], "ggr_usd_today": round(today_v, 2),
            "ggr_usd_baseline_avg": round(base_v, 2),
            "pct_change": round(pct_change, 2) if pct_change is not None else None,
        })
    breakdown.sort(key=lambda g: (g["pct_change"] is None, g["pct_change"]))
    return breakdown


def _render_report(site: str, as_of_date: str, comparison: dict, breakdown: list, headline: str) -> str:
    comp_lines = "\n".join(
        f"- {m}: {v['actual']} vs 7d baseline avg {v['baseline_avg_7d']} "
        f"({'+' if (v['pct_change'] or 0) >= 0 else ''}{v['pct_change']}%)"
        for m, v in comparison.items()
    )
    game_lines = "\n".join(
        f"- {g['game_id']}: {g['ggr_usd_today']} vs baseline avg {g['ggr_usd_baseline_avg']} "
        f"({'+' if (g['pct_change'] or 0) >= 0 else ''}{g['pct_change']}%)"
        for g in breakdown
    )
    dau_engaged = comparison.get("dau", {}).get("pct_change") or 0
    ggr_engaged = comparison.get("ggr_usd", {}).get("pct_change") or 0
    co_movement = (
        "DAU and GGR moved in the same direction - consistent with a broad usage change."
        if (dau_engaged < -5 and ggr_engaged < -5) or (dau_engaged > 5 and ggr_engaged > 5)
        else "GGR moved without a matching DAU shift - may be narrower than an overall usage change "
             "(e.g. a payout/game-math issue) rather than fewer people playing."
    )

    return (
        f"### First-Look Report: {site} on {as_of_date}\n\n"
        f"### Headline\n{headline}\n\n"
        f"### Site-Level vs 7-Day Baseline\n{comp_lines}\n\n"
        f"### Per-Game GGR Breakdown (vs 7-day baseline avg)\n{game_lines}\n\n"
        f"### Co-Movement Check\n{co_movement}\n\n"
        f"### Suggested Next Steps\n"
        f"- Confirm whether this is isolated to the worst-performing game(s) above or platform-wide.\n"
        f"- Check for a known deploy/incident on {as_of_date} for {site}.\n"
        f"- If deposits also dropped, prioritize checking the payment provider integration."
    )


def _headline(site: str, as_of_date: str, comparison: dict) -> str:
    lines = "\n".join(f"{m}: {v['pct_change']}% vs baseline" for m, v in comparison.items())
    prompt = (
        "You are writing a ONE-SENTENCE headline for an internal analytics incident report. "
        "Do not restate exact numbers - describe direction and severity in words only.\n\n"
        f"Site: {site}, date: {as_of_date}\nMetric changes vs 7-day baseline:\n{lines}\n\n"
        "Respond with ONLY a JSON object: {\"headline\": \"...\"}"
    )
    try:
        resp = bedrock.converse(
            modelId=MODEL_ID, messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 150, "temperature": 0.1},
        )
        raw = resp["output"]["message"]["content"][0]["text"].strip()
    except Exception as error:
        print(json.dumps({
            "warning": "headline generation failed, using fallback",
            "error_type": type(error).__name__,
        }))
        return _HEADLINE_FALLBACK

    stripped = raw
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:]
        stripped = stripped.strip()
    try:
        headline = json.loads(stripped).get("headline", "")
        if headline and not _NUMERIC_HEADLINE_RE.search(headline):
            return headline
    except (json.JSONDecodeError, AttributeError):
        pass
    print(json.dumps({
        "warning": "headline parse or no-number contract failed, using fallback",
        "raw_response": raw,
    }))
    return _HEADLINE_FALLBACK


def handler(event, context):
    reports = []
    for record in event["Records"]:
        attrs = record["Sns"].get("MessageAttributes") or {}

        # Defensive even though an SNS filter policy already restricts this
        # subscription to alert_type=data_anomaly. The filter is the primary
        # control; this is the belt to its braces, because a subscription
        # policy is edited in a different place from this code and the two can
        # drift. Skipping a malformed message beats crashing the whole batch.
        alert_type = (attrs.get("alert_type") or {}).get("Value")
        site = (attrs.get("client_site_id") or {}).get("Value")
        as_of_date = (attrs.get("as_of_date") or {}).get("Value")
        if alert_type != "data_anomaly" or not site or not as_of_date:
            print(json.dumps({"skipped": True, "reason": "unexpected alert envelope",
                               "alert_type": alert_type, "has_site": bool(site),
                               "has_date": bool(as_of_date)}))
            continue

        comparison = _site_baseline_comparison(site, as_of_date)
        breakdown = _game_breakdown(site, as_of_date)
        headline = _headline(site, as_of_date, comparison)
        report_text = _render_report(site, as_of_date, comparison, breakdown, headline)

        key = f"gold/first_look_reports/{site}_{as_of_date}.json"
        s3.put_object(
            Bucket=BUCKET, Key=key,
            Body=json.dumps({"client_site_id": site, "as_of_date": as_of_date, "report_text": report_text,
                              "comparison": comparison, "game_breakdown": breakdown}).encode("utf-8"),
            ContentType="application/json",
        )
        if REPORTS_TOPIC_ARN:
            sns.publish(
                TopicArn=REPORTS_TOPIC_ARN,
                Subject=f"First-look report: {site} on {as_of_date}",
                Message=json.dumps({
                    "report_type": "FIRST_LOOK",
                    "client_site_id": site,
                    "as_of_date": as_of_date,
                    "headline": headline,
                    "report_s3_uri": f"s3://{BUCKET}/{key}",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }),
                MessageAttributes={
                    "report_type": {
                        "DataType": "String",
                        "StringValue": "FIRST_LOOK",
                    },
                    "client_site_id": {
                        "DataType": "String",
                        "StringValue": site,
                    },
                },
            )
        reports.append({"client_site_id": site, "as_of_date": as_of_date, "report_text": report_text})

    return {"reports": reports}
