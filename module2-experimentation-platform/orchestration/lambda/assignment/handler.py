"""Step 1 of the experiment lifecycle: deterministic hash-based player
split, written to the lake as gold_experiment_assignments.

Audience targeting is site-level, not game-level - player_features
aggregates a player's activity across every game they touch, so there's no
per-game column to filter on. A production system wanting game-specific
targeting would need a player-x-game feature grain; documented as a known
simplification (see feature_registry/FEATURES.md).
"""
import hashlib
import json
import os

import boto3
from athena_utils import run_athena_query, fetch_all_rows
from dynamo_utils import clean_decimals, now_iso

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["EXPERIMENTS_TABLE_NAME"])
s3 = boto3.client("s3")
BUCKET = os.environ["LAKE_BUCKET_NAME"]


def _assign_variant(experiment_id: str, seed: int, player_id: str, variants: list) -> str:
    digest = hashlib.md5(f"{experiment_id}:{seed}:{player_id}".encode()).hexdigest()
    bucket = int(digest, 16) % 10000
    cumulative = 0.0
    for v in variants:
        cumulative += float(v["weight"]) * 10000
        if bucket < cumulative:
            return v["name"]
    return variants[-1]["name"]


def handler(event, context):
    experiment_id = event["experiment_id"]
    as_of_date = event["as_of_date"]

    item = table.get_item(Key={"experiment_id": experiment_id}).get("Item")
    if not item:
        raise ValueError(f"experiment {experiment_id} not found")
    item = clean_decimals(item)

    audience = item.get("audience") or {}
    site = audience.get("client_site_id", item["client_site_id"])
    variants = item["variants"]
    seed = int(item["assignment_seed"])

    sql = f"""
    SELECT DISTINCT player_id FROM gold_player_features
    WHERE snapshot_date = '{as_of_date}' AND client_site_id = '{site}' AND sessions_7d > 0
    """
    rows = fetch_all_rows(run_athena_query(sql))
    player_ids = [r["player_id"] for r in rows]

    variant_counts = {v["name"]: 0 for v in variants}
    lines = []
    assigned_at = now_iso()
    for player_id in player_ids:
        variant = _assign_variant(experiment_id, seed, player_id, variants)
        variant_counts[variant] += 1
        lines.append(json.dumps({
            "experiment_id": experiment_id,
            "player_id": player_id,
            "variant": variant,
            "assigned_at": assigned_at,
        }))

    s3.put_object(
        Bucket=BUCKET,
        Key=f"gold/experiment_assignments/{experiment_id}.jsonl",
        Body=("\n".join(lines)).encode("utf-8"),
        ContentType="application/x-ndjson",
    )

    return {
        "experiment": item,
        "variant_counts": variant_counts,
        "total_assigned": len(player_ids),
    }
