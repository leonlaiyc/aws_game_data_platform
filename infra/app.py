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

app = cdk.App()

env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION"),
)

foundation = FoundationStack(app, "AuroraGamesFoundationStack", env=env)
registry = RegistryStack(app, "AuroraGamesRegistryStack", env=env, lake_bucket=foundation.lake_bucket)
OrchestrationStack(
    app, "AuroraGamesOrchestrationStack", env=env,
    lake_bucket=foundation.lake_bucket, experiments_table=registry.experiments_table,
)
GovernanceStack(app, "AuroraGamesGovernanceStack", env=env, lake_bucket=foundation.lake_bucket)
AnomalyStack(app, "AuroraGamesAnomalyStack", env=env, lake_bucket=foundation.lake_bucket)
StreamingStack(app, "AuroraGamesStreamingStack", env=env)
AnalyticsAssistantStack(app, "AuroraGamesAnalyticsAssistantStack", env=env, lake_bucket=foundation.lake_bucket)
SupportChatbotStack(app, "AuroraGamesSupportChatbotStack", env=env)

app.synth()
