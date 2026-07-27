# Module 2 Demo

Runs 3 concurrent experiments end to end and prints each one's final state, analysis, and
Bedrock-generated readout - showing the registry, SRM check, guardrail auto-stop, and readout all
trigger for real.

```bash
cd module2-experimentation-platform/demo
../../data-foundation/.venv/Scripts/python.exe run_demo.py
```

Takes a few minutes: it injects demo data, rebuilds the lake (`silver_events` +
`gold_player_features`), starts all 3 Step Functions executions, and polls until they finish.

## The 3 scenarios

| Scenario | Site / game | What's injected | Expected outcome |
|---|---|---|---|
| Clean winner | site_a / game_01 (payout tweak) | Treatment group gets an extra, real bet event/day for the monitoring window - a genuine, positive, house-edge-consistent revenue boost | Completes normally; analysis shows a real positive lift; grounded Bedrock readout |
| Guardrail auto-stop | site_c / game_02 (art/UX change) | Treatment group gets an extra big-loss bet event/day (small bet, large win) | Guardrail (`ggr_usd_7d >= 0`) breaches within the first monitoring day; auto-stops to `stopped_early` + SNS alert |
| SRM violation | site_b | **Nothing injected.** The script creates/deletes cheap draft experiments (no Athena calls) until the real, unmodified hash-based assignment happens to produce a chi-square-significant imbalance for that day's small eligible population | Hard-fails during `srm_check`, before monitoring/analysis/readout ever run |

The SRM scenario is deliberately *not* faked by breaking the assignment logic - it demonstrates the
check catching a genuinely bad randomization outcome, which is what it exists to do in production.

## Why data has to be injected for scenarios 1 and 2

Assignment happens by hashing `(experiment_id, seed, player_id)` - it decides who's in which group,
it doesn't change how those players already behaved in the past. Our lake is a fixed historical
simulation, so "control" and "treatment" players are otherwise statistically identical; without an
injected difference there's no real effect to detect. `registry`'s `assignment_seed` was changed
from `random.randint` to a deterministic hash of `experiment_id` specifically so this script can
predict the real split *before* calling `/start`, and inject matching data for exactly the players
who will land in "treatment" - the orchestration's own assignment step then independently
reproduces the identical split (same formula), so nothing about the real pipeline is bypassed or
faked.

Injected events are added as a *second* file under each `bronze/dt=.../` partition
(`demo_clean_winner_boost.jsonl.gz` / `demo_guardrail_breach.jsonl.gz`) rather than modifying the
simulator's original output - Athena reads every file under a partition, so this coexists cleanly
and `data-foundation/event_simulator`'s output stays untouched.

## Verified output (actual run)

```
Result: Clean winner
  state: analyzed
  control: n=75 mean=4.6909  treatment: n=60 mean=34.5622
  lift: 636.79%  p_value: 0  significant: True
  guardrail_status: sessions_7d ok
  grounding_check_passed: True

Result: Guardrail auto-stop
  state: analyzed
  stop_reason: guardrail_breach: ggr_usd_7d=-100.9127 vs min threshold 0.0
  control: n=79 mean=2.5858  treatment: n=77 mean=-100.9127
  grounding_check_passed: True

Result: SRM violation
  state: stopped_early
  stop_reason: srm_violation: p_value=0.001702 chi2=9.8462 (threshold 0.01)
  (never reached monitoring/analysis/readout - correct: SRM hard-fail skips them)
```

Two real bugs were caught and fixed while getting a clean run here, both instructive:
- The Bedrock grounding-check regex split scientific notation (`1e-06`, a very common p-value
  format for a strongly significant result) into `1` and `-06`, false-flagging the latter as an
  invented number. Fixed by adding an optional exponent group to the number regex.
- Injected demo events initially used one shared `device_id` string per scenario across every
  treatment player - which then falsely lit up `arbitrage_ring_check.sql` (looks exactly like a
  device shared across dozens of "different" accounts). Fixed by deriving a per-player device_id.

## Cleaning up demo data

Demo experiments are ordinary rows in the `aurora-games-experiments` table; delete them the same
way as any other experiment. The injected bronze files can be removed with:

```bash
aws s3 rm s3://<bucket>/bronze/ --recursive --exclude "*" --include "*demo_clean_winner_boost*" --include "*demo_guardrail_breach*"
```

then rerun `data-foundation/lake/build_lake.py` and `feature_registry/build_feature_registry.py`
to restore the lake to its pre-demo state.
