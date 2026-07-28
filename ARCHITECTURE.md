# Architecture

Design rationale for the Aurora Games data platform. Each module section covers Pain → Reasoning →
Architecture → Trade-offs, and the [Design review](#design-review--aws-data-analytics-lens-questions)
section at the end answers AWS Data Analytics Lens-style questions against what is actually
deployed.

Diagrams: [`diagrams/`](diagrams/). Cost: [`docs/cost-analysis.md`](docs/cost-analysis.md).

**On honesty in this document:** where something is not implemented, it is named as a gap along
with the condition that would justify building it, rather than omitted. A design document that only
lists strengths isn't a design document.

## data-foundation

See [data-foundation/README.md](data-foundation/README.md) for the pipeline and the multi-tenant
governance write-up; the [Design review](#design-review--aws-data-analytics-lens-questions) section
covers isolation, lineage, and data quality in more depth.

## Module 1 — Anomaly & Arbitrage Detection

See [module1-anomaly-detection/README.md](module1-anomaly-detection/README.md) for the Pain ->
Architecture write-up. This section covers the batch-vs-streaming dual-path trade-off in full,
since that's the piece with the most AWS-SA-relevant nuance.

### Why batch alone is insufficient, and why streaming alone would be overkill

The steady-state architecture is **daily batch** (`data_anomaly/`, `arbitrage_detection/`): cheap,
simple, and adequate for the two pain points this module targets - a retention drop or an
arbitrage ring both play out over hours to days, not seconds. A once-daily EWMA check catches
either well within the window where a human would still consider the response "quick." Batch alone
becomes insufficient only for a different class of problem: a payout/RTP bug or an exploit that
drains value in minutes, where "worst case, we notice tomorrow morning" is a real, unacceptable
loss. That's the one scenario `streaming/` demonstrates real-time detection for - not because
streaming is generally better, but because it's the right tool for that specific failure mode.
Running everything as streaming would mean paying Kinesis's per-shard-hour cost permanently for
problems that don't need sub-minute detection - the wrong trade-off at this project's cost target.

### Event-time vs. processing-time

`streaming/lambda/aggregator/handler.py` buckets by **processing time** - when the Lambda actually
runs - not by each event's own `event_ts`. This is a deliberate simplification: it needs no
watermarking or "how long do we wait for stragglers" logic, at the cost of accuracy when
event-time and processing-time diverge (e.g. a producer buffering and sending a burst of
older-timestamped events all at once - as this project's own demo does). A system needing correct
event-time semantics - "this spike really happened at 14:03, even though we didn't process it
until 14:05" - would need a real windowing engine (Kinesis Data Analytics / Managed Flink) that
tracks watermarks and can hold a window open for a bounded amount of allowed lateness before
closing it. That's a permanent, non-trivial cost addition (Flink/KDA has its own persistent
runtime charge) which this project's throughput doesn't justify.

### Late-arriving data

Neither path currently re-opens a closed window for a late record. Batch: `gold_daily_kpi` is
rebuilt from a fixed CTAS each run, so a late-arriving event before the next rebuild is simply
included next time - "late" mostly resolves itself by the next day's batch. Streaming: a record
processed after its window has expired (DynamoDB TTL) starts a *new* window rather than correcting
the old one - the historical aggregate for that minute is permanently whatever was captured before
TTL eviction. Acceptable for this demo's timescales; a production system with a real lateness
requirement would need the same watermarking mechanism noted above.

### Duplicate events

Kinesis + Lambda event source mappings are **at-least-once**, not exactly-once - a retried batch
(e.g. after a transient Lambda error) can reprocess already-counted records. No de-duplication is
implemented in `streaming/`'s rolling-window counters (would need tracking processed sequence
numbers or a per-event idempotency key) - documented as a known gap appropriate for a short demo,
not a production posture. The batch path doesn't have this problem: Athena CTAS re-derives Gold
tables from Silver each run, so a duplicate Bronze event would need to be a duplicate *source*
event to double-count, not a pipeline-level concern.

### Avoiding false alerts

Three separate mechanisms across this module, each solving a different false-positive risk:
- **EWMA's k-sigma threshold** (3σ, not 2σ) trades detection speed for fewer false positives on
  ordinary day-to-day DAU/GGR noise.
- **Arbitrage detection requires two independent signals** (device fan-out *and* an abnormal
  cash-out ratio) rather than either alone - see `module1-anomaly-detection/README.md`.
- **Streaming's alert de-duplication** (a conditional DynamoDB update) ensures one alert per
  breached window, not one per Kinesis batch for as long as the breach persists - verified in the
  demo (270 events across multiple batches produced exactly one SNS message).

## Module 2 — Experimentation Platform

See [module2-experimentation-platform/](module2-experimentation-platform/) for the sub-module
READMEs. This section covers the parts with the most SA-relevant reasoning: the real pain point
(which is not the obvious one), two deliberate service substitutions, and how the readout is made
trustworthy.

### The actual pain point: visibility, not rigor

The obvious framing — "this company doesn't run rigorous experiments" — is the wrong one. The real
problem was **tracking the status of several concurrent A/B tests**: knowing which experiments were
live, which had already tripped a guardrail, and which were on their third iteration required
asking each owner individually or sitting through a standup where everyone reported in turn. The
registry's centralized visibility is therefore the primary value; SRM checks, guardrail automation,
and the feature registry are standardization and optimization on top of it, not the headline.

This shows up directly in the schema: `related_experiment_id` exists because experiments in this
domain are usually iterated several times before they conclude, and "how many rounds has this idea
been through, and what happened each time" was previously tribal knowledge held by one person.

### Substitution 1: SageMaker Feature Store → lake-based feature registry

Feature Store's value is online serving (single-digit-millisecond lookups for real-time inference)
plus point-in-time-correct training sets. This platform needs neither: experiment assignment and
analysis are batch operations reading yesterday's features. What it *does* need is the governance
half — a documented, versioned definition of what each feature means, so "high-value player" means
the same thing in every experiment.

So the feature registry is a Gold table (`gold_player_features`) plus
[`FEATURES.md`](module2-experimentation-platform/feature_registry/FEATURES.md) as the definition of
record — the same "single source of truth" pattern as `KPI_DEFINITIONS.md`. **Migration trigger:**
if features were ever needed for real-time inference (e.g. live personalization at request time),
the online-store requirement would justify Feature Store; batch-only usage does not.

### Substitution 2: Amazon Q Business → direct Bedrock (Nova Lite)

Q Business is a managed RAG-over-enterprise-documents product with per-user licensing. The readout
needs the opposite shape: not retrieval over documents, but **synthesis over a structured analysis
result we already computed**. There is nothing to retrieve — the statistics, guardrail outcomes,
and caveat flags are all in hand before the model is called. Paying per-user licensing for a
retrieval engine we don't use would be the wrong fit at any price.

### What makes the readout trustworthy

Two mechanisms, deliberately separated:

- **Code renders every number.** The Key Stats and Guardrail Status sections are built by Python
  from the analysis result. The model receives them and writes only `conclusion` and
  `recommendation` as qualitative prose. A regex-based grounding check runs afterward as a
  *secondary* safety net — it catches drift, but the guarantee comes from the model never being
  asked to produce a figure in the first place.
- **Code decides which caveats must be addressed.** `analysis` computes deterministic flags
  (`SAMPLE_IMBALANCE`, `SMALL_SAMPLE`, `GUARDRAIL_NEAR_THRESHOLD`, `SUSPICIOUSLY_LARGE_EFFECT`,
  `WIDE_UNCERTAINTY`) from thresholds in code. The prompt lists every flag present and requires the
  Conclusion to address all of them. **The model chooses how to phrase a caveat, never whether to
  mention it** — the failure mode where an LLM quietly omits an inconvenient limitation is closed
  structurally, not by asking it nicely.

### Why SRM and SAMPLE_IMBALANCE are both needed

They answer different questions and can legitimately disagree. The **SRM check** is a chi-square
test asking "is this split deviation *statistically implausible* for a sample this size?" — with
few users, a 60/40 split is entirely consistent with a fair coin, so SRM passes. **SAMPLE_IMBALANCE**
is a flat ratio check asking "is this split *lopsided enough that a reader should be told*?" —
regardless of whether chance explains it. A small experiment can therefore pass SRM (no evidence of
a bug in the assignment system) while still deserving a caveat (the comparison is unbalanced enough
to weaken the conclusion). Collapsing them into one check would either spam false SRM alarms on
small experiments or silently ship lopsided readouts as if they were clean.

## Module 3 — Analytics NL Assistant *(repointed 2026-07-27, was "Support Chatbot")*

See [module3-analytics-assistant/README.md](module3-analytics-assistant/README.md) for the full
Pain -> Architecture write-up, verified demo output, and the build-vs-buy analysis against Amazon
Quick with a usage-volume cost crossover. The original document-RAG/support-chatbot concept was
dropped, not deferred — no vector store (S3 Vectors) is needed for this design.

### Templates vs. free-form text-to-SQL

The model never writes SQL. It classifies a question and extracts slots (metric, site, date
range) from a closed set, re-validated against a whitelist before being substituted into one of 5
hand-written, reviewed SQL templates (`semantic_layer/templates.py`). This is strictly less
capable than text-to-SQL — it can only ever answer the 5 KPIs it has a template for — in exchange
for a hard, structural guarantee: every number in an `answerable` response is a real query result,
never a model-generated figure, and every template is auditable against `KPI_DEFINITIONS.md`
before it ships. Free-form text-to-SQL over a real production schema is also a real injection
surface (a crafted question steering generated SQL) that a closed template set with
whitelisted-only substitution simply doesn't have.

### A Guardrails false-positive, and why it matters for this module specifically

Bedrock Guardrails' `PROMPT_ATTACK` filter initially flagged **every** request — including
completely benign questions — at HIGH confidence, because the first implementation put the whole
system prompt (metric catalog, output schema, classification rules) into the same `user`-role
turn as the question. A dense block of imperative instructions in the user turn is exactly the
shape of an injected prompt trying to hijack the model, so the filter couldn't distinguish our own
trusted instructions from an attack. Moving the static instructions into `converse()`'s `system`
parameter and leaving only the raw question in `messages` fixed it — this is the architecturally
correct separation regardless of Guardrails, and a genuine injection attempt still correctly fires
the guardrail afterward (verified in the demo). Worth calling out on its own because it's a
concrete, non-obvious lesson about how Guardrails' attack heuristics actually work, not just a bug
fix.

### Cost: why "how many questions per month" isn't the right crossover variable

Amazon Quick's realistic cost floor (a $250/month per-account infra fee once Q&A/Pro is enabled,
plus a $250/month minimum question-capacity tier) is roughly $500+/month regardless of usage.
Verified Nova Lite pricing ($0.06/million input tokens, $0.24/million output tokens) puts this
module's marginal cost at roughly $0.00005 per question, with Athena/Lambda/API Gateway cost
similarly negligible at this project's data volume — so the custom stack never "loses" to Quick on
raw per-question economics at any realistic volume. The real trade-off is scope, not volume: Quick
sells a complete BI platform (dashboards, broad ad hoc NL Q&A across any connected source, zero
semantic-layer engineering); a narrow, hard-grounded set of 5 governed KPIs is exactly the case
where that platform is overkill and a thin custom layer is both cheaper and more correct. See the
README for the full write-up and the resulting real-client recommendation (Quick as the primary
BI surface, a thin custom layer only for the Module 1 alert -> first-look-report integration).

