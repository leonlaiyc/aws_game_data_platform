"""Builds gold_player_features on top of the data-foundation lake (silver_events
must already exist - run data-foundation/lake/build_lake.py first).

Requires: `aws configure` already set up, and the FoundationStack already
deployed (`cdk deploy` from infra/).
"""
import json
import string
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "data-foundation"))
from event_simulator import config as sim_config  # noqa: E402

STACK_NAME = "AuroraGamesFoundationStack"
FEATURE_DIR = Path(__file__).parent
DDL_FILE = FEATURE_DIR / "ddl" / "gold_player_features.sql"
FEATURE_PUBLICATION_MANIFEST = "manifests/published/gold_player_features.json"

session = boto3.Session()
cfn = session.client("cloudformation")
s3 = session.client("s3")
athena = session.client("athena")


def get_stack_outputs() -> dict:
    resp = cfn.describe_stacks(StackName=STACK_NAME)
    outputs = resp["Stacks"][0]["Outputs"]
    return {o["OutputKey"]: o["OutputValue"] for o in outputs}


def clear_prefix(bucket: str, prefix: str):
    paginator = s3.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        keys.extend(o["Key"] for o in page.get("Contents", []))
    for i in range(0, len(keys), 1000):
        batch = keys[i : i + 1000]
        s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in batch]})


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
        reason = status.get("StateChangeReason", "unknown error")
        raise RuntimeError(f"Query failed ({state}): {reason}\n--- SQL ---\n{sql}")
    return query_id


def print_query_results(query_id: str, max_rows: int = 20):
    resp = athena.get_query_results(QueryExecutionId=query_id, MaxResults=max_rows + 1)
    rows = resp["ResultSet"]["Rows"]
    if not rows:
        print("  (no rows)")
        return
    header = [c.get("VarCharValue", "") for c in rows[0]["Data"]]
    print("  " + " | ".join(header))
    for row in rows[1 : max_rows + 1]:
        print("  " + " | ".join(c.get("VarCharValue", "") for c in row["Data"]))


def publish_completion_manifest(bucket: str, max_date: str):
    body = {
        "table": "gold_player_features",
        "published_through": max_date,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "source": "fixed_simulator_build",
    }
    s3.put_object(
        Bucket=bucket,
        Key=FEATURE_PUBLICATION_MANIFEST,
        Body=json.dumps(body, sort_keys=True).encode("utf-8"),
        ContentType="application/json",
    )
    print(f"Published completion marker through {max_date}.")


def main():
    outputs = get_stack_outputs()
    bucket = outputs["LakeBucketName"]
    database = outputs["GlueDatabaseName"]
    workgroup = outputs["AthenaWorkgroupName"]
    print(f"Bucket={bucket} Database={database} Workgroup={workgroup}")

    print("Clearing previous gold_player_features output (for idempotent re-runs) ...")
    s3.delete_object(Bucket=bucket, Key=FEATURE_PUBLICATION_MANIFEST)
    clear_prefix(bucket, "gold/player_features/")
    clear_prefix(bucket, "athena-results/tables/")

    template = string.Template(DDL_FILE.read_text(encoding="utf-8"))
    sql = template.substitute(
        bucket=bucket,
        min_date=sim_config.START_DATE.isoformat(),
        num_days_minus_1=sim_config.NUM_DAYS - 1,
    )
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    print(f"Running {DDL_FILE.name} ({len(statements)} statement(s)) ...")
    for statement in statements:
        code_lines = [ln for ln in statement.splitlines() if ln.strip() and not ln.strip().startswith("--")]
        label = code_lines[0][:60] if code_lines else statement[:60]
        print(f"  {label} ...")
        run_query(statement, database, workgroup)
    print("gold_player_features built.")

    print("\n=== Row count ===")
    qid = run_query("SELECT COUNT(*) AS row_count FROM gold_player_features", database, workgroup)
    print_query_results(qid)

    print("\n=== Ring player features during the arbitrage window (should show a high withdrawal ratio) ===")
    start = sim_config.START_DATE + timedelta(days=sim_config.ARBITRAGE_RING_START_DAY)
    end = sim_config.START_DATE + timedelta(days=sim_config.ARBITRAGE_RING_END_DAY)
    ring_check_sql = f"""
    SELECT snapshot_date, player_id, deposit_amount_usd_7d, withdrawal_amount_usd_7d,
           withdrawal_to_deposit_ratio_7d, bonus_claims_30d
    FROM gold_player_features
    WHERE player_id = 'p_ring_00' AND snapshot_date BETWEEN '{start}' AND '{end}'
    ORDER BY snapshot_date
    """
    qid = run_query(ring_check_sql, database, workgroup)
    print_query_results(qid)

    print("\n=== A normal player's withdrawal_to_deposit_ratio_7d for comparison ===")
    normal_check_sql = """
    SELECT snapshot_date, player_id, deposit_amount_usd_7d, withdrawal_amount_usd_7d,
           withdrawal_to_deposit_ratio_7d
    FROM gold_player_features
    WHERE player_id = 'p_000000'
    ORDER BY snapshot_date DESC
    LIMIT 10
    """
    qid = run_query(normal_check_sql, database, workgroup)
    print_query_results(qid)

    max_date = (sim_config.START_DATE + timedelta(days=sim_config.NUM_DAYS - 1)).isoformat()
    publish_completion_manifest(bucket, max_date)


if __name__ == "__main__":
    main()
