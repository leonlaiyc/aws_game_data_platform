"""Every word an external partner sees that is NOT the LLM-authored
answer_body lives here.

Version: v1 (2026-07-28)

This file is the reason brand and tone stay consistent: greeting,
acknowledgment and closing are selected by code from these fixed strings, so a
model can neither drift the tone nor invent a promise the business hasn't made.
The LLM authors exactly one slot (answer_body) and nothing else.

Two deliberate wording rules encoded here:

1. **Never say "human", "agent", or "real person".** Escalation copy refers to
   the "senior integration support team" / "a dedicated integration engineer".
   Telling a partner they're being handed to a human invites them to demand one
   immediately on every future question.
2. **Blocked content is never explained.** The refusal copy does not say what
   tripped the filter, because explaining the boundary teaches how to evade it.
"""

GREETING = (
    "Thanks for contacting LEON Data Platform integration guidance."
)

# Selected by code from a deterministic signal (whether the partner is
# reporting a problem or asking for information), never by the model.
ACKNOWLEDGMENT_ERROR_REPORT = "Sorry you're running into this - let's get it sorted."
ACKNOWLEDGMENT_INFO_REQUEST = "Happy to help with that."

CLOSING_NORMAL = (
    "This answer is based on LEON Data Platform's official integration documentation. "
    "If anything is still unclear, just ask."
)

CLOSING_ESCALATION = (
    "I don't have enough in our integration documentation to answer this confidently, so I've "
    "raised it with our senior integration support team under reference {ticket_id}. "
    "A dedicated integration engineer will follow up with you directly."
)

CLOSING_CLARIFICATION = "Once I know that, I can give you an exact answer."

CLOSING_OUT_OF_SCOPE = (
    "I'm here specifically for LEON Data Platform integration topics - authentication, webhooks, "
    "settlement, environments and releases. Ask me anything in that area."
)

# BLOCKED CONTENT: fixed refusal, deliberately uninformative about the cause.
BLOCKED_RESPONSE = (
    "I'm not able to help with that request. If you have a question about your LEON Data Platform "
    "integration, I'm glad to help with that instead."
)

OUT_OF_SCOPE_BODY = (
    "That's outside what I can help with."
)

# Used when output validation fails - a pure-template response with escalation,
# so a structurally broken reply is never shown to a partner.
VALIDATION_FALLBACK_BODY = (
    "I want to make sure you get an accurate answer on this one."
)
