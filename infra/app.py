#!/usr/bin/env python3
import os

import aws_cdk as cdk

from infra.foundation_stack import FoundationStack
from infra.registry_stack import RegistryStack
from infra.orchestration_stack import OrchestrationStack
from infra.governance_stack import GovernanceStack
from infra.anomaly_stack import AnomalyStack
from infra.streaming_stack import StreamingStack
from infra.analytics_assistant_stack import AnalyticsAssistantStack
from infra.support_chatbot_stack import SupportChatbotStack
from infra.observability_stack import ObservabilityStack

app = cdk.App()

env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION"),
)

foundation = FoundationStack(app, "AuroraGamesFoundationStack", env=env)
registry = RegistryStack(app, "AuroraGamesRegistryStack", env=env, lake_bucket=foundation.lake_bucket)
orchestration = OrchestrationStack(
    app, "AuroraGamesOrchestrationStack", env=env,
    lake_bucket=foundation.lake_bucket, experiments_table=registry.experiments_table,
    exposures_table=registry.exposures_table,
)
GovernanceStack(app, "AuroraGamesGovernanceStack", env=env, lake_bucket=foundation.lake_bucket)
anomaly = AnomalyStack(app, "AuroraGamesAnomalyStack", env=env, lake_bucket=foundation.lake_bucket)
# Kinesis bills per shard-hour with no free tier, so this stack is NOT part of
# the default app: `cdk deploy --all` must never be able to leave a meter
# running. It is only synthesised when explicitly asked for:
#
#     cdk deploy AuroraGamesStreamingStack -c enable_streaming=true
#
# Use module1-anomaly-detection/streaming/run_streaming_demo.sh, which deploys,
# demos, destroys, and then verifies the stream is actually gone.
if app.node.try_get_context("enable_streaming") in ("true", True):
    StreamingStack(app, "AuroraGamesStreamingStack", env=env)
analytics = AnalyticsAssistantStack(
    app, "AuroraGamesAnalyticsAssistantStack", env=env, lake_bucket=foundation.lake_bucket)
chatbot = SupportChatbotStack(app, "AuroraGamesSupportChatbotStack", env=env)

ObservabilityStack(
    app, "AuroraGamesObservabilityStack", env=env,
    # Referenced by name rather than by construct so this stack can be deployed
    # or replaced without a cross-stack export locking the others in place -
    # the same reasoning as importing the alert topic by ARN elsewhere.
    lambda_function_names={
        "AnomalyDetector": anomaly.anomaly_fn.function_name,
        "ArbitrageDetector": anomaly.arbitrage_fn.function_name,
        "AskAnswer": analytics.ask_answer_fn.function_name,
        "FirstLookReport": analytics.first_look_fn.function_name,
        "SupportChat": chatbot.chat_fn.function_name,
    },
    state_machine_arn=orchestration.state_machine.state_machine_arn,
    dlq_names=[
        "aurora-games-first-look-subscription-dlq",
        "aurora-games-first-look-invocation-dlq",
    ],
)

app.synth()
