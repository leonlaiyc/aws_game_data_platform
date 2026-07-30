"""Registers Module 2 assignment and product-exposure tables in Athena. Run once after
infra deploy (or again any time the DDL changes) - safe to run before any
experiment has been assigned, since it just declares schema/location.
"""
import string
import time
from pathlib import Path

import boto3

STACK_NAME = "AuroraGamesFoundationStack"
DDL_FILES = [
    Path(__file__).parent / "ddl" / "gold_experiment_assignments.sql",
    Path(__file__).parent / "ddl" / "gold_experiment_exposures.sql",
]

def split_sql_statements(sql: str) -> list[str]:
    """Split DDL without treating semicolons in comments or quotes as terminators."""
    statements: list[str] = []
    current: list[str] = []
    in_single_quote = False
    in_double_quote = False
    in_line_comment = False
    index = 0

    while index < len(sql):
        char = sql[index]
        next_char = sql[index + 1] if index + 1 < len(sql) else ""

        if in_line_comment:
            if char in "\r\n":
                in_line_comment = False
                current.append(char)
            index += 1
            continue

        if not in_single_quote and not in_double_quote and char == "-" and next_char == "-":
            in_line_comment = True
            index += 2
            continue

        if char == "'" and not in_double_quote:
            current.append(char)
            if in_single_quote and next_char == "'":
                current.append(next_char)
                index += 2
                continue
            in_single_quote = not in_single_quote
            index += 1
            continue

        if char == '"' and not in_single_quote:
            current.append(char)
            if in_double_quote and next_char == '"':
                current.append(next_char)
                index += 2
                continue
            in_double_quote = not in_double_quote
            index += 1
            continue

        if char == ";" and not in_single_quote and not in_double_quote:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(char)
        index += 1

    statement = "".join(current).strip()
    if statement:
        statements.append(statement)
    return statements


def run_query(athena_client, sql: str, database: str, workgroup: str) -> str:
    resp = athena_client.start_query_execution(
        QueryString=sql, QueryExecutionContext={"Database": database}, WorkGroup=workgroup
    )
    query_id = resp["QueryExecutionId"]
    while True:
        status = athena_client.get_query_execution(
            QueryExecutionId=query_id
        )["QueryExecution"]["Status"]
        state = status["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)
    if state != "SUCCEEDED":
        raise RuntimeError(f"Query failed ({state}): {status.get('StateChangeReason')}\n--- SQL ---\n{sql}")
    return query_id


def main():
    session = boto3.Session()
    cfn = session.client("cloudformation")
    athena = session.client("athena")
    outputs = {o["OutputKey"]: o["OutputValue"] for o in cfn.describe_stacks(StackName=STACK_NAME)["Stacks"][0]["Outputs"]}
    bucket, database, workgroup = outputs["LakeBucketName"], outputs["GlueDatabaseName"], outputs["AthenaWorkgroupName"]

    for ddl_file in DDL_FILES:
        sql = string.Template(
            ddl_file.read_text(encoding="utf-8")
        ).substitute(bucket=bucket)
        for statement in split_sql_statements(sql):
            label = next(
                (
                    line
                    for line in statement.splitlines()
                    if line.strip() and not line.strip().startswith("--")
                ),
                statement[:60],
            )
            print(f"{label[:60]} ...")
            run_query(athena, statement, database, workgroup)
        print(f"{ddl_file.stem} registered.")


if __name__ == "__main__":
    main()
