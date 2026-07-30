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
(the feature build's published-through date), or an explicit
{"client_site_id", "as_of_date"} for the demo to replay a specific historical
day.
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
PUBLICATION_MANIFEST_KEY = "manifests/published/gold_player_features.json"
CONSUMPTION_MARKER_KEY = "manifests/consumed/arbitrage_detection.json"
DETECTOR_ID = "multi_account_arbitrage_review"
DETECTOR_VERSION = "rules-v2-explainable"
REVIEW_STATUS = "REVIEW_REQUIRED"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _discover_sites() -> list:
    rows = fetch_all_rows(run_athena_query("SELECT DISTINCT client_site_id FROM gold_player_features"))
    return [r["client_site_id"] for r in rows]


def _publication_manifest() -> dict:
    """Read the feature build-success marker; MAX(snapshot_date) is not proof
    that a producer has finished writing a partition."""
    obj = s3.get_object(Bucket=BUCKET, Key=PUBLICATION_MANIFEST_KEY)
    manifest = json.loads(obj["Body"].read())
    if manifest.get("table") != "gold_player_features":
        raise ValueError(f"unexpected publication manifest: {manifest}")
    published_through = manifest.get("published_through")
    if not published_through or not manifest.get("published_at"):
        raise ValueError("gold_player_features publication manifest is incomplete")
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


def _fanout_devices(site: str, as_of_date: str) -> dict:
    """Return the graph evidence for every player on a high-fanout device.

    The earlier implementation returned only a list of device IDs. That was
    enough to make a decision but not enough to explain it: the alert could not
    state how many linked accounts existed or identify the related players
    used as evidence.
    """
    window_start = (
        date.fromisoformat(as_of_date) - timedelta(days=DEVICE_FANOUT_WINDOW_DAYS - 1)
    ).isoformat()
    sql = f"""
    SELECT device_id, ARRAY_AGG(DISTINCT player_id) AS player_ids, COUNT(DISTINCT player_id) AS n
    FROM silver_events
    WHERE client_site_id = '{site}' AND device_id IS NOT NULL
      AND dt BETWEEN '{window_start}' AND '{as_of_date}'
    GROUP BY device_id
    HAVING COUNT(DISTINCT player_id) >= {DEVICE_FANOUT_MIN_PLAYERS}
    """
    rows = fetch_all_rows(run_athena_query(sql))
    devices_by_player = {}
    for r in rows:
        # Athena renders ARRAY_AGG as e.g. "[p_ring_00, p_ring_01]" via
        # get_query_results, not JSON - parse it directly.
        raw = r["player_ids"].strip("[]")
        player_ids = sorted(p.strip() for p in raw.split(",") if p.strip()) if raw else []
        for pid in player_ids:
            devices_by_player.setdefault(pid, []).append({
                "device_id": r["device_id"],
                "linked_player_count": int(r["n"]),
                "linked_player_ids": player_ids,
            })
    return devices_by_player


def _player_features(site: str, as_of_date: str, player_ids: list) -> dict:
    if not player_ids:
        return {}
    id_list = ", ".join(f"'{p}'" for p in player_ids)
    sql = f"""
    WITH peer_baseline AS (
        SELECT
            approx_percentile(withdrawal_to_deposit_ratio_7d, 0.5) AS wd_ratio_median,
            approx_percentile(withdrawal_to_deposit_ratio_7d, 0.99) AS wd_ratio_p99,
            approx_percentile(CAST(bonus_claims_30d AS DOUBLE), 0.5) AS bonus_claims_median,
            approx_percentile(CAST(bonus_claims_30d AS DOUBLE), 0.99) AS bonus_claims_p99
        FROM gold_player_features
        WHERE client_site_id = '{site}' AND snapshot_date = '{as_of_date}'
    )
    SELECT
        pf.player_id,
        pf.withdrawal_to_deposit_ratio_7d,
        pf.bonus_claims_30d,
        peer.wd_ratio_median,
        peer.wd_ratio_p99,
        peer.bonus_claims_median,
        peer.bonus_claims_p99
    FROM gold_player_features pf
    CROSS JOIN peer_baseline peer
    WHERE pf.client_site_id = '{site}' AND pf.snapshot_date = '{as_of_date}'
      AND pf.player_id IN ({id_list})
    """
    rows = fetch_all_rows(run_athena_query(sql))
    return {r["player_id"]: r for r in rows}


def _optional_float(value):
    return float(value) if value not in (None, "") else None


def _excess_contribution(actual: float, threshold: float) -> float:
    """An interpretable review-priority contribution, not a probability."""
    if threshold <= 0:
        return 0.0
    return round(actual / threshold, 4)


def _build_explainable_finding(
    site: str,
    as_of_date: str,
    player_id: str,
    shared_device_evidence: list,
    feature_row: dict,
):
    """Build a review finding whose decision can be reconstructed from output.

    A player is still flagged only when two independent signal families are
    present: graph linkage plus abnormal behaviour. The returned review score
    is the sum of transparent threshold ratios and is used only for ordering
    an investigation queue; it is deliberately not called a fraud probability.
    """
    if not shared_device_evidence or not feature_row:
        return None

    wd_ratio = _optional_float(feature_row.get("withdrawal_to_deposit_ratio_7d"))
    bonus_claims = int(feature_row.get("bonus_claims_30d") or 0)
    max_linked = max(int(d["linked_player_count"]) for d in shared_device_evidence)
    linked_players = sorted({
        linked
        for device in shared_device_evidence
        for linked in device["linked_player_ids"]
        if linked != player_id
    })
    device_ids = sorted({d["device_id"] for d in shared_device_evidence})

    reason_codes = [{
        "code": "SHARED_DEVICE_FANOUT",
        "signal_family": "entity_linkage",
        "actual": max_linked,
        "threshold": DEVICE_FANOUT_MIN_PLAYERS,
        "contribution": _excess_contribution(max_linked, DEVICE_FANOUT_MIN_PLAYERS),
        "explanation": (
            f"{max_linked} accounts used a linked device in the "
            f"{DEVICE_FANOUT_WINDOW_DAYS}-day evidence window; the review threshold is "
            f"{DEVICE_FANOUT_MIN_PLAYERS}."
        ),
    }]

    behavioural_reasons = []
    if wd_ratio is not None and wd_ratio > WD_RATIO_THRESHOLD:
        behavioural_reasons.append({
            "code": "CASHOUT_RATIO_HIGH",
            "signal_family": "player_behaviour",
            "actual": round(wd_ratio, 4),
            "threshold": WD_RATIO_THRESHOLD,
            "peer_median": _optional_float(feature_row.get("wd_ratio_median")),
            "peer_p99": _optional_float(feature_row.get("wd_ratio_p99")),
            "contribution": _excess_contribution(wd_ratio, WD_RATIO_THRESHOLD),
            "explanation": (
                f"The 7-day withdrawal-to-deposit ratio is {round(wd_ratio, 4)}, "
                f"above the review threshold of {WD_RATIO_THRESHOLD}."
            ),
        })
    if bonus_claims > BONUS_CLAIMS_THRESHOLD:
        behavioural_reasons.append({
            "code": "BONUS_CLAIM_BURST",
            "signal_family": "player_behaviour",
            "actual": bonus_claims,
            "threshold": BONUS_CLAIMS_THRESHOLD,
            "peer_median": _optional_float(feature_row.get("bonus_claims_median")),
            "peer_p99": _optional_float(feature_row.get("bonus_claims_p99")),
            "contribution": _excess_contribution(bonus_claims, BONUS_CLAIMS_THRESHOLD),
            "explanation": (
                f"The player claimed {bonus_claims} bonuses in 30 days, above the "
                f"review threshold of {BONUS_CLAIMS_THRESHOLD}."
            ),
        })

    # Device sharing alone is explainable (family computer, internet cafe).
    # Abnormal cash-out/bonus behaviour alone is also explainable. Only their
    # combination creates a review item.
    if not behavioural_reasons:
        return None
    reason_codes.extend(behavioural_reasons)

    review_score = round(sum(float(r["contribution"]) for r in reason_codes), 4)
    evidence_start = (
        date.fromisoformat(as_of_date) - timedelta(days=DEVICE_FANOUT_WINDOW_DAYS - 1)
    ).isoformat()
    return {
        "player_id": player_id,
        "client_site_id": site,
        "status": REVIEW_STATUS,
        "detector_id": DETECTOR_ID,
        "detector_version": DETECTOR_VERSION,
        "review_score": review_score,
        "score_interpretation": (
            "Sum of code-owned actual-to-threshold ratios for queue ordering; "
            "not a probability of fraud."
        ),
        "evidence_window": {"start": evidence_start, "end": as_of_date},
        "reason_codes": reason_codes,
        "shared_device_ids": device_ids,
        "linked_player_ids": linked_players,
        "withdrawal_to_deposit_ratio_7d": wd_ratio,
        "bonus_claims_30d": bonus_claims,
        # Backward-compatible human-readable field used by the existing SNS
        # formatter and demo. Every sentence is rendered from the structured
        # evidence above, never authored by a model.
        "reasons": [r["explanation"] for r in reason_codes],
        "recommended_checks": [
            "Review linked accounts' registration and session timing.",
            "Compare withdrawal destinations and payment methods.",
            "Confirm whether the shared device has a legitimate household or venue explanation.",
        ],
        "decision_note": (
            "This is a review-priority signal, not a determination that the player committed fraud."
        ),
    }


def _check_site(site: str, as_of_date: str) -> dict:
    devices_by_player = _fanout_devices(site, as_of_date)
    features = _player_features(site, as_of_date, list(devices_by_player.keys()))

    flagged = []
    for player_id, shared_device_evidence in devices_by_player.items():
        feat = features.get(player_id)
        if not feat:
            continue  # not a player on this site, or no snapshot that day
        finding = _build_explainable_finding(
            site, as_of_date, player_id, shared_device_evidence, feat,
        )
        if finding:
            flagged.append(finding)

    flagged.sort(key=lambda player: (-player["review_score"], player["player_id"]))

    result = {
        "client_site_id": site,
        "as_of_date": as_of_date,
        "detector_id": DETECTOR_ID,
        "detector_version": DETECTOR_VERSION,
        "flagged_players": flagged,
    }
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