## Deliberately excluded services

- **Kinesis Data Streams** — not needed for the steady-state architecture; our SLA tolerance
  (minutes, not sub-second) is met by micro-batch ingestion straight to S3, at zero idle cost.
  **Exception**: Module 1 includes one short-lived, separately-stacked streaming path (explicit
  teardown after its demo) purely to demonstrate the capability — this doesn't change the
  steady-state batch default. Migration path if sub-second ingestion were ever a permanent need:
  swap the batch writer for a Kinesis producer + Firehose.
- **OpenSearch Serverless, and vector stores generally** — OpenSearch Serverless has an hourly OCU
  floor (~$175/month minimum) regardless of usage, which alone would break this project's
  near-zero-idle-cost constraint. But the deeper reason is that **no module needs retrieval at
  all**: Module 3 answers from a semantic layer of pre-approved SQL templates over structured Gold
  tables, not from documents. A vector store would be infrastructure in search of a problem here.
  **Migration trigger:** a genuine document corpus too large to fit in-context (partner integration
  guides, support runbooks) would justify one — and S3 Vectors, not OpenSearch Serverless, would be
  the cost-appropriate starting point at that scale.
- **Provisioned Redshift / EMR** — data volume (tens of MB) doesn't justify a provisioned cluster;
  Athena's per-query pricing ($5/TB scanned) costs fractions of a cent at this scale.

