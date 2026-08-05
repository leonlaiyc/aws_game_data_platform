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
Its deploy-time S3 asset cache was nevertheless purged after both completed
PoCs were retired; the bootstrap bucket and ECR repository are empty.

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
  A root-authorized follow-up then detached its remaining policy and deleted
  the inert user object. A final IAM inventory returned zero IAM users.
- The account-level `CDKToolkit` stack was deliberately retained and was not
  counted as a project workload resource.

## Account-wide and earlier-PoC follow-up

A root-authorized account sweep completed on **2026-08-05 11:39
(Asia/Taipei)**. It covered all 17 enabled AWS Regions rather than only the
Tokyo deployment Region.

- The earlier semiconductor PoC's `ManufacturingAnomalyStack` was already in
  `DELETE_COMPLETE`. Its final two orphaned Lambda log groups (3,751 bytes in
  total, last used on 2026-07-19) were explicitly deleted.
- No active semiconductor/manufacturing resources were found by service
  inventory, resource-name, or tag searches.
- No workload resources were found in CloudFormation (apart from
  `CDKToolkit`), EC2/EBS, NAT Gateway, VPC Endpoint, ELB, RDS, OpenSearch,
  Redshift, ElastiCache, Kinesis, ECS/EKS, SageMaker, EFS/FSx, MSK, DMS,
  Lambda, DynamoDB, API Gateway, EventBridge, Step Functions, SNS/SQS, Glue,
  Athena, Backup, CodeBuild/CodePipeline, Amplify, or Bedrock Knowledge Bases.
- Additional checks found no customer-managed KMS keys, Advanced SSM
  parameters, QuickSight subscription, CloudTrail event data stores, AWS
  Config recorders, GuardDuty/Macie resources, VPN/Transit Gateway/Client VPN,
  Directory Service, WorkSpaces, Transfer Family, Batch, Cognito user pools,
  AppSync APIs, ACM certificates, or WAF web ACLs.
- The shared CDK bootstrap S3 bucket contained 181 cached deployment objects
  (113,589,734 bytes). All current and historical object versions, delete
  markers, and multipart uploads were removed. Its ECR repository contained
  zero images.
- The account-wide USD 5 CloudWatch billing alarm and its confirmed email SNS
  subscription remain enabled as a cost-safety control. They are not workload
  resources.

The only intentional AWS infrastructure left is the empty `CDKToolkit`
bootstrap, the IAM Identity Center/SSO access path, AWS-managed service-linked
roles, and the USD 5 billing alert. These are account administration and safety
controls, not executable resources from either PoC.

Result: no executable, scheduled, storage, observability, or API resource from
either PoC remains active. The public portfolio is now evidence-backed and
static, while the AWS implementations remain reproducible from source.
