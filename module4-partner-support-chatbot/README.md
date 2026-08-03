# Module 4 — Partner Integration Support Chatbot

Status: **operationally verified PoC** as of 2026-07-29. Durable session state,
operator-only partner notifications, credential-like content rejection,
durable tickets, and account-local delivery all passed against AWS. The
identity-derived two-audience corpus described below is implemented and tested
locally, but has not been deployed as part of this change.

## Pain Point

LEON Game Data Platform's integration engineers spend a large share of their week answering the same partner
questions — why a webhook signature fails, which environment a credential belongs to, when sandbox
resets. Each one is individually cheap and collectively expensive, and the questions that genuinely
need an engineer get queued behind the ones that don't.

There are two different integration directions: game providers connect launch
and wallet/round APIs into LEON Game Data Platform, while 2C client operators consume
LEON Game Data Platform authentication, webhook, settlement, release, and maintenance
interfaces. Their documentation is deliberately separate.

A bot that answers the easy ones is straightforward. The hard part, and the actual subject of this
module, is **the bot knowing when not to answer** — and being unable to embarrass the company when
it does.

## Where RAG appears

At this corpus size, the implemented path is a **small-corpus RAG-style
pipeline**: IAM identity selects the provider or operator corpus, deterministic
relevance checks decide whether the question belongs, the selected corpus is
placed into the model context, Bedrock generates a grounded answer, and code
validates or escalates the result. It does not pretend that a vector store is
already present. Production onboarding would first replace the simulated files
with official, versioned, access-tagged partner documents; chunking, vector
retrieval, or a managed knowledge base becomes justified when that corpus no
longer fits the controlled full-context approach.

## Two rules, applied everywhere

**1. Three of the four refusal decisions are made before the model is consulted at all.**
Guardrails intervention, domain relevance and underspecification are computed in code or reported
by a service — the model is never asked "is this user being abusive?" or "is this on topic?",
which are the judgements an LLM is least reliable at and least auditable for.

The fourth, `ESCALATION`, *does* depend on the model: it reports `context_sufficient` about the
context it was given, and that boolean decides answer-versus-escalate. That is a deliberate
division — judging whether a corpus covers a question is a reading-comprehension task, which is
what the model is actually good at — but it is worth stating plainly rather than claiming code
decides everything. If the model wrongly reports sufficiency, the answer is wrong; what code still
guarantees is that the *response structure* and the *absence of internal identifiers* hold either
way.

**2. The shape of the reply is code's, not the model's.** The response is assembled from five slots
and the model authors exactly one of them.

## The four categories

| # | Category | Trigger | Escalates? |
|---|---|---|---|
| 1 | `BLOCKED_CONTENT` | Bedrock Guardrails intervened on the raw question | No |
| 2 | `OUT_OF_SCOPE` | Lexical domain relevance below threshold, or no domain anchor term | No — not a support issue |
| 3 | `CLARIFICATION_NEEDED` | In-domain but underspecified | No — resolves without human load |
| 4 | `ESCALATION` | In-domain and specific, but the corpus doesn't cover it | Yes, with a ticket |

Default when none fire: answer normally.

**The order is the design.** Clarification deliberately precedes escalation: a question that only
needs "sandbox or production?" must never consume an engineer's time, and questions like that are
the bulk of the load this module exists to remove. Out-of-scope deliberately does *not* escalate —
someone asking about the weather doesn't have a support issue, and ticketing it would train the
queue to be noise.

An escalation ticket is not decorative copy. Before the API returns its `AGS-...` reference, the
Lambda conditionally writes an `OPEN` work item to the on-demand
`aurora-games-support-tickets` DynamoDB table. If that write fails, the invocation fails instead of
promising a ticket that no support engineer can find. The ticket stores the partner question and
routing reason; raw model output and the full corpus remain only in the operator audit log.

First-turn state is also durable: `aurora-games-support-sessions` uses an
atomic conditional write so cold starts and concurrent Lambda containers agree
on whether a greeting has already been shown. The record expires after 24
hours; it stores no conversation body. Session keys are namespaced by partner
audience so the two integration directions cannot collide.

The caller cannot select an audience in the request body. Exact IAM role
mapping selects `game_provider`, `client_operator`, or the internal operator
view; unknown identities fail closed. Only that audience's files are scored
and passed to the model. The two account-local PoC roles add no hourly charge;
production still needs per-partner federation and tenant claims.

Cost control is enforced before Guardrails or model inference: an atomic
counter in the existing session table allows at most 50 valid requests per UTC
day for each identity-derived audience. Questions are capped at 1,000
characters (one Guardrails text unit), and excess traffic receives HTTP 429.
This complements the API's per-second throttle with a daily spend-volume
boundary and adds no table or always-on worker. The stage itself is limited to
0.1 requests/second with a burst of 2 because a human support PoC does not need
machine-rate throughput; this also bounds invalid requests that never reach
the daily paid-path counter.

