# Operations Runbook

Every alarm in `AuroraGamesObservabilityStack` publishes to one topic,
`aurora-games-ops-alerts`. This page says what each one means and what to do about it. An alarm
without a documented response is a notification, not an alert.

---

## Alarm responses

### `*Errors` — a Lambda threw an unhandled exception

**Means:** at least one invocation failed in a 5-minute window. Which function tells you a lot:

| Function | Likely cause |
|---|---|
| `AnomalyDetector` / `ArbitrageDetector` | Athena query failure — usually a Lake Formation permission or a table that was rebuilt while a query was in flight |
| `FirstLookReport` | An alert arrived that it could not process, or Athena/Bedrock failed. Check the invocation DLQ |
| `AskAnswer` / `SupportChat` | Bedrock throttling, or a malformed request |

**Do:**
1. `aws logs tail /aws/lambda/<function> --since 30m` — the exception and the failing SQL are logged.
2. If it is `AccessDeniedException` on Athena or Glue, go to
   [Lake Formation permissions](#lake-formation-access-denied-after-adding-a-table-or-a-role).
3. If it is a transient Bedrock throttle, no action — retries cover it. If it persists, the account
   is hitting a model quota.

### `*Throttles` — a Lambda hit a concurrency limit

**Means:** invocations were rejected, not just slow. At this project's volume this should never fire;
if it does, something is invoking in a loop.

**Do:** find the invoker before raising the limit. A retry storm answered with more concurrency gets
more expensive, not more correct.

### `ExperimentLifecycleFailures` — a Step Functions execution failed

**Means:** an experiment may be mid-flight with no readout and no explicit stop, so it is neither
running nor concluded.

**Do:**
1. `aws stepfunctions list-executions --state-machine-arn <arn> --status-filter FAILED`
2. `aws stepfunctions get-execution-history --execution-arn <arn>` — the failing state is named.
3. The lifecycle is safe to re-run for the same experiment: assignment is a deterministic hash, so a
   repeat produces the identical split rather than re-randomising participants.

### `Dlq*` — a dead letter queue is non-empty

**Means:** an alert failed and was **given up on**. This is the only alarm here that indicates
already-lost work rather than a live problem.

Two queues, two different failures:

| Queue | Meaning |
|---|---|
| `...-subscription-dlq` | SNS could not deliver to the Lambda at all |
| `...-invocation-dlq` | Delivered fine, then the function threw through all retries |

**Do:**
1. `aws sqs receive-message --queue-url <url> --max-number-of-messages 10` — the original alert is
   intact in the body.
2. Fix the cause, then replay by invoking `FirstLookReport` directly with the same payload.
3. Purge the queue only after replaying — an empty DLQ is indistinguishable from one you forgot.

### `MonthlyCostBudget` — forecast or actual spend over $5

**Means:** at a steady state under $0.10/month, this is not gradual drift. Something hourly-billed is
running.

**Do, in order of likelihood:**
```bash
aws kinesis list-streams
```
```bash
aws ec2 describe-nat-gateways --filter "Name=state,Values=available"
```
```bash
aws rds describe-db-instances
```
The streaming stack is the usual suspect — it bills ~$14/shard-month and is the only resource in
this project designed to be temporary. It should never be present outside a demo:
```bash
cd infra && cdk destroy AuroraGamesStreamingStack -c enable_streaming=true --force
```
Then **verify by listing, not by the destroy exit code** — see
[teardown](#teardown-and-verifying-it).

---

## Failure modes and their blast radius

| Failure | Effect | Recovery | Data loss |
|---|---|---|---|
| Lake rebuild fails midway | Gold table empty until re-run — `build_lake.py` deletes before writing and there is no atomic swap | Re-run `build_lake.py`; it converges | None (Bronze is the source) |
| Detector Lambda fails | That day's check is skipped | Re-run with an explicit `{client_site_id, as_of_date}` — the same path the demos use, so it is continuously exercised | None |
| `FirstLookReport` fails | No auto-report for that alert; the SNS alert itself still went out | Replay from the DLQ | None |
| Step Functions execution fails | Experiment stuck between states | Re-run the lifecycle | None |
| Bedrock unavailable | Module 2 readouts lose their narrative section, Modules 3/4 return errors | Wait; Module 2's readout still renders all code-generated sections | None |
| Athena workgroup limit hit | Query cancelled at the 1 GB scan cap | Intended behaviour — investigate the query, don't raise the cap reflexively | None |

**The pattern worth noticing:** no failure mode above loses data, because Bronze is immutable and
every derived table is rebuilt from it. That property is what makes "just re-run it" a legitimate
first response rather than a hope.

---

## Common tasks

### Lake Formation: `AccessDenied` after adding a table or a role

The recurring gotcha in this project. Two distinct causes:

**A new table is not visible to a Lambda.** Every new Glue table is auto-granted to
`IAM_ALLOWED_PRINCIPALS`, which defers to IAM — but a role without explicit Lake Formation grants
still gets denied on a table where that grant has been revoked. Grant explicitly:
```bash
aws lakeformation grant-permissions --principal DataLakePrincipalIdentifier=<role-arn> --permissions DESCRIBE --resource '{"Database":{"Name":"aurora_games_lake"}}'
```

**Queries against `gold_daily_kpi` fail for a role that used to work.** That prefix is registered
with Lake Formation for the tenant isolation demo, so reads are brokered by Lake Formation rather
than IAM alone. The role needs `lakeformation:GetDataAccess`. Registering a location changes the
access path for **every** consumer of it, not just the ones being constrained.

### Rotating or adding an analyst role

1. Add the site to `CLIENT_SITES` in `infra/infra/governance_stack.py` and deploy.
2. Run `python data-foundation/governance/setup_client_isolation.py` to create the filter and grant.
3. Run `python data-foundation/governance/verify_isolation.py` — it exits non-zero if either the
   Athena path leaks or the direct-S3 path is *not* denied.

Never grant the role S3 access on the data prefixes to "make Athena work". Athena does not need it,
and it silently makes the row filter decorative.

### Teardown, and verifying it

```bash
cd infra && cdk destroy --all
```
Then verify by listing resources, because a destroy that reports success while a resource lingers is
the failure that costs money for weeks:
```bash
aws kinesis list-streams
```
```bash
aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE
```

---

## What is not covered

Named rather than left as an implied promise:

- **No synthetic canary.** Nothing proves the APIs still answer *correctly* — only that they are not
  erroring. A wrong-but-successful answer raises no alarm.
- **No data freshness alarm.** If the lake stopped being rebuilt, the detectors would keep passing
  on stale data and nothing would say so.
- **No on-call rotation or paging.** The topic has no subscribers by default; add one before
  treating any of this as monitored.
- **SLOs are stated but mostly not instrumented.** [threat-model.md](threat-model.md) defines the
  targets; the alarms detect failure rather than degradation, so a system that is slow-but-working
  raises nothing.
- **No CloudTrail.** No record of AWS control-plane actions - who assumed a role, changed a policy,
  or deleted a stack. Application-level decision logging is thorough; this is the layer below it.
