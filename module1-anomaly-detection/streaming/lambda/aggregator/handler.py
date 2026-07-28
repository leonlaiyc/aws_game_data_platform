"""Real-time RTP/volume aggregation over a Kinesis stream of bet events,
using a rolling DynamoDB window rather than a stream-processing framework
(Kinesis Data Analytics / Managed Flink) - appropriate for this demo's
throughput and lifetime, not a claim that it's the right choice at scale
(see module1-anomaly-detection/streaming/README.md's trade-off notes).

Window key: processing time (when this Lambda runs), floored to the
minute - not event time (the producer's event_ts). This is simpler
(no watermarking/lateness handling needed) and is a documented, deliberate
simplification: a record that's a few seconds "late" by its own event_ts
still lands in whatever window is current when it's actually processed,
rather than the window it logically belongs to. Accurate event-time
semantics would need a real windowing engine that tracks watermarks and
waits for late arrivals up to an allowed lateness - out of scope here.

Duplicates: Kinesis + Lambda event source mapping is at-least-once, not
exactly-once - a retried batch (e.g. after a transient Lambda error) could
double-count some records into these totals. No de-duplication is
implemented (would need tracking processed sequence numbers or an
idempotency key per event) - a known, documented gap appropriate for a
short demo, not a production posture.
"""
import base64
import json
import os
import time
from collections import defaultdict
from decimal import Decimal

import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["WINDOW_TABLE_NAME"])
sns = boto3.client("sns")
ALERTS_TOPIC_ARN = os.environ["ALERTS_TOPIC_ARN"]
RTP_ALERT_THRESHOLD = float(os.environ["RTP_ALERT_THRESHOLD"])
VOLUME_ALERT_THRESHOLD = int(os.environ["VOLUME_ALERT_THRESHOLD"])
WINDOW_TTL_SECONDS = 600  # old windows self-clean via DynamoDB TTL, no manual sweep needed


def _current_window_minute() -> str:
    return time.strftime("%Y-%m-%dT%H:%M", time.gmtime())


def _try_claim_alert(window_id: str) -> bool:
    """Only the first batch to observe a breach for a given window actually
    alerts - later batches still over threshold are no-ops, avoiding an SNS
    message per batch for as long as the window stays breached."""
    try:
        table.update_item(
            Key={"window_id": window_id},
            UpdateExpression="SET alerted = :true",
            ConditionExpression="attribute_not_exists(alerted)",
            ExpressionAttributeValues={":true": True},
        )
        return True
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return False


def handler(event, context):
    # Aggregate this invocation's batch locally first - records commonly
    # share a (site, window) within one batch, so one atomic DynamoDB
    # update per site per batch is cheaper than one per record.
    window_minute = _current_window_minute()
    batch_totals = defaultdict(lambda: {"bet_total": 0.0, "win_total": 0.0, "event_count": 0})

    for record in event["Records"]:
        payload = json.loads(base64.b64decode(record["kinesis"]["data"]))
        agg = batch_totals[payload["client_site_id"]]
        agg["bet_total"] += float(payload["bet_amount"])
        agg["win_total"] += float(payload["win_amount"])
        agg["event_count"] += 1

    results = []
    for site, totals in batch_totals.items():
        window_id = f"{site}#{window_minute}"
        resp = table.update_item(
            Key={"window_id": window_id},
            UpdateExpression="SET expires_at = :expires ADD bet_total :bet, win_total :win, event_count :count",
            ExpressionAttributeValues={
                ":expires": int(time.time()) + WINDOW_TTL_SECONDS,
                ":bet": Decimal(str(round(totals["bet_total"], 4))),
                ":win": Decimal(str(round(totals["win_total"], 4))),
                ":count": totals["event_count"],
            },
            ReturnValues="ALL_NEW",
        )
        current = resp["Attributes"]
        bet_total = float(current["bet_total"])
        win_total = float(current["win_total"])
        event_count = int(current["event_count"])
        rtp = win_total / bet_total if bet_total > 0 else 0.0

        breach_reasons = []
        if rtp > RTP_ALERT_THRESHOLD:
            breach_reasons.append(f"RTP={round(rtp, 4)} exceeds {RTP_ALERT_THRESHOLD}")
        if event_count > VOLUME_ALERT_THRESHOLD:
            breach_reasons.append(f"volume={event_count} events exceeds {VOLUME_ALERT_THRESHOLD}/minute")

        alerted = False
        if breach_reasons and _try_claim_alert(window_id):
            alerted = True
            sns.publish(
                TopicArn=ALERTS_TOPIC_ARN,
                Subject=f"Real-time anomaly: {site} window {window_minute}",
                Message=f"Window {window_id}: bet_total={round(bet_total, 2)}, win_total={round(win_total, 2)}, "
                        f"event_count={event_count}\n\n" + "\n".join(f"- {r}" for r in breach_reasons),
            )

        results.append({"window_id": window_id, "bet_total": bet_total, "win_total": win_total,
                         "event_count": event_count, "rtp": round(rtp, 4), "alerted": alerted})

    return {"windows_updated": results}
