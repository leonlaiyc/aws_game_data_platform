from pathlib import Path

from aws_cdk import (
    Duration,
    Stack,
    CfnOutput,
    RemovalPolicy,
    aws_apigateway as apigateway,
    aws_bedrock as bedrock,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subscriptions,
    aws_sqs as sqs,
)
from constructs import Construct

from infra.foundation_stack import OPERATOR_ROLE_NAME

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE4_DIR = REPO_ROOT / "module4-partner-support-chatbot"
GAME_PROVIDER_ROLE_NAME = "aurora-games-game-provider-partner"
CLIENT_OPERATOR_ROLE_NAME = "aurora-games-client-operator-partner"


class SupportChatbotStack(Stack):
    """Module 4: partner integration support chatbot.

    Its own Guardrail rather than a share of Module 3's: the two bots face
    different audiences (external partners vs. internal analysts) and therefore
    need different denied topics. Guardrails bill per text unit evaluated with
    no idle charge, so a second one costs nothing to keep.

    No vector store or knowledge base service: the corpus ships inside the
    Lambda package and is passed in-context. Escalations are real work items,
    however, so a small on-demand DynamoDB table persists support tickets."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        guardrail = bedrock.CfnGuardrail(
            self,
            "SupportGuardrail",
            name="aurora-games-partner-support-guardrail",
            description="Keeps the external partner support bot on-topic and resistant to prompt injection.",
            # Deliberately uninformative about what was blocked - explaining the
            # boundary to an external user teaches them how to evade it. The
            # handler substitutes its own fixed refusal copy anyway.
            blocked_input_messaging="I'm not able to help with that request.",
            blocked_outputs_messaging="I'm not able to help with that request.",
            content_policy_config=bedrock.CfnGuardrail.ContentPolicyConfigProperty(
                filters_config=[
                    bedrock.CfnGuardrail.ContentFilterConfigProperty(
                        type="PROMPT_ATTACK", input_strength="HIGH", output_strength="NONE",
                    ),
                    bedrock.CfnGuardrail.ContentFilterConfigProperty(
                        type="INSULTS", input_strength="HIGH", output_strength="HIGH",
                    ),
                    bedrock.CfnGuardrail.ContentFilterConfigProperty(
                        type="HATE", input_strength="HIGH", output_strength="HIGH",
                    ),
                    bedrock.CfnGuardrail.ContentFilterConfigProperty(
                        type="SEXUAL", input_strength="HIGH", output_strength="HIGH",
                    ),
                    bedrock.CfnGuardrail.ContentFilterConfigProperty(
                        type="VIOLENCE", input_strength="MEDIUM", output_strength="MEDIUM",
                    ),
                ]
            ),
            topic_policy_config=bedrock.CfnGuardrail.TopicPolicyConfigProperty(
                topics_config=[
                    bedrock.CfnGuardrail.TopicConfigProperty(
                        name="CommercialTerms",
                        type="DENY",
                        definition="Questions about pricing, revenue share, contract terms, or commercial "
                                   "negotiation. These are handled by the partner's account manager, never "
                                   "by a support assistant.",
                        examples=[
                            "What revenue share can you offer us?",
                            "Can we renegotiate our contract rate?",
                        ],
                    ),
                    bedrock.CfnGuardrail.TopicConfigProperty(
                        name="OtherPartnerData",
                        type="DENY",
                        definition="Requests for information about other partners, their integrations, "
                                   "their traffic, or their commercial arrangements.",
                        examples=[
                            "Which other operators use your platform?",
                            "How much volume does your biggest partner do?",
                        ],
                    ),
                ]
            ),
        )
        guardrail_version = bedrock.CfnGuardrailVersion(
            self, "SupportGuardrailVersion", guardrail_identifier=guardrail.attr_guardrail_id,
        )

        self.tickets_table = tickets_table = dynamodb.Table(
            self,
            "SupportTickets",
            table_name="aurora-games-support-tickets",
            partition_key=dynamodb.Attribute(
                name="ticket_id", type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.sessions_table = sessions_table = dynamodb.Table(
            self,
            "SupportSessions",
            table_name="aurora-games-support-sessions",
            partition_key=dynamodb.Attribute(
                name="session_id", type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            max_read_request_units=10,
            max_write_request_units=10,
            time_to_live_attribute="expires_at",
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.notifications_topic = notifications_topic = sns.Topic(
            self,
            "PartnerNotifications",
            topic_name="aurora-games-partner-notifications",
            display_name="Aurora Games partner operational notifications",
        )
        # No external recipient is subscribed automatically. This queue is a
        # deterministic, account-local delivery sink for the operation demo.
        # A real partner must explicitly opt in to its own endpoint.
        self.notification_audit_queue = notification_audit_queue = sqs.Queue(
            self,
            "PartnerNotificationAuditQueue",
            queue_name="aurora-games-partner-notification-audit",
            retention_period=Duration.days(1),
            removal_policy=RemovalPolicy.DESTROY,
        )
        notifications_topic.add_subscription(
            sns_subscriptions.SqsSubscription(
                notification_audit_queue,
                raw_message_delivery=True,
            )
        )

        self.chat_fn = chat_fn = _lambda.Function(
            self, "SupportChat",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.handler",
            # The knowledge base and the versioned prompts live inside this
            # asset directory, so a prompt or a doc change is a code change that
            # goes through the same review and deploy path as everything else.
            code=_lambda.Code.from_asset(str(MODULE4_DIR / "lambda" / "chat")),
            environment={
                "GUARDRAIL_ID": guardrail.attr_guardrail_id,
                "GUARDRAIL_VERSION": guardrail_version.attr_version,
                "OPERATOR_PRINCIPAL_PATTERN": OPERATOR_ROLE_NAME,
                "GAME_PROVIDER_PRINCIPAL_PATTERN": GAME_PROVIDER_ROLE_NAME,
                "CLIENT_OPERATOR_PRINCIPAL_PATTERN": CLIENT_OPERATOR_ROLE_NAME,
                "DAILY_REQUEST_LIMIT": "50",
                "SUPPORT_TICKETS_TABLE_NAME": tickets_table.table_name,
                "SUPPORT_SESSIONS_TABLE_NAME": sessions_table.table_name,
            },
            timeout=Duration.seconds(30),
            memory_size=256,  # the whole corpus is loaded and held per container
            # NOTE: reserved_concurrent_executions would be the right control
            # here - a per-function ceiling on concurrent Bedrock spend and on
            # how much of the account's concurrency pool one endpoint can take.
            # It cannot be set in this account: the total Lambda concurrency
            # limit is 10, and AWS requires at least 10 to remain unreserved, so
            # any reservation is rejected outright.
            #
            # The practical effect is that the account-wide limit of 10 is the
            # only concurrency ceiling, and it is *shared* - a burst against
            # this endpoint can starve the detectors and the experiment
            # lifecycle. API Gateway throttling above is what actually caps the
            # burst; a production account with a normal limit should add the
            # reservation as well. See docs/threat-model.md.
        )
        chat_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[f"arn:aws:bedrock:{self.region}::foundation-model/amazon.nova-lite-v1:0"],
            )
        )
        chat_fn.add_to_role_policy(
            iam.PolicyStatement(actions=["bedrock:ApplyGuardrail"], resources=[guardrail.attr_guardrail_arn])
        )
        tickets_table.grant_write_data(chat_fn)
        sessions_table.grant_read_write_data(chat_fn)

        notification_fn = _lambda.Function(
            self,
            "PartnerNotificationPublisher",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=_lambda.Code.from_asset(
                str(MODULE4_DIR / "lambda" / "notification")
            ),
            environment={
                "NOTIFICATIONS_TOPIC_ARN": notifications_topic.topic_arn,
                "OPERATOR_PRINCIPAL_PATTERN": OPERATOR_ROLE_NAME,
            },
            timeout=Duration.seconds(10),
        )
        notifications_topic.grant_publish(notification_fn)

        api = apigateway.RestApi(
            self, "SupportChatApi", rest_api_name="aurora-games-partner-support-api",
            deploy_options=apigateway.StageOptions(
                stage_name="prod",
                # Rate limiting is a *cost* control here as much as an availability
                # one. Every request past the classifier costs Bedrock tokens, so an
                # authenticated caller with a loop turns this endpoint into someone
                # else's free LLM on our bill. IAM auth answers "who are you"; it
                # says nothing about "how often".
                # A support PoC does not need machine-to-machine throughput.
                # Keep even invalid/blocked traffic from turning API/Lambda
                # request pricing into a material bill.
                throttling_rate_limit=0.1,
                throttling_burst_limit=2,
            ),
        )
        chat_resource = api.root.add_resource("chat")
        chat_resource.add_method(
            "POST", apigateway.LambdaIntegration(chat_fn),
            # Also gates the audit track: debug output is now authorised by
            # identity rather than by a boolean the caller sets on itself.
            authorization_type=apigateway.AuthorizationType.IAM,
        )
        api.root.add_resource("notifications").add_method(
            "POST",
            apigateway.LambdaIntegration(notification_fn),
            authorization_type=apigateway.AuthorizationType.IAM,
        )

        # These are account-local PoC identities, not a claim that external
        # federation is production-ready. IAM roles have no hourly charge and
        # let the handler derive which of the two integration directions may be
        # answered without trusting a request-body audience flag.
        self.game_provider_role = game_provider_role = iam.Role(
            self,
            "GameProviderPartnerRole",
            role_name=GAME_PROVIDER_ROLE_NAME,
            assumed_by=iam.AccountPrincipal(self.account),
            description="PoC game-provider identity scoped to inbound game integration support",
        )
        self.client_operator_role = client_operator_role = iam.Role(
            self,
            "ClientOperatorPartnerRole",
            role_name=CLIENT_OPERATOR_ROLE_NAME,
            assumed_by=iam.AccountPrincipal(self.account),
            description="PoC client-operator identity scoped to outbound platform API support",
        )
        chat_invoke = iam.PolicyStatement(
            actions=["execute-api:Invoke"],
            resources=[api.arn_for_execute_api("POST", "/chat", "prod")],
        )
        game_provider_role.add_to_policy(chat_invoke)
        client_operator_role.add_to_policy(
            iam.PolicyStatement(
                actions=["execute-api:Invoke"],
                resources=[api.arn_for_execute_api("POST", "/chat", "prod")],
            )
        )

        CfnOutput(self, "ChatApiUrl", value=api.url)
        CfnOutput(self, "SupportChatFunctionName", value=chat_fn.function_name)
        CfnOutput(self, "SupportGuardrailId", value=guardrail.attr_guardrail_id)
        CfnOutput(self, "SupportTicketsTableName", value=tickets_table.table_name)
        CfnOutput(self, "SupportSessionsTableName", value=sessions_table.table_name)
        CfnOutput(
            self, "GameProviderPartnerRoleArn", value=game_provider_role.role_arn
        )
        CfnOutput(
            self,
            "ClientOperatorPartnerRoleArn",
            value=client_operator_role.role_arn,
        )
        CfnOutput(
            self,
            "PartnerNotificationsTopicArn",
            value=notifications_topic.topic_arn,
        )
        CfnOutput(
            self,
            "PartnerNotificationAuditQueueUrl",
            value=notification_audit_queue.queue_url,
        )
