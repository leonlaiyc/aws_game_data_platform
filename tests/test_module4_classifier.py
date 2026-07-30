"""Unit tests for Module 4's deterministic layer.

Everything tested here decides an outcome *before* the model is consulted, or
constrains what the model's output is allowed to do afterwards. That is the
part worth testing: the model's judgement is not reproducible, but the code
that surrounds it must be.

Includes a regression test for the specific false positive that forced the
anchor-term requirement, so that lesson cannot be quietly undone by a
threshold tweak.
"""
import json
from pathlib import Path

import pytest

from conftest import REPO_ROOT, load_handler  # noqa: E402

CHAT_DIR = REPO_ROOT / "module4-partner-support-chatbot" / "lambda" / "chat"
handler = load_handler(
    "m4_chat_handler", CHAT_DIR,
    env={"GUARDRAIL_ID": "test", "GUARDRAIL_VERSION": "1",
         "SUPPORT_TICKETS_TABLE_NAME": "test-support-tickets",
         "SUPPORT_SESSIONS_TABLE_NAME": "test-support-sessions",
         "AWS_DEFAULT_REGION": "ap-northeast-1"},
)
from config import DOMAIN_RELEVANCE_MIN, SPECIFIC_TERM_COUNT_MIN  # noqa: E402


def classify(question: str) -> str:
    """The deterministic part of the pipeline, up to the model call."""
    relevance = handler._score_relevance(question)
    in_domain = (relevance["overall"] >= DOMAIN_RELEVANCE_MIN
                 and bool(relevance["anchor_terms_matched"]))
    if not in_domain:
        return "OUT_OF_SCOPE"
    return "CLARIFICATION_NEEDED" if handler._clarification_reason(question, relevance) else "TO_MODEL"


@pytest.mark.parametrize("question", [
    "What is a good recipe for carbonara?",
    "What's the weather like today?",
    "Can you recommend a stock to buy?",
])
def test_off_topic_questions_are_out_of_scope(question):
    assert classify(question) == "OUT_OF_SCOPE"


def test_question_with_only_stopwords_fails_closed_as_out_of_scope():
    assert classify("what is this?") == "OUT_OF_SCOPE"


def test_incidental_word_overlap_does_not_count_as_relevance():
    """Regression: "Who won the football match last night?" scored 0.40 -
    above DOMAIN_RELEVANCE_MIN - because "match" appears in the knowledge base
    in "your totals do not match". Ratio alone cannot separate an incidental
    collision on an ordinary English word from real topical relevance, which is
    why an anchor term is also required. Tuning the ratio must not reintroduce
    this."""
    question = "Who won the football match last night?"
    relevance = handler._score_relevance(question)
    assert relevance["overall"] >= DOMAIN_RELEVANCE_MIN, (
        "the premise of this test no longer holds - the question no longer "
        "clears the ratio threshold, so it is not exercising the anchor rule"
    )
    assert relevance["anchor_terms_matched"] == []
    assert classify(question) == "OUT_OF_SCOPE"


@pytest.mark.parametrize("question", [
    "My webhook signature check keeps failing",
    "When does sandbox reset?",
    "Why am I getting 403 environment_mismatch?",
    "How do I rotate the webhook signing secret for production?",
])
def test_in_domain_specific_questions_reach_the_model(question):
    assert classify(question) == "TO_MODEL"


@pytest.mark.parametrize("question", [
    "What is the base URL for settlement?",
    "Which credentials do I use?",
])
def test_environment_sensitive_questions_need_clarification(question):
    """Answering these means picking an environment on the partner's behalf and
    being wrong about half the time."""
    assert classify(question) == "CLARIFICATION_NEEDED"
    reason, _ = handler._clarification_reason(question, handler._score_relevance(question))
    assert reason == "environment_sensitive_term_without_environment"


def test_naming_the_environment_removes_the_need_to_clarify():
    assert classify("What is the base URL for settlement in production?") == "TO_MODEL"


