# Architecture

Status: stub — will be populated incrementally as each module is built, with a final polish pass in Phase 4.

Each module section below follows: Pain -> Reasoning -> Architecture -> Trade-offs -> Cost -> Scale-up path.

## data-foundation

See [data-foundation/README.md](data-foundation/README.md).

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

TBD (Phase 2a). Must document two deliberate substitutions: SageMaker Feature Store -> lake-based
feature registry, and Amazon Q Business -> direct Bedrock (Nova Lite) report generation.

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
- **OpenSearch Serverless** — has an hourly OCU floor (~$175/month minimum) regardless of usage;
  S3 Vectors (GA Dec 2025) gives us Bedrock Knowledge Base support at near-zero idle cost instead.
- **Provisioned Redshift / EMR** — data volume (tens of MB) doesn't justify a provisioned cluster;
  Athena's per-query pricing ($5/TB scanned) costs fractions of a cent at this scale.
