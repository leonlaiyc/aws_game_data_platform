from aws_cdk import (
    Duration,
    Stack,
    CfnOutput,
    RemovalPolicy,
    aws_s3 as s3,
    aws_glue as glue,
    aws_athena as athena,
)
from constructs import Construct

GLUE_DATABASE_NAME = "aurora_games_lake"
ATHENA_WORKGROUP_NAME = "aurora-games-wg"

# The single internal-operator identity. Handlers that need to distinguish an
# internal operator from an external caller match the caller's ARN against this
# name - Module 3 for unrestricted tenant scope, Module 4 for access to the
# audit track. Kept here so the stacks that create the role and the stacks that
# authorise against it cannot drift apart.
#
# Matching on a role-name convention is a demo simplification. A real
# deployment would carry the entitlement in a verified IdP claim rather than
# inferring it from an ARN, because role names are not a security boundary the
# moment anyone can create a role with a matching name.
OPERATOR_ROLE_NAME = "aurora-games-operator"

# Safety cap so a mistaken query can never scan more than this and rack up cost.
# 1 GB at $5/TB scanned is $0.005 - a generous ceiling for a lake that is tens of MB.
ATHENA_BYTES_SCANNED_CUTOFF = 1_073_741_824


class FoundationStack(Stack):
    """S3 data lake (bronze/silver/gold), Glue Catalog database, and an Athena
    workgroup with a cost-scanning cutoff. This is the shared foundation every
    other module (anomaly detection, experimentation, chatbot) reads from."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.lake_bucket = s3.Bucket(
            self,
            "LakeBucket",
            bucket_name=f"aurora-games-lake-{self.account}-{self.region}",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=False,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="AbortIncompleteMultipartUploads",
                    enabled=True,
                    abort_incomplete_multipart_upload_after=Duration.days(7),
                )
            ],
        )

        self.glue_database = glue.CfnDatabase(
            self,
            "GlueDatabase",
            catalog_id=self.account,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name=GLUE_DATABASE_NAME,
                description="Aurora Games lake tables (bronze/silver/gold) - single source of truth for all modules.",
            ),
        )

        self.athena_workgroup = athena.CfnWorkGroup(
            self,
            "AthenaWorkgroup",
            name=ATHENA_WORKGROUP_NAME,
            description="Workgroup for Aurora Games lake queries, capped to prevent runaway scan cost.",
            work_group_configuration=athena.CfnWorkGroup.WorkGroupConfigurationProperty(
                result_configuration=athena.CfnWorkGroup.ResultConfigurationProperty(
                    output_location=f"s3://{self.lake_bucket.bucket_name}/athena-results/"
                ),
                # Not enforced: CTAS statements need to set their own
                # `external_location` (to write into our silver/gold prefixes
                # instead of the query-results prefix), which Athena disallows
                # when a workgroup enforces a centralized result location.
                enforce_work_group_configuration=False,
                publish_cloud_watch_metrics_enabled=True,
                bytes_scanned_cutoff_per_query=ATHENA_BYTES_SCANNED_CUTOFF,
            ),
        )

        CfnOutput(self, "LakeBucketName", value=self.lake_bucket.bucket_name)
        CfnOutput(self, "GlueDatabaseName", value=GLUE_DATABASE_NAME)
        CfnOutput(self, "AthenaWorkgroupName", value=ATHENA_WORKGROUP_NAME)
