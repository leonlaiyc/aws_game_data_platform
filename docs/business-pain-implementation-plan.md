# Business-Pain Implementation Plan

Status: **implemented, AWS-verified, and intentionally retired**. This was the
2026-07-30 implementation plan; its final operation paths were exercised on
AWS by 2026-08-03 and the PoC runtime was torn down on 2026-08-05. See
[AWS PoC teardown evidence](aws-teardown-evidence.md).

This plan is intentionally narrower than a service catalogue. Work is accepted
only when it addresses one of the four stated operating pains and does not add
an unjustified fixed AWS cost.

## Cost-first rules

- No AWS deployment is part of this change.
- Reuse existing Lambdas, topics, tables, and logs before adding a resource.
- No NAT Gateway, vector database, provisioned search/compute, licensed BI
  seat, or always-on worker.
- Prefer scheduled or on-demand work with publication markers and hard query
  limits.
- Record outcomes in existing structured logs before paying for custom metrics
  or another analytics store.
- Cap M4 at 50 valid requests per UTC day per identity-derived audience, before
  any paid Guardrails or model call; cap each question at one 1,000-character
  Guardrails text unit.
- Limit the entire M4 REST stage to 0.1 requests/second with burst 2 so invalid
  requests that stop before the daily counter cannot create machine-rate API
  and Lambda charges.
- Do not expose player-level or country-level answers until those dimensions
  exist in governed data and identity-derived tenant policy.

## Scope and delivery

| Priority | Business pain | Locally implemented now | Explicit next boundary |
|---|---|---|---|
| 1 | Parallel experiments are invisible until someone asks in chat or a stand-up | Registry create now requires a business `owner`; `created_by` and `updated_by` come from the authenticated IAM principal; the central local view shows owner, creator, lifecycle, SRM, guardrail health, allocation, and end time | Add SSO/team filters and richer audit history only when multiple regular operators justify hosting an internal UI |
| 1 | SRM/guardrail checks and stopping are delayed; features are rebuilt by different analysts | Existing exposure SRM, hourly monitoring, atomic allocation kill switch, and shared feature registry remain the control plane; this change makes responsibility visible rather than adding another service | Add feature lineage/usage telemetry only when duplicate feature incidents can be measured |
| 2 | Retention/revenue problems are noticed manually or by an isolated monitoring tool | The existing anomaly Lambda now runs a weekly mature-cohort D1/D7 retention check in addition to daily DAU/GGR; alerts enter the same SNS → Module 3 first-look path | Keep arbitrage scope on explainable, known risk signals until real reviewed outcomes can calibrate thresholds |
| 3 | Sudden “why did revenue drop?” questions interrupt analysts and grow with client count | Module 3 adds a governed `diagnose` path that reuses the first-look SQL and renders the site baseline plus per-game GGR evidence without a second model call; retention alerts also produce a first-look report | Country and individual-player questions remain blocked until governed dimensions and tenant-scoped authorization exist |
| 4 | Both game providers and 2C client operators repeat different integration questions across time zones | IAM identity now selects isolated `game_provider` or `client_operator` corpora; unknown identities fail closed; tickets record audience; existing audit logs record answer/clarification/escalation outcomes | Replace the two account-local PoC roles with per-partner federation claims before external production use; connect tickets/notifications only after the CRM/channel and opt-in owner are chosen |

## Incremental cost shape

| Change | Fixed idle charge | Variable use |
|---|---:|---|
| Weekly mature-retention schedule | None from additional compute | About 4–5 Lambda invocations/month and one discovery plus one Athena query per site per run |
| M2 owner/provenance fields and local dashboard column | None | A few additional DynamoDB bytes per experiment; the dashboard remains localhost-only |
| M3 on-demand diagnosis | None | Two existing Athena query shapes per diagnosis; no additional Bedrock answer-writing call |
| Retention first-look report | None | Existing Lambda/S3/SNS path; report text is code-rendered without a model call |
| M4 audience roles and packaged Markdown corpora | IAM has no additional charge; no vector store | Only the selected small corpus contributes model input tokens when an answer reaches the model |
| M4 daily cost quota | No new table; atomic counter uses the existing TTL session table | At most 50 paid-path requests per UTC day per audience |
| Structured outcome fields | No custom metrics | A small increase in existing CloudWatch log bytes |

At the current three-site PoC size, the weekly retention path adds roughly
17–18 Athena queries per month. Even if every query hits Athena's 10 MB minimum,
that is under 0.2 GB scanned per month, far below one cent at the standard
$5/TB example rate. This estimate does not rely on credits.

Official sources checked 2026-07-30:
[Athena pricing](https://aws.amazon.com/athena/pricing/),
[Lambda pricing](https://aws.amazon.com/lambda/pricing/),
[EventBridge pricing](https://aws.amazon.com/eventbridge/pricing/),
[IAM FAQ](https://aws.amazon.com/iam/faqs/), and
[CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/).

## Deployment gate

Before any later deployment:

1. Run the full offline test suite and `cdk synth`.
2. Run `python scripts/verify_paid_account_controls.py`.
3. Review the synthesized diff for new hourly/provisioned resources.
4. Reconfirm the USD 5 budget and destination ownership.
5. Deploy only with an explicit user decision, then run the module-specific
   AWS-path demos and inspect Cost Explorer after charges have settled.
