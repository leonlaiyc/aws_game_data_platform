"""Shared helpers for the module2 demo script: stack outputs, Athena
polling, calling the deployed API, and replicating the exact same
deterministic assignment logic the real Lambdas use (so this script can
compute a real split in advance and inject matching per-variant data
before triggering the actual pipeline).
"""
import gzip
import hashlib
import json
import sys
import time
import uuid
from pathlib import Path

import boto3

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "data-foundation"))
sys.path.insert(0, str(REPO_ROOT / "demo_lib"))
from event_simulator.config import CLIENT_SITES  # noqa: E402
from signed_request import assume, signed_request  # noqa: E402

session = boto3.Session()
cfn = session.client("cloudformation")
athena = session.client("athena")
s3 = session.client("s3")
_operator_session = None


def stack_outputs(stack_name: str) -> dict:
    resp = cfn.describe_stacks(StackName=stack_name)
    return {o["OutputKey"]: o["OutputValue"] for o in resp["Stacks"][0]["Outputs"]}


def run_query(sql: str, database: str, workgroup: str) -> str:
    resp = athena.start_query_execution(
        QueryString=sql, QueryExecutionContext={"Database": database}, WorkGroup=workgroup
    )
    query_id = resp["QueryExecutionId"]
    while True:
        status = athena.get_query_execution(QueryExecutionId=query_id)["QueryExecution"]["Status"]
        state = status["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)
    if state != "SUCCEEDED":
        raise RuntimeError(f"Athena query failed ({state}): {status.get('StateChangeReason')}\n--- SQL ---\n{sql}")
    return query_id


def fetch_all_rows(query_id: str) -> list:
    rows = []
    header = None
    paginator = athena.get_paginator("get_query_results")
    for page in paginator.paginate(QueryExecutionId=query_id):
        for row in page["ResultSet"]["Rows"]:
            values = [c.get("VarCharValue") for c in row["Data"]]
            if header is None:
                header = values
                continue
            rows.append(dict(zip(header, values)))
    return rows


def api_request(api_url: str, method: str, path: str, body: dict = None) -> dict:
    global _operator_session
    url = api_url.rstrip("/") + path
    if _operator_session is None:
        _operator_session = assume("aurora-games-operator", "module2-demo")
    status, response = signed_request(_operator_session, method, url, body)
    if status >= 400:
        raise RuntimeError(f"registry API {method} {path} returned {status}: {response}")
    return response


# --- Mirrors registry/lambda/api/handler.py's _derive_seed and
# orchestration/lambda/assignment/handler.py's _assign_variant exactly,
# so this script can predict the real assignment before triggering it. ---

def derive_seed(experiment_id: str) -> int:
    return int(hashlib.md5(experiment_id.encode()).hexdigest(), 16) % (2**31 - 1) + 1


def assign_variant(experiment_id: str, seed: int, player_id: str, variants: list) -> str:
    digest = hashlib.md5(f"{experiment_id}:{seed}:{player_id}".encode()).hexdigest()
    bucket = int(digest, 16) % 10000
    cumulative = 0.0
    for v in variants:
        cumulative += float(v["weight"]) * 10000
        if bucket < cumulative:
            return v["name"]
    return variants[-1]["name"]


def eligible_players(database: str, workgroup: str, client_site_id: str, as_of_date: str) -> list:
    sql = f"""
    SELECT DISTINCT player_id FROM gold_player_features
    WHERE snapshot_date = '{as_of_date}' AND client_site_id = '{client_site_id}' AND sessions_7d > 0
    """
    rows = fetch_all_rows(run_query(sql, database, workgroup))
    return [r["player_id"] for r in rows]


def inject_bronze_file(bucket: str, dt: str, suffix: str, events: list):
    """Adds a second file under an existing bronze/dt=.../ partition -
    Athena reads every file under a partition, so this coexists with the
    original events.jsonl.gz from the simulator without touching it."""
    body = "\n".join(json.dumps(e, ensure_ascii=False) for e in events).encode("utf-8")
    key = f"bronze/dt={dt}/{suffix}.jsonl.gz"
    s3.put_object(Bucket=bucket, Key=key, Body=gzip.compress(body))


def make_bet_event(experiment_tag: str, player_id: str, client_site_id: str, game_id: str, event_ts: str,
                    bet_amount: float, win_amount: float) -> dict:
    site = CLIENT_SITES[client_site_id]
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "bet_settled",
        "event_ts": event_ts,
        "player_id": player_id,
        "session_id": str(uuid.uuid4()),
        "game_id": game_id,
        "client_site_id": client_site_id,
        "region": site["region"],
        "platform": "web",
        # Per-player, not shared across the group - a shared literal string
        # here would falsely light up module1's device-fan-out fraud query.
        "device_id": f"dev_demo_{experiment_tag}_{player_id}",
        "ip_hash": f"ip_demo_{experiment_tag}_{player_id}",
        "payload": {
            "game_round_id": str(uuid.uuid4()),
            "bet_amount": round(bet_amount, 2),
            "win_amount": round(win_amount, 2),
            "currency": site["currency"],
        },
    }
