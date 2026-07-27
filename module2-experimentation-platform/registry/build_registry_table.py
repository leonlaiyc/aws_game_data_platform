"""Registers the experiments_export Athena table over the S3 snapshot kept
in sync by ExperimentsExportHandler (see README.md). Safe to run any time
after the RegistryStack is deployed - it doesn't need any experiments to
exist yet, since it just declares the schema/location.
"""
import string
import time
from pathlib import Path

import boto3

STACK_NAME = "AuroraGamesFoundationStack"
DDL_FILE = Path(__file__).parent / "ddl" / "experiments_export.sql"

session = boto3.Session()
cfn = session.client("cloudformation")
athena = session.client("athena")


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
        raise RuntimeError(f"Query failed ({state}): {status.get('StateChangeReason')}\n--- SQL ---\n{sql}")
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


def main():
    outputs = {o["OutputKey"]: o["OutputValue"] for o in cfn.describe_stacks(StackName=STACK_NAME)["Stacks"][0]["Outputs"]}
    bucket, database, workgroup = outputs["LakeBucketName"], outputs["GlueDatabaseName"], outputs["AthenaWorkgroupName"]

    sql = string.Template(DDL_FILE.read_text(encoding="utf-8")).substitute(bucket=bucket)
    for statement in [s.strip() for s in sql.split(";") if s.strip()]:
        label = next((ln for ln in statement.splitlines() if ln.strip() and not ln.strip().startswith("--")), statement[:60])
        print(f"{label[:60]} ...")
        run_query(statement, database, workgroup)
    print("experiments_export table registered.")

    print("\n=== Current experiments ===")
    qid = run_query(
        "SELECT experiment_id, name, state, oec_metric, stop_reason FROM experiments_export",
        database, workgroup,
    )
    print_query_results(qid)


if __name__ == "__main__":
    main()
