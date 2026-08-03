import json

from conftest import REPO_ROOT, load_handler


M1 = REPO_ROOT / "module1-anomaly-detection"
incident_api = load_handler(
    "m1_incident_api_handler",
    M1 / "incident_api",
    env={
        "INCIDENTS_TABLE_NAME": "test-incidents",
        "OPERATOR_PRINCIPAL_PATTERN": "aurora-games-operator",
        "AWS_DEFAULT_REGION": "ap-northeast-1",
    },
)


def event(method="GET", body=None, incident_id=None, role="aurora-games-operator"):
    value = {
        "httpMethod": method,
        "requestContext": {
            "identity": {
                "userArn": f"arn:aws:sts::1:assumed-role/{role}/session"
            }
        },
    }
    if body is not None:
        value["body"] = json.dumps(body)
    if incident_id is not None:
        value["pathParameters"] = {"incident_id": incident_id}
    return value


class FakeTable:
    def __init__(self):
        self.item = {
            "incident_id": "site_b#2026-06-10T11",
            "status": "DETECTED",
            "detected_at": "2026-06-10T11:05:00Z",
        }

    def scan(self, **kwargs):
        return {"Items": [dict(self.item)]}

    def get_item(self, **kwargs):
        return {"Item": dict(self.item)}

    def update_item(self, **kwargs):
        assert kwargs["ExpressionAttributeValues"][":previous"] == "DETECTED"
        self.item["status"] = kwargs["ExpressionAttributeValues"][":status"]
        return {"Attributes": dict(self.item)}


def test_operator_can_move_detected_incident_to_investigating(monkeypatch):
    monkeypatch.setattr(incident_api, "table", FakeTable())

    response = incident_api.handler(
        event(
            "POST",
            {"status": "INVESTIGATING"},
            "site_b#2026-06-10T11",
        ),
        None,
    )

    assert response["statusCode"] == 200
    assert json.loads(response["body"])["incident"]["status"] == "INVESTIGATING"


def test_non_operator_cannot_read_or_change_incidents(monkeypatch):
    monkeypatch.setattr(incident_api, "table", FakeTable())

    response = incident_api.handler(event(role="aurora-games-analyst-site_b"), None)

    assert response["statusCode"] == 403