## Design review — AWS Data Analytics Lens questions

The questions a reviewer would actually ask, answered against what is deployed. Where the honest
answer is "not implemented," it says so and names the trigger that would change the decision.

### How is client data isolated in a multi-tenant lake?

At the **catalog layer**, via Lake Formation row-level data cell filters: each analyst role carries
a filter of `client_site_id = '<its own site>'` on `gold_daily_kpi`. The filter is applied when
Athena plans the query, so a role physically cannot read another client's rows — verified by
assuming each role via STS and confirming the row counts
([`verify_isolation.py`](data-foundation/governance/verify_isolation.py)).

The alternative — filtering by `client_site_id` in application code or per-client S3 prefixes with
IAM policies — was rejected because it puts tenant isolation one forgotten `WHERE` clause away from
a cross-tenant leak, and because prefix-based IAM can't express row-level rules over a shared table
at all. **Gotcha worth knowing:** every new Glue table is automatically granted to
`IAM_ALLOWED_PRINCIPALS`, which defers entirely to IAM and silently bypasses the filter; that grant
must be explicitly revoked per table or the isolation is decorative.

### How are metric definitions, catalog, and lineage governed?

One document per concern, each treated as the definition of record rather than documentation of an
implementation: [`KPI_DEFINITIONS.md`](data-foundation/KPI_DEFINITIONS.md) for business metrics
(GGR, DAU, ARPU, D1/D7 retention) and
[`FEATURES.md`](module2-experimentation-platform/feature_registry/FEATURES.md) for experiment
features. Both are versioned, and consumers cite the version: Module 3's answers carry a source
footer naming the table *and* the `KPI_DEFINITIONS.md` anchor, so a disputed number is traceable to
its definition in one step.

