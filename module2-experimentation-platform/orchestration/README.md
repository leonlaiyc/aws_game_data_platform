# Experiment Orchestration

Step Functions state machine (`aurora-games-experiment-lifecycle`) supports two
operation modes after assignment and its preflight balance check:

```
                               +-- replay: historical monitoring Map --+
assignment -> balance check --+                                      +-> analysis -> readout
                               +-- live: Wait until planned end -------+

EventBridge hourly -> actual exposure SRM + guardrails
                   -> breach: allocation_enabled=false -> stop execution -> SNS
```

## Steps

1. **Assignment** (`lambda/assignment`) - deterministic hash-based split (`md5(experiment_id:seed:player_id)`)
   over the audience's eligible players (site-level, active in the last 7 days - see the
   simplification note in `feature_registry/FEATURES.md`). Writes
   `gold_experiment_assignments/<experiment_id>.jsonl`.
2. **SRM check** (`lambda/srm_check`) - chi-square goodness-of-fit test, 2-variant only. Pure
   computation (no AWS calls); p-value via `erfc` since chi-square at df=1 is exactly the square
   of a standard normal. `p_value < 0.01` hard-fails the experiment (`stopped_early`,
   `stop_reason` prefixed `srm_violation:`) - stricter than the usual 0.05 since this check runs
   on every experiment and a false positive kills a real one.
3. **Monitoring** (`lambda/monitoring_check`) - a Step Functions `Map` state replays each day in
   the experiment's window (the demo's dates are historical, so "waiting" is instant); the *same*
   Lambda is also wired to an EventBridge hourly schedule (`{"scheduled": true}` input) that scans
   every currently-running experiment against today's real date - that's the actual always-on
   production path. In live mode it queries immutable product exposure events,
   waits for at least 100 exposures before applying the `p < 0.01` SRM rule,
   and joins guardrails to the exposed treatment cohort rather than the
   eligibility assignment. On a breach it atomically sets
   `allocation_enabled=false`, records structured monitoring status, stops the
   waiting execution, and publishes SNS.
4. **Analysis** (`lambda/analysis`) - reads **only** `gold_player_features`
   joined against assignments in replay mode or actual exposures in live mode
   (never recomputes aggregates from Bronze/Silver). Two-sample z-test
   (normal CDF via `math.erf`) for the OEC metric's significance, plus guardrail status at the
   same analysis date (the first breach date if monitoring caught one, else the last planned day).
   Also emits `flags`: deterministic, rule-based caveats computed alongside the stats -
   `SAMPLE_IMBALANCE` (group sizes notably unequal even though SRM passed the *designed*-ratio
   test), `SMALL_SAMPLE` (either arm below 100), `SUSPICIOUSLY_LARGE_EFFECT` (|lift| > 100% - in a
   real setting this signals a data/setup issue more often than a genuine effect), `WIDE_UNCERTAINTY`
   (the 95% CI half-width exceeds the point estimate itself, reusing the z-test's already-computed
   standard error), and `GUARDRAIL_NEAR_THRESHOLD` (passed, but within 1 standard error of
   breaching). Thresholds are simple, documented constants (see the module docstring) rather than
   values calibrated from historical variance, which this project's scale doesn't have.
