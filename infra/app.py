#!/usr/bin/env python3
import os

import aws_cdk as cdk

from infra.foundation_stack import FoundationStack

app = cdk.App()

env = cdk.Environment(
    account=os.getenv("CDK_DEFAULT_ACCOUNT"),
    region=os.getenv("CDK_DEFAULT_REGION"),
)

FoundationStack(app, "AuroraGamesFoundationStack", env=env)

app.synth()