def test_bare_in_domain_term_is_underspecified_not_out_of_scope():
    """"webhook?" scores a perfect ratio while conveying nothing. It is on
    topic - the right response is to ask, not to refuse."""
    assert classify("webhook?") == "CLARIFICATION_NEEDED"
    relevance = handler._score_relevance("webhook?")
    assert relevance["matched_terms"] < SPECIFIC_TERM_COUNT_MIN


class TestLeakageGuard:
    @pytest.mark.parametrize("text", [
        "Covered in the Aurora Games Partner Integration Guide (Document ID: AG-INT-001).",
        "See section §3.2 for signature verification.",
        "This is described in integration_guide.md.",
    ])
    def test_internal_identifiers_are_detected(self, text):
        assert handler._detect_leakage(text)

    def test_clean_answer_passes(self):
        assert handler._detect_leakage(
            "Verify the signature against the raw request body, not re-serialized JSON."
        ) == []

    def test_leaking_answer_fails_validation(self):
        slots = {"greeting": None, "acknowledgment": handler.copy.ACKNOWLEDGMENT_INFO_REQUEST,
                 "answer_body": "See AG-INT-001 §1.2.", "closing": handler.copy.CLOSING_NORMAL}
        result = handler._validate(slots, "ANSWERED")
        assert result["passed"] is False
        assert "internal_identifier_leak" in result["problems"]


class TestSlotOwnership:
    def test_model_authored_text_in_a_code_owned_slot_is_rejected(self):
        """Only answer_body may contain text the model wrote. Tone and brand
        consistency are structural, so a closing the model invented must fail
        validation rather than reach a partner."""
        slots = {"greeting": None, "acknowledgment": handler.copy.ACKNOWLEDGMENT_INFO_REQUEST,
                 "answer_body": "Sandbox resets on Sundays.",
                 "closing": "Hope that helps, let me know if you need anything else!!"}
        result = handler._validate(slots, "ANSWERED")
        assert result["passed"] is False
        assert any("non_code_owned_text_in_closing" in p for p in result["problems"])

    def test_blocked_content_requires_the_exact_refusal(self):
        assert handler._validate(
            {"greeting": None, "acknowledgment": None,
             "answer_body": handler.copy.BLOCKED_RESPONSE, "closing": None},
            "BLOCKED_CONTENT")["passed"] is True

        assert handler._validate(
            {"greeting": None, "acknowledgment": None,
             "answer_body": "I can't help because your message was flagged as abusive.",
             "closing": None},
            "BLOCKED_CONTENT")["passed"] is False

    def test_answering_with_an_empty_body_fails(self):
        result = handler._validate(
            {"greeting": None, "acknowledgment": handler.copy.ACKNOWLEDGMENT_INFO_REQUEST,
             "answer_body": "", "closing": handler.copy.CLOSING_NORMAL}, "ANSWERED")
        assert "empty_answer_body_when_answering" in result["problems"]


class TestMetaReferenceStripping:
    @pytest.mark.parametrize("text", [
        "The reference material does not provide information on rotating secrets.",
        "That isn't covered in the documentation provided.",
    ])
    def test_meta_narration_is_dropped(self, text):
        assert handler._strip_meta_references(text) == ""

    def test_a_real_answer_survives(self):
        text = "Tokens are valid for 3600 seconds and there is no refresh flow."
        assert handler._strip_meta_references(text) == text


class TestDebugAuthorisation:
    def _event(self, arn):
        return {"requestContext": {"identity": {"userArn": arn}}}

    def test_partner_cannot_self_authorise_debug(self, monkeypatch):
        monkeypatch.setattr(handler, "OPERATOR_PRINCIPAL_PATTERN", "aurora-games-operator")
        assert handler._debug_authorised(
            self._event("arn:aws:sts::1:assumed-role/some-partner-role/x")) is False

    def test_operator_is_authorised(self, monkeypatch):
        monkeypatch.setattr(handler, "OPERATOR_PRINCIPAL_PATTERN", "aurora-games-operator")
        assert handler._debug_authorised(
            self._event("arn:aws:sts::1:assumed-role/aurora-games-operator/x")) is True

    def test_similar_role_name_is_not_authorised(self, monkeypatch):
        monkeypatch.setattr(handler, "OPERATOR_PRINCIPAL_PATTERN", "aurora-games-operator")
        assert handler._debug_authorised(
            self._event("arn:aws:sts::1:assumed-role/evil-aurora-games-operator/x")) is False

    def test_empty_pattern_authorises_nobody(self, monkeypatch):
        """A blank pattern must not compile to something that matches every
        ARN - the default has to fail closed."""
        monkeypatch.setattr(handler, "OPERATOR_PRINCIPAL_PATTERN", "")
        assert handler._debug_authorised(
            self._event("arn:aws:sts::1:assumed-role/aurora-games-operator/x")) is False


