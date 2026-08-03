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
from diagnostics import (
    game_breakdown as _game_breakdown,
    hourly_baseline_comparison as _hourly_baseline_comparison,
    render_report as _render_report,
    site_baseline_comparison as _site_baseline_comparison,
)

bedrock = boto3.client("bedrock-runtime")
s3 = boto3.client("s3")
sns = boto3.client("sns")
MODEL_ID = "amazon.nova-lite-v1:0"
BUCKET = os.environ["LAKE_BUCKET_NAME"]
REPORTS_TOPIC_ARN = os.environ.get("REPORTS_TOPIC_ARN", "")

_NUMERIC_HEADLINE_RE = re.compile(
    r"\d|\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|"
    r"forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|"
    r"first|second|third|quarter|half|double|triple)\b",
    re.IGNORECASE,
)
_HEADLINE_FALLBACK = "Anomaly detected - see the breakdown below for details."


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


def _render_retention_report(payload: dict) -> tuple[str, str]:
    """Render detector-owned evidence without asking a model to restate it."""
    site = payload["client_site_id"]
    week_start = payload["cohort_week_start"]
    week_end = payload["cohort_week_end"]
    lines = "\n".join(
        (
            f"- {signal['metric']}: {signal['actual']} vs pooled baseline "
            f"{signal['baseline']} (drop={signal['absolute_drop']}, "
            f"z={signal['z_score']}, current n="
            f"{signal['current_cohort_size']}, baseline n="
            f"{signal['baseline_cohort_size']})"
        )
        for signal in payload.get("alerts", [])
    )
    headline = "A mature weekly retention cohort crossed the review threshold."
    report = (
        f"### Retention First-Look: {site}, {week_start} to {week_end}\n\n"
        f"### Headline\n{headline}\n\n"
        f"### Sample-Weighted Comparison\n{lines}\n\n"
        f"### Interpretation Boundary\n"
        f"This is a review signal, not proof of a product defect. Cohorts are "
        f"only evaluated after D7 outcomes mature, and both statistical and "
        f"minimum practical-drop thresholds must pass.\n\n"
        f"### Suggested Next Steps\n"
        f"- Check onboarding, payment, release, and acquisition-channel changes "
        f"for the cohort week.\n"
        f"- Segment the affected cohort before changing the detector threshold."
    )
    return report, headline


def _render_hourly_report(
    site: str,
    event_hour: str,
    comparison: dict,
    headline: str,
) -> str:
    labels = {
        "active_users": "active users",
        "sessions": "sessions",
        "processed_events": "processed events",
    }
    lines = "\n".join(
        f"- {labels[metric]}: {values['actual']} vs same-hour baseline "
        f"{values['baseline']} ({values['pct_change']}%)"
        for metric, values in comparison.items()
    )
    return (
        f"### Hourly First-Look: {site} at {event_hour}\n\n"
        f"### Headline\n{headline}\n\n"
        f"### Same-Hour Comparison\n{lines}\n\n"
        f"### Interpretation Boundary\n"
        f"This is an investigation signal, not a confirmed root cause. "
        f"Check ingestion and service health before attributing the movement "
        f"to user behaviour.\n\n"
        f"### Suggested Next Steps\n"
        f"- Check data ingestion completeness for the affected hour.\n"
        f"- Check service health and recent releases for {site}."
    )


