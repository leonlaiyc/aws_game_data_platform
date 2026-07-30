"""Regression tests for claims that prose generation cannot violate."""
from conftest import REPO_ROOT, load_handler

M2_LAMBDA = REPO_ROOT / "module2-experimentation-platform" / "orchestration" / "lambda"
readout = load_handler(
    "m2_readout_handler",
    M2_LAMBDA / "readout",
    extra_paths=[M2_LAMBDA / "common" / "python"],
    env={
        "EXPERIMENTS_TABLE_NAME": "test-experiments",
        "AWS_DEFAULT_REGION": "ap-northeast-1",
    },
)

M3_LAMBDA = REPO_ROOT / "module3-analytics-assistant" / "lambda"
first_look = load_handler(
    "m3_first_look_handler",
    M3_LAMBDA / "first_look_report",
    extra_paths=[M3_LAMBDA / "common" / "python"],
    env={
        "LAKE_BUCKET_NAME": "test-lake",
        "GLUE_DATABASE_NAME": "test",
        "ATHENA_WORKGROUP_NAME": "test",
        "REPORTS_TOPIC_ARN": "arn:aws:sns:ap-northeast-1:123:test",
        "AWS_DEFAULT_REGION": "ap-northeast-1",
    },
)


def analysis_result():
    return {
        "oec_metric": "ggr_usd_7d",
        "control_n": 100,
        "control_mean": 10,
        "treatment_n": 100,
        "treatment_mean": 11,
        "lift_pct": 10,
        "p_value": 0.02,
        "significant": True,
        "guardrail_status": [],
        "flags": [],
    }


def test_readout_rejects_even_correctly_repeated_numbers():
    ok, tokens = readout._grounding_check(
        "The treatment improved the result by 10 percent.", {}, analysis_result(),
    )
    assert ok is False
    assert tokens == ["10"]


def test_readout_accepts_qualitative_prose():
    ok, tokens = readout._grounding_check(
        "The treatment produced a meaningful, statistically credible improvement.",
        {},
        analysis_result(),
    )
    assert ok is True
    assert tokens == []


def test_readout_parse_requires_both_narrative_fields():
    conclusion, recommendation, parsed_ok = readout._parse_llm_json(
        '{"conclusion":"A credible improvement."}',
    )
    assert conclusion
    assert recommendation == ""
    assert parsed_ok is False


def test_bedrock_failure_preserves_deterministic_readout(monkeypatch):
    class FailingBedrock:
        def converse(self, **kwargs):
            raise RuntimeError("simulated outage")

    class FakeTable:
        def __init__(self):
            self.request = None

        def update_item(self, **kwargs):
            self.request = kwargs

    fake_table = FakeTable()
    monkeypatch.setattr(readout, "bedrock", FailingBedrock())
    monkeypatch.setattr(readout, "table", fake_table)

    result = readout.handler({
        "experiment_id": "exp_test",
        "assignment": {"experiment": {"name": "Test experiment"}},
        "analysis_result": analysis_result(),
    }, None)

    assert result["llm_text_accepted"] is False
    assert result["model_error"] == "RuntimeError"
    assert "### Key Stats" in result["report_text"]
    assert "n=100" in result["report_text"]
    assert fake_table.request is not None


def test_first_look_rejects_numeric_headline(monkeypatch):
    class NumericBedrock:
        def converse(self, **kwargs):
            return {
                "output": {
                    "message": {
                        "content": [{"text": '{"headline":"GGR fell 10 percent."}'}],
                    },
                },
            }

    monkeypatch.setattr(first_look, "bedrock", NumericBedrock())
    headline = first_look._headline("site_a", "2026-06-29", {
        "ggr_usd": {"pct_change": -10},
    })
    assert headline == first_look._HEADLINE_FALLBACK


def test_first_look_bedrock_outage_uses_fallback(monkeypatch):
    class FailingBedrock:
        def converse(self, **kwargs):
            raise RuntimeError("simulated outage")

    monkeypatch.setattr(first_look, "bedrock", FailingBedrock())
    headline = first_look._headline("site_a", "2026-06-29", {
        "ggr_usd": {"pct_change": -10},
    })
    assert headline == first_look._HEADLINE_FALLBACK
