# Cost Analysis

## Headline

At this project's scale the platform costs **on the order of a few cents per month** in steady
state, and **near-exactly zero when nobody is using it**. That is not an accident of small data —
it is the direct result of one design rule applied everywhere: *no service that bills while idle.*

The more useful finding for an SA conversation is the shape of the cost, not the magnitude:

> **This architecture's cost is driven almost entirely by which services are chosen to exist, not
> by how much data flows through them.** Going 100x on data moves the bill from cents to a couple
> of dollars. Adding one always-on managed service — OpenSearch Serverless, a Redshift cluster, MSK,
> or Amazon Quick — moves it from cents to hundreds, at *any* data volume.

Every service selection in [ARCHITECTURE.md](../ARCHITECTURE.md) follows from that asymmetry.

---

## Observed cost to date — and why it is not the whole story

Pulled from Cost Explorer for 2026-07-01 → 2026-07-28 (the project's entire lifetime; first commit
was 2026-07-26):

| Service | Unblended cost |
|---|---|
| Amazon S3 | $0.0000003 |
| Amazon DynamoDB | $0.0000000002 |
| AWS Data Transfer | −$0.0000003 |
| **Everything else** | **$0 recorded** |

**Three caveats, because reporting this as "$0" would be misleading:**

1. **Cost Explorer lags roughly 24 hours.** The figures above were pulled on 2026-07-28, so
   2026-07-28's usage — which includes the Kinesis streaming stack's entire lifetime and all of
   Module 3's deployment and testing — **is not yet reflected**. The Kinesis charge in particular
   is a real, non-zero amount that has not landed yet (estimated below).
2. **This account benefits from AWS Free Tier allowances** on Lambda, API Gateway, SNS, DynamoDB and
   CloudWatch. A real client account past its first 12 months would not. **Every modeled figure
   below deliberately ignores Free Tier**, so the numbers transfer to a real engagement.
3. **Athena, Bedrock and Lambda usage here is genuinely tiny**, so several line items round below
   Cost Explorer's display precision rather than being truly zero.

**Re-check after 2026-07-30** for the settled figure including the Kinesis charge.

---

## The one deliberately non-zero cost: Kinesis

Kinesis Data Streams was the only service used in this project with **no free tier and a
bills-while-idle model**, and it was chosen knowingly, for one demo, then destroyed.

Verified pricing (checked before building, per this project's verify-before-build rule):

- **Provisioned:** $0.015 per shard-hour, charged continuously regardless of traffic.
- **On-Demand Standard:** $0.040 per stream-hour *plus* per-GB data charges — **more expensive at
  idle** than provisioned, which is counter-intuitive and worth knowing.
- **No free tier in either mode.**

Decision: provisioned, 1 shard, in its own CDK stack with `RemovalPolicy.DESTROY`, deployed and
torn down inside a single session.

| | |
|---|---|
| Shards | 1 |
| Approximate lifetime | ~1–2 hours |
| **Estimated charge** | **~$0.02 – $0.03** |
| If left running for a month | **~$10.95/shard-month** |

That last row is the entire justification for the teardown discipline. Teardown was verified by
directly listing the resources afterward (`aws kinesis list-streams` returning empty), not inferred
from the destroy command having been issued — a distinction that matters, because a stack deletion
that silently fails leaves a meter running that nobody is watching.

---

## Steady-state monthly model

What runs on a schedule with no human involved: two EventBridge-triggered detector Lambdas daily,
plus Module 2's monitoring schedule.

| Component | Driver | Modeled monthly cost |
|---|---|---|
| Athena | ~300 queries/month, each well under the per-query minimum billing unit, at $5/TB | **~$0.02** |
| Lambda | ~100 invocations × ~3 s × 128 MB | **< $0.01** |
| S3 | 42.5 MB stored (verified), plus request charges | **< $0.01** |
| DynamoDB | On-demand, minimal scheduled writes | **< $0.01** |
| SNS / EventBridge / CloudWatch Logs | Handful of messages, small log volume | **< $0.01** |
| Bedrock (Nova Lite) | $0 — only invoked on demand, nothing scheduled | **$0.00** |
| API Gateway | $0 — only charged per request | **$0.00** |
| **Total** | | **well under $0.10/month** |

Note which line is largest: **Athena**, and not because of data volume — because each query is
billed with a minimum scanned-bytes floor, so a few hundred tiny queries cost more than the bytes
would suggest. At this scale the pipeline's cost is dominated by *query count*, not *data size*.

---

## Marginal cost per use

These are the numbers to reach for when someone asks "what does one more user cost?"

| Action | Cost |
|---|---|
| One Module 3 NL question | **~$0.00005** (≈500 input + ~100 output tokens on Nova Lite, at $0.06/M in and $0.24/M out) plus a sub-cent Athena query |
| One Module 2 experiment readout | Fractions of a cent — one Bedrock call over an already-computed analysis result |
| One first-look report | ~3 Athena queries + one Bedrock call ≈ **under $0.01** |
| One Module 4 partner question, answered | **~$0.0002** — the whole 7.8 KB corpus (~2,000 tokens) goes in-context on every request |
| One Module 4 question, refused before the model | **~$0.000002** — an `ApplyGuardrail` call, or zero if the scope check rejects it first |

Module 4's answered-question cost is roughly **4x** Module 3's, purely because passing the entire
corpus in-context trades tokens for infrastructure. That is the trade working as intended: ~$0.0002
per question buys the removal of a vector store, its ingestion pipeline, and its idle cost. It stops
being a good trade at roughly a 50x larger corpus, where per-question token cost would exceed what a
retrieval layer costs to run.

Note also the ordering effect: the two cheapest categories (`BLOCKED_CONTENT` and `OUT_OF_SCOPE`)
are decided **before** any model call, so abuse and off-topic traffic — the volume most likely to
spike — is also the volume that costs essentially nothing to reject.

At **20,000 NL questions per month** the Bedrock cost is still about **$1**. This is why the
build-vs-buy comparison against Amazon Quick does not turn on question volume — see below.

---

## Build vs. buy: the crossover is scope, not volume

Verified Amazon Quick (QuickSight) pricing:

| Item | Price |
|---|---|
| Reader (includes NL Q&A over one source) | $3 / user / month |
| Author | $24–$40 / user / month |
| Q Question Capacity | $250 / month for 500 questions ($0.50 overage; $0.30 at 60k/yr commitment) |
| Per-account infrastructure fee (once Pro users or Q&A enabled) | **$250 / month** |

Realistic floor: **~$500/month before anyone asks a single question.** Against a custom marginal
cost of ~$0.00005/question, there is no volume at which Quick becomes cheaper per question.

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

**The highest-leverage optimization is not more compute — it is file format.** Converting Silver and
Gold to Parquet with partition pruning and column projection would cut scanned bytes roughly 10–50x,
taking the rebuild line back under a dollar. That is the first thing to do at 100x, before anything
architectural.

The genuine architectural cliff at 100x is **ingestion**, not query: many small files per client per
day is the classic small-file problem, and that is the point where Kinesis Data Firehose earns its
cost by buffering and compacting on the way in.

---

## Cost controls actually implemented

Not aspirations — these are in the deployed code:

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