Lineage is **structural rather than tooled**: Bronze → Silver → Gold is a fixed CTAS chain in
version-controlled SQL, so any Gold column's derivation is readable from the repo. **Honest gap:**
there is no automated column-level lineage graph (Glue's lineage features or DataZone would provide
one). At four Gold tables the SQL *is* the lineage; the trigger to adopt tooling is when the number
of Gold tables or the number of teams writing them makes reading the SQL impractical.

### What happens when a transform job fails, or data arrives late?

**Failure:** the Silver/Gold build is a rebuild-from-source CTAS, not an incremental append, which
makes it idempotent — a failed or partially-completed run is fixed by re-running it, with no
compensating cleanup and no risk of double-counting. This is the main reason the pipeline is
tolerable to operate without an orchestrator like Step Functions or MWAA sitting over it.

**Late data:** batch resolves it implicitly — because Gold is rebuilt from the full Silver history
each run, an event that lands after a given day's build is simply included the next time. The
streaming path does *not*: a record arriving after its rolling window has expired via DynamoDB TTL
starts a new window rather than correcting the closed one. That's acceptable for a demo and stated
as a known limitation; a real lateness requirement needs watermarking (Managed Flink), which carries
a permanent runtime cost this project's throughput doesn't justify.

### What data-quality checks exist?

Three, at different layers, and one deliberate omission:

- **Schema/type enforcement at Silver** — the CTAS casts explicitly, so malformed records fail the
  build loudly rather than silently producing nulls in Gold.
- **Statistical plausibility at read time** — Module 1's EWMA detector is, in effect, a continuous
  data-quality monitor: a pipeline bug that halves DAU looks the same as a real DAU drop, and both
  should page someone.
- **Assignment integrity** — Module 2's SRM check catches a broken randomizer, which is a
  data-quality failure specific to experimentation.

**Omission:** there is no declarative constraint framework (Glue Data Quality, Deequ) asserting
things like "GGR is never null" or "DAU ≤ registered players." At this scale the CTAS plus the
detectors cover the realistic failure modes; the trigger for adopting one is multiple teams writing
into Gold, where you can no longer reason about every writer.

