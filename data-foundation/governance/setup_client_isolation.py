"""One-time (idempotent) setup for the client-data-isolation demo:

1. Revokes the IAM_ALLOWED_PRINCIPALS compatibility grant on gold_daily_kpi.
   Every new Glue table gets this grant by default (see
   module2-experimentation-platform/orchestration/README.md's Lake
   Formation note) - it means "defer entirely to IAM", which makes a
   Lake Formation row-level filter a no-op for any principal whose IAM
   policy happens to allow glue:GetTable etc. It must be revoked on this
   specific table (not the whole database - other tables keep working
   the default way) for the filters below to actually be enforced.
2. Creates one row-level Data Filter per client site
   (client_site_id = '<site>').
3. Grants SELECT with that filter to the matching analyst IAM role
   (created by infra/infra/governance_stack.py).

Run with the account's own Data Lake Administrator credentials - this is
a script, not a CDK resource, because `cdk deploy` runs as the CDK
bootstrap's CloudFormation execution role, which is not a registered Data
Lake Administrator (see governance_stack.py's docstring).
"""
import boto3

STACK_NAME = "AuroraGamesFoundationStack"
GOVERNANCE_STACK_NAME = "AuroraGamesGovernanceStack"
DATABASE_NAME = "aurora_games_lake"
TABLE_NAME = "gold_daily_kpi"
CLIENT_SITES = ["site_a", "site_b", "site_c"]

session = boto3.Session()
cfn = session.client("cloudformation")
lakeformation = session.client("lakeformation")
sts = session.client("sts")


def stack_outputs(stack_name: str) -> dict:
    resp = cfn.describe_stacks(StackName=stack_name)
    return {o["OutputKey"]: o["OutputValue"] for o in resp["Stacks"][0]["Outputs"]}


def revoke_iam_allowed_principals():
    try:
        lakeformation.revoke_permissions(
            Principal={"DataLakePrincipalIdentifier": "IAM_ALLOWED_PRINCIPALS"},
            Resource={"Table": {"DatabaseName": DATABASE_NAME, "Name": TABLE_NAME}},
            Permissions=["ALL"],
        )
        print(f"Revoked IAM_ALLOWED_PRINCIPALS on {TABLE_NAME}.")
    except lakeformation.exceptions.InvalidInputException as e:
        # Already revoked (idempotent re-run) - Lake Formation raises this
        # rather than a no-op success when the grant doesn't exist.
        print(f"IAM_ALLOWED_PRINCIPALS already revoked on {TABLE_NAME} (or never existed): {e}")


def create_data_filter(account_id: str, site: str):
    filter_name = f"{site}_only"
    try:
        lakeformation.create_data_cells_filter(
            TableData={
                "TableCatalogId": account_id,
                "DatabaseName": DATABASE_NAME,
                "TableName": TABLE_NAME,
                "Name": filter_name,
                "RowFilter": {"FilterExpression": f"client_site_id = '{site}'"},
                "ColumnWildcard": {"ExcludedColumnNames": []},
            }
        )
        print(f"Created data filter '{filter_name}'.")
    except lakeformation.exceptions.AlreadyExistsException:
        print(f"Data filter '{filter_name}' already exists, skipping.")


def grant_filtered_select(account_id: str, site: str, role_arn: str):
    filter_name = f"{site}_only"
    lakeformation.grant_permissions(
        Principal={"DataLakePrincipalIdentifier": role_arn},
        Resource={
            "DataCellsFilter": {
                "TableCatalogId": account_id,
                "DatabaseName": DATABASE_NAME,
                "TableName": TABLE_NAME,
                "Name": filter_name,
            }
        },
        Permissions=["SELECT"],
    )
    print(f"Granted SELECT on filter '{filter_name}' to {role_arn}.")


def main():
    account_id = sts.get_caller_identity()["Account"]
    governance_outputs = stack_outputs(GOVERNANCE_STACK_NAME)

    revoke_iam_allowed_principals()

    for site in CLIENT_SITES:
        create_data_filter(account_id, site)
        label = "".join(p.capitalize() for p in site.split("_"))
        role_arn = governance_outputs[f"AnalystRoleArn{label}"]
        grant_filtered_select(account_id, site, role_arn)

    print("\nClient isolation setup complete. Run verify_isolation.py to confirm.")


if __name__ == "__main__":
    main()
