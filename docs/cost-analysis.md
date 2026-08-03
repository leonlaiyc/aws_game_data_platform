# Cost Analysis

## Headline

At this project's scale the data plane costs cents, but the platform has a deliberate
**observability floor of roughly $1.30/month at gross list price**: 13 standard CloudWatch alarms
at the Tokyo rate before any free allocation. Compute still scales to zero; operational visibility
does not.

The more useful finding for an SA conversation is the shape of the cost, not the magnitude:

> **This architecture's cost is driven almost entirely by which services are chosen to exist, not
> by how much data flows through them.** At current scale the alarm fleet costs more than the
> workload. Going 100x on data moves the data-plane bill by dollars; choosing a provisioned or
> licensed platform can change it by orders of magnitude regardless of bytes.

Every service selection in [ARCHITECTURE.md](../ARCHITECTURE.md) follows from that asymmetry.

---

## Observed cost — point-in-time estimate, not a settled invoice

Built and deployed over 2026-07-26 → 2026-07-29. Cost Explorer estimate captured on 2026-07-29:

| | |
|---|---|
| **Gross usage estimated so far** | **$0.1156** |
| Free Tier credits | −$0.1156 |
| **Net charged** | **~$0.00** |

### Reading the two numbers correctly

The billing console reports **$0.12 for the month** while Cost Explorer's default view reports
essentially zero. Both are right and neither is the number to quote:

- The console figure is **usage before credits**.
- Cost Explorer's default `UnblendedCost` is **net of credits**.

Grouping by `RECORD_TYPE` separates them (`Usage` $0.1156, `Credit` −$0.1156). **The gross figure is
the one that transfers to a client**, because their account will not have these credits. Reporting
the net "$0" would be true of this account and useless to anyone else — which is why every model in
this document deliberately ignores Free Tier. Cost Explorer marked the period estimated, and
monthly CloudWatch alarm charges may post later, so this is evidence of early usage shape rather
than a final total.

### Where the $0.1156 went

| Service | Gross usage | Note |
|---|---|---|
| **AWS Cost Explorer API** | **$0.0400** | **The largest single line item — see below** |
| Amazon S3 | $0.0360 | Dominated by request count, not the 42 MB stored |
| Amazon Bedrock | $0.0234 | Every demo run across Modules 2, 3 and 4 |
| Amazon Athena | $0.0114 | ~every query in every demo and every lake rebuild |
| Amazon API Gateway | $0.0030 | |
| Amazon Kinesis | $0.0012 | The entire streaming demo |
| Amazon DynamoDB | $0.0006 | |
| CloudWatch, Secrets Manager | $0.00005 | |

### Three things this actually taught, which the model did not predict

**1. Investigating the cost cost more than running the platform.** The Cost Explorer API bills
**$0.01 per request**, and querying it a handful of times while writing this document produced the
single largest line item — more than S3, Bedrock and Athena individually, and 33x the entire Kinesis
demo. It is a real and easily-missed cost of cost-consciousness itself, and a genuine argument for
using the free Billing console or a scheduled export rather than ad hoc API calls when the amounts
under investigation are this small.

**2. The Kinesis estimate was ~20x too conservative.** This document previously estimated
$0.02–0.04 based on an assumed 1–2 hour stack lifetime. Actual: **$0.0012**. The deploy-demo-destroy
cycle was far shorter than the estimate assumed. The teardown discipline is still correct — the
*rate* is what matters, and $14/shard-month is the number that justifies it — but the estimate
should have been derived from the actual window rather than a guess at it.

**3. S3 request charges, not storage, dominate at this scale.** $0.036 against 42 MB stored. Every
Athena query writes result objects, every CTAS rewrites a prefix, and each of those is billable
requests. At small data volumes the instinct to optimise storage is misdirected; request count is
the lever.

### What the early model missed

The first model counted requests and bytes but omitted the fixed alarm fleet, which made its
"well under $0.10/month" headline false. The $0.1156 snapshot mostly reflects development and demo
activity; it is too early to validate a full month's alarm charge. The corrected steady-state model
below prices those alarms explicitly.

