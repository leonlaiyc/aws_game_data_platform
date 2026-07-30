"""Operator-only outbound notification contract for Module 4."""
import json

from conftest import REPO_ROOT, load_handler

NOTIFICATION_DIR = (
    REPO_ROOT
    / "module4-partner-support-chatbot"
    / "lambda"
    / "notification"
)
handler = load_handler(
    "m4_notification_handler",
    NOTIFICATION_DIR,
    env={
        "NOTIFICATIONS_TOPIC_ARN": "arn:aws:sns:ap-northeast-1:123:test",
        "OPERATOR_PRINCIPAL_PATTERN": "aurora-games-operator",
        "AWS_DEFAULT_REGION": "ap-northeast-1",
    },
)

OPERATOR_EVENT = {
    "requestContext": {
        "identity": {
            "userArn": (
                "arn:aws:sts::123:assumed-role/"
                "aurora-games-operator/session"
            )
        }
    }
}


def payload():
    return {
        "notification_type": "MAINTENANCE",
        "title": "Settlement API maintenance",
        "message": "Settlement callbacks may be delayed during the window.",
        "effective_at": "2026-08-01T02:00:00+08:00",
        "client_site_ids": ["site_a", "site_c"],
        "affected_games": [],
    }


def test_similar_or_partner_role_cannot_publish():
    event = {
        "requestContext": {
            "identity": {
                "userArn": (
                    "arn:aws:sts::123:assumed-role/"
                    "evil-aurora-games-operator/session"
                )
            }
        },
        "body": json.dumps(payload()),
    }
    response = handler.handler(event, None)
    assert response["statusCode"] == 403


def test_credential_like_material_is_rejected_before_sns(monkeypatch):
    class ShouldNotPublish:
        def publish(self, **kwargs):
            raise AssertionError("sensitive content must not reach SNS")

    monkeypatch.setattr(handler, "sns", ShouldNotPublish())
    body = payload()
    body["message"] = "Use api_key=super-secret-value during maintenance."
    response = handler.handler(
        {**OPERATOR_EVENT, "body": json.dumps(body)}, None
    )
    result = json.loads(response["body"])

    assert response["statusCode"] == 400
    assert "credential-like material" in result["error"]


def test_valid_notification_is_structured_and_filterable(monkeypatch):
    class FakeSns:
        def __init__(self):
            self.request = None

        def publish(self, **kwargs):
            self.request = kwargs
            return {"MessageId": "message-123"}

    sns = FakeSns()
    monkeypatch.setattr(handler, "sns", sns)
    response = handler.handler(
        {**OPERATOR_EVENT, "body": json.dumps(payload())}, None
    )
    result = json.loads(response["body"])
    published = json.loads(sns.request["Message"])

    assert response["statusCode"] == 202
    assert result["status"] == "PUBLISHED"
    assert published["notification_type"] == "MAINTENANCE"
    assert published["client_site_ids"] == ["site_a", "site_c"]
    assert (
        sns.request["MessageAttributes"]["notification_type"]["StringValue"]
        == "MAINTENANCE"
    )
