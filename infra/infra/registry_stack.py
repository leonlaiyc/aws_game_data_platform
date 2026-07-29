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

from infra.orchestration_stack import STATE_MACHINE_NAME

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_LAMBDA_DIR = REPO_ROOT / "module2-experimentation-platform" / "registry" / "lambda"

TABLE_NAME = "aurora-games-experiments"


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

        state_machine_arn = f"arn:aws:states:{self.region}:{self.account}:stateMachine:{STATE_MACHINE_NAME}"

        api_lambda = _lambda.Function(
            self,
            "ExperimentsApiHandler",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=_lambda.Code.from_asset(str(REGISTRY_LAMBDA_DIR / "api")),
            environment={
                "EXPERIMENTS_TABLE_NAME": self.experiments_table.table_name,
                "ORCHESTRATION_STATE_MACHINE_ARN": state_machine_arn,
            },
            timeout=Duration.seconds(10),
        )
        self.experiments_table.grant_read_write_data(api_lambda)
        # Referenced by ARN pattern (not a CDK object reference) to avoid a
        # circular stack dependency - OrchestrationStack already depends on
        # this stack's experiments_table, so it can't also be a constructor
        # input here. See orchestration_stack.py's STATE_MACHINE_NAME.
        api_lambda.add_to_role_policy(
            iam.PolicyStatement(actions=["states:StartExecution"], resources=[state_machine_arn])
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

        api = apigateway.RestApi(
            self,
            "ExperimentsApi",
            rest_api_name="aurora-games-experiments-api",
            deploy_options=apigateway.StageOptions(stage_name="prod"),
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

        CfnOutput(self, "ExperimentsApiUrl", value=api.url)
        CfnOutput(self, "ExperimentsTableName", value=self.experiments_table.table_name)