---

## The deliberately short-lived hourly cost: Kinesis

Kinesis Data Streams is the only short-lived service here that bills continuously per provisioned
unit, and it was chosen knowingly for one demo, then destroyed. CloudWatch alarms also have an idle
cost, but they are retained deliberately because observability is a steady-state requirement.

Verified pricing (checked before building, per this project's verify-before-build rule):

- **Provisioned:** **$0.0195 per shard-hour in ap-northeast-1 (Tokyo)**, charged continuously
  regardless of traffic. (The widely-quoted $0.015 is the us-east-1 rate; Tokyo carries roughly a
  30% premium. Worth stating because AWS pricing pages default to US regions and it is easy to
  quote a number that is right for a region you are not deploying in — the same caveat applies to
  the Bedrock rates below.)
- **On-Demand Standard:** a higher per-stream-hour charge *plus* per-GB data charges — **more
  expensive at idle** than provisioned, which is counter-intuitive and worth knowing.
- **No free tier in either mode.**

Decision: provisioned, 1 shard, in its own CDK stack with `RemovalPolicy.DESTROY`, deployed and
torn down inside a single session.

| | |
|---|---|
| Shards | 1 |
| Approximate lifetime | ~1–2 hours |
| **Observed Cost Explorer estimate** | **$0.0012** |
| If left running for a month | **~$14.24/shard-month** (730 h × $0.0195) |

The four orders of magnitude between those two rows is the whole point. The demo cost nothing
because it lasted minutes; the same stack forgotten for a month costs more than everything else in
this project combined, several times over.

That last row is the entire justification for the teardown discipline. Two things enforce it beyond
good intentions:

- The stack is **excluded from the default CDK app** behind a context flag, so `cdk deploy --all`
  cannot create it. (It used to be in the default app while the docs described a deploy-demo-destroy
  policy — a policy that only exists in prose is not a control.)
- `run_streaming_demo.sh` deploys, demos, destroys, and then **verifies by listing streams
  directly**, exiting non-zero if one survives. A `cdk destroy` that reports success while a
  resource lingers is exactly the failure that costs money for weeks, so its exit code is not
  treated as proof.

---

## Steady-state monthly model

What exists or runs with no human involved: 13 standard alarms, two EventBridge-triggered detector
Lambdas daily, plus Module 2's monitoring schedule.

| Component | Driver | Modeled monthly cost |
|---|---|---|
| Athena | Up to ~300 queries/month with fresh daily publications/active experiments; unchanged detector publications are skipped | **~$0.02** |
| Lambda | ~100 invocations × ~3 s × 128 MB | **< $0.01** |
| S3 | 42.5 MB stored (verified), plus request charges | **< $0.01** |
| DynamoDB | On-demand, minimal scheduled writes | **< $0.01** |
| SNS / EventBridge / CloudWatch Logs | Handful of messages, small log volume | **< $0.01** |
| CloudWatch standard alarms | 13 alarm metrics × $0.10 in Tokyo | **$1.30 gross list price** |
| Bedrock (Nova Lite) | $0 — only invoked on demand, nothing scheduled | **$0.00** |
| API Gateway | $0 — only charged per request | **$0.00** |
| **Total** | | **under $2/month gross list price** |

The first 10 alarm metrics may be covered by the CloudWatch free allocation when the account is
eligible, reducing that line to roughly $0.30, but the portable client model does not assume
credits. After alarms, Athena is the largest scheduled data-plane line because each query has a
minimum scanned-bytes floor. Official unit source:
[Amazon CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/).

---

### Module 2 live-exposure increment (checked 2026-07-29)

The live experiment path adds a second DynamoDB table and a route to services
that were already in the default architecture. It does **not** add a
provisioned worker, database cluster, NAT Gateway, long-running container, or
per-user licence.

| Service/change | Region | Billing unit and applicable allowance | Idle charge | Default? | Conservative demo estimate |
|---|---|---|---|---|---:|
| DynamoDB exposure table | `ap-northeast-1` | On-demand RRU/WRU plus storage. The documented 25 RCU/WCU Free Tier is for provisioned capacity, so it is **not** assumed here. Transactional sub-1 KB exposure writes use two write request units. | No provisioned throughput charge; stored bytes remain billable. | Yes | `< $0.08` for 10,000 accepted exposures, reads and the stream copy |
| DynamoDB Streams -> Lambda -> S3 | `ap-northeast-1` | Stream reads, Lambda requests/GB-seconds, S3 PUT/storage. DynamoDB documents 2.5 million stream reads/month in its Free Tier, but the gross model does not rely on it. | No compute idle charge; S3 storage persists. | Yes | `< $0.04` for the same 10,000-event demo |
| API Gateway exposure route | `ap-northeast-1` | REST API requests and data transfer. The one-million-call offer is time-limited for new accounts, so it is **not** assumed. | None | Yes | `< $0.05` for 10,000 requests |
| Step Functions live `Wait` | `ap-northeast-1` | Standard Workflow state transitions. A Wait does not accrue duration charges; the always-available allowance is 4,000 transitions/month. | No charge while waiting | Yes | `$0` inside 4,000 monthly transitions |
| Hourly EventBridge rule | `ap-northeast-1` | Same-account scheduled delivery plus the target Lambda invocation. | No provisioned worker | Yes | `< $0.01` at about 720 invocations/month |
| **Modeled increment** | | Gross list-price shape, before credits | | | **`< $0.20/month` at side-project volume** |

Official sources checked on that date:
[DynamoDB pricing](https://aws.amazon.com/dynamodb/pricing/),
[DynamoDB on-demand request units and idle behavior](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/on-demand-capacity-mode.html),
[API Gateway pricing](https://aws.amazon.com/api-gateway/pricing/),
[Step Functions pricing](https://aws.amazon.com/step-functions/pricing/), and
[EventBridge pricing](https://aws.amazon.com/eventbridge/pricing/).

Cost controls are executable, not just estimates:

- the REST stage is capped at 10 requests/second and 20 burst;
- the exposure table is capped at 25 on-demand read and write request
  units/second; AWS describes this cap as best-effort rather than an absolute
  financial ceiling;
- each exposure expires after 180 days through DynamoDB TTL;
- the analytics copy is append-only S3 data and the query table uses date
  partition projection;
- the existing USD 5 budget still warns at 80% forecast and 100% actual.

Scale trigger: when the product needs sustained traffic above 10 exposure
requests/second, raise the API/table caps only after load and cost modeling.
When stream-exported S3 objects create a measurable small-file penalty, replace
the Lambda export with buffered Firehose delivery and compact Parquet. For
high-cardinality monitoring, replace the current per-experiment DynamoDB Query
with stream-maintained aggregate counters.

Teardown is dependency ordered:

```powershell
cd infra
cdk destroy AuroraGamesOrchestrationStack --force
cdk destroy AuroraGamesRegistryStack --force
```

Independent read-only verification:

```powershell
aws dynamodb describe-table --table-name aurora-games-experiment-exposures
aws dynamodb describe-table --table-name aurora-games-experiments
aws stepfunctions list-state-machines --query "stateMachines[?name=='aurora-games-experiment-lifecycle']"
aws apigateway get-rest-apis --query "items[?name=='aurora-games-experiments-api']"
```

For a full teardown, both `describe-table` calls must return
`ResourceNotFoundException` and both list queries must return an empty list.
These default PoC stacks were intentionally retained after the authorised
2026-07-29 deployment; only the independently billed streaming stack follows
the immediate deploy-demo-destroy lifecycle.

### Module 3/4 delivery and work-item increment (checked 2026-07-29)

The new analytics fallback tickets, support sessions, first-look delivery, and
partner notification demo reuse DynamoDB, SNS, SQS, Lambda, and API Gateway.
No email, SMS, webhook, or other external recipient is subscribed by default.

| Resource | Billing unit | Idle charge | Cost/control decision |
|---|---|---|---|
| Analytics ticket table | DynamoDB on-demand requests + stored bytes | No provisioned throughput | 5 RRU/WRU best-effort cap; 90-day TTL |
| Support session table | DynamoDB on-demand requests + stored bytes | No provisioned throughput | 10 RRU/WRU best-effort cap; 24-hour TTL |
| First-look SNS -> SQS audit delivery | SNS API/delivery and SQS requests | No minimum fee | One-day queue retention; account-local only |
| Partner notification SNS -> SQS audit delivery | SNS API/delivery and SQS requests | No minimum fee | Operator-only publisher; credential-like content rejected |

Official sources checked on that date:
[SNS pricing](https://aws.amazon.com/sns/pricing/) states that Standard topics
are request/delivery priced with no upfront commitment, and
[SQS pricing](https://aws.amazon.com/sqs/pricing/) states that there is no
minimum fee and all customers receive one million requests per month. The
portable gross model still treats each request as billable rather than using
credits or allowances. At 100 chat/session operations, ten tickets, and ten
notifications per month, this increment is conservatively **below $0.01/month**
before the already-modeled Bedrock and API costs.

Scale triggers:

- when support sessions need full conversation context, store a bounded
  redacted turn history rather than only first-turn state;
- when tickets need assignment, SLA, ownership, and resolution workflow,
  replace the minimal DynamoDB queue with the company's CRM/ITSM connector;
- when a real partner opts in, add a confirmed, tenant-filtered delivery
  endpoint. SMS and dedicated origination identities are specifically excluded
  from this PoC because they can introduce destination-dependent or recurring
  charges;
- when delivery needs retry policies and per-partner fan-out at scale, add
  DLQs and subscription management rather than widening the audit queue.

### Four-pain-point increment (checked 2026-07-30; not deployed)

This local change does not add a provisioned service or an external recipient.
It reuses existing request-priced resources and keeps the central experiment
view on localhost.

| Change | Billing unit | Idle charge | Conservative current-scale increment |
|---|---|---|---:|
| Weekly mature D1/D7 retention check | Existing Lambda request/duration plus Athena bytes scanned; about 4.35 runs/month | No additional compute idle charge | `< $0.01/month`; about 17–18 queries/month for three sites |
| M2 `owner`/identity provenance | Existing DynamoDB on-demand writes and stored bytes | No provisioned throughput | Negligible bytes per experiment |
| M3 on-demand diagnosis | Two existing Athena query shapes per request | None when unused | Usage-only; no second Bedrock narration call |
| Retention first-look | Existing Lambda, S3, and SNS path | None when unused | Usage-only; code-rendered without a model call |
| Two M4 audience roles | IAM role/policy objects | IAM is offered at no additional charge | `$0` IAM service charge |
| Two packaged support corpora | Lambda package and selected Bedrock input tokens | No vector store/search capacity | Usage-only when an answer reaches the model |
| M4 daily cost quota | Existing DynamoDB session-table conditional update | No new table | 50 valid requests/UTC day/audience before Guardrails or inference; 1,000-character input cap |
| M4 stage throttle | API Gateway request rate | None | 0.1 request/second, burst 2; bounds invalid as well as valid traffic |
| Outcome measurement | Existing CloudWatch structured log bytes | No custom metric | Negligible at PoC request volume |
| M1 incident status | DynamoDB on-demand reads/writes plus one IAM-protected API request per manual transition | No provisioned throughput | Negligible at demo scale; normally one write when detected and at most two operator updates |

Athena bills by bytes scanned with a 10 MB minimum per query. At 18 minimum
queries this path scans about 180 MB/month, roughly `$0.0009` using AWS's
standard `$5/TB` example rate. Lambda is request and GB-second priced; four or
five additional invocations per month are immaterial even without relying on
credits. The EventBridge rule creates no worker process between invocations.

Official sources checked 2026-07-30:
[Athena pricing](https://aws.amazon.com/athena/pricing/),
[Lambda pricing](https://aws.amazon.com/lambda/pricing/),
[EventBridge pricing](https://aws.amazon.com/eventbridge/pricing/),
[IAM FAQ](https://aws.amazon.com/iam/faqs/), and
[CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/).

The change remains **locally verified / deployment pending**. No `cdk deploy`
or AWS mutation was run, so it has produced no new AWS bill.

Teardown:

```powershell
cd infra
cdk destroy AuroraGamesAnalyticsAssistantStack --force
cdk destroy AuroraGamesSupportChatbotStack --force
```

Read-only verification:

```powershell
aws dynamodb describe-table --table-name aurora-games-analytics-tickets
aws dynamodb describe-table --table-name aurora-games-support-sessions
aws sns list-topics --query "Topics[?contains(TopicArn, 'aurora-games-first-look-reports') || contains(TopicArn, 'aurora-games-partner-notifications')]"
aws sqs get-queue-url --queue-name aurora-games-first-look-report-audit
aws sqs get-queue-url --queue-name aurora-games-partner-notification-audit
```

## Marginal cost per use

These are the numbers to reach for when someone asks "what does one more user cost?"

| Action | Cost |
|---|---|
| One Module 3 NL question | **~$0.00005** (≈500 input + ~100 output tokens on Nova Lite, at $0.06/M in and $0.24/M out) plus a sub-cent Athena query |
| One Module 2 experiment readout | Fractions of a cent — one Bedrock call over an already-computed analysis result |
| One first-look report | ~3 Athena queries + one Bedrock call ≈ **under $0.01** |
| One Module 4 partner question, answered | Fractions of a cent — the identity-selected audience corpus goes in-context; no vector store is queried |
| One Module 4 question, refused by Guardrails | One `ApplyGuardrail` input check. AWS currently lists content filters at $0.15/1,000 text units and denied topics separately at $0.15/1,000 text units; individual filter categories/topics are not each multiplied as separate safeguard charges. |
| One Module 4 question, refused as out of scope | One `ApplyGuardrail` input check, then no model call. It is cheaper than an answered question but **not $0**. |

**Rate caveat:** the Nova Lite figures above are US-region rates. Tokyo is higher. The conclusion
(negligible at this volume) is unaffected, but the arithmetic would need redoing before quoting
these to a client.

Module 4's answered-question cost is higher than Module 3's because passing the
selected corpus in-context trades tokens for infrastructure. That is the trade
working as intended: a small per-question increment buys the removal of a
vector store, its ingestion pipeline, and its idle cost. Re-evaluate when the
audience corpus no longer fits comfortably in one prompt or measured token cost
exceeds a retrieval layer's total operating cost.

Note also the ordering effect: `BLOCKED_CONTENT` and `OUT_OF_SCOPE` are decided
before any model call, so abuse and off-topic traffic avoid inference spend.
Both still incur the standalone input Guardrails evaluation because security
classification intentionally runs first.

At **20,000 Module 3 model questions per month**, model-token cost remains on
the order of dollars under the cited rates. Module 4's PoC cannot reach that
traffic: its pre-Bedrock quota caps each of three audiences at 50 accepted
requests per UTC day (at most about 4,500 per 30-day month).

---

## Build vs. buy: the crossover is scope, not volume

Verified Amazon Quick (QuickSight) pricing:

| Item | Price |
|---|---|
| Reader (includes NL Q&A over one source) | $3 / user / month |
| Author | $24–$40 / user / month |
| Q Question Capacity | $250 / month for 500 questions ($0.50 overage; $0.30 at 60k/yr commitment) |
| Per-account infrastructure fee (once Pro users or Q&A enabled) | **$250 / month** |

**Important qualification:** these two $250 charges are not universal. Per-user pricing is an
alternative path, and a small team of Readers on a plain per-user plan pays far less than $500/month
— the infrastructure fee and the question-capacity plan apply to particular configurations
(Pro users, or Q&A enabled at capacity). Treating "$500/month floor" as the only possible Quick
cost would overstate the case for building.

The honest comparison: **for a handful of users, Quick can be tens of dollars a month, not
hundreds** — and against a custom marginal cost of ~$0.00005/question, there is still no volume at
which Quick wins on cost per question.

**But cheaper-per-question is the wrong lens.** Quick sells a complete BI platform: dashboards, ad
hoc exploration across any connected source, a polished end-user UI, and zero ongoing engineering
to build or maintain a semantic layer. Rebuilding that would cost far more in engineering time than
$500/month.

**Recommendation for a real client:** adopt Amazon Quick as the primary self-service BI surface,
and keep a thin custom layer only where the requirement is something Quick structurally does not
provide — deep integration with an existing pipeline and a hard "never state an unverified number"
guarantee. In this project that is Module 3's Capability B (alert → first-look report), not
Capability A.

---

## Cost at 100x

100x is ~500k players and ~4 GB of events over the same window.

| Component | At 100x | Notes |
|---|---|---|
| S3 storage | ~$0.10/month | 4 GB; storage is never the problem at this scale |
| Athena — Gold-reading detectors | Essentially unchanged | Gold size grows with days × sites, **not** with event volume |
| Athena — Silver/Gold rebuilds | ~$0.60/month if rebuilt daily | 4 GB full scan ≈ $0.02 per rebuild |
| Lambda | Low single-digit dollars | Longer runtimes, same invocation count |
| **Total** | **a few dollars per month** | |

**The highest-leverage optimization is not more compute.** Silver and Gold are already Parquet, so
the next levers are incremental partition rebuilds, compaction/file sizing, and making every query
use the existing partition pruning and column projection. Recommending a Parquet conversion here
would be prescribing work that the repository already completed.

The genuine architectural cliff at 100x is **ingestion**, not query: many small files per client per
day is the classic small-file problem, and that is the point where Kinesis Data Firehose earns its
cost by buffering and compacting on the way in.

---

## Cost controls actually implemented

Not aspirations — these are in the repository/CDK. Changes on
`codex/acceptance-hardening` were deployed and verified on 2026-07-29:

- **Athena workgroup bytes-scanned cap** (`aurora-games-wg`) — a hard ceiling per query, so a
  runaway or accidental full-table scan fails instead of billing. Note this still applies even
  though `enforce_work_group_configuration` is `False` (which was required to let CTAS write to its
  own `external_location`).
- **DynamoDB on-demand billing** — verified `PAY_PER_REQUEST`, so idle cost is genuinely zero rather
  than a small provisioned-capacity floor.
- **No always-on compute anywhere in the steady state** — no EC2, no NAT Gateway, no RDS, no
  provisioned cluster. Verified by direct resource listing, not assumed.
- **The streaming stack is a separate CDK stack** — specifically so it can be destroyed
  independently without touching anything else, and so its cost is visible rather than buried
  inside a larger stack.
- **Nova Lite rather than a larger model** — the tasks (classify a question, write one qualitative
  paragraph) do not need frontier-model capability, and the grounding-by-construction design means
  the model is never responsible for numerical accuracy in the first place.

## What is deliberately *not* optimized

Being honest about the trade-offs taken:

- **CloudWatch Logs retention is 2 years** (CDK's default). At this log volume the cost is
  immaterial, so it was not worth tuning; at scale it would be one of the first things to shorten.
- **Gold tables are rebuilt in full rather than incrementally.** This costs more Athena scan than
  strictly necessary in exchange for idempotency — a property worth paying for, because it makes
  every failure recoverable by simply re-running. The trade flips at 100x.
- **Lambda memory is left at the 128 MB default.** Right-sizing upward can sometimes *reduce* total
  cost by finishing faster; at ~100 invocations/month there is nothing meaningful to recover.
