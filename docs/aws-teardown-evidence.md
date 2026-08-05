# AWS PoC Teardown Evidence

## Purpose

The live AWS proof-of-concept was intentionally retired after implementation,
AWS operation-path verification, cost measurement, and demo recording were
complete. The public GitHub Pages walkthrough, recorded demo, source code,
tests, architecture decisions, and cost evidence remain available without
requiring idle cloud resources.

## Verified deployment before teardown

Read-only inventory captured on **2026-08-05 10:38 (Asia/Taipei)** in
`ap-northeast-1`:

- 8 `AuroraGames*` CloudFormation stacks were in `CREATE_COMPLETE` or
  `UPDATE_COMPLETE`.
- The stacks contained 17 Lambda functions, 6 DynamoDB tables, 4 API Gateway
  REST APIs, 4 EventBridge rules, 4 Athena workgroups, 1 S3 lake bucket,
  1 Step Functions state machine, 5 SNS topics, 4 SQS queues, 2 Bedrock
  Guardrails, and 13 CloudWatch alarms.
- All four scheduled rules were enabled: two hourly, one daily, and one weekly.
- The 13 CloudWatch alarms were all in `OK` state.
- No Kinesis Data Stream remained. The separately metered streaming demo had
  already completed its deploy-demo-destroy lifecycle.
- The observed cost snapshot remains documented in
  [`cost-analysis.md`](cost-analysis.md): USD 0.1156 gross usage estimated on
  2026-07-29 before credits.

The deployed stack set was:

1. `AuroraGamesFoundationStack`
2. `AuroraGamesRegistryStack`
3. `AuroraGamesOrchestrationStack`
4. `AuroraGamesGovernanceStack`
5. `AuroraGamesAnomalyStack`
6. `AuroraGamesAnalyticsAssistantStack`
7. `AuroraGamesSupportChatbotStack`
8. `AuroraGamesObservabilityStack`

## Data-destruction boundary

The S3 lake used `RemovalPolicy.DESTROY` with automatic object deletion. All
six DynamoDB tables also used `RemovalPolicy.DESTROY`. Their contents were
synthetic PoC data and were deliberately treated as disposable. The CDK source,
fixtures, offline tests, and recorded demonstration are the durable evidence.

The CDK bootstrap stack (`CDKToolkit`) is not part of this project teardown. It
is account-level deployment tooling and may be reused by future CDK projects.

## Post-teardown verification

Teardown completed on **2026-08-05 11:00 (Asia/Taipei)**.

- All 8 `AuroraGames*` CloudFormation stacks were deleted. The foundation
  stack initially reached `DELETE_FAILED` because Athena would not delete a
  workgroup containing query history; `aurora-games-wg` was then deleted with
  Athena's recursive-delete option and the stack retry completed.
- Independent list/describe checks returned no project resources in
  CloudFormation, S3, DynamoDB, Lambda, API Gateway, EventBridge, CloudWatch
  alarms, Step Functions, SNS, SQS, Athena, Kinesis, CloudWatch Logs, Glue,
  Bedrock Guardrails, or project IAM roles.
- 19 retained or orphaned project CloudWatch log groups were explicitly
  deleted, including the two historical streaming-demo groups.
- The stack-managed USD 5 project budget was deleted with the observability
  stack. Future account-wide budget controls should be managed independently
  from disposable workload stacks.
- The only long-lived access key for the separately created
  `aurora-games-cdk` IAM user was deleted and independently confirmed invalid.
  The user has no Console login profile. Its inert IAM user object and attached
  policy could not be removed by the available SSO deployment role because
  that role intentionally has no IAM-user administration permission; final
  metadata deletion requires the account root user or another identity with
  `iam:DeleteUser` and related user-policy permissions.
- The account-level `CDKToolkit` stack was deliberately retained and was not
  counted as a project workload resource.

Result: no executable, scheduled, storage, observability, or API resource from
the PoC remains billable. The public portfolio is now evidence-backed and
static, while the AWS implementation remains reproducible from source.
