from pathlib import Path

from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    CfnOutput,
    aws_apigateway as apigateway,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_lambda_event_sources as lambda_event_sources,
    aws_s3 as s3,
)
from constructs import Construct

from infra.foundation_stack import OPERATOR_ROLE_NAME
from infra.orchestration_stack import STATE_MACHINE_NAME

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_LAMBDA_DIR = REPO_ROOT / "module2-experimentation-platform" / "registry" / "lambda"

TABLE_NAME = "aurora-games-experiments"
EXPOSURES_TABLE_NAME = "aurora-games-experiment-exposures"


class RegistryStack(Stack):
    """DynamoDB experiment registry + a CRUD API (API Gateway + Lambda) +
    a Streams-triggered exporter that keeps a queryable snapshot in S3 for
    Athena dashboarding. This is the metadata/state layer module2's Step
    Functions orchestration reads and writes as an experiment moves through
    draft -> running -> (stopped_early | completed) -> analyzed."""

    def __init__(self, scope: Construct, construct_id: str, lake_bucket: s3.IBucket, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.experiments_table = dynamodb.Table(
            self,
            "ExperimentsTable",
            table_name=TABLE_NAME,
            partition_key=dynamodb.Attribute(name="experiment_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
        )
        # Product-runtime exposure events are separate from experiment
        # metadata so a high-volume treatment path cannot make registry reads
        # or state transitions noisy. PAY_PER_REQUEST has no provisioned idle
        # capacity; TTL bounds storage after the demo/useful audit window.
        self.exposures_table = dynamodb.Table(
            self,
            "ExperimentExposuresTable",
            table_name=EXPOSURES_TABLE_NAME,
            partition_key=dynamodb.Attribute(
                name="experiment_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="event_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            # API Gateway is capped at 10 requests/s and a transactional
            # exposure consumes roughly two write units for sub-1 KB items.
            # This best-effort ceiling prevents an accidental caller loop from
            # scaling the paid-plan table toward the account-wide default.
            max_read_request_units=25,
            max_write_request_units=25,
            time_to_live_attribute="expires_at",
            removal_policy=RemovalPolicy.DESTROY,
            stream=dynamodb.StreamViewType.NEW_IMAGE,
        )

        state_machine_arn = f"arn:aws:states:{self.region}:{self.account}:stateMachine:{STATE_MACHINE_NAME}"
        execution_arn = f"arn:aws:states:{self.region}:{self.account}:execution:{STATE_MACHINE_NAME}:*"

        api_lambda = _lambda.Function(
            self,
            "ExperimentsApiHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=_lambda.Code.from_asset(str(REGISTRY_LAMBDA_DIR / "api")),
            environment={
                "EXPERIMENTS_TABLE_NAME": self.experiments_table.table_name,
                "EXPOSURES_TABLE_NAME": self.exposures_table.table_name,
                "ORCHESTRATION_STATE_MACHINE_ARN": state_machine_arn,
                # The API is IAM-authenticated, but authentication alone is
                # not tenant authorization. The handler maps the signed role
                # to a site and filters every registry operation accordingly.
                "OPERATOR_PRINCIPAL_PATTERN": OPERATOR_ROLE_NAME,
                "ALLOWED_CLIENT_SITES": "site_a,site_b,site_c",
            },
            timeout=Duration.seconds(10),
        )
        self.experiments_table.grant_read_write_data(api_lambda)
        self.exposures_table.grant_read_write_data(api_lambda)
        # grant_read_write_data covers individual item APIs but not DynamoDB's
        # cross-table transaction action used to make allocation check +
        # exposure insert atomic.
        api_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["dynamodb:TransactWriteItems"],
                resources=[
                    self.experiments_table.table_arn,
                    self.exposures_table.table_arn,
                ],
            )
        )
        # Referenced by ARN pattern (not a CDK object reference) to avoid a
        # circular stack dependency - OrchestrationStack already depends on
        # this stack's experiments_table, so it can't also be a constructor
        # input here. See orchestration_stack.py's STATE_MACHINE_NAME.
        api_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["states:StartExecution"],
                resources=[state_machine_arn],
            )
        )
        api_lambda.add_to_role_policy(
            iam.PolicyStatement(actions=["states:StopExecution"], resources=[execution_arn])
        )

        export_lambda = _lambda.Function(
            self,
            "ExperimentsExportHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=_lambda.Code.from_asset(str(REGISTRY_LAMBDA_DIR / "export")),
            environment={"LAKE_BUCKET_NAME": lake_bucket.bucket_name},
            timeout=Duration.seconds(10),
        )
        lake_bucket.grant_read_write(export_lambda, "gold/experiments_export/*")
        export_lambda.add_event_source(
            lambda_event_sources.DynamoEventSource(
                self.experiments_table,
                starting_position=_lambda.StartingPosition.TRIM_HORIZON,
                batch_size=10,
                retry_attempts=2,
            )
        )

        exposure_export_lambda = _lambda.Function(
            self,
            "ExperimentExposuresExportHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=_lambda.Code.from_asset(str(REGISTRY_LAMBDA_DIR / "exposure_export")),
            environment={"LAKE_BUCKET_NAME": lake_bucket.bucket_name},
            timeout=Duration.seconds(10),
        )
        lake_bucket.grant_write(exposure_export_lambda, "gold/experiment_exposures/*")
        exposure_export_lambda.add_event_source(
            lambda_event_sources.DynamoEventSource(
                self.exposures_table,
                starting_position=_lambda.StartingPosition.LATEST,
                batch_size=100,
                retry_attempts=2,
                report_batch_item_failures=True,
            )
        )

        api = apigateway.RestApi(
            self,
            "ExperimentsApi",
            rest_api_name="aurora-games-experiments-api",
            deploy_options=apigateway.StageOptions(
                stage_name="prod",
                # Rate limiting is a *cost* control here as much as an availability
                # one. Every request past the classifier costs Bedrock tokens, so an
                # authenticated caller with a loop turns this endpoint into someone
                # else's free LLM on our bill. IAM auth answers "who are you"; it
                # says nothing about "how often".
                throttling_rate_limit=10,
                throttling_burst_limit=20,
            ),
        )
        integration = apigateway.LambdaIntegration(api_lambda)
        # Every method requires SigV4-signed IAM credentials. This API mutates
        # experiment state - an unauthenticated caller could start, stop or
        # delete a running experiment - so leaving it open (the API Gateway
        # default of authorizationType NONE) was a straightforward mistake, not
        # a documented trade-off.
        auth = {"authorization_type": apigateway.AuthorizationType.IAM}

        experiments = api.root.add_resource("experiments")
        experiments.add_method("POST", integration, **auth)
        experiments.add_method("GET", integration, **auth)

        experiment_item = experiments.add_resource("{id}")
        experiment_item.add_method("GET", integration, **auth)
        experiment_item.add_method("PATCH", integration, **auth)
        experiment_item.add_method("DELETE", integration, **auth)

        experiment_item.add_resource("start").add_method("POST", integration, **auth)
        experiment_item.add_resource("stop").add_method("POST", integration, **auth)
        experiment_item.add_resource("exposures").add_method("POST", integration, **auth)

        CfnOutput(self, "ExperimentsApiUrl", value=api.url)
        CfnOutput(self, "ExperimentsTableName", value=self.experiments_table.table_name)
        CfnOutput(self, "ExperimentExposuresTableName", value=self.exposures_table.table_name)
