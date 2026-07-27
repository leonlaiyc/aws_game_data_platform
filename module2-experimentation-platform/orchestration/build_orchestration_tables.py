"""Registers gold_experiment_assignments in Athena. Run once after
infra deploy (or again any time the DDL changes) - safe to run before any
experiment has been assigned, since it just declares schema/location.
"""
import string
import time
from pathlib import Path

import boto3

STACK_NAME = "AuroraGamesFoundationStack"
DDL_FILE = Path(__file__).parent / "ddl" / "gold_experiment_assignments.sql"

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


def main():
    outputs = {o["OutputKey"]: o["OutputValue"] for o in cfn.describe_stacks(StackName=STACK_NAME)["Stacks"][0]["Outputs"]}
    bucket, database, workgroup = outputs["LakeBucketName"], outputs["GlueDatabaseName"], outputs["AthenaWorkgroupName"]

    sql = string.Template(DDL_FILE.read_text(encoding="utf-8")).substitute(bucket=bucket)
    for statement in [s.strip() for s in sql.split(";") if s.strip()]:
        label = next((ln for ln in statement.splitlines() if ln.strip() and not ln.strip().startswith("--")), statement[:60])
        print(f"{label[:60]} ...")
        run_query(statement, database, workgroup)
    print("gold_experiment_assignments registered.")


if __name__ == "__main__":
    main()
