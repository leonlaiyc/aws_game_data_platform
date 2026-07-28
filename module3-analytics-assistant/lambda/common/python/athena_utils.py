"""Shared Athena polling helper - same pattern used across this project's
other Lambda Layers (see module2/module1's own copies)."""
import os
import time

import boto3

athena = boto3.client("athena")


def run_athena_query(sql: str, database: str = None, workgroup: str = None) -> str:
    database = database or os.environ["GLUE_DATABASE_NAME"]
    workgroup = workgroup or os.environ["ATHENA_WORKGROUP_NAME"]
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