5. **Readout** (`lambda/readout`) - assembles a 5-section report from two different sources, not
   one LLM call writing the whole thing. "Key Stats", "Guardrail Status", and **"Caveats"** (the
   raw `flags`, verbatim) are rendered directly from `analysis_result` by our own code - Bedrock
   never sees these as something to reproduce, so there's no way for a figure to be wrong there.
   Bedrock (Nova Lite) only writes "Conclusion" and "Next-round Recommendation" - explicitly
   instructed to give a qualitative verdict in words, not to restate any figure, **and required to
   address every flag present** (it may only choose how to phrase each caveat, not whether to
   mention it) - returned as structured JSON (`{"conclusion": ..., "recommendation": ...}`) rather
   than free-form prose. A regex-based grounding check still runs as a secondary safety net over
   just those two LLM-authored fields: **any numeric token is rejected**, even if it correctly
   repeats an input value, so numeric ownership stays mechanically unambiguous. Rejected prose is
   withheld and recorded in `readout.grounding_check_passed`. If Bedrock is unavailable, the same
   deterministic-only fallback is persisted instead of failing the completed analysis. A separate,
   cheap coverage check
   (`readout.coverage_check`) asserts every flag actually made it into the prompt
   (`flags_in_prompt` - a self-check against our own code silently dropping one) and that the
   Conclusion is long enough to plausibly have addressed all of them
   (`conclusion_non_trivial` - a coarse word-count heuristic, not literal keyword matching, which
   would be fragile against paraphrasing). A failed coverage contract also withholds the narrative;
   the check is not merely an annotation.

   This is a stronger guarantee than checking a fully-LLM-written report after the fact (the
   original design): a number can't be hallucinated in the sections that matter most because the
   LLM never writes them, and a caveat can't be silently omitted because the LLM is required to
   address it rather than left to judge whether it's worth mentioning. Division of labor:
   deterministic code owns everything requiring correctness and auditability (the numbers, the
   significance decision, the caveat triggers); the LLM is confined to what it's reliable at -
   synthesis and audience-appropriate communication. This isn't distrust of the LLM - it's placing
   it where it's reliable. An assistant that also judges and reports numbers is one nobody dares
   use in a high-trust setting, because one hallucination voids the whole report; an assistant
   confined to trustworthy language synthesis is one that actually gets used daily.

`mark_state` is a small shared Lambda for the two transitions that need nothing but a conditional
DynamoDB update: SRM hard-fail and natural completion after the monitoring loop finishes clean.

## Starting an execution

`POST /experiments/{id}/start` (see `registry/README.md`) with
`{"duration_days": 7}` starts live mode and waits without running compute.
`{"mode":"replay","as_of_date":"2026-05-10","duration_days":10}` keeps the
fast historical demo. The registry API computes the replay dates and calls `StartExecution` directly
(no EventBridge hop for this trigger - see `registry_stack.py` for why the state machine ARN is a
fixed name rather than a CDK cross-stack reference).

## A Lake Formation gotcha worth knowing

Even with `AdministratorAccess`-equivalent IAM policies granting `glue:GetPartition` etc., Lambda
executions failed with `Insufficient permissions ... glue:GetPartition ... on resource: catalog`.
This AWS account has **Lake Formation** governing the Glue Data Catalog; new tables do inherit an
`IAM_ALLOWED_PRINCIPALS` grant by default, but no principal could evaluate against it because the
account had zero registered **Data Lake Administrators**. Fix:

```bash
aws lakeformation put-data-lake-settings --data-lake-settings '{"DataLakeAdmins": [...]}'
aws lakeformation grant-permissions --principal '{"DataLakePrincipalIdentifier": "<lambda-role-arn>"}' \
  --resource '{"Database": {"Name": "aurora_games_lake"}}' --permissions DESCRIBE
aws lakeformation grant-permissions --principal '{"DataLakePrincipalIdentifier": "<lambda-role-arn>"}' \
  --resource '{"Table": {"DatabaseName": "aurora_games_lake", "TableWildcard": {}}}' --permissions SELECT DESCRIBE
```

Done once per new Lambda role that queries Athena (`assignment`, `monitoring_check`, `analysis`
here) - IAM policies alone aren't sufficient in an account where Lake Formation is active.

## Verified end to end

A clean-winner run (2026-05-15, 10-day window, guardrail threshold set impossibly loose so it
never breaches): 319 players split 159/160 (SRM p=0.955), all 10 monitoring days clean, analysis
and a grounded Bedrock readout completed, final state `analyzed`. SRM-fail and guardrail-breach
paths are exercised by `demo/` (see that module's README).
