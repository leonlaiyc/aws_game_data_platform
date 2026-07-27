from aws_cdk import (
    CfnOutput,
    Stack,
    aws_iam as iam,
    aws_s3 as s3,
)
from constructs import Construct

from infra.foundation_stack import ATHENA_WORKGROUP_NAME, GLUE_DATABASE_NAME

CLIENT_SITES = ["site_a", "site_b", "site_c"]
ISOLATION_DEMO_TABLE = "gold_daily_kpi"


def _label(site: str) -> str:
    return "".join(p.capitalize() for p in site.split("_"))  # "site_a" -> "SiteA"


class GovernanceStack(Stack):
    """One IAM role per client site, demonstrating the multi-tenant data
    isolation boundary: each role can only ever see its own site's rows in
    gold_daily_kpi, enforced by a Lake Formation row-level Data Filter (not
    by application logic - see data-foundation/governance/README.md).

    This stack only creates the IAM roles. The Lake Formation Data Filters
    and grants themselves are NOT CDK resources here: `cdk deploy` runs as
    the CDK bootstrap's CloudFormation execution role, which isn't a
    registered Lake Formation Data Lake Administrator, so it would hit the
    same "Insufficient permissions" wall documented in
    module2-experimentation-platform/orchestration/README.md. Consistent
    with how that was resolved, the Lake Formation setup here is a script
    (data-foundation/governance/setup_client_isolation.py) run with the
    account's own Data Lake Administrator credentials, not a CDK resource.
    """

    def __init__(self, scope: Construct, construct_id: str, lake_bucket: s3.IBucket, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.analyst_roles = {}
        for site in CLIENT_SITES:
            label = _label(site)
            role = iam.Role(
                self,
                f"Analyst{label}",
                role_name=f"aurora-games-analyst-{site}",
                assumed_by=iam.AccountPrincipal(self.account),
                description=(
                    f"Demo role: can only ever see {site}'s rows in {ISOLATION_DEMO_TABLE}, "
                    "enforced by a Lake Formation row-level filter, not by application logic. "
                    "Trust policy is simplified to the account root for demo purposes; a real "
                    "deployment would scope this to a specific client-side identity (SSO group, "
                    "federated role, etc.)."
                ),
            )
            role.add_to_policy(
                iam.PolicyStatement(
                    actions=["athena:StartQueryExecution", "athena:GetQueryExecution", "athena:GetQueryResults"],
                    resources=[f"arn:aws:athena:{self.region}:{self.account}:workgroup/{ATHENA_WORKGROUP_NAME}"],
                )
            )
            role.add_to_policy(
                iam.PolicyStatement(
                    # Scoped to only the one table this role is meant to see -
                    # least privilege independent of the row-filter itself.
                    actions=["glue:GetTable", "glue:GetDatabase", "glue:GetPartition", "glue:GetPartitions"],
                    resources=[
                        f"arn:aws:glue:{self.region}:{self.account}:catalog",
                        f"arn:aws:glue:{self.region}:{self.account}:database/{GLUE_DATABASE_NAME}",
                        f"arn:aws:glue:{self.region}:{self.account}:table/{GLUE_DATABASE_NAME}/{ISOLATION_DEMO_TABLE}",
                    ],
                )
            )
            role.add_to_policy(
                iam.PolicyStatement(actions=["lakeformation:GetDataAccess"], resources=["*"])
            )
            lake_bucket.grant_read_write(role)  # read the underlying Parquet + write Athena query results

            self.analyst_roles[site] = role
            CfnOutput(self, f"AnalystRoleArn{label}", value=role.role_arn)
