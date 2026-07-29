from pathlib import Path

from aws_cdk import (
    Duration,
    Stack,
    CfnOutput,
    aws_apigateway as apigateway,
    aws_bedrock as bedrock,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_lambda_destinations as lambda_destinations,
    aws_s3 as s3,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subscriptions,
    aws_sqs as sqs,
)
from constructs import Construct

from infra.foundation_stack import ATHENA_WORKGROUP_NAME, GLUE_DATABASE_NAME, OPERATOR_ROLE_NAME

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE3_DIR = REPO_ROOT / "module3-analytics-assistant"

# This project's data is a fixed historical simulation
# (data-foundation/event_simulator/config.py: 2026-05-01 for 60 days), not
# live - these stand in for "today" and the available data range.
AS_OF_DATE = "2026-06-29"
DATA_MIN_DATE = "2026-05-01"
DATA_MAX_DATE = "2026-06-29"

ANOMALY_ALERTS_TOPIC_NAME = "aurora-games-anomaly-alerts"  # owned by AuroraGamesAnomalyStack (Module 1)


class AnalyticsAssistantStack(Stack):
    """Module 3: NL analytics assistant. Capability A (ask_answer) is a
    semantic-layer Q&A API - NL question -> Bedrock (Guardrails attached)
    parses intent -> a pre-approved SQL template runs via Athena -> a
    code-rendered, grounded answer. Capability B (first_look_report)
    subscribes to Module 1's anomaly SNS topic and auto-generates a
    drill-down report per alert. See module3-analytics-assistant/README.md
    for the build-vs-buy (Amazon Quick) and templates-vs-text-to-SQL
    write-ups."""

    def __init__(self, scope: Construct, construct_id: str, lake_bucket: s3.IBucket, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- Guardrails: denied topics + prompt-attack protection ---
        guardrail = bedrock.CfnGuardrail(
            self,
            "AnalyticsGuardrail",
            name="aurora-games-analytics-guardrail",
            description="Keeps the NL analytics assistant on-topic and resistant to prompt injection.",
            blocked_input_messaging="This assistant only helps with Aurora Games analytics questions and can't process this request.",
            blocked_outputs_messaging="This assistant only helps with Aurora Games analytics questions and can't process this request.",
            content_policy_config=bedrock.CfnGuardrail.ContentPolicyConfigProperty(
                filters_config=[
                    bedrock.CfnGuardrail.ContentFilterConfigProperty(
                        type="PROMPT_ATTACK", input_strength="HIGH", output_strength="NONE",
                    ),
                    bedrock.CfnGuardrail.ContentFilterConfigProperty(
                        type="INSULTS", input_strength="MEDIUM", output_strength="MEDIUM",
                    ),
                    bedrock.CfnGuardrail.ContentFilterConfigProperty(
                        type="HATE", input_strength="MEDIUM", output_strength="MEDIUM",
                    ),
                ]
            ),
            topic_policy_config=bedrock.CfnGuardrail.TopicPolicyConfigProperty(
                topics_config=[
                    bedrock.CfnGuardrail.TopicConfigProperty(
                        name="OffTopicAdvice",
                        type="DENY",
                        definition="Requests for legal, financial, medical, or other personal advice unrelated "
                                   "to Aurora Games gaming analytics.",
                        examples=["Should I invest in crypto?", "What medication should I take for a headache?"],
                    )
                ]
            ),
        )
        guardrail_version = bedrock.CfnGuardrailVersion(
            self, "AnalyticsGuardrailVersion", guardrail_identifier=guardrail.attr_guardrail_id,
        )

        # --- Capability A: ask_answer ---
        ask_answer_layer = _lambda.LayerVersion(
            self, "AskAnswerCommonLayer",
            code=_lambda.Code.from_asset(str(MODULE3_DIR / "lambda" / "common")),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            description="Shared athena_utils + the semantic-layer templates for Module 3's Lambdas.",
        )
        self.ask_answer_fn = _lambda.Function(
            self, "AskAnswer",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=_lambda.Code.from_asset(str(MODULE3_DIR / "lambda" / "ask_answer")),
            environment={
                "GLUE_DATABASE_NAME": GLUE_DATABASE_NAME,
                "ATHENA_WORKGROUP_NAME": ATHENA_WORKGROUP_NAME,
                "GUARDRAIL_ID": guardrail.attr_guardrail_id,
                "GUARDRAIL_VERSION": guardrail_version.attr_version,
                "AS_OF_DATE": AS_OF_DATE,
                "DATA_MIN_DATE": DATA_MIN_DATE,
                "DATA_MAX_DATE": DATA_MAX_DATE,
                "OPERATOR_PRINCIPAL_PATTERN": OPERATOR_ROLE_NAME,
            },
            timeout=Duration.seconds(30),
            layers=[ask_answer_layer],
        )
        self._grant_lake_read(self.ask_answer_fn, lake_bucket)
        self.ask_answer_fn.add_to_role_policy(
            iam.PolicyStatement(actions=["bedrock:InvokeModel"],
                                 resources=[f"arn:aws:bedrock:{self.region}::foundation-model/amazon.nova-lite-v1:0"])
        )
        self.ask_answer_fn.add_to_role_policy(
            iam.PolicyStatement(actions=["bedrock:ApplyGuardrail"], resources=[guardrail.attr_guardrail_arn])
        )

        api = apigateway.RestApi(
            self, "AnalyticsAssistantApi", rest_api_name="aurora-games-analytics-assistant-api",
            deploy_options=apigateway.StageOptions(stage_name="prod"),
        )
        # IAM auth is not just access control here - it is the tenant boundary.
        # The handler derives which client site the caller may query from the
        # authenticated identity. An earlier version read `caller_scope` from
        # the request body, which meant any caller could omit it (becoming
        # unrestricted) or name someone else's site.
        api.root.add_resource("ask").add_method(
            "POST", apigateway.LambdaIntegration(self.ask_answer_fn),
            authorization_type=apigateway.AuthorizationType.IAM,
        )
        CfnOutput(self, "AskApiUrl", value=api.url)

        # --- Capability B: first_look_report, subscribed to Module 1's anomaly topic ---
        first_look_layer = _lambda.LayerVersion(
            self, "FirstLookCommonLayer",
            code=_lambda.Code.from_asset(str(MODULE3_DIR / "lambda" / "common")),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_12],
            description="Shared athena_utils for the first_look_report Lambda.",
        )
        self.first_look_fn = _lambda.Function(
            self, "FirstLookReport",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=_lambda.Code.from_asset(str(MODULE3_DIR / "lambda" / "first_look_report")),
            environment={
                "GLUE_DATABASE_NAME": GLUE_DATABASE_NAME,
                "ATHENA_WORKGROUP_NAME": ATHENA_WORKGROUP_NAME,
                "LAKE_BUCKET_NAME": lake_bucket.bucket_name,
            },
            timeout=Duration.seconds(60),
            layers=[first_look_layer],
            # Separate from the subscription DLQ above: that one catches
            # messages SNS could not deliver, this catches invocations that
            # delivered fine and then threw. Previously neither existed, so a
            # failing alert was retried twice and then gone with no trace.
            on_failure=lambda_destinations.SqsDestination(sqs.Queue(
                self, "FirstLookInvocationDlq",
                queue_name="aurora-games-first-look-invocation-dlq",
                retention_period=Duration.days(14),
            )),
            retry_attempts=2,
        )
        self._grant_lake_read(self.first_look_fn, lake_bucket)
        lake_bucket.grant_write(self.first_look_fn, "gold/first_look_reports/*")
        self.first_look_fn.add_to_role_policy(
            iam.PolicyStatement(actions=["bedrock:InvokeModel"],
                                 resources=[f"arn:aws:bedrock:{self.region}::foundation-model/amazon.nova-lite-v1:0"])
        )

        # Imported by fixed ARN (not a CDK cross-stack object reference) -
        # same pattern used for registry -> orchestration's state machine,
        # to avoid coupling this stack's lifecycle to AuroraGamesAnomalyStack.
        anomaly_topic = sns.Topic.from_topic_arn(
            self, "ImportedAnomalyTopic", f"arn:aws:sns:{self.region}:{self.account}:{ANOMALY_ALERTS_TOPIC_NAME}",
        )
        # Two publishers share this topic: the EWMA detector and the arbitrage
        # detector. This consumer only knows how to drill down on a metric
        # anomaly, so it filters rather than receiving everything and deciding
        # afterwards - the filter is evaluated by SNS, so a message it doesn't
        # want never becomes an invocation, a failure, or a bill.
        anomaly_topic.add_subscription(sns_subscriptions.LambdaSubscription(
            self.first_look_fn,
            filter_policy={
                "alert_type": sns.SubscriptionFilter.string_filter(allowlist=["data_anomaly"]),
            },
            dead_letter_queue=sqs.Queue(
                self, "FirstLookSubscriptionDlq",
                queue_name="aurora-games-first-look-subscription-dlq",
                retention_period=Duration.days(14),
            ),
        ))

        CfnOutput(self, "FirstLookReportFunctionName", value=self.first_look_fn.function_name)
        CfnOutput(self, "AskAnswerFunctionName", value=self.ask_answer_fn.function_name)
        CfnOutput(self, "GuardrailId", value=guardrail.attr_guardrail_id)

    def _grant_lake_read(self, fn: _lambda.Function, lake_bucket: s3.IBucket):
        lake_bucket.grant_read_write(fn)  # read Silver/Gold + write Athena query results
        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["athena:StartQueryExecution", "athena:GetQueryExecution", "athena:GetQueryResults"],
                resources=[f"arn:aws:athena:{self.region}:{self.account}:workgroup/{ATHENA_WORKGROUP_NAME}"],
            )
        )
        # Required because gold/daily_kpi/ is a Lake-Formation-registered
        # location. Registering a location changes the access path for EVERY
        # consumer of it, not only the roles you were trying to constrain -
        # these Lambdas broke with "Insufficient permissions" the moment the
        # registration landed, despite their IAM policies being unchanged.
        # Worth knowing before registering anything in a live account.
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
