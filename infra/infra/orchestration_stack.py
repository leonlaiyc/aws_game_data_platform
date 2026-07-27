from pathlib import Path

from aws_cdk import (
    Duration,
    Stack,
    CfnOutput,
    aws_dynamodb as dynamodb,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_s3 as s3,
    aws_sns as sns,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
)
from constructs import Construct

from infra.foundation_stack import ATHENA_WORKGROUP_NAME, GLUE_DATABASE_NAME

REPO_ROOT = Path(__file__).resolve().parents[2]
ORCH_LAMBDA_DIR = REPO_ROOT / "module2-experimentation-platform" / "orchestration" / "lambda"

STATE_MACHINE_NAME = "aurora-games-experiment-lifecycle"


class OrchestrationStack(Stack):
    """Step Functions state machine driving an experiment through
    assignment -> srm_check -> monitoring -> analysis -> readout, plus the
    EventBridge-scheduled guardrail monitor that runs independently of any
    one execution. See module2-experimentation-platform/orchestration/README.md."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        lake_bucket: s3.IBucket,
        experiments_table: dynamodb.ITable,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.alerts_topic = sns.Topic(self, "AlertsTopic", topic_name="aurora-games-experiment-alerts")

        common_layer = _lambda.LayerVersion(
            self,
            "CommonLayer",
            code=_lambda.Code.from_asset(str(ORCH_LAMBDA_DIR / "common")),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            description="Shared athena_utils / dynamo_utils helpers for the orchestration Lambdas.",
        )

        common_env = {
            "EXPERIMENTS_TABLE_NAME": experiments_table.table_name,
            "GLUE_DATABASE_NAME": GLUE_DATABASE_NAME,
            "ATHENA_WORKGROUP_NAME": ATHENA_WORKGROUP_NAME,
            "LAKE_BUCKET_NAME": lake_bucket.bucket_name,
            "ALERTS_TOPIC_ARN": self.alerts_topic.topic_arn,
        }

        def make_lambda(construct_id: str, dir_name: str, timeout_seconds: int = 30, use_layer: bool = True) -> _lambda.Function:
            fn = _lambda.Function(
                self,
                construct_id,
                runtime=_lambda.Runtime.PYTHON_3_12,
                handler="handler.handler",
                code=_lambda.Code.from_asset(str(ORCH_LAMBDA_DIR / dir_name)),
                environment=common_env,
                timeout=Duration.seconds(timeout_seconds),
                layers=[common_layer] if use_layer else [],
            )
            experiments_table.grant_read_write_data(fn)
            return fn

        assignment_fn = make_lambda("Assignment", "assignment", timeout_seconds=60)
        srm_check_fn = make_lambda("SrmCheck", "srm_check", use_layer=False)  # pure computation, no Athena/DynamoDB
        monitoring_check_fn = make_lambda("MonitoringCheck", "monitoring_check", timeout_seconds=60)
        analysis_fn = make_lambda("Analysis", "analysis", timeout_seconds=90)
        readout_fn = make_lambda("Readout", "readout", timeout_seconds=30)
        mark_state_fn = make_lambda("MarkState", "mark_state")  # needs dynamo_utils from the common layer

        # Athena/Glue access for the Lambdas that query the lake. Least-privilege
        # would scope S3 to just the gold/player_features, gold/experiment_assignments,
        # and athena-results prefixes each Lambda actually touches; granted broadly
        # here to keep the stack readable at this project's scale.
        for fn in (assignment_fn, monitoring_check_fn, analysis_fn):
            lake_bucket.grant_read_write(fn)
            fn.add_to_role_policy(
                iam.PolicyStatement(
                    actions=["athena:StartQueryExecution", "athena:GetQueryExecution", "athena:GetQueryResults"],
                    resources=[f"arn:aws:athena:{self.region}:{self.account}:workgroup/{ATHENA_WORKGROUP_NAME}"],
                )
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

        readout_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[f"arn:aws:bedrock:{self.region}::foundation-model/amazon.nova-lite-v1:0"],
            )
        )

        self.alerts_topic.grant_publish(monitoring_check_fn)
        self.alerts_topic.grant_publish(mark_state_fn)

        # --- State machine definition ---

        assignment_task = tasks.LambdaInvoke(
            self, "AssignmentTask", lambda_function=assignment_fn, payload_response_only=True, result_path="$.assignment"
        )
        srm_task = tasks.LambdaInvoke(
            self, "SrmCheckTask", lambda_function=srm_check_fn, payload_response_only=True, result_path="$.srm"
        )

        srm_fail_task = tasks.LambdaInvoke(
            self,
            "MarkSrmFailed",
            lambda_function=mark_state_fn,
            payload_response_only=True,
            result_path="$.state_mark",
            payload=sfn.TaskInput.from_object({
                "experiment_id.$": "$.experiment_id",
                "from_state": "running",
                "to_state": "stopped_early",
                "reason.$": "States.Format('srm_violation: p_value={} chi2={} (threshold {})', $.srm.p_value, $.srm.chi2, $.srm.threshold)",
                "notify": True,
            }),
        )

        monitoring_check_task = tasks.LambdaInvoke(
            self, "MonitoringCheckTask", lambda_function=monitoring_check_fn, payload_response_only=True
        )
        monitoring_map = sfn.Map(
            self,
            "MonitoringLoop",
            items_path="$.check_dates",
            result_path="$.monitoring_results",
            max_concurrency=1,
            item_selector={
                "check_date.$": "$$.Map.Item.Value",
                "experiment_id.$": "$.experiment_id",
                "guardrail_metrics.$": "$.assignment.experiment.guardrail_metrics",
            },
        )
        monitoring_map.item_processor(monitoring_check_task)

        mark_completed_task = tasks.LambdaInvoke(
            self,
            "MarkCompleted",
            lambda_function=mark_state_fn,
            payload_response_only=True,
            result_path="$.state_mark",
            payload=sfn.TaskInput.from_object({
                "experiment_id.$": "$.experiment_id",
                "from_state": "running",
                "to_state": "completed",
                "notify": False,
            }),
        )

        analysis_task = tasks.LambdaInvoke(
            self, "AnalysisTask", lambda_function=analysis_fn, payload_response_only=True, result_path="$.analysis_result"
        )
        readout_task = tasks.LambdaInvoke(
            self, "ReadoutTask", lambda_function=readout_fn, payload_response_only=True, result_path="$.readout"
        )

        happy_path = (
            monitoring_map.next(mark_completed_task)
            .next(analysis_task)
            .next(readout_task)
            .next(sfn.Succeed(self, "Analyzed"))
        )

        srm_choice = (
            sfn.Choice(self, "SrmPassed?")
            .when(sfn.Condition.boolean_equals("$.srm.passed", True), happy_path)
            .otherwise(srm_fail_task.next(sfn.Succeed(self, "SrmFailed")))
        )

        definition = assignment_task.next(srm_task).next(srm_choice)

        self.state_machine = sfn.StateMachine(
            self,
            "ExperimentLifecycle",
            state_machine_name=STATE_MACHINE_NAME,
            definition_body=sfn.DefinitionBody.from_chainable(definition),
            timeout=Duration.minutes(15),
        )

        # Production monitoring path: independent of any one execution, checks
        # every currently-running experiment against today's date.
        scheduled_rule = events.Rule(
            self,
            "MonitoringSchedule",
            schedule=events.Schedule.rate(Duration.hours(1)),
        )
        scheduled_rule.add_target(
            targets.LambdaFunction(monitoring_check_fn, event=events.RuleTargetInput.from_object({"scheduled": True}))
        )

        CfnOutput(self, "StateMachineArn", value=self.state_machine.state_machine_arn)
        CfnOutput(self, "AlertsTopicArn", value=self.alerts_topic.topic_arn)
