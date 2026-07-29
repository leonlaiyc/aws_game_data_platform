# Module 4 — Partner Integration Support Chatbot

## Pain Point

Aurora Games' integration engineers spend a large share of their week answering the same partner
questions — why a webhook signature fails, which environment a credential belongs to, when sandbox
resets. Each one is individually cheap and collectively expensive, and the questions that genuinely
need an engineer get queued behind the ones that don't.

A bot that answers the easy ones is straightforward. The hard part, and the actual subject of this
module, is **the bot knowing when not to answer** — and being unable to embarrass the company when
it does.

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

| # | Category | Trigger (all deterministic) | Escalates? |
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

This project has no vector store anywhere, by design. The corpus is four documents and fits
in-context in full, so "retrieval relevance" is replaced by two deterministic checks in
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
partner using unanticipated vocabulary gets wrongly refused. At four documents that is a good
trade. It is the first thing that flips if the corpus grows.

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
  gets at most a neutral *"based on Aurora Games' official integration documentation"*. Exposing the
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
   Aurora Games Partner Integration Guide (Document ID: AG-INT-001)."

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
```

Shows all four categories firing with the triggering signal annotated, the first-turn-only
greeting, and the leakage guard. Verified output: **8/8 checks passed** against the deployed stack.

## Known limitations

Stated plainly rather than omitted:

- **Session tracking is in-memory**, so the first-turn greeting rule doesn't survive a cold start or
  span concurrent containers. Production needs DynamoDB with a TTL — the same pattern
  [Module 1's streaming aggregator](../module1-anomaly-detection/streaming/) already uses.
- **Operator identity is matched by IAM role-name convention**, which is a demo simplification: a
  role name is not a security boundary once anyone can create a role with a matching name. A real
  deployment would carry the entitlement in a verified IdP claim.
- **The whole corpus is sent on every request** (~7,800 characters). Fine at four documents, and the
  reason no vector store is needed; it is also the hard ceiling on how far this design scales.
- **No conversation history.** Each request is independent, so a partner answering the clarification
  question has to restate their original question. Multi-turn context is the obvious next increment.
