from pathlib import Path

from aws_cdk import (
    Duration,
    Stack,
    CfnOutput,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_s3 as s3,
    aws_sns as sns,
)
from constructs import Construct

from infra.foundation_stack import ATHENA_WORKGROUP_NAME, GLUE_DATABASE_NAME

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE1_DIR = REPO_ROOT / "module1-anomaly-detection"


class AnomalyStack(Stack):
    """Batch anomaly detection (data_anomaly) and rule-based arbitrage
    detection (arbitrage_detection) - both scheduled Lambdas reading only
    from the shared Gold tables (gold_daily_kpi, gold_player_features,
    silver_events), never recomputing their own aggregates. See
    module1-anomaly-detection/README.md."""

    def __init__(self, scope: Construct, construct_id: str, lake_bucket: s3.IBucket, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.alerts_topic = sns.Topic(self, "AlertsTopic", topic_name="aurora-games-anomaly-alerts")

        self.anomaly_fn = self._make_detector(
            "AnomalyDetector",
            MODULE1_DIR / "data_anomaly" / "lambda",
            lake_bucket,
            schedule_description="Daily EWMA anomaly check across all client sites",
        )
        # Retention is intentionally weekly: daily cohorts are too small and
        # D7 outcomes are incomplete until seven days later. Reuse the same
        # Lambda/package and publication manifest, but keep an independent
        # consumption marker so the daily and weekly paths cannot suppress one
        # another.
        retention_rule = events.Rule(
            self,
            "RetentionAnomalySchedule",
            description="Weekly mature-cohort D1/D7 retention check",
            schedule=events.Schedule.cron(
                minute="0",
                hour="0",
                week_day="MON",
            ),
        )
        retention_rule.add_target(
            targets.LambdaFunction(
                self.anomaly_fn,
                event=events.RuleTargetInput.from_object(
                    {"scheduled": True, "cadence": "weekly"}
                ),
            )
        )
        self.arbitrage_fn = self._make_detector(
            "ArbitrageDetector",
            MODULE1_DIR / "arbitrage_detection" / "lambda",
            lake_bucket,
            schedule_description="Daily rule-based arbitrage/multi-account check across all client sites",
        )

        CfnOutput(self, "AlertsTopicArn", value=self.alerts_topic.topic_arn)

    def _make_detector(self, name: str, lambda_dir: Path, lake_bucket: s3.IBucket, schedule_description: str) -> _lambda.Function:
        layer = _lambda.LayerVersion(
            self,
            f"{name}CommonLayer",
            code=_lambda.Code.from_asset(str(lambda_dir / "common")),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            description=f"Shared athena_utils helper for {name}.",
        )
        fn = _lambda.Function(
            self,
            name,
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=_lambda.Code.from_asset(str(lambda_dir / "detector")),
            environment={
                "GLUE_DATABASE_NAME": GLUE_DATABASE_NAME,
                "ATHENA_WORKGROUP_NAME": ATHENA_WORKGROUP_NAME,
                "LAKE_BUCKET_NAME": lake_bucket.bucket_name,
                "ALERTS_TOPIC_ARN": self.alerts_topic.topic_arn,
            },
            timeout=Duration.seconds(90),
            layers=[layer],
        )

        lake_bucket.grant_read_write(fn)
        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["athena:StartQueryExecution", "athena:GetQueryExecution", "athena:GetQueryResults"],
                resources=[f"arn:aws:athena:{self.region}:{self.account}:workgroup/{ATHENA_WORKGROUP_NAME}"],
            )
        )
        # gold/daily_kpi/ is registered with Lake Formation for the tenant
        # isolation demo, so reads of it are brokered by Lake Formation rather
        # than IAM alone - including from this detector, which is otherwise
        # unrelated to that demo. See analytics_assistant_stack for the same
        # note on registration blast radius.
        fn.add_to_role_policy(
            iam.PolicyStatement(actions=["lakeformation:GetDataAccess"], resources=["*"])
        )
        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["glue:GetTable", "glue:GetTables", "glue:GetDatabase", "glue:GetPartition", "glue:GetPartitions"],
                resources=[
                    f"arn:aws:glue:{self.region}:{self.account}:catalog",
                    f"arn:aws:glue:{self.region}:{self.account}:database/{GLUE_DATABASE_NAME}",
                    f"arn:aws:glue:{self.region}:{self.account}:table/{GLUE_DATABASE_NAME}/*",
                ],
            )
        )
        self.alerts_topic.grant_publish(fn)

        rule = events.Rule(self, f"{name}Schedule", description=schedule_description, schedule=events.Schedule.rate(Duration.hours(24)))
        rule.add_target(targets.LambdaFunction(fn, event=events.RuleTargetInput.from_object({"scheduled": True})))

        CfnOutput(self, f"{name}FunctionName", value=fn.function_name)
        return fn