Operational notifications are a separate operator-only API:
`POST /notifications` accepts a structured `NEW_GAME` or `MAINTENANCE`
message, validates site/game identifiers and timestamp, rejects
credential-like material, and publishes to
`aurora-games-partner-notifications`. The default stack subscribes only an
account-local SQS audit queue. It does not contact a partner until an explicit
recipient and opt-in workflow are approved.

### Category 1 runs first, via ApplyGuardrail rather than the model call

Guardrails is evaluated on the raw question through the standalone **`ApplyGuardrail`** API, which
checks content against a guardrail *without* invoking a model.

**Gotcha:** the natural way to attach Guardrails is `converse`'s `guardrailConfig`, and the natural
cost optimisation is to run cheap checks before paying for inference. Do both and Guardrails
silently becomes the *last* check rather than the first — a prompt-injection attempt contains no
integration vocabulary, so the scope check rejects it first and it gets recorded as `OUT_OF_SCOPE`.
The partner sees a sensible refusal either way; the audit trail files a security event as a topic
mismatch, where nobody will ever alert on it. `ApplyGuardrail` gives the correct order and the cost
saving at the same time.

### How relevance is scored without a vector store

This project has no vector store anywhere, by design. Each identity-scoped
corpus is small enough to fit in-context, so "retrieval relevance" is replaced by two deterministic checks in
[`config.py`](lambda/chat/config.py):

1. **Overlap ratio** — the fraction of the question's content words that appear in the knowledge
   base's vocabulary, above `DOMAIN_RELEVANCE_MIN`.
2. **At least one domain anchor term** from a curated list.

The second check exists because of a specific failure. *"Who won the football match last night?"*
scored **0.40** — above threshold — purely because "match" also appears in the corpus in *"your
totals do not match"*. Incidental collisions on ordinary English words are exactly what a
bag-of-words score cannot distinguish from real topical relevance, and no threshold value fixes
that. The anchor list is the deterministic stand-in for the notion of *aboutness* that an embedding
model would give you for free.

**This is the honest cost of not running a vector store**, and it is stated plainly rather than
glossed: the anchor list is curated, so every new corpus topic needs its anchors added, and a
partner using unanticipated vocabulary gets wrongly refused. At the current corpus size that is a
good trade. It is the first thing that flips if the corpus grows.

### Why "topic ambiguity" is not a usable clarification signal

An obvious-looking trigger is "the top two documents scored within a small margin, so the question
must be ambiguous". Measured on 7 representative questions it misfired on 3, including plainly
answerable ones like *"When does sandbox reset?"*.

The cause is structural rather than a badly-chosen margin: knowledge base documents legitimately
share vocabulary — the FAQ and the maintenance calendar both discuss sandbox resets — so a near-tie
is the *normal* case, not evidence of ambiguity. No margin value fixes it. Clarification is
triggered on underspecification instead (`SPECIFIC_TERM_COUNT_MIN` and the environment check), and
the rejected signal is documented in `config.py` so it does not get reinvented.

### Thresholds are calibration knobs, not magic numbers

Every threshold lives in [`config.py`](lambda/chat/config.py) with its rationale, and **every
classification decision is logged with the scores that produced it and the thresholds in force at
the time**. That is what makes them tunable against real traffic rather than guessed at. The
starting values are deliberately permissive, because wrongly telling a partner their real question
is out of scope damages the relationship far more than occasionally engaging with an off-topic one.

## The five-slot response

| Slot | Authored by | Notes |
|---|---|---|
| 1. greeting | **code** | First turn of a session only |
| 2. acknowledgment | **code** | Selected by a deterministic problem-report vs information-request signal |
| 3. answer_body | **the model** | The only LLM-authored slot |
| 4. sources | *(suppressed — see below)* | Not a user-facing slot at all |
| 5. closing | **code** | Selected by outcome: normal / clarification / escalation |

All fixed copy lives in [`prompts/fixed_copy_v1.py`](lambda/chat/prompts/fixed_copy_v1.py). Brand
and tone consistency is therefore a structural guarantee — a model cannot drift the tone or invent
a commitment the business hasn't made, because it never writes those words.

Two wording rules are encoded there deliberately:

- **Never say "human", "agent", or "real person."** Escalation refers to the "senior integration
  support team" and "a dedicated integration engineer". Telling a partner they're being handed to a
  human invites them to demand one immediately on every future question.
- **Blocked content is never explained.** Explaining what tripped the filter teaches how to evade it.

### Output validation