def _store_and_publish(
    site: str,
    as_of_date: str,
    report_text: str,
    headline: str,
    report_type: str,
    evidence: dict,
) -> dict:
    suffix = {
        "RETENTION_FIRST_LOOK": "retention",
        "HOURLY_FIRST_LOOK": "hourly",
    }.get(report_type, "daily")
    key_time = as_of_date.replace(" ", "T").replace(":00:00.000", "")
    key = f"gold/first_look_reports/{site}_{key_time}_{suffix}.json"
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(
            {
                "client_site_id": site,
                "as_of_date": as_of_date,
                "report_type": report_type,
                "report_text": report_text,
                **evidence,
            }
        ).encode("utf-8"),
        ContentType="application/json",
    )
    if REPORTS_TOPIC_ARN:
        sns.publish(
            TopicArn=REPORTS_TOPIC_ARN,
            Subject=f"{report_type.replace('_', ' ').title()}: {site} on {as_of_date}",
            Message=json.dumps(
                {
                    "report_type": report_type,
                    "client_site_id": site,
                    "as_of_date": as_of_date,
                    "headline": headline,
                    "report_s3_uri": f"s3://{BUCKET}/{key}",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            ),
            MessageAttributes={
                "report_type": {
                    "DataType": "String",
                    "StringValue": report_type,
                },
                "client_site_id": {
                    "DataType": "String",
                    "StringValue": site,
                },
            },
        )
    return {
        "client_site_id": site,
        "as_of_date": as_of_date,
        "report_type": report_type,
        "report_text": report_text,
    }


def handler(event, context):
    reports = []
    for record in event["Records"]:
        attrs = record["Sns"].get("MessageAttributes") or {}

        # Defensive even though an SNS filter policy already restricts this
        # subscription to the two supported business alert types. The filter
        # is the primary control; this is the belt to its braces, because a
        # subscription policy is edited in a different place from this code
        # and the two can drift. Skipping beats crashing the whole batch.
        alert_type = (attrs.get("alert_type") or {}).get("Value")
        site = (attrs.get("client_site_id") or {}).get("Value")
        as_of_date = (attrs.get("as_of_date") or {}).get("Value")
        if (
            alert_type not in {
                "data_anomaly",
                "hourly_data_anomaly",
                "retention_anomaly",
            }
            or not site
            or not as_of_date
        ):
            print(json.dumps({"skipped": True, "reason": "unexpected alert envelope",
                               "alert_type": alert_type, "has_site": bool(site),
                               "has_date": bool(as_of_date)}))
            continue

        if alert_type == "retention_anomaly":
            try:
                payload = json.loads(record["Sns"]["Message"])
            except (KeyError, TypeError, json.JSONDecodeError):
                print(json.dumps({
                    "skipped": True,
                    "reason": "malformed retention alert body",
                }))
                continue
            if (
                payload.get("client_site_id") != site
                or payload.get("cohort_week_end") != as_of_date
                or not payload.get("alerts")
            ):
                print(json.dumps({
                    "skipped": True,
                    "reason": "retention alert attributes/body mismatch",
                }))
                continue
            report_text, headline = _render_retention_report(payload)
            reports.append(
                _store_and_publish(
                    site,
                    as_of_date,
                    report_text,
                    headline,
                    "RETENTION_FIRST_LOOK",
                    {"retention_evidence": payload},
                )
            )
            continue

        if alert_type == "hourly_data_anomaly":
            event_hour = (attrs.get("event_hour") or {}).get("Value")
            if not event_hour:
                print(json.dumps({
                    "skipped": True,
                    "reason": "hourly alert missing event_hour",
                }))
                continue
            comparison = _hourly_baseline_comparison(site, event_hour)
            headline = _headline(site, event_hour, comparison)
            report_text = _render_hourly_report(
                site, event_hour, comparison, headline
            )
            reports.append(_store_and_publish(
                site,
                event_hour,
                report_text,
                headline,
                "HOURLY_FIRST_LOOK",
                {"event_hour": event_hour, "comparison": comparison},
            ))
            continue

        comparison = _site_baseline_comparison(site, as_of_date)
        breakdown = _game_breakdown(site, as_of_date)
        headline = _headline(site, as_of_date, comparison)
        report_text = _render_report(site, as_of_date, comparison, breakdown, headline)
        reports.append(
            _store_and_publish(
                site,
                as_of_date,
                report_text,
                headline,
                "FIRST_LOOK",
                {
                    "comparison": comparison,
                    "game_breakdown": breakdown,
                },
            )
        )

    return {"reports": reports}