class TestPartnerAudienceIsolation:
    def _event(self, role):
        return {
            "requestContext": {
                "identity": {
                    "userArn": f"arn:aws:sts::1:assumed-role/{role}/session"
                }
            }
        }

    def _configure_roles(self, monkeypatch):
        monkeypatch.setattr(
            handler, "OPERATOR_PRINCIPAL_PATTERN", "aurora-games-operator"
        )
        monkeypatch.setattr(
            handler,
            "GAME_PROVIDER_PRINCIPAL_PATTERN",
            "aurora-games-game-provider-partner",
        )
        monkeypatch.setattr(
            handler,
            "CLIENT_OPERATOR_PRINCIPAL_PATTERN",
            "aurora-games-client-operator-partner",
        )

    def test_exact_identity_selects_answer_corpus(self, monkeypatch):
        self._configure_roles(monkeypatch)
        assert handler._partner_audience(
            self._event("aurora-games-game-provider-partner")
        ) == "game_provider"
        assert handler._partner_audience(
            self._event("aurora-games-client-operator-partner")
        ) == "client_operator"
        assert handler._partner_audience(
            self._event("aurora-games-operator")
        ) == "internal_operator"

    def test_similar_or_unknown_role_fails_closed(self, monkeypatch):
        self._configure_roles(monkeypatch)
        with pytest.raises(handler.PartnerScopeResolutionError):
            handler._partner_audience(
                self._event("evil-aurora-games-game-provider-partner")
            )

    def test_two_partner_directions_cannot_see_each_others_documents(self):
        provider_docs = handler._knowledge_for_audience("game_provider")
        operator_docs = handler._knowledge_for_audience("client_operator")

        assert provider_docs
        assert operator_docs
        assert all(name.startswith("game_provider/") for name in provider_docs)
        assert all(name.startswith("client_operator/") for name in operator_docs)
        assert not set(provider_docs) & set(operator_docs)
        assert "provider_transaction_id" in handler._build_context("game_provider")
        assert "provider_transaction_id" not in handler._build_context(
            "client_operator"
        )


def test_escalation_ticket_is_a_persisted_work_item(monkeypatch):
    class FakeTickets:
        def __init__(self):
            self.calls = []

        def put_item(self, **kwargs):
            self.calls.append(kwargs)

    fake = FakeTickets()
    monkeypatch.setattr(handler, "tickets", fake)
    audit = {
        "session_id": "partner-session",
        "trigger": "model_reported_context_insufficient",
    }

    handler._persist_ticket("AGS-ABC12345", "How do I enable an unsupported flow?", audit)

    assert len(fake.calls) == 1
    request = fake.calls[0]
    assert request["ConditionExpression"] == "attribute_not_exists(ticket_id)"
    assert request["Item"]["ticket_id"] == "AGS-ABC12345"
    assert request["Item"]["status"] == "OPEN"
    assert request["Item"]["question"] == "How do I enable an unsupported flow?"
    assert request["Item"]["final_category"] == "ESCALATION"
    assert request["Item"]["partner_audience"] == "unknown"


