"""Alert-driven and on-demand diagnostics share code-owned analysis."""
import io
import json

from conftest import REPO_ROOT, load_handler

M3 = REPO_ROOT / "module3-analytics-assistant" / "lambda"
ask = load_handler(
    "m3_diagnostics_ask",
    M3 / "ask_answer",
    extra_paths=[M3 / "common" / "python"],
    env={
        "GUARDRAIL_ID": "test",
        "GUARDRAIL_VERSION": "1",
        "AS_OF_DATE": "2026-06-29",
        "DATA_MIN_DATE": "2026-05-01",
        "DATA_MAX_DATE": "2026-06-29",
        "GLUE_DATABASE_NAME": "test",
        "ATHENA_WORKGROUP_NAME": "test",
        "AWS_DEFAULT_REGION": "ap-northeast-1",
    },
)
first_look = load_handler(
    "m3_diagnostics_first_look",
    M3 / "first_look_report",
    extra_paths=[M3 / "common" / "python"],
    env={
        "LAKE_BUCKET_NAME": "test-lake",
        "GLUE_DATABASE_NAME": "test",
        "ATHENA_WORKGROUP_NAME": "test",
        "REPORTS_TOPIC_ARN": "arn:aws:sns:ap-northeast-1:123:test",
        "AWS_DEFAULT_REGION": "ap-northeast-1",
    },
)


def test_diagnose_slots_require_scoped_site_and_complete_date():
    parsed = ask._validate_slots(
        {
            "category": "diagnose",
            "client_site_id": "site_b",
            "game_id": "game_02",
            "end_date": "2026-06-10",
        },
        {
            "published_from": "2026-05-01",
            "published_through": "2026-06-29",
        },
    )
    assert parsed["category"] == "diagnose"

    rejected = ask._validate_slots(
        {
            "category": "diagnose",
            "client_site_id": "site_z",
            "end_date": "2026-06-10",
        }
    )
    assert rejected["category"] == "needs_clarification"


def test_on_demand_diagnosis_reuses_code_owned_render(monkeypatch):
    comparison = {
        "dau": {
            "actual": 90,
            "baseline_avg_7d": 200,
            "pct_change": -55,
        },
        "ggr_usd": {
            "actual": 100,
            "baseline_avg_7d": 220,
            "pct_change": -54.55,
        },
    }
    breakdown = [
        {
            "game_id": "game_02",
            "ggr_usd_today": 10,
            "ggr_usd_baseline_avg": 50,
            "pct_change": -80,
        }
    ]
    monkeypatch.setattr(
        ask.diagnostics, "site_baseline_comparison", lambda *_: comparison
    )
    monkeypatch.setattr(
        ask.diagnostics, "game_breakdown", lambda *_: breakdown
    )

    result = ask._run_diagnosis("site_b", "2026-06-10")

    assert "First-Look Report" in result["report_text"]
    assert result["comparison"] == comparison
    assert result["game_breakdown"] == breakdown


class FakeS3:
    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body, **kwargs):
        self.objects[Key] = json.loads(Body)


class FakeSns:
    def __init__(self):
        self.messages = []

    def publish(self, **kwargs):
        self.messages.append(kwargs)
        return {"MessageId": "message-1"}


def test_retention_alert_becomes_first_look_without_model_call(monkeypatch):
    payload = {
        "client_site_id": "site_b",
        "cohort_week_start": "2026-06-15",
        "cohort_week_end": "2026-06-21",
        "alerts": [
            {
                "metric": "d7_retention_rate",
                "actual": 0.2,
                "baseline": 0.45,
                "absolute_drop": 0.25,
                "z_score": -3.2,
                "current_cohort_size": 140,
                "baseline_cohort_size": 600,
            }
        ],
    }
    event = {
        "Records": [
            {
                "Sns": {
                    "Message": json.dumps(payload),
                    "MessageAttributes": {
                        "alert_type": {"Value": "retention_anomaly"},
                        "client_site_id": {"Value": "site_b"},
                        "as_of_date": {"Value": "2026-06-21"},
                    },
                }
            }
        ]
    }
    fake_s3 = FakeS3()
    fake_sns = FakeSns()
    monkeypatch.setattr(first_look, "s3", fake_s3)
    monkeypatch.setattr(first_look, "sns", fake_sns)
    monkeypatch.setattr(
        first_look.bedrock,
        "converse",
        lambda **_: (_ for _ in ()).throw(
            AssertionError("retention path must not call Bedrock")
        ),
    )

    result = first_look.handler(event, None)

    assert result["reports"][0]["report_type"] == "RETENTION_FIRST_LOOK"
    assert "Sample-Weighted Comparison" in result["reports"][0]["report_text"]
    assert len(fake_sns.messages) == 1


def test_hourly_alert_reads_precomputed_evidence_before_headline(monkeypatch):
    comparison = {
        "active_users": {
            "actual": 2,
            "baseline": 9.3,
            "lower_bound": 5,
            "upper_bound": 14,
            "pct_change": -78.49,
        },
        "sessions": {
            "actual": 2,
            "baseline": 8.1,
            "lower_bound": 4,
            "upper_bound": 12,
            "pct_change": -75.31,
        },
        "processed_events": {
            "actual": 19,
            "baseline": 81.6,
            "lower_bound": 40,
            "upper_bound": 123,
            "pct_change": -76.72,
        },
    }
    calls = []
    monkeypatch.setattr(
        first_look,
        "_hourly_baseline_comparison",
        lambda site, event_hour: calls.append((site, event_hour)) or comparison,
    )
    monkeypatch.setattr(
        first_look,
        "_headline",
        lambda site, event_hour, evidence: (
            calls.append(("headline", evidence))
            or "Site usage fell materially below its same-hour baseline."
        ),
    )
    fake_s3 = FakeS3()
    fake_sns = FakeSns()
    monkeypatch.setattr(first_look, "s3", fake_s3)
    monkeypatch.setattr(first_look, "sns", fake_sns)
    event = {
        "Records": [{
            "Sns": {
                "Message": json.dumps({"alerts": [{"metric": "active_users"}]}),
                "MessageAttributes": {
                    "alert_type": {"Value": "hourly_data_anomaly"},
                    "client_site_id": {"Value": "site_b"},
                    "as_of_date": {"Value": "2026-06-10"},
                    "event_hour": {"Value": "2026-06-10 13:00:00.000"},
                },
            }
        }]
    }

    result = first_look.handler(event, None)

    report = result["reports"][0]
    assert calls[0] == ("site_b", "2026-06-10 13:00:00.000")
    assert calls[1] == ("headline", comparison)
    assert report["report_type"] == "HOURLY_FIRST_LOOK"
    assert "Same-Hour Comparison" in report["report_text"]
    assert (
        "gold/first_look_reports/site_b_2026-06-10T13_hourly.json"
        in fake_s3.objects
    )
    assert len(fake_sns.messages) == 1
