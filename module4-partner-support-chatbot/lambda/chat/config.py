"""Tunable parameters for the fallback classifier.

These are deliberately in one named, documented place rather than inline magic
numbers, because in production **these are the knobs you actually calibrate**.
Every classification decision is logged to the audit track together with the
scores that produced it and the thresholds in force at the time, so the values
below can be tuned against real logged traffic rather than guessed at. That
feedback loop is the point; the specific starting values are not sacred.

How they would be calibrated for real: collect a held-out set of real partner
questions, label the correct category for each, then sweep DOMAIN_RELEVANCE_MIN
to trade off "wrongly told a partner their real question is out of scope"
(threshold too high) against "tried to answer a question about the weather"
(threshold too low). The first error is far more damaging to a partner
relationship, so the starting value below is deliberately permissive.
"""

# --- OUT OF SCOPE ------------------------------------------------------------
# Fraction of the question's content words that must also appear in the
# knowledge base's vocabulary for the question to count as in-domain.
#
# This lexical overlap score is a deterministic stand-in for the retrieval
# relevance score a RAG system would use. This module deliberately has no
# vector store (the corpus fits in-context), so relevance is computed in code
# instead - see README.md for why that trade was made and where it breaks down.
DOMAIN_RELEVANCE_MIN = 0.34

# A question must ALSO contain at least one of these anchor terms. Overlap ratio
# alone is not enough, and the failing case that forced this is instructive:
# "Who won the football match last night?" scored 0.40 - above threshold -
# purely because "match" also appears in the knowledge base in "your totals do
# not match". Incidental collisions on ordinary English words are exactly what
# a bag-of-words score cannot distinguish from real topical relevance.
#
# The anchor list is the deterministic stand-in for what an embedding model
# would give you for free: a notion of *aboutness* rather than word presence.
# It is curated and therefore has an obvious maintenance cost - every new
# knowledge base topic needs its anchors added, and a partner using unanticipated
# vocabulary gets wrongly refused. That cost is the honest price of not running
# a vector store, and it is the first thing that would flip if the corpus grew.
DOMAIN_ANCHOR_TERMS = {
    # authentication
    "authenticate", "authentication", "auth", "oauth", "token", "tokens", "bearer",
    "credentials", "credential", "secret", "unauthorized", "401", "403",
    "environment_mismatch", "mismatch", "certification", "certified",
    # environments
    "sandbox", "production", "environment", "environments", "staging",
    # webhooks
    "webhook", "webhooks", "signature", "signatures", "hmac", "sha256", "payload",
    "retry", "retries", "idempotent", "event_id", "endpoint", "endpoints",
    # settlement
    "settlement", "settle", "settled", "reconcile", "reconciliation", "round_id",
    # game-provider inbound integration
    "launch", "launch_token", "wallet", "balance", "bet", "win", "cancel",
    "rollback", "round", "provider_transaction_id", "idempotency",
    "idempotency_conflict", "game_not_enabled", "currency", "currencies",
    "manifest", "rtp", "jackpot", "player", "players",
    # platform
    "integration", "partner", "partners", "api", "apis", "portal", "maintenance",
    "release", "releases", "deprecated", "deprecation", "version",
}

# --- CLARIFICATION NEEDED ----------------------------------------------------
# Minimum number of recognised domain terms for an in-domain question to count
# as *specific* rather than merely on-topic. A bare "webhook?" scores a perfect
# relevance ratio of 1.0 while conveying almost nothing, so ratio alone can't
# separate "on topic and answerable" from "on topic and far too vague". Below
# this count the question is in-domain but underspecified -> ask, don't guess.
SPECIFIC_TERM_COUNT_MIN = 2

# Terms whose correct answer differs by environment. A question containing one
# of these but naming no environment is underspecified: answering it would mean
# picking an environment on the partner's behalf and being wrong ~half the time.
ENVIRONMENT_SENSITIVE_TERMS = {
    "url", "urls", "endpoint", "endpoints", "credentials", "credential",
    "secret", "token", "base", "host",
}

ENVIRONMENT_TERMS = {"sandbox", "production", "prod", "staging", "test", "live"}

# NOTE - a heuristic that was built, measured, and deliberately removed:
# "topic ambiguity", firing CLARIFICATION when the top two knowledge base
# documents scored within a small margin of each other. Local testing showed it
# misfiring on 3 of 7 representative questions, including plainly answerable
# ones ("When does sandbox reset?"). The reason is structural rather than a bad
# margin value: these documents legitimately share vocabulary - the FAQ and the
# maintenance calendar both discuss sandbox resets - so a near-tie is the normal
# case, not evidence of ambiguity. A lexical score cannot distinguish "two
# documents cover this topic consistently" from "this question is ambiguous",
# and no threshold fixes that. Retained here as a note because knowing why a
# signal was rejected is worth more than the signal would have been.

# --- Acknowledgment selection (code-owned, not model-owned) ------------------
# Presence of any of these switches the acknowledgment copy from
# "information request" to "problem report".
ERROR_REPORT_TERMS = {
    "error", "fail", "failing", "failed", "failure", "broken", "break",
    "not", "cannot", "cant", "wrong", "issue", "problem", "stopped",
    "unauthorized", "mismatch", "missing", "disappeared", "duplicate",
}

# --- Output validation -------------------------------------------------------
# Patterns that must never appear in a response shown to an external partner.
# These match this knowledge base's internal identifiers: document IDs like
# "AG-INT-001", section markers like "§2.3", and raw filenames.
LEAKAGE_PATTERNS = [
    r"AG-[A-Z]{3}-\d{3}",     # internal document IDs
    r"§\s*\d+(\.\d+)*",        # section markers
    r"\b\w+\.md\b",            # source filenames
    r"Document ID",
]

# Phrases that break the illusion that the assistant simply *knows* things, by
# narrating its own retrieval process at the partner ("the reference material
# does not provide..."). The prompt already forbids these; observed model output
# showed it saying them anyway on escalation, which is exactly why this is
# enforced in code rather than trusted to the prompt. Matching text is dropped
# from answer_body - on escalation the closing copy already says everything the
# partner needs, more gracefully.
META_REFERENCE_PATTERNS = [
    r"reference material",
    r"(context|documentation|material|information) (provided|given|available)",
    r"provided (context|documentation|material)",
    r"does not (provide|contain|include|specify|mention|cover)",
    r"(isn't|is not) (covered|specified|mentioned|available)",
    r"based on the (context|material)",
]