def test_session_first_turn_is_durable_across_lambda_containers(monkeypatch):
    class ConditionalCheckFailedException(Exception):
        pass

    class FakeSessions:
        class meta:
            class client:
                class exceptions:
                    pass

        def __init__(self):
            self.seen = set()
            self.refreshes = []

        def put_item(self, Item, **kwargs):
            if Item["session_id"] in self.seen:
                raise ConditionalCheckFailedException()
            self.seen.add(Item["session_id"])

        def update_item(self, **kwargs):
            self.refreshes.append(kwargs)

    FakeSessions.meta.client.exceptions.ConditionalCheckFailedException = (
        ConditionalCheckFailedException
    )
    sessions = FakeSessions()
    monkeypatch.setattr(handler, "sessions", sessions)
    monkeypatch.setattr(handler.time, "time", lambda: 1000)

    assert handler._is_first_turn("partner-123") is True
    assert handler._is_first_turn("partner-123") is False
    assert len(sessions.refreshes) == 1
    assert (
        sessions.refreshes[0]["ExpressionAttributeValues"][":expires_at"]
        == 1000 + handler.SESSION_TTL_SECONDS
    )


def test_daily_cost_quota_is_atomic_and_fails_closed(monkeypatch):
    class ConditionalCheckFailedException(Exception):
        pass

    class FakeSessions:
        class meta:
            class client:
                class exceptions:
                    pass

        def __init__(self):
            self.count = 0

        def update_item(self, **kwargs):
            limit = kwargs["ExpressionAttributeValues"][":request_limit"]
            if self.count >= limit:
                raise ConditionalCheckFailedException()
            self.count += 1

    FakeSessions.meta.client.exceptions.ConditionalCheckFailedException = (
        ConditionalCheckFailedException
    )
    sessions = FakeSessions()
    monkeypatch.setattr(handler, "sessions", sessions)
    monkeypatch.setattr(handler, "DAILY_REQUEST_LIMIT", 2)

    handler._claim_daily_request("game_provider")
    handler._claim_daily_request("game_provider")
    with pytest.raises(handler.DailyRequestLimitExceeded):
        handler._claim_daily_request("game_provider")
    assert sessions.count == 2


@pytest.mark.parametrize("body", [
    {},
    {"question": ""},
    {"question": ["not", "a", "string"]},
    {"question": "x" * 1001},
    {"question": "valid", "session_id": []},
])
def test_invalid_request_shape_is_rejected_before_aws_calls(body, monkeypatch):
    class ShouldNotRun:
        def apply_guardrail(self, **kwargs):
            raise AssertionError("Guardrails must not run for invalid input")

    monkeypatch.setattr(handler, "bedrock", ShouldNotRun())
    response = handler.handler({"body": json.dumps(body)}, None)
    assert response["statusCode"] == 400


def test_valid_request_from_unmapped_identity_is_rejected_before_aws_calls(
    monkeypatch,
):
    class ShouldNotRun:
        def apply_guardrail(self, **kwargs):
            raise AssertionError("Guardrails must not run for an unmapped caller")

    monkeypatch.setattr(handler, "bedrock", ShouldNotRun())
    response = handler.handler(
        {
            "body": json.dumps(
                {"question": "How do I retry a bet?", "session_id": "session-1"}
            ),
            "requestContext": {
                "identity": {
                    "userArn": "arn:aws:sts::1:assumed-role/unknown-partner/x"
                }
            },
        },
        None,
    )
    assert response["statusCode"] == 403


def test_daily_quota_returns_429_before_guardrails(monkeypatch):
    class ShouldNotRun:
        def apply_guardrail(self, **kwargs):
            raise AssertionError("Guardrails must not run after quota rejection")

    monkeypatch.setattr(handler, "bedrock", ShouldNotRun())
    monkeypatch.setattr(
        handler,
        "GAME_PROVIDER_PRINCIPAL_PATTERN",
        "aurora-games-game-provider-partner",
    )
    monkeypatch.setattr(
        handler,
        "_claim_daily_request",
        lambda *_: (_ for _ in ()).throw(handler.DailyRequestLimitExceeded()),
    )
    response = handler.handler(
        {
            "body": json.dumps(
                {"question": "How do I retry a bet?", "session_id": "session-1"}
            ),
            "requestContext": {
                "identity": {
                    "userArn": (
                        "arn:aws:sts::1:assumed-role/"
                        "aurora-games-game-provider-partner/x"
                    )
                }
            },
        },
        None,
    )
    assert response["statusCode"] == 429
