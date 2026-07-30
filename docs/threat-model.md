# Threat Model and Service Levels

Two questions this document exists to answer, neither of which the rest of the docs answers
directly: **who would attack this and would they get anywhere**, and **what does "healthy" mean
numerically**.

Baseline rows below were checked against the deployed account. Controls added on
`codex/acceptance-hardening` were deployed and exercised against AWS on
2026-07-29; remaining production gaps are still stated explicitly.
Where a control is missing it says so, rather than being quietly upgraded to "not applicable".

---

## Part 1 — Threat model

### Scope

**In scope:** the three internet-facing APIs, the multi-tenant lake, the Bedrock spend they can
drive, and the audit trail that would let anyone reconstruct what happened.

**Out of scope:** AWS's own security of the underlying services, and physical/social attacks on the
account owner. Also out of scope: the simulated data itself has no real personal information, so
data-sensitivity classification is deliberately not modelled — a real deployment holding player PII
would need that first, before anything below.

### Who, what they want, and whether they get it

| # | Attacker | What they want | Stopped? | By what |
|---|---|---|---|---|
| 1 | Anonymous internet scanner | A free/open endpoint to use or abuse | **Yes** | All three APIs require SigV4-signed IAM credentials; unsigned requests return 403 (verified) |
| 2 | Partner A's analyst credentials | Partner B's revenue data | **Yes** | Scope derives from the signing identity, not the request. Verified across all 9 caller×site combinations, plus forged `caller_scope` in the body being ignored |
| 3 | A stolen analyst role | The raw Parquet, bypassing the row filter | **Yes** | Analyst roles hold no S3 permission on the data. `verify_isolation.py` attempts the bypass and asserts it is denied |
| 4 | An external partner | The knowledge base's internal structure (doc names, section IDs) | **Yes** | Suppressed in the user-facing response and enforced by a validator, not by the prompt — verified catching the model actually emitting `Document ID: AG-INT-001` |
| 5 | An external partner | The audit track (raw model output, context passed, scores) | **Yes** | Authorised by IAM identity. Previously a `debug` flag in the request body, i.e. self-service |
| 6 | Anyone with prompt-injection skills | Extract the system prompt, or steer the assistant | **Yes** | Bedrock Guardrails `PROMPT_ATTACK`, evaluated on the raw question **before** any other check via `ApplyGuardrail` |
| 7 | **Any authenticated caller** | **Free LLM inference on our bill** | **Partly** | **See below** |
| 8 | **Any authenticated caller** | **Run up the Athena bill** | **Partly** | **See below** |
| 9 | Anyone | Tamper with lake data | **Yes** | No role except the pipeline's own has write access to the data prefixes; S3 public access fully blocked; SSE-AES256 at rest (all verified) |
| 10 | **An insider or a compromised admin** | **Act without leaving a trace** | **No** | **See below** |

### The three that are not fully closed

#### 7 & 8 — Cost as an attack surface

**The finding that made writing this worthwhile.** Authentication answers *who are you*. It says
nothing about *how often*, and every request past the classifier costs Bedrock tokens. An
authenticated partner with a `while` loop is, in effect, using the account as someone else's LLM —
and the same shape of abuse against the analytics API drives Athena scans.

**Mitigated during this exercise:**
- **API Gateway throttling** on all three APIs: Module 2 and Module 3 use
  10 req/s sustained with burst 20; the human-facing Module 4 PoC is locally
  configured at 0.1 req/s with burst 2, plus a 50-request UTC-day quota per
  identity-derived audience before paid AI calls.
  Normal use is unaffected; a loop is shed.
- **Athena per-query scan cap** of 1 GB, which already existed. A runaway query is cancelled rather
  than billed to completion.
- **AWS Budgets** notification at $5, forecast and actual — the backstop that catches whatever the
  specific controls miss.

**Still open, and why:**
- **No per-function reserved concurrency.** This is the correct control and it **cannot be set in
  this account**: the total Lambda concurrency limit is 10 and AWS requires at least 10 to remain
  unreserved, so any reservation is rejected. The practical consequence is that the account-wide
  limit of 10 is the only concurrency ceiling and it is *shared* — a burst against the chatbot can
  starve the detectors and the experiment lifecycle. In an account with a normal limit, reserve
  per-function.
- **No aggregate Athena spend cap.** The per-query cap bounds one query, not a thousand of them.
  Athena workgroups support a workgroup-wide data usage limit; it is configured in the console
  rather than exposed in the API this project deploys with.
