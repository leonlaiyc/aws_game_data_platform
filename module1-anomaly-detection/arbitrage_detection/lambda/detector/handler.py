"""Rule-based arbitrage/multi-account detection, combining two signals
that neither alone proves fraud:

1. Device fan-out (from Silver, 30-day rolling window): devices shared
   across an abnormal number of distinct player_ids. On its own this could
   be a shared family computer or an internet cafe - not proof of anything.
2. Per-player behavior (from gold_player_features, the feature registry -
   never recomputed here): withdrawal_to_deposit_ratio_7d and
   bonus_claims_30d, the abnormal-cash-out and bonus-abuse signals.

Only players who show BOTH a shared-device fan-out AND an abnormal
behavior ratio get flagged - fan-out alone or ratio alone is each
individually explainable; the combination is the actual arbitrage-ring
signature this project's scripted scenario embeds (see
data-foundation/event_simulator/config.py's ARBITRAGE_RING_* constants).

Same dual-mode pattern as data_anomaly/detector and module2's
monitoring_check: {"scheduled": true} for the real production path
(today's date), or an explicit {"client_site_id", "as_of_date"} for the
demo to replay a specific historical day.
"""
import json
import os
import time
from datetime import date, timedelta

import boto3
from athena_utils import fetch_all_rows, run_athena_query

s3 = boto3.client("s3")
sns = boto3.client("sns")
BUCKET = os.environ["LAKE_BUCKET_NAME"]
ALERTS_TOPIC_ARN = os.environ["ALERTS_TOPIC_ARN"]

DEVICE_FANOUT_WINDOW_DAYS = 30
DEVICE_FANOUT_MIN_PLAYERS = 3   # a device shared by fewer than this is unremarkable
WD_RATIO_THRESHOLD = 0.8        # withdrawal_to_deposit_ratio_7d above this is abnormal cash-out behavior
BONUS_CLAIMS_THRESHOLD = 5      # bonus_claims_30d above this alone is a bonus-abuse signal


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _discover_sites() -> list:
    rows = fetch_all_rows(run_athena_query("SELECT DISTINCT client_site_id FROM gold_player_features"))
    return [r["client_site_id"] for r in rows]


def _fanout_devices(as_of_date: str) -> dict:
    window_start = (date.fromisoformat(as_of_date) - timedelta(days=DEVICE_FANOUT_WINDOW_DAYS)).isoformat()
    sql = f"""
    SELECT device_id, ARRAY_AGG(DISTINCT player_id) AS player_ids, COUNT(DISTINCT player_id) AS n
    FROM silver_events
    WHERE device_id IS NOT NULL AND dt BETWEEN '{window_start}' AND '{as_of_date}'
    GROUP BY device_id
    HAVING COUNT(DISTINCT player_id) >= {DEVICE_FANOUT_MIN_PLAYERS}
    """
    rows = fetch_all_rows(run_athena_query(sql))
    devices_by_player = {}
    for r in rows:
        # Athena renders ARRAY_AGG as e.g. "[p_ring_00, p_ring_01]" via
        # get_query_results, not JSON - parse it directly.
        raw = r["player_ids"].strip("[]")
        player_ids = [p.strip() for p in raw.split(",")] if raw else []
        for pid in player_ids:
            devices_by_player.setdefault(pid, []).append(r["device_id"])
    return devices_by_player


def _player_features(site: str, as_of_date: str, player_ids: list) -> dict:
    if not player_ids:
        return {}
    id_list = ", ".join(f"'{p}'" for p in player_ids)
    sql = f"""
    SELECT player_id, withdrawal_to_deposit_ratio_7d, bonus_claims_30d
    FROM gold_player_features
    WHERE client_site_id = '{site}' AND snapshot_date = '{as_of_date}' AND player_id IN ({id_list})
    """
    rows = fetch_all_rows(run_athena_query(sql))
    return {r["player_id"]: r for r in rows}


def _check_site(site: str, as_of_date: str) -> dict:
    devices_by_player = _fanout_devices(as_of_date)
    # Site-filtering happens implicitly below: _player_features only returns rows for
    # this site, so a fan-out candidate who isn't on `site` simply won't match.
    features = _player_features(site, as_of_date, list(devices_by_player.keys()))

    flagged = []
    for player_id, shared_devices in devices_by_player.items():
        feat = features.get(player_id)
        if not feat:
            continue  # not a player on this site, or no snapshot that day
        wd_ratio = float(feat["withdrawal_to_deposit_ratio_7d"]) if feat["withdrawal_to_deposit_ratio_7d"] else None
        bonus_claims = int(feat["bonus_claims_30d"]) if feat["bonus_claims_30d"] else 0

        reasons = []
        if wd_ratio is not None and wd_ratio > WD_RATIO_THRESHOLD:
            reasons.append(f"withdrawal_to_deposit_ratio_7d={wd_ratio} exceeds {WD_RATIO_THRESHOLD} while sharing a device with {len(set(shared_devices))} other account(s) worth of fan-out")
        if bonus_claims > BONUS_CLAIMS_THRESHOLD:
            reasons.append(f"bonus_claims_30d={bonus_claims} exceeds {BONUS_CLAIMS_THRESHOLD}")

        if reasons:
            flagged.append({
                "player_id": player_id,
                "client_site_id": site,
                "shared_device_ids": sorted(set(shared_devices)),
                "withdrawal_to_deposit_ratio_7d": wd_ratio,
                "bonus_claims_30d": bonus_claims,
                "reasons": reasons,
            })

    result = {"client_site_id": site, "as_of_date": as_of_date, "flagged_players": flagged}
    if flagged:
        _publish_alert(result)
    return result


def _publish_alert(result: dict):
    key = f"gold/flagged_players/{result['client_site_id']}_{result['as_of_date']}.json"
    body = {**result, "detected_at": _now_iso()}
    s3.put_object(Bucket=BUCKET, Key=key, Body=json.dumps(body).encode("utf-8"), ContentType="application/json")

    lines = [f"- {p['player_id']}: {'; '.join(p['reasons'])}" for p in result["flagged_players"]]
    sns.publish(
        TopicArn=ALERTS_TOPIC_ARN,
        Subject=f"Arbitrage suspects flagged: {result['client_site_id']} on {result['as_of_date']}",
        Message=f"{len(result['flagged_players'])} player(s) flagged on {result['client_site_id']} "
                f"as of {result['as_of_date']}:\n\n" + "\n".join(lines),
        # Gotcha: a shared SNS topic is an interface. When a new subscriber
        # (module3's first_look_report) started reading MessageAttributes, this
        # publisher owed them too - otherwise that consumer throws on every
        # arbitrage alert. Either every publisher sends the agreed envelope or
        # the subscription filters on a type discriminator; this topic does
        # both, and alert_type is what the filter policy matches on.
        MessageAttributes={
            "alert_type": {"DataType": "String", "StringValue": "arbitrage"},
            "schema_version": {"DataType": "String", "StringValue": "1"},
            "client_site_id": {"DataType": "String", "StringValue": result["client_site_id"]},
            "as_of_date": {"DataType": "String", "StringValue": result["as_of_date"]},
        },
    )


def handler(event, context):
    if event.get("scheduled"):
        today = time.strftime("%Y-%m-%d", time.gmtime())
        return {"checked": [_check_site(site, today) for site in _discover_sites()]}

    return _check_site(event["client_site_id"], event["as_of_date"])
