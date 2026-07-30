# What I Got Wrong First

This project is not only a catalogue of final architecture decisions. These
are six cases where a test or operational observation changed the design and
how that lesson maps back to the original business problems.

## 1. A visible row filter did not prove tenant isolation

**I first assumed:** creating one Lake Formation row-level Data Filter per
client site was enough to make the shared Gold table tenant-safe.

**The implementation showed:** new Glue tables receive an
`IAM_ALLOWED_PRINCIPALS` backward-compatibility grant. If it remains, access can
defer to IAM and silently make the separately configured row filter a no-op.
Direct S3 `GetObject` permission is a second bypass path because it reads the
underlying Parquet without going through Lake Formation.

**I learned:** the intended query path can pass while the security boundary is
still bypassable. A configured control is not evidence that the control is
enforced.

**I changed:** setup revokes the compatibility grant on the filtered table,
registers its S3 prefix with Lake Formation, and gives analyst roles no direct
data-object access. Verification assumes every site role and proves both
directions: Athena returns only that site's rows, while direct `GetObject` is
denied.

**Business meaning:** a B2B tenant boundary is real only when the bypass path
fails too. Otherwise every dashboard, assistant, or future BI tool rests on a
decorative isolation claim.

## 2. A security control can fail by being too aggressive

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

## 3. Lexical relevance is not semantic relevance

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

## 4. More signals can make a classifier worse

**I first assumed:** a "topic ambiguity" signal would improve escalation.

**The test showed:** it duplicated other evidence and made ordinary questions
look uncertain without separating true engineering escalations.

**I learned:** a named feature is not valuable because it sounds plausible. It
must change decisions on representative cases.

**I changed:** the redundant signal was removed, and clarification remains
ahead of escalation in the decision order.

**Business meaning:** a question that only needs "sandbox or production?"
should not consume an engineer ticket.

## 5. A rolling baseline can absorb an ongoing incident

**I first assumed:** if an EWMA detector fired on the first bad day, it would
keep firing while the metric stayed low.

**The test showed:** in the scripted `site_b` incident, 2026-06-10 fired with
DAU 91 versus an EWMA baseline of 204 (about 3.9 standard deviations). The same
incident did not fire on 2026-06-12: two depressed days had entered the
trailing window, pulling the baseline down and widening the computed standard
deviation.

**I learned:** onset detection and persistent-incident state are different
problems. Re-alerting forever is not automatically better.

**I changed:** the project describes the detector as an onset signal, preserves
the evidence window and thresholds in each alert, and routes the first alert
into investigation rather than making repeated alerts the incident state.

**Business meaning:** the goal is to shorten time-to-discovery and start a
useful investigation, not maximize alert count.

## 6. A prompt request is not an enforcement boundary

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