Structural checks only, no semantic judgement: required slots present, `answer_body` non-empty when
answering, no non-code-owned text in the code-owned slots, and no internal identifiers in what the
partner sees. On failure the response is replaced wholesale with a pure-template escalation — at
this volume a retry loop isn't worth the latency, and a structurally broken reply must never reach
a partner.

A second sanitiser strips **meta-references** — the model narrating its own sourcing at the partner
("the reference material does not provide..."). The prompt already forbids this; observed output
did it anyway on escalation, which is precisely the argument for enforcing it in code.

## Source provenance: two tracks, and why

This is the sharpest difference from the rest of the project.

- **User-facing:** no document names, IDs, section numbers, or filenames — ever. An external partner
  gets at most a neutral *"based on LEON Game Data Platform's official integration documentation"*. Exposing the
  structure of an internal knowledge base to a vendor is an information leak, and it clutters the
  conversation with detail no partner asked for.
- **Audit track:** full provenance for *every* response — documents loaded, relevance scores,
  thresholds in force, characters of context passed, raw model output, validation results, guardrail
  assessment — logged to CloudWatch and returned only in explicit debug mode.

**Grounding auditability is an operator guarantee, not a user-facing feature.** Note the deliberate
contrast: [Module 2's](../module2-experimentation-platform/) readout cites its numbers visibly and
that stays correct, because its audience is analysts *inside* the company. The suppression here is
specific to an external audience — the same project, opposite correct answers, driven by who is
reading.

### Verified: the guard catching a real leak

From a real run against the deployed stack. Asked to cite its sources, the model **ignored its
instructions** and produced an internal document ID:

```
model output (audit track, never shown to the partner):
  "Webhook signature verification is covered in section 3.2 of the
   LEON Game Data Platform Partner Integration Guide (Document ID: AG-INT-001)."

validation      : passed=False  problems=['internal_identifier_leak']
patterns matched: ['AG-[A-Z]{3}-\d{3}', 'Document ID']
fallback applied: True

internal identifiers reaching the partner: NONE
```

This is the whole argument for code-level enforcement in one screenshot: the prompt said don't, the
model did anyway, and the partner was never exposed to it.

## Prompt management: build vs. managed

Prompts and fixed copy live in a versioned [`prompts/`](lambda/chat/prompts/) directory, so a
wording change is a code change that goes through the same review and deploy path as everything
else. At this scale — two prompt assets, one author — that is the right amount of process.

**Amazon Bedrock Prompt Management** is the managed alternative, and the trigger to adopt it is
organisational rather than technical: when non-engineers (support leads, legal, localisation) need
to edit copy without a pull request, or when prompt variants need A/B testing with versioned
rollback independent of a deployment. Neither applies yet. Same reasoning shape as
[Module 3's Amazon Quick analysis](../module3-analytics-assistant/README.md) — the managed service
is bought for the workflow it enables, not for the capability.

## Running the demo

```bash
python module4-partner-support-chatbot/demo/run_demo.py
python module4-partner-support-chatbot/demo/run_notification_demo.py
```

Shows all four categories firing with the triggering signal annotated, the first-turn-only
greeting, and the leakage guard. The second command publishes one maintenance
notice, verifies SNS-to-SQS delivery, and deletes only its matching audit
message. The deployed chat output passed **8/8 checks** and the notification
path passed API-to-SNS-to-SQS delivery plus matching-message cleanup.

## Known limitations

Every audit record also emits `measurement_event=partner_support_outcome`,
`automation_outcome`, `requires_human`, audience, and whether a model was
invoked. These fields reuse the existing structured CloudWatch log, avoiding
always-on analytics infrastructure or extra custom-metric charges.

Stated plainly rather than omitted:

- **Partner audience is matched by IAM role-name convention**, which is an
  account-local PoC simplification, not per-partner tenant identity. A real
  deployment must carry partner ID and audience in verified federation claims.
- **The selected audience corpus is sent on every model request.** Fine at the
  current document count and the reason no vector store is needed; it is also
  the hard ceiling on how far this design scales.
- **No conversation history.** Each request is independent, so a partner answering the clarification
  question has to restate their original question. DynamoDB currently tracks
  only whether the session has been seen, not its messages. A bounded,
  redacted turn history is the next increment.
- **The ticket table is a minimal write path, not a full case-management system.** It proves the
  escalation is actionable, but there is no status GSI, SLA timer, assignment workflow, or agent UI.
  Those belong in an existing CRM/ITSM integration once the receiving system is chosen.
- **No real partner notification subscriber is installed.** The SQS sink
  proves delivery without external side effects. Production needs explicit
  partner opt-in, per-tenant filters, unsubscribe handling, retry/DLQ policy,
  and an approved channel.
