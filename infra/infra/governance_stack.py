from aws_cdk import (
    CfnOutput,
    Stack,
    aws_athena as athena,
    aws_iam as iam,
    aws_s3 as s3,
)
from constructs import Construct

from infra.foundation_stack import GLUE_DATABASE_NAME, OPERATOR_ROLE_NAME

CLIENT_SITES = ["site_a", "site_b", "site_c"]
ISOLATION_DEMO_TABLE = "gold_daily_kpi"
ANALYST_RESULTS_PREFIX = "athena-results/analyst"


def _label(site: str) -> str:
    return "".join(p.capitalize() for p in site.split("_"))  # "site_a" -> "SiteA"


class GovernanceStack(Stack):
    """One IAM role per client site, demonstrating the multi-tenant data
    isolation boundary: each role can only ever see its own site's rows in
    gold_daily_kpi, enforced by a Lake Formation row-level Data Filter (not
    by application logic - see data-foundation/governance/README.md).

    ## The bug this stack used to contain, and what it teaches

    An earlier version granted each analyst role `grant_read_write` on the
    entire lake bucket, with a comment cheerfully explaining that this was
    to "read the underlying Parquet". That made the row-level filter
    **decorative**: a role could simply `aws s3 cp` the Gold objects and read
    every tenant's rows - and, because the grant included write, modify them.
    Meanwhile the isolation test only ever exercised the Athena path, saw it
    correctly filtered, and reported success.

    The lesson is about verification, not about IAM: an absolute claim
    ("physically unable to read another tenant's data") requires testing the
    *bypass* path, not just the intended one. A positive test on the happy
    path cannot substantiate a negative claim. `verify_isolation.py` now
    asserts the direct-S3 read is denied, which is the test that should have
    existed before the claim was ever written down.

    ## How isolation actually works now

    Analyst roles hold **no S3 permission on the data at all**. Athena reaches
    the underlying objects through Lake Formation credential vending
    (`lakeformation:GetDataAccess` against a registered location), so the only
    path to the data applies the row filter by construction. Each role also
    gets its own Athena workgroup writing to its own results prefix, so one
    tenant's query output is not readable by another - previously they all
    shared one prefix that every role could read.

    Those per-site workgroups set `enforce_work_group_configuration=True`,
    unlike the shared pipeline workgroup. The pipeline one has it off because
    CTAS needs to specify its own `external_location`; analysts never run
    CTAS, so here enforcement is exactly right - it stops a caller redirecting
    results somewhere the isolation boundary doesn't cover.

    This stack only creates IAM roles and workgroups. The Lake Formation
    location registration, Data Filters and grants are NOT CDK resources:
    `cdk deploy` runs as the CDK bootstrap's CloudFormation execution role,
    which isn't a registered Data Lake Administrator. They live in
    data-foundation/governance/setup_client_isolation.py, run with the
    account's own admin credentials.
    """

    def __init__(self, scope: Construct, construct_id: str, lake_bucket: s3.IBucket, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The internal-operator counterpart to the per-tenant analyst roles.
        # Module 3 treats it as unscoped (may query any site); Module 4 lets it
        # see the audit track. Everything else is scoped or refused, so this
        # role is the only way to get an unrestricted view - which is what
        # makes "fail closed" implementable rather than aspirational.
        self.operator_role = iam.Role(
            self, "Operator",
            role_name=OPERATOR_ROLE_NAME,
            assumed_by=iam.AccountPrincipal(self.account),
            description="Internal operator: unrestricted tenant scope in Module 3, audit-track "
                        "access in Module 4. Assumed by demos and by human operators.",
        )
        self.operator_role.add_to_policy(
            iam.PolicyStatement(actions=["execute-api:Invoke"],
                                 resources=[f"arn:aws:execute-api:{self.region}:{self.account}:*/*/*/*"])
        )
        CfnOutput(self, "OperatorRoleArn", value=self.operator_role.role_arn)

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
            # Its own workgroup, its own results prefix. Enforcement is ON here
            # (see class docstring): an analyst must not be able to redirect
            # query output outside the prefix its isolation is scoped to.
            results_prefix = f"{ANALYST_RESULTS_PREFIX}/{site}/"
            workgroup_name = f"aurora-games-analyst-{site}"
            athena.CfnWorkGroup(
                self, f"AnalystWorkgroup{label}",
                name=workgroup_name,
                recursive_delete_option=True,
                work_group_configuration=athena.CfnWorkGroup.WorkGroupConfigurationProperty(
                    enforce_work_group_configuration=True,
                    bytes_scanned_cutoff_per_query=100 * 1024 * 1024,  # 100 MB ceiling per analyst query
                    result_configuration=athena.CfnWorkGroup.ResultConfigurationProperty(
                        output_location=f"s3://{lake_bucket.bucket_name}/{results_prefix}"
                    ),
                ),
            )
            role.add_to_policy(
                iam.PolicyStatement(
                    actions=["athena:StartQueryExecution", "athena:GetQueryExecution", "athena:GetQueryResults"],
                    resources=[f"arn:aws:athena:{self.region}:{self.account}:workgroup/{workgroup_name}"],
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
            # Lets this role call the IAM-authorised analytics API, where its
            # own ARN determines which site it may ask about.
            role.add_to_policy(
                iam.PolicyStatement(actions=["execute-api:Invoke"],
                                     resources=[f"arn:aws:execute-api:{self.region}:{self.account}:*/*/*/*"])
            )

            # DELIBERATELY NOT `lake_bucket.grant_read_write(role)`.
            #
            # The role gets no S3 permission on bronze/, silver/ or gold/ at
            # all. Athena reads the underlying objects using credentials Lake
            # Formation vends after applying the row filter, so the filtered
            # path is the ONLY path. Granting the role direct S3 access - as an
            # earlier version did - would let it bypass the filter entirely
            # with a plain GetObject, which is precisely what the negative test
            # in verify_isolation.py now asserts is impossible.
            #
            # The one S3 permission it does need is its own query results.
            role.add_to_policy(
                iam.PolicyStatement(
                    actions=["s3:GetObject", "s3:PutObject", "s3:AbortMultipartUpload"],
                    resources=[f"{lake_bucket.bucket_arn}/{results_prefix}*"],
                )
            )
            # Listing is restricted to the role's own results prefix...
            role.add_to_policy(
                iam.PolicyStatement(
                    actions=["s3:ListBucket"],
                    resources=[lake_bucket.bucket_arn],
                    conditions={"StringLike": {"s3:prefix": [f"{results_prefix}*"]}},
                )
            )
            # ...but GetBucketLocation is a bucket-level call that does not
            # support the s3:prefix condition key, so pairing them in one
            # conditioned statement silently denies it and Athena fails with
            # "Unable to verify/create output bucket". It reveals only the
            # bucket's region, so granting it unconditionally is not a leak.
            role.add_to_policy(
                iam.PolicyStatement(
                    actions=["s3:GetBucketLocation"], resources=[lake_bucket.bucket_arn],
                )
            )

            self.analyst_roles[site] = role
            CfnOutput(self, f"AnalystRoleArn{label}", value=role.role_arn)
            CfnOutput(self, f"AnalystWorkgroupName{label}", value=workgroup_name)
