# AWS Game Data Platform — CDK application

This directory defines the complete AWS infrastructure for the portfolio platform. The default app
synthesizes eight steady-state stacks:

1. Foundation — S3 lake, Glue catalog, Athena workgroup.
2. Registry — DynamoDB experiment metadata, IAM-authenticated CRUD API, S3 export.
3. Orchestration — Step Functions experiment lifecycle and analysis Lambdas.
4. Governance — analyst/operator roles, scoped Athena workgroups, Lake Formation controls.
5. Anomaly — scheduled batch detectors and the business-alert topic.
6. Analytics assistant — IAM-authenticated Q&A and alert-triggered first-look reporting.
7. Support chatbot — Guardrail, IAM-authenticated API, Lambda, and support-ticket table.
8. Observability — 13 CloudWatch alarms, DLQ alarms, SNS operations topic, and a $5 budget.

`AuroraGamesStreamingStack` is intentionally absent by default because its Kinesis shard bills
while idle. It appears only with `-c enable_streaming=true`.

## Toolchain

- Python 3.12
- Node.js 22 LTS
- AWS CDK v2 CLI
- AWS CLI credentials for `ap-northeast-1`
- A bootstrapped CDK environment and a Lake Formation data lake administrator

```bash
python -m venv .venv
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

## Verify without touching AWS

From the repository root:

```bash
python -m pytest
cd infra
cdk synth
cdk synth -c enable_streaming=true AuroraGamesStreamingStack
```

The test suite synthesizes the security-sensitive stacks and asserts IAM authentication, analyst S3
scope, registry lifecycle permissions, DLQs, the support ticket store, and exclusion of Kinesis from
the default app.

## Deployment sequence

Deployment changes AWS resources and cost, so review `cdk diff` before authorizing it. The
acceptance-hardening branch is not represented as deployed until this sequence is run and the live
negative tests pass.

```bash
cdk diff --all
cdk deploy --all
../data-foundation/.venv/Scripts/python.exe ../data-foundation/lake/build_lake.py
../data-foundation/.venv/Scripts/python.exe ../module2-experimentation-platform/feature_registry/build_feature_registry.py
../data-foundation/.venv/Scripts/python.exe ../data-foundation/governance/setup_client_isolation.py
../data-foundation/.venv/Scripts/python.exe ../data-foundation/governance/verify_isolation.py
```

The two builders invalidate their old completion marker before replacing data and republish only
after verification succeeds. Scheduled detectors consume that marker rather than guessing
completeness from `MAX(dt)`.

For the streaming path, use
`../module1-anomaly-detection/streaming/run_streaming_demo.sh`; it deploys, exercises, destroys, and
then lists Kinesis directly to verify teardown.
