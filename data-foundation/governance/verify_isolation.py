"""Proves the client-data-isolation boundary: assumes each site's analyst
role and runs the same query against gold_daily_kpi - a table containing
all 3 sites' rows - and shows each role only ever sees its own site's
data, plus one run with the caller's own (unfiltered) credentials for
contrast.

Requires setup_client_isolation.py to have been run first.
"""
import time

import boto3

STACK_NAME = "AuroraGamesFoundationStack"
GOVERNANCE_STACK_NAME = "AuroraGamesGovernanceStack"
CLIENT_SITES = ["site_a", "site_b", "site_c"]
QUERY = "SELECT client_site_id, COUNT(*) AS rows FROM gold_daily_kpi GROUP BY client_site_id ORDER BY client_site_id"

session = boto3.Session()
cfn = session.client("cloudformation")
sts = session.client("sts")


def stack_outputs(stack_name: str) -> dict:
    resp = cfn.describe_stacks(StackName=stack_name)
    return {o["OutputKey"]: o["OutputValue"] for o in resp["Stacks"][0]["Outputs"]}


def run_query_as(athena_client, sql: str, database: str, workgroup: str) -> list:
    resp = athena_client.start_query_execution(
        QueryString=sql, QueryExecutionContext={"Database": database}, WorkGroup=workgroup
    )
    query_id = resp["QueryExecutionId"]
    while True:
        status = athena_client.get_query_execution(QueryExecutionId=query_id)["QueryExecution"]["Status"]
        state = status["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(1)
    if state != "SUCCEEDED":
        raise RuntimeError(f"Query failed ({state}): {status.get('StateChangeReason')}")

    rows = []
    header = None
    for page in athena_client.get_paginator("get_query_results").paginate(QueryExecutionId=query_id):
        for row in page["ResultSet"]["Rows"]:
            values = [c.get("VarCharValue") for c in row["Data"]]
            if header is None:
                header = values
                continue
            rows.append(dict(zip(header, values)))
    return rows


def assumed_session(role_arn: str) -> boto3.Session:
    creds = sts.assume_role(RoleArn=role_arn, RoleSessionName="isolation-verification")["Credentials"]
    return boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )


def main():
    foundation = stack_outputs(STACK_NAME)
    governance = stack_outputs(GOVERNANCE_STACK_NAME)
    database, workgroup = foundation["GlueDatabaseName"], foundation["AthenaWorkgroupName"]

    print("=== Baseline: caller's own (unfiltered admin) credentials ===")
    rows = run_query_as(session.client("athena"), QUERY, database, workgroup)
    print(f"  Sees {len(rows)} site(s): {rows}")

    for site in CLIENT_SITES:
        label = "".join(p.capitalize() for p in site.split("_"))
        role_arn = governance[f"AnalystRoleArn{label}"]
        print(f"\n=== Assumed role for {site}: {role_arn} ===")
        assumed = assumed_session(role_arn)
        rows = run_query_as(assumed.client("athena"), QUERY, database, workgroup)
        sites_seen = {r["client_site_id"] for r in rows}
        ok = sites_seen == {site}
        print(f"  Sees {len(rows)} site(s): {rows}")
        print(f"  {'PASS' if ok else 'FAIL'}: expected to see only '{site}'")


if __name__ == "__main__":
    main()
