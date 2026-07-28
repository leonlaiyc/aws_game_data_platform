from pathlib import Path

from aws_cdk import (
    Duration,
    Stack,
    CfnOutput,
    aws_apigateway as apigateway,
    aws_bedrock as bedrock,
    aws_iam as iam,
    aws_lambda as _lambda,
)
from constructs import Construct

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE4_DIR = REPO_ROOT / "module4-partner-support-chatbot"


class SupportChatbotStack(Stack):
    """Module 4: partner integration support chatbot.

    Its own Guardrail rather than a share of Module 3's: the two bots face
    different audiences (external partners vs. internal analysts) and therefore
    need different denied topics. Guardrails bill per text unit evaluated with
    no idle charge, so a second one costs nothing to keep.

    No vector store, no knowledge base service, no storage of any kind - the
    corpus ships inside the Lambda package and is passed in-context. That is
    the whole infrastructure footprint: a Guardrail, a function, and an
    endpoint."""

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

        chat_fn = _lambda.Function(
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
            },
            timeout=Duration.seconds(30),
            memory_size=256,  # the whole corpus is loaded and held per container
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

        api = apigateway.RestApi(
            self, "SupportChatApi", rest_api_name="aurora-games-partner-support-api",
            deploy_options=apigateway.StageOptions(stage_name="prod"),
        )
        api.root.add_resource("chat").add_method("POST", apigateway.LambdaIntegration(chat_fn))

        CfnOutput(self, "ChatApiUrl", value=api.url)
        CfnOutput(self, "SupportChatFunctionName", value=chat_fn.function_name)
        CfnOutput(self, "SupportGuardrailId", value=guardrail.attr_guardrail_id)
