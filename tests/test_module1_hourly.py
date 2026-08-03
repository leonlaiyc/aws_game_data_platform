"""Hourly monitoring consumes prepared same-hour features and publishes evidence."""
import io
import json

from conftest import REPO_ROOT, load_handler

M1 = REPO_ROOT / "module1-anomaly-detection"
hourly = load_handler(
    "m1_hourly_handler",
    M1 / "data_anomaly" / "lambda" / "detector",
    extra_paths=[M1 / "data_anomaly" / "lambda" / "common" / "python"],
    env={
        "LAKE_BUCKET_NAME": "test-lake",
        "ALERTS_TOPIC_ARN": "arn:aws:sns:ap-northeast-1:123:test",
        "GLUE_DATABASE_NAME": "test",
        "ATHENA_WORKGROUP_NAME": "test",
        "AWS_DEFAULT_REGION": "ap-northeast-1",
    },
)


class FakeS3:
    class exceptions:
        class NoSuchKey(Exception):
            pass

    def __init__(self, objects=None):
        self.objects = objects or {}

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise self.exceptions.NoSuchKey()
        value = self.objects[Key]
        return {"Body": io.BytesIO(json.dumps(value).encode())}

    def put_object(self, Bucket, Key, Body, **kwargs):
        self.objects[Key] = json.loads(Body)


class FakeSns:
    def __init__(self):
        self.messages = []

    def publish(self, **kwargs):
        self.messages.append(kwargs)


def _feature():
    row = {
        "event_hour": "2026-06-10 13:00:00.000",
        "client_site_id": "site_b",
        "baseline_points": "7",
        "active_users": "2",
        "active_users_baseline": "9.3",
        "active_users_lower_bound": "5",
        "active_users_upper_bound": "14",
        "sessions": "8",
        "sessions_baseline": "8.1",
        "sessions_lower_bound": "5",
        "sessions_upper_bound": "12",
        "processed_events": "19",
        "processed_events_baseline": "81.6",
        "processed_events_lower_bound": "40",
        "processed_events_upper_bound": "123",
    }
    return row


def test_hourly_check_uses_precomputed_bounds_and_publishes(monkeypatch):
    fake_s3 = FakeS3()
    fake_sns = FakeSns()
    monkeypatch.setattr(hourly, "s3", fake_s3)
    monkeypatch.setattr(hourly, "sns", fake_sns)
    monkeypatch.setattr(hourly, "_fetch_hourly_feature", lambda *_: _feature())

    result = hourly._check_hourly_site("site_b", "2026-06-10 13:00:00.000")

    assert [alert["metric"] for alert in result["alerts"]] == [
        "active_users",
        "processed_events",
    ]
    assert result["alerts"][0]["baseline"] == 9.3
    assert len(fake_sns.messages) == 1
    attrs = fake_sns.messages[0]["MessageAttributes"]
    assert attrs["alert_type"]["StringValue"] == "hourly_data_anomaly"
    assert attrs["event_hour"]["StringValue"] == "2026-06-10 13:00:00.000"
    assert any(key.startswith("gold/anomaly_alerts/site_b_2026-06-10T13") for key in fake_s3.objects)


def test_hourly_schedule_consumes_each_publication_once(monkeypatch):
    publication = {
        "table": "gold_hourly_monitoring_features",
        "published_at": "2026-08-03T01:00:00Z",
        "published_through": "2026-06-17",
    }
    fake_s3 = FakeS3({hourly.HOURLY_PUBLICATION_MANIFEST_KEY: publication})
    monkeypatch.setattr(hourly, "s3", fake_s3)
    monkeypatch.setattr(hourly, "_discover_hourly_sites", lambda: ["site_b"])
    monkeypatch.setattr(hourly, "_check_hourly_site", lambda site: {"client_site_id": site})

    first = hourly.handler({"scheduled": True, "cadence": "hourly"}, None)
    second = hourly.handler({"scheduled": True, "cadence": "hourly"}, None)

    assert first == {"checked": [{"client_site_id": "site_b"}], "cadence": "hourly"}
    assert second["skipped"] == "publication already processed"