### Athena or Redshift?

**Athena, decisively, at this scale** — and the reasoning is about access pattern, not just data
size. The workload is bursty and infrequent: a handful of Lambda-issued queries per day, scanning
kilobytes. Redshift Serverless bills by RPU-second with a minimum charge per query burst, and
provisioned Redshift bills continuously; either means paying for a query engine that is idle
essentially all the time. Athena's per-query model matches a workload that is idle by default.

**Where it flips:** Redshift becomes correct when queries stop being sporadic and start being
concurrent and interactive — a BI tool with dozens of analysts issuing sub-second dashboard queries,
where Athena's per-query planning latency and lack of result caching across users start to hurt, and
where sustained utilization makes a provisioned cluster cheaper per query than $5/TB. A rough
threshold: sustained multi-user interactive BI over hundreds of GB. This project is three orders of
magnitude below that.

### What breaks at 100x, and what's the plan?

100x here is ~500k players and ~4 GB of events over the same window — still small in absolute
terms, so most of the architecture holds. What changes:

1. **Bronze query cost becomes real.** At 4 GB, full scans start costing measurable money. The fix
   is already half-built: Bronze uses partition projection, so the change is converting Silver/Gold
   to **Parquet with partition pruning and column projection** — likely a 10–50x scan reduction, and
   the single highest-leverage change.
2. **CTAS rebuild time stops being free.** Full rebuild-from-source becomes minutes, not seconds.
   The idempotency benefit is worth keeping as long as possible; past that, move to
   **incremental partition-level rebuilds** (rewrite only the affected `dt` partitions), accepting
   the added complexity of tracking what needs rebuilding.
3. **The direct-to-S3 ingestion assumption breaks.** Many small files per client per day is the
   classic small-file problem. That is the point where **Firehose** earns its cost — buffering and
   compacting on the way in, rather than a compaction job cleaning up afterward.
4. **What does not change:** Lake Formation isolation, the KPI/semantic-layer governance, Module 3's
   template approach, and the Lambda-based detectors all scale without redesign. The detectors read
   Gold aggregates, whose size grows with days and sites, not with event volume.

### Monitoring, alerting, retry, rollback, backfill

- **Monitoring/alerting:** business-level anomalies go to SNS via Module 1. Infrastructure-level
  monitoring is Lambda's default CloudWatch metrics and logs, with full structured audit logging in
  Module 3's classification path. **Honest gap:** there are no CloudWatch alarms on operational
  metrics (Lambda error rate, Step Functions execution failures) — a real deployment needs them, and
  this is the first thing to add before calling any of it production-ready.
- **Retry:** Step Functions provides per-state retry for Module 2. Lambda's async invocation retry
  covers the SNS-triggered path. **Gap:** no dead-letter queues, so a poison-pill SNS message is
  dropped after retries rather than parked for inspection.
- **Rollback:** everything is CDK, so infrastructure rollback is CloudFormation's. Data rollback is
  the CTAS idempotency property — re-running from Silver reproduces Gold deterministically.
- **Backfill:** the same mechanism as a normal run. Both detectors accept an explicit
  `{client_site_id, as_of_date}` payload precisely so a historical day can be replayed — that's how
  the demos work, which means the backfill path is exercised continuously rather than being untested
  code that only runs during an incident.

### Why not Snowflake, Kafka, or Redshift?

- **Snowflake** — the credit model has a minimum billing increment per warehouse resume, so a
  workload of a few small queries per day pays for far more compute than it uses. It also adds a
  second identity and governance plane alongside IAM/Lake Formation, which for a multi-tenant
  isolation requirement means maintaining tenant boundaries in two systems instead of one.
- **Kafka (MSK)** — brokers bill continuously whether or not anything is published. This project's
  steady state is batch, and even the streaming demo needed a single shard for minutes. MSK becomes
  right when there are multiple independent consumer groups needing replayable, ordered streams —
  i.e. when the streaming path stops being one producer and one consumer.
- **Redshift** — covered above: it's an availability-and-concurrency answer, and this workload is
  sporadic and single-user by nature.

The common thread: every one of these is a **fixed-cost-when-idle** service, and this platform is
idle almost all the time. That single property, more than data volume, drives the whole
serverless-first design.
