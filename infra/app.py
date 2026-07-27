#!/usr/bin/env python3
import os

import aws_cdk as cdk

from infra.foundation_stack import FoundationStack
from infra.registry_stack import RegistryStack
from infra.orchestration_stack import OrchestrationStack

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

app.synth()
