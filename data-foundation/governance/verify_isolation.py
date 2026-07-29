"""Proves the client-data-isolation boundary - in both directions.

**Positive test:** each site's analyst role queries gold_daily_kpi (a table
holding all 3 sites' rows) through Athena and sees only its own site.

**Negative test:** the same role attempts to read the underlying Parquet
directly from S3, and must be denied.

The negative test is the point of this script. An earlier version only ran the
positive one, watched the row filter work, and concluded that a role was
"physically unable" to read another tenant's data. It wasn't: the roles held
`grant_read_write` on the whole lake bucket, so a plain `GetObject` bypassed
Lake Formation entirely. The positive test passed the whole time.

**A positive test on the intended path cannot substantiate a claim about
every other path.** If a design claims something is impossible, the test has
to attempt the thing.

Exits non-zero if any check fails, so it is usable as a gate rather than
something a human has to read carefully.

Requires setup_client_isolation.py to have been run first.
"""
import sys
import time

import boto3
from botocore.exceptions import ClientError

STACK_NAME = "AuroraGamesFoundationStack"
GOVERNANCE_STACK_NAME = "AuroraGamesGovernanceStack"
CLIENT_SITES = ["site_a", "site_b", "site_c"]
GOLD_TABLE_PREFIX = "gold/daily_kpi/"
QUERY = ("SELECT client_site_id, COUNT(*) AS row_count FROM gold_daily_kpi "
         "GROUP BY client_site_id ORDER BY client_site_id")

session = boto3.Session()
cfn = session.client("cloudformation")
sts = session.client("sts")
s3_admin = session.client("s3")


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

    rows, header = [], None
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


def a_gold_object_key(bucket: str) -> str:
    """Any real object under the Gold table's prefix, found with admin
    credentials so the negative test targets a key that genuinely exists -
    otherwise a NoSuchKey could be mistaken for a successful denial."""
    resp = s3_admin.list_objects_v2(Bucket=bucket, Prefix=GOLD_TABLE_PREFIX, MaxKeys=10)
    for obj in resp.get("Contents", []):
        if not obj["Key"].endswith("/"):
            return obj["Key"]
    raise RuntimeError(f"No objects found under s3://{bucket}/{GOLD_TABLE_PREFIX}")


def check_direct_s3_denied(assumed: boto3.Session, bucket: str, key: str) -> bool:
    """The bypass attempt. Must be denied."""
    try:
        assumed.client("s3").get_object(Bucket=bucket, Key=key)
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("AccessDenied", "AccessDeniedException", "403"):
            return True
        print(f"    unexpected error code {code!r} - treating as NOT a clean denial")
        return False
    return False  # the read succeeded: isolation is bypassable


def main() -> int:
    foundation = stack_outputs(STACK_NAME)
    governance = stack_outputs(GOVERNANCE_STACK_NAME)
    database = foundation["GlueDatabaseName"]
    bucket = foundation["LakeBucketName"]
    gold_key = a_gold_object_key(bucket)

    failures = []

    print("=== Baseline: caller's own (unfiltered admin) credentials ===")
    rows = run_query_as(session.client("athena"), QUERY, database, foundation["AthenaWorkgroupName"])
    print(f"  Sees {len(rows)} site(s): {rows}")
    if len(rows) != len(CLIENT_SITES):
        failures.append(f"baseline expected {len(CLIENT_SITES)} sites, saw {len(rows)}")

    print(f"\n=== Negative test target: s3://{bucket}/{gold_key} ===")

    for site in CLIENT_SITES:
        label = "".join(p.capitalize() for p in site.split("_"))
        role_arn = governance[f"AnalystRoleArn{label}"]
        workgroup = governance[f"AnalystWorkgroupName{label}"]
        print(f"\n=== {site} ({role_arn}) ===")
        assumed = assumed_session(role_arn)

        # 1. Positive: the intended path is filtered.
        rows = run_query_as(assumed.client("athena"), QUERY, database, workgroup)
        sites_seen = {r["client_site_id"] for r in rows}
        if sites_seen == {site}:
            print(f"  [PASS] Athena path filtered - sees only {site}: {rows}")
        else:
            print(f"  [FAIL] Athena path leaked - saw {sorted(sites_seen)}")
            failures.append(f"{site}: Athena returned {sorted(sites_seen)}")

        # 2. Negative: every other path is closed.
        if check_direct_s3_denied(assumed, bucket, gold_key):
            print("  [PASS] direct S3 GetObject on the Gold data denied")
        else:
            print("  [FAIL] direct S3 GetObject SUCCEEDED - the row filter is bypassable")
            failures.append(f"{site}: direct S3 read of {gold_key} was not denied")

    print("\n" + "=" * 70)
    if failures:
        print(f"FAILED ({len(failures)}):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"PASSED: {len(CLIENT_SITES)} roles, each filtered on the Athena path "
          f"and denied on the direct-S3 path")
    return 0


if __name__ == "__main__":
    sys.exit(main())
