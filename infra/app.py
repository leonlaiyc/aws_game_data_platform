#!/usr/bin/env python3
import os

import aws_cdk as cdk

from infra.foundation_stack import FoundationStack
from infra.registry_stack import RegistryStack

app = cdk.App()

env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION"),
)

foundation = FoundationStack(app, "AuroraGamesFoundationStack", env=env)
RegistryStack(app, "AuroraGamesRegistryStack", env=env, lake_bucket=foundation.lake_bucket)

app.synth()
