# Module 1 — Anomaly & Arbitrage Detection

## Pain Point

Two silent-failure modes a B2B gaming platform actually experiences, and why neither is caught by
looking at a dashboard once a week:

1. **A retention or revenue drop goes unnoticed for weeks.** A payment provider integration
   breaks, a client site's app update has a bug, or a game's math has a regression — DAU or GGR
   quietly craters for one client site, and unless someone happens to be looking at that specific
   site's numbers that day, it surfaces in a monthly report after real revenue has already been
   lost.
2. **A coordinated multi-account ring runs undetected.** A handful of accounts sharing devices/IPs
   cycle deposits through minimal wagering into fast withdrawals — bonus abuse or payment
   arbitrage. Any single account's activity looks unremarkable in isolation; the pattern only
   shows up when you look *across* accounts.

Both need **automated, always-on detection**, not a human periodically remembering to check.

## Architecture

Three components, in increasing order of "how real-time":

| | Reads from | Cadence | Signal |
|---|---|---|---|
| [`data_anomaly/`](data_anomaly/) | `gold_daily_kpi` | Daily (EventBridge) | EWMA-based control limit on DAU/GGR per site |
| [`arbitrage_detection/`](arbitrage_detection/) | `silver_events` (device fan-out) + `gold_player_features` (behavior) | Daily (EventBridge) | Shared-device fan-out **combined with** abnormal cash-out ratio |
| [`streaming/`](streaming/) | Kinesis (live) | Real-time | RTP/volume threshold on a rolling window — short-lived demo, not steady-state |

All three publish to SNS on a hit and write their evidence to S3 (`gold/anomaly_alerts/`,
`gold/flagged_players/`) so findings are Athena-queryable, not just an email that scrolls away.

### Why arbitrage detection needs two signals, not one

Device fan-out alone (many accounts on one device) is explainable — a shared family computer, an
internet cafe. An abnormal withdrawal-to-deposit ratio alone is explainable too — a big winner
genuinely cashing out. **Neither alone is flagged; only players who show both** get flagged (see
`arbitrage_detection/lambda/detector/handler.py`'s docstring). This mirrors the same reasoning
Module 2's readout uses for caveats: a single weak signal shouldn't trigger an action a human
would consider a false alarm.

### Why the EWMA baseline can "catch up" to a sustained drop

Verified against the scripted scenario: checking **day 1** of `site_b`'s week-long drop
(2026-06-10) fires cleanly (DAU actual=91 vs EWMA baseline=204, ~3.9 standard deviations).
Checking **day 3** (2026-06-12) does not — by then the trailing history window used to compute the
baseline already includes 2 already-depressed days, pulling the baseline down and widening the
computed standard deviation. This is a real, known property of EWMA-style detection, not a bug:
it's tuned to catch the *onset* of a shift, and adapts toward a sustained new level rather than
alarming on it forever. A production system wanting both "catch the onset" and "stay alarmed while
still abnormal vs. the pre-incident baseline" would keep a separate, non-adapting reference
baseline for extended incidents - out of scope here.

## Deliberate design choices

- **Batch is the default architecture; a short-lived streaming path demonstrates real-time
  capability without becoming permanent infrastructure.** See `streaming/README.md` for why
  Kinesis has no idle-free pricing mode and is deployed/torn down around its own demo, and
  `ARCHITECTURE.md` for the full batch-vs-streaming trade-off (event-time vs processing-time,
  late-arriving data, duplicate events, false-alert avoidance).
- **Both batch detectors read only from the shared Gold tables** (`gold_daily_kpi`,
  `gold_player_features`) — same "single source of truth" principle as Module 2, never
  recomputing their own aggregates from Silver/Bronze.
- **Same dual-mode Lambda pattern used throughout this project** (see Module 2's
  `monitoring_check`): `{"scheduled": true}` is the real EventBridge-driven production path
  (discovers every site, checks today); an explicit `{"client_site_id", "as_of_date"}` lets the
  demo replay a specific historical day against the fixed simulated dataset.

## Running the demo

```bash
cd module1-anomaly-detection/demo
../../data-foundation/.venv/Scripts/python.exe run_demo.py
```

Verified output: the anomaly detector fires on `site_b`'s scripted drop (actual DAU=91 vs EWMA
baseline=204, ~3.9σ); the arbitrage detector flags exactly the 6 scripted ring players
(`p_ring_00`..`p_ring_05`), each sharing 2 devices with 5 other "distinct" accounts and showing a
~0.89-0.92 withdrawal-to-deposit ratio (see `data-foundation/README.md` for how that scenario was
seeded). For the streaming path, see `streaming/README.md`'s own deploy → demo → teardown cycle
(kept separate since it isn't run as part of this always-on demo).
