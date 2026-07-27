"""Builds the Aurora Games data lake end to end:

1. Uploads the local simulator output (data-foundation/event_simulator/output)
   to S3 as gzip-compressed Bronze JSONL.
2. Runs the DDL in data-foundation/lake/ddl/ in order (Bronze external table,
   Silver Parquet CTAS, two Gold Parquet CTAS).
3. Runs the example queries in data-foundation/lake/queries/ and prints the
   results, as an end-to-end sanity check.

Requires: `aws configure` already set up, and the FoundationStack already
deployed (`cdk deploy` from infra/).
"""
import gzip
import string
import sys
import time
from datetime import timedelta
from pathlib import Path

import boto3

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from event_simulator import config as sim_config  # noqa: E402

STACK_NAME = "AuroraGamesFoundationStack"
LAKE_DIR = Path(__file__).parent
SIMULATOR_OUTPUT = LAKE_DIR.parent / "event_simulator" / "output"
DDL_DIR = LAKE_DIR / "ddl"
QUERIES_DIR = LAKE_DIR / "queries"

session = boto3.Session()
region = session.region_name
cfn = session.client("cloudformation")
s3 = session.client("s3")
athena = session.client("athena")


def get_stack_outputs() -> dict:
    resp = cfn.describe_stacks(StackName=STACK_NAME)
    outputs = resp["Stacks"][0]["Outputs"]
    return {o["OutputKey"]: o["OutputValue"] for o in outputs}


def upload_bronze(bucket: str):
    day_dirs = sorted(SIMULATOR_OUTPUT.glob("dt=*"))
    if not day_dirs:
        raise SystemExit(f"No simulator output found under {SIMULATOR_OUTPUT}. Run the simulator first.")

    print(f"Uploading {len(day_dirs)} days of bronze data to s3://{bucket}/bronze/ ...")
    for day_dir in day_dirs:
        src = day_dir / "events.jsonl"
        if not src.exists():
            continue
        raw = src.read_bytes()
        compressed = gzip.compress(raw)
        key = f"bronze/{day_dir.name}/events.jsonl.gz"
        s3.put_object(Bucket=bucket, Key=key, Body=compressed)
    print("Bronze upload complete.")

    manifest = SIMULATOR_OUTPUT / "scenario_manifest.json"
    if manifest.exists():
        s3.put_object(Bucket=bucket, Key="manifests/scenario_manifest.json", Body=manifest.read_bytes())
        print("Uploaded scenario_manifest.json.")


def clear_prefix(bucket: str, prefix: str):
    paginator = s3.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        keys.extend(o["Key"] for o in page.get("Contents", []))
    if not keys:
        return
    for i in range(0, len(keys), 1000):
        batch = keys[i : i + 1000]
        s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in batch]})


def run_query(sql: str, database: str, workgroup: str) -> str:
    resp = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": database},
        WorkGroup=workgroup,
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
        values = [c.get("VarCharValue", "") for c in row["Data"]]
        print("  " + " | ".join(values))


def main():
    outputs = get_stack_outputs()
    bucket = outputs["LakeBucketName"]
    database = outputs["GlueDatabaseName"]
    workgroup = outputs["AthenaWorkgroupName"]
    print(f"Bucket={bucket} Database={database} Workgroup={workgroup} Region={region}")

    upload_bronze(bucket)

    print("\nClearing any previous Silver/Gold output (for idempotent re-runs) ...")
    clear_prefix(bucket, "silver/events/")
    clear_prefix(bucket, "gold/daily_kpi/")
    clear_prefix(bucket, "gold/cohort_retention/")
    clear_prefix(bucket, "athena-results/tables/")  # staging debris from any previously failed CTAS

    min_date = sim_config.START_DATE.isoformat()
    max_date = (sim_config.START_DATE + timedelta(days=sim_config.NUM_DAYS - 1)).isoformat()

    print("\nRunning DDL ...")
    for ddl_file in sorted(DDL_DIR.glob("*.sql")):
        template = string.Template(ddl_file.read_text(encoding="utf-8"))
        sql = template.substitute(bucket=bucket, min_date=min_date, max_date=max_date)
        # Athena only allows one statement per StartQueryExecution call, but each
        # DDL file has a DROP TABLE IF EXISTS followed by the CREATE statement.
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        for statement in statements:
            code_lines = [ln for ln in statement.splitlines() if ln.strip() and not ln.strip().startswith("--")]
            label = code_lines[0][:60] if code_lines else statement[:60]
            print(f"  {ddl_file.name}: {label} ...")
            run_query(statement, database, workgroup)
    print("DDL complete: bronze_events, silver_events, gold_daily_kpi, gold_cohort_retention.")

    print("\nRunning example queries ...")
    for query_file in sorted(QUERIES_DIR.glob("*.sql")):
        print(f"\n=== {query_file.name} ===")
        sql = query_file.read_text(encoding="utf-8").strip().rstrip(";")
        query_id = run_query(sql, database, workgroup)
        print_query_results(query_id)


if __name__ == "__main__":
    main()
