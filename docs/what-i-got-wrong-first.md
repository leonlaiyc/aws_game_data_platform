# What I Got Wrong First

This project is not only a catalogue of final architecture decisions. These
are five cases where a test or operational observation changed the design and
how that lesson maps back to the original business problems.

## 1. A security control can fail by being too aggressive

**I first assumed:** putting the complete instruction context into the text
sent to Bedrock Guardrails was the safest option.

**The test showed:** the instruction-like system text caused
`PROMPT_ATTACK` to block every normal Module 3 request.

**I learned:** a control's position in the request path matters as much as the
control itself. Security that destroys availability is still a failed design.

**I changed:** Guardrails now evaluates untrusted user text, while trusted
system instructions stay in the later model invocation. The blocked path is
tested independently.

**Business meaning:** an analytics assistant cannot reduce analyst
interruptions if its safety layer rejects legitimate business questions.

## 2. Lexical relevance is not semantic relevance

**I first assumed:** keyword overlap was enough to reject unrelated Module 4
questions cheaply.

**The test showed:** an unrelated football question scored as relevant because
generic words such as "match" also appeared in reconciliation documents.

**I learned:** a cheap heuristic needs domain anchors and calibrated negative
examples, not just a similarity-looking number.

**I changed:** the classifier requires audience-specific domain evidence,
keeps its thresholds in versioned code, and tests unrelated near-collisions.

**Business meaning:** falsely rejecting a real integration question harms a
partner relationship; sending obvious noise to a model wastes money. Both
error directions need explicit tests.

## 3. More signals can make a classifier worse

**I first assumed:** a "topic ambiguity" signal would improve escalation.

**The test showed:** it duplicated other evidence and made ordinary questions
look uncertain without separating true engineering escalations.

**I learned:** a named feature is not valuable because it sounds plausible. It
must change decisions on representative cases.

**I changed:** the redundant signal was removed, and clarification remains
ahead of escalation in the decision order.

**Business meaning:** a question that only needs "sandbox or production?"
should not consume an engineer ticket.

## 4. A rolling baseline can absorb an ongoing incident

**I first assumed:** if an EWMA detector fired on the first bad day, it would
keep firing while the metric stayed low.

**The test showed:** the baseline caught up after repeated low observations, so
later days no longer crossed the same onset threshold.

**I learned:** onset detection and persistent-incident state are different
problems. Re-alerting forever is not automatically better.

**I changed:** the project describes the detector as an onset signal, preserves
the evidence window and thresholds in each alert, and routes the first alert
into investigation rather than making repeated alerts the incident state.

**Business meaning:** the goal is to shorten time-to-discovery and start a
useful investigation, not maximize alert count.

## 5. A prompt request is not an enforcement boundary

**I first assumed:** telling a model not to expose internal source identifiers
would be sufficient for partner-facing answers.

**The test showed:** the model still emitted an internal document identifier.

**I learned:** instructions guide generation; deterministic code must enforce
the external disclosure contract.

**I changed:** Module 4 validates the generated slot, replaces unsafe output
before delivery, keeps full evidence only in the operator audit path, and
tests the attempted leak.

**Business meaning:** the same principle now governs the whole platform:
models may phrase approved qualitative content, while code owns numbers,
identity, routing, and disclosure.
