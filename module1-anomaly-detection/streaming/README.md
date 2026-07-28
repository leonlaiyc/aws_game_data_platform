# Real-Time Streaming Path (short-lived, cost-controlled)

Demonstrates real-time RTP (return-to-player) and volume anomaly detection alongside
`data_anomaly/`'s steady-state batch detection: `simulator -> Kinesis (1 shard) -> Lambda ->
DynamoDB rolling window -> SNS`.

**This is a capability demonstration, not part of the steady-state architecture.** The batch path
remains the default; see `ARCHITECTURE.md` for the full dual-path trade-off discussion (why batch
alone is insufficient for same-hour incidents, event-time vs processing-time, late-arriving data,
duplicate events, false-alert avoidance).

## Why this is its own stack, deployed and destroyed on demand

**Kinesis Data Streams has no "pay only when used" mode** (verified 2026-07-28): Provisioned
bills $0.015/shard-hour continuously regardless of traffic; On-Demand Standard bills a separate
fixed $0.040/stream-hour *plus* per-GB data-in — actually pricier at idle. No free tier at all.
Every hour this stack exists costs money whether or not a demo is running. `AuroraGamesStreamingStack`
is therefore kept entirely separate from the always-on stacks (`Foundation`/`Registry`/
`Orchestration`/`Governance`/`Anomaly`), so it can be deployed, demoed, and torn down in one sitting
without touching anything else.

## Run it

```bash
cd infra && cdk deploy AuroraGamesStreamingStack
cd ../module1-anomaly-detection/streaming/demo
../../../data-foundation/.venv/Scripts/python.exe run_streaming_demo.py
# ... inspect the result (see below) ...
cd ../../../infra && cdk destroy AuroraGamesStreamingStack --force
```

**A timing gotcha hit while verifying this**: the Lambda's Kinesis event source mapping uses
`starting_position=LATEST` (only ever process new records, not stream history). Running the demo
*immediately* after `cdk deploy` finishes can race the mapping's internal poller startup - records
sent in that window are simply gone (`LATEST` doesn't replay), and the demo shows an empty window.
Waiting even ~30-60 seconds after deploy before running the demo avoids this. Confirmed via
`aws lambda list-event-source-mappings ... --query 'EventSourceMappings[0].LastProcessingResult'`
showing `"No records processed"` on the first attempt, then succeeding on retry.

## What the demo does

Sends 20 "normal" bet events (RTP 0.60 - ordinary house edge) followed by 250 "anomalous" events
(RTP 0.99 - simulating a payout exploit/bug), all to `client_site_id=site_a`. Both land in the
same processing-time window (a UTC-minute bucket), so the blended totals trip **both** configured
thresholds at once:

```
=== Window state: site_a#2026-07-28T01:47 ===
bet_total=2700.00 win_total=2595.00 event_count=270 rtp=0.9611
alerted=True
```

`rtp=0.9611 > 0.95` (RTP_ALERT_THRESHOLD) and `event_count=270 > 200` (VOLUME_ALERT_THRESHOLD) -
exactly one SNS alert fires (see `_try_claim_alert` in the Lambda - a conditional DynamoDB update
ensures later batches that are still over threshold don't each send their own message).

## Design notes

- **Aggregation via Lambda + a DynamoDB rolling window, not Kinesis Data Analytics / Managed
  Flink.** A real windowing engine would be the production answer at meaningful throughput or if
  accurate event-time semantics were required; it also has its own persistent runtime cost, which
  doesn't fit a short-lived demo. The DynamoDB atomic-counter pattern here is simple, cheap
  (on-demand billing, TTL-expired windows need no manual cleanup), and sufficient to demonstrate
  the real-time alerting capability.
- **Windows are keyed by processing time** (when the Lambda runs), not the event's own `event_ts`.
  Simpler - no watermarking or "how long to wait for late data" logic needed - but means a record
  that's a few seconds late by its own timestamp still lands in whatever window is current when
  it's actually processed, not the window it logically belongs to. See `handler.py`'s docstring
  and `ARCHITECTURE.md` for what accurate event-time windowing would require.
- **No de-duplication.** Kinesis + Lambda event source mappings are at-least-once, not
  exactly-once - a retried batch could double-count records into these totals. Not implemented
  here (would need tracking processed sequence numbers or a per-event idempotency key) - a
  documented gap appropriate for a short demo, not a production posture.
- **Alert de-duplication**: implemented and verified (one alert per window regardless of how many
  batches stay over threshold), via a conditional `attribute_not_exists` DynamoDB update.
