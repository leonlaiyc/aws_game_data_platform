# Project Constraints and Definition of Done

Lifecycle status: the constraints governed the verified AWS PoC through 2026-08-03. Runtime
resources were intentionally torn down on 2026-08-05; they apply again before any redeployment.
See [AWS PoC teardown evidence](aws-teardown-evidence.md).

These are delivery constraints, not optional recommendations. A feature is not
`Done` unless it satisfies the relevant checks below.

## 1. Paid-account, free-first cost policy

The AWS account uses the **paid plan** so that the project can access services
that are unavailable on the free account plan. Free Tier credits and account
credits may reduce the invoice, but they are never used to justify an
architecture or to describe a service as free.

Before adding or materially changing an AWS service, record all of the
following in `docs/cost-analysis.md`:

1. AWS Region used by the project (`ap-northeast-1`, unless the service is
   global).
2. Official pricing URL and the date it was checked.
3. Billing unit: request, GB-second, state transition, GB stored, shard-hour,
   OCU-hour, RPU-hour, user-month, or another unit.
4. Whether the account's applicable Free Tier allowance covers the demo. Do
   not assume that a new-account offer applies to this paid account.
5. Whether merely deploying the resource creates an idle charge.
6. Whether the resource is part of the default CDK app.
7. The exact teardown command and a read-only command that verifies teardown.
8. A conservative gross list-price estimate without credits.
9. The scale or latency trigger that would justify adopting the service.

If any of those answers is unknown, the service must not enter the default
deployment.

The existing USD 5 monthly budget is a backstop, not authorisation to spend up
to USD 5. Design choices must still minimise gross cost below that threshold.

### Deployment modes

- **Default:** scale-to-zero or request-priced resources only. No Kinesis
  stream, provisioned cluster, managed search capacity, NAT Gateway, or
  licensed BI user.
- **Ephemeral demo:** a metered resource may be deployed only by an explicit
  context flag or wrapper that runs `deploy -> demo -> destroy -> verify`.
- **Scale-up design:** services that are not cost-appropriate now are described
  with measurable adoption triggers; they are not deployed only to add a
  service name to the portfolio.

No automated implementation step may run `cdk deploy`, create a paid AWS
resource, or subscribe an external recipient without an explicit deployment
decision. Local tests and `cdk synth` come first.

Before any deployment, run:

```powershell
python scripts/verify_paid_account_controls.py
```

Deployment is blocked unless the USD 5 budget, both thresholds, at least one
confirmed alert destination, and the absence of leftover project Kinesis
streams are verified from AWS. As of 2026-07-29, the budget thresholds exist
and the Ops SNS topic has one confirmed email subscriber; the gate passes.

## 2. Explainability contract for risk and anomaly alerts

An alert about a player, client site, game, or experiment must explain why it
exists. A bare anomaly score is not a valid output.

Every entity-level risk alert must persist:

- `detector_id` and `detector_version`;
- entity and tenant identifiers;
- evidence window and data publication timestamp;
- stable `reason_code` values;
- actual values, comparison baselines, thresholds, and peer percentiles when
  available;
- the contribution of each signal to any composite review score;
- linked entities used as evidence (with sensitive values hashed);
- a human-readable explanation rendered from those facts by code;
- recommended investigation steps;
- an explicit non-final decision such as `REVIEW_REQUIRED`, never an
  unsupported declaration that a player committed fraud.

Deterministic rules remain the first layer. A novelty detector may be added,
but it must expose the feature deviations that drove the result. An LLM may
rewrite code-owned evidence for readability; it may not decide whether to
alert, invent a reason, or alter a number.

## 3. Operational demo contract

The videos demonstrate operation only. Business context, architecture, and
service-selection rationale belong in the accompanying presentation.

Every demoable feature must have:

1. One documented command.
2. A deterministic scenario identifier or seed.
3. Machine-checked expected results and a non-zero exit code on failure.
4. A prerequisite check that fails before making AWS calls when configuration
   is incomplete.
5. A concise output that identifies the AWS evidence location.
6. A cleanup action and, for metered resources, an independent teardown
   verification.
7. A gross cost note for one run.
8. A target recording time of roughly 1-3 minutes.

Exact commands and recording status are tracked in the team's local delivery
checklist, which is intentionally not published to the repository.

## 4. Feature Definition of Done

A feature may be labelled `Done` only when:

- the implementation and infrastructure are committed;
- offline tests pass in CI;
- the deployed stack matches the committed CDK template;
- the AWS-path demo passes against the deployed version;
- cost and teardown have been checked under the paid-account policy;
- tenant/security boundaries have a negative-path test where applicable;
- operational evidence is persisted and traceable;
- the operation-only demo is deterministic and recordable;
- known production gaps and the scale-up trigger are documented.

Until all conditions hold, use one of:

- `Designed`
- `Locally implemented`
- `Locally verified / deployment pending`
- `Deployed PoC`
- `Operationally verified`
