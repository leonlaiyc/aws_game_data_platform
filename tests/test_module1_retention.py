"""Weekly retention monitoring uses mature, sample-weighted cohorts."""
import io
import json

from conftest import REPO_ROOT, load_handler

M1 = REPO_ROOT / "module1-anomaly-detection"
retention = load_handler(
    "m1_retention_handler",
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


def test_latest_week_is_complete_and_d7_mature():
    # Published on Monday 29 June: D7 maturity reaches Monday 22 June, but the
    # most recent *complete* cohort week still ends on Sunday 21 June.
    assert retention._latest_complete_retention_week("2026-06-29") == (
        "2026-06-15",
        "2026-06-21",
    )


def _week(start, size, d1, d7):
    return {
        "cohort_week_start": start,
        "cohort_size": str(size),
        "d1_retained": str(d1),
        "d7_retained": str(d7),
    }


def test_weighted_retention_drop_alerts():
    rows = [
        _week("2026-05-18", 100, 60, 40),
        _week("2026-05-25", 200, 120, 80),
        _week("2026-06-01", 100, 60, 40),
        _week("2026-06-08", 200, 120, 80),
        _week("2026-06-15", 140, 42, 21),
    ]

    signal = retention._retention_signal(
        rows, "d1_retention_rate", "2026-06-15"
    )

    assert signal["baseline"] == 0.6
    assert signal["actual"] == 0.3
    assert signal["baseline_cohort_size"] == 600
    assert signal["alert"] is True


def test_small_or_partial_cohort_does_not_alert():
    rows = [
        _week("2026-05-18", 100, 60, 40),
        _week("2026-05-25", 100, 60, 40),
        _week("2026-06-01", 100, 60, 40),
        _week("2026-06-08", 100, 60, 40),
        _week("2026-06-15", 20, 1, 1),
    ]

    signal = retention._retention_signal(
        rows, "d1_retention_rate", "2026-06-15"
    )

    assert signal["skipped"] == "insufficient cohort size"
    assert "alert" not in signal


def test_retention_alert_carries_review_evidence_contract(monkeypatch):
    rows = [
        _week("2026-05-18", 100, 60, 40),
        _week("2026-05-25", 200, 120, 80),
        _week("2026-06-01", 100, 60, 40),
        _week("2026-06-08", 200, 120, 80),
        _week("2026-06-15", 140, 42, 21),
    ]
    published = []
    monkeypatch.setattr(retention, "_fetch_retention_weeks", lambda *_: rows)
    monkeypatch.setattr(
        retention, "_publish_retention_alert", published.append
    )

    result = retention._check_retention_site(
        "site_a",
        "2026-06-15",
        "2026-06-21",
        {
            "table": "gold_daily_kpi",
            "published_at": "2026-06-30T00:00:00Z",
            "published_through": "2026-06-29",
        },
    )

    assert result["decision"] == "REVIEW_REQUIRED"
    assert result["detector_id"] == "weekly_mature_cohort_retention"
    assert result["reason_codes"] == ["MATURE_RETENTION_RATE_DROP"]
    assert result["data_publication"]["published_through"] == "2026-06-29"
    assert result["recommended_checks"]
    assert published == [result]


class NoSuchKey(Exception):
    pass


class FakeS3:
    class exceptions:
        NoSuchKey = NoSuchKey

    def __init__(self):
        self.objects = {
            retention.PUBLICATION_MANIFEST_KEY: json.dumps(
                {
                    "table": "gold_daily_kpi",
                    "published_through": "2026-06-29",
                    "published_at": "2026-06-30T00:00:00Z",
                }
            ).encode()
        }

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise NoSuchKey(Key)
        return {"Body": io.BytesIO(self.objects[Key])}

    def put_object(self, Bucket, Key, Body, **kwargs):
        self.objects[Key] = Body


def test_weekly_marker_is_independent_from_daily_marker(monkeypatch):
    fake_s3 = FakeS3()
    monkeypatch.setattr(retention, "s3", fake_s3)
    monkeypatch.setattr(retention, "_discover_sites", lambda: ["site_a"])
    monkeypatch.setattr(
        retention,
        "_check_retention_site",
        lambda site, start, end, publication: {
            "client_site_id": site,
            "cohort_week_start": start,
            "cohort_week_end": end,
        },
    )

    first = retention.handler(
        {"scheduled": True, "cadence": "weekly"}, None
    )
    second = retention.handler(
        {"scheduled": True, "cadence": "weekly"}, None
    )

    assert first["cadence"] == "weekly"
    assert len(first["checked"]) == 1
    assert second["checked"] == []
    assert retention.RETENTION_CONSUMPTION_MARKER_KEY in fake_s3.objects
    assert retention.CONSUMPTION_MARKER_KEY not in fake_s3.objects