- **No WAF.** Rate limiting is per-stage, not per-caller, so one abusive caller consumes the shared
  budget and degrades everyone. Per-principal quotas would need API Gateway usage plans (which are
  API-key based, awkward alongside IAM auth) or AWS WAF rate rules.

#### 10 — No audit trail at the AWS API level

**There is no CloudTrail in this account** (verified: `describe-trails` returns nothing).

Application-level logging is thorough — Module 3 and Module 4 log every classification decision with
the scores and thresholds that produced it. But there is no record of *AWS control-plane* actions:
who assumed a role, who changed an IAM policy, who deleted a stack. For a project whose central
claim is governance, that is the most conspicuous gap in this table.

**Why it is not simply switched on:** it is a live infrastructure change with an ongoing (small) S3
storage cost, and this project's standing rule is that billable additions are a decision, not a
default. A single-region management-event trail is the right shape, and at this account's activity
level the storage would be pennies.

### What this exercise changed

Writing the table is what surfaced 7, 8 and 10 — none of them had come up during six days of
building, and none were in the external review either. The three fixes that came out of it
(throttling on all three APIs, plus documenting the concurrency limit honestly rather than assuming
a reservation was in place) took under an hour.

The general lesson: **enumerate attackers systematically, or you find holes by luck.** The security
issues fixed earlier in this project were found by an external reviewer reading the code. That works,
but it does not scale and it is not repeatable.

---

## Part 2 — Service level objectives

Without these, "is the system healthy?" has no answer. Alarms report *broken*; they cannot report
*degraded*.

These are objectives for a system at this project's scale, not commitments to a customer.

### Detection

| Objective | Target | How it is measured today |
|---|---|---|
| An anomaly present in a published partition is alerted on | Within 24 h of the publication marker | The daily EventBridge schedule reads the explicit build-success marker. **Not currently instrumented** — nothing measures marker age or alert latency |
| Detector runs complete successfully | ≥ 99% of scheduled runs | `AnomalyDetectorErrors` / `ArbitrageDetectorErrors` alarms fire on any failure |
| A fired alert produces a first-look report | ≥ 99%, within 5 min | DLQ depth alarms catch the failures; latency is not measured |

### Query and assistant APIs

| Objective | Target | How it is measured today |
|---|---|---|
| `ask_answer` responds | 95% within 10 s | **Not measured.** API Gateway Latency metric exists; no alarm is set on it |
| `ask_answer` availability | 99% of requests non-5xx | `AskAnswerErrors` alarm catches Lambda exceptions, not 4xx/5xx at the gateway |
| Every `answerable` response is traceable to a query result | **100%, no exceptions** | Structural: numbers are code-rendered from query results and the model never produces figures |
| Cross-tenant leakage | **0, no exceptions** | 9-combination matrix in the Module 3 demo, plus the isolation negative test. Both exit non-zero on failure |

### Experiment lifecycle

| Objective | Target | How it is measured today |
|---|---|---|
| A started experiment reaches a terminal state | 99% | `ExperimentLifecycleFailures` alarm |
| No readout contains an unverifiable number | **100%** | The grounding check rejects: failing prose is dropped and the report falls back to code-rendered sections |
| An experiment breaching a guardrail is stopped | Before the next scheduled check | Guardrail monitoring inside the state machine's Map state |
| Registry cross-tenant access | **0, no exceptions** | Identity-derived tenant scope plus offline negative tests; deployed verification remains pending for this branch |

### Cost

| Objective | Target | How it is measured today |
|---|---|---|
| Steady-state monthly spend | < $2 gross list price | 13 standard alarms account for ~$1.30/month before free allocation; AWS Budgets at $5 (forecast + actual) remains a deliberately loose backstop |
| No hourly-billed resource outlives its demo | 0 tolerance | `run_streaming_demo.sh` verifies by listing; the budget alarm is the backstop if it is bypassed |

### The honest summary of the two columns

The two "no exceptions" objectives — **no cross-tenant leakage** and **no unverifiable number** —
are the ones this project is actually built around, and both are enforced structurally and tested.

Most of the *latency and availability* objectives are **stated but not instrumented**. That is the
real state of things: the alarms detect failure, not degradation. Closing it means percentile
latency alarms on the API Gateway metrics and a freshness check on the lake, neither of which is
built. Stating the targets without measuring them is still worth doing — it is what makes the gap
visible instead of unexamined — but they should not be read as being met.
