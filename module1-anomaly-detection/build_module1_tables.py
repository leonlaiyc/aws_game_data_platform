"""Registers anomaly_alerts and flagged_players in Athena. Safe to run any
time after infra deploy - just declares schema/location, no data needed
yet.
"""
import string
import time
from pathlib import Path

import boto3

STACK_NAME = "AuroraGamesFoundationStack"
DDL_FILES = [
    Path(__file__).parent / "data_anomaly" / "ddl" / "anomaly_alerts.sql",
    Path(__file__).parent / "arbitrage_detection" / "ddl" / "flagged_players.sql",
]

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

    for ddl_file in DDL_FILES:
        sql = string.Template(ddl_file.read_text(encoding="utf-8")).substitute(bucket=bucket)
        for statement in [s.strip() for s in sql.split(";") if s.strip()]:
            label = next((ln for ln in statement.splitlines() if ln.strip() and not ln.strip().startswith("--")), statement[:60])
            print(f"{ddl_file.name}: {label[:60]} ...")
            run_query(statement, database, workgroup)
    print("anomaly_alerts and flagged_players registered.")


if __name__ == "__main__":
    main()
