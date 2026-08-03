"""Module 2 live-operation checks.

The central distinction under test is assignment vs. exposure: assignment is
an eligibility decision, while SRM and live guardrails must be grounded in
events actually accepted by the product-facing exposure API.
"""
import importlib.util
from decimal import Decimal

from conftest import REPO_ROOT, load_handler

MONITOR_DIR = (
    REPO_ROOT
    / "module2-experimentation-platform"
    / "orchestration"
    / "lambda"
    / "monitoring_check"
)
COMMON_LAYER_DIR = (
    REPO_ROOT
    / "module2-experimentation-platform"
    / "orchestration"
    / "lambda"
    / "common"
    / "python"
)
handler = load_handler(
    "m2_live_monitoring_handler",
    MONITOR_DIR,
    extra_paths=[COMMON_LAYER_DIR],
    env={
        "EXPERIMENTS_TABLE_NAME": "test-experiments",
        "EXPOSURES_TABLE_NAME": "test-exposures",
        "ALERTS_TOPIC_ARN": "arn:aws:sns:ap-northeast-1:123:test",
        "AWS_DEFAULT_REGION": "ap-northeast-1",
    },
)

DASHBOARD_VIEW_MODEL = (
    REPO_ROOT
    / "module2-experimentation-platform"
    / "dashboard"
    / "view_model.py"
)
spec = importlib.util.spec_from_file_location(
    "m2_dashboard_view_model", DASHBOARD_VIEW_MODEL
)
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


class FakeExposures:
    def __init__(self, variants):
        self.items = [
            {"player_id": f"player_{index}", "variant": variant}
            for index, variant in enumerate(variants)
        ]

    def query(self, **kwargs):
        return {"Items": self.items}


def experiment():
    return {
        "experiment_id": "exp_test",
        "variants": [
            {"name": "control", "weight": Decimal("0.5")},
            {"name": "treatment", "weight": Decimal("0.5")},
        ],
    }


def test_exposure_srm_waits_for_a_meaningful_sample(monkeypatch):
    monkeypatch.setattr(
        handler,
        "exposures_table",
        FakeExposures(["control"] * 49 + ["treatment"] * 50),
    )
    result = handler._check_exposure_srm(experiment())

    assert result["total_exposed"] == 99
    assert result["status"] == "insufficient_sample"
    assert result["passed"] is None


def test_exposure_srm_accepts_a_balanced_product_split(monkeypatch):
    monkeypatch.setattr(
        handler,
        "exposures_table",
        FakeExposures(["control"] * 50 + ["treatment"] * 50),
    )
    result = handler._check_exposure_srm(experiment())

    assert result["source"] == "product_exposures"
    assert result["observed"] == {"control": 50, "treatment": 50}
    assert result["passed"] is True
    assert result["p_value"] == 1.0


def test_exposure_srm_rejects_a_severely_skewed_product_split(monkeypatch):
    monkeypatch.setattr(
        handler,
        "exposures_table",
        FakeExposures(["control"] * 99 + ["treatment"]),
    )
    result = handler._check_exposure_srm(experiment())

    assert result["status"] == "breached"
    assert result["passed"] is False
    assert result["p_value"] < result["threshold"]
    assert result["observed"] == {"control": 99, "treatment": 1}


def test_exposure_srm_counts_unique_players_not_repeat_impressions(monkeypatch):
    exposures = FakeExposures(["control"] * 50 + ["treatment"] * 50)
    exposures.items.extend([
        {"player_id": "player_0", "variant": "control"}
        for _ in range(20)
    ])
    monkeypatch.setattr(handler, "exposures_table", exposures)

    result = handler._check_exposure_srm(experiment())

    assert result["total_exposed"] == 100
    assert result["observed"] == {"control": 50, "treatment": 50}
    assert result["passed"] is True


def test_live_guardrail_query_uses_exposures_not_eligibility(monkeypatch):
    captured = []

    def fake_run(sql):
        captured.append(sql)
        return "query-id"

    monkeypatch.setattr(handler, "run_athena_query", fake_run)
    monkeypatch.setattr(
        handler,
        "fetch_all_rows",
        lambda query_id: [{"value": "2.5"}],
    )

    breaches = handler._check_guardrails(
        "exp_test",
        "2026-07-29",
        [{"metric": "sessions_7d", "direction": "min", "threshold": 3}],
        "gold_experiment_exposures",
        execution_mode="live",
        client_site_id="site_a",
        game_id="game_01",
    )

    assert len(breaches) == 1
    assert "FROM gold_experiment_exposures" in captured[0]
    assert "variant = 'treatment'" in captured[0]
    assert "gold_experiment_assignments" not in captured[0]
    assert "FROM gold_hourly_kpi" in captured[0]
    assert "SUM(hk.sessions)" in captured[0]
    assert "hk.client_site_id = 'site_a'" in captured[0]
    assert "hk.game_id = 'game_01'" in captured[0]


def test_central_view_surfaces_parallel_health_and_kill_switch():
    view = dashboard.build_view_model([
        {
            "experiment_id": "exp_live",
            "name": "Live checkout",
            "client_site_id": "site_a",
            "game_id": "game_01",
            "state": "running",
            "execution_mode": "live",
            "allocation_enabled": True,
            "monitoring_status": {
                "checked_at": "2026-07-29T00:00:00Z",
                "srm": {
                    "status": "insufficient_sample",
                    "total_exposed": 42,
                    "minimum_exposures": 100,
                },
            },
        },
        {
            "experiment_id": "exp_stopped",
            "name": "Stopped payout",
            "client_site_id": "site_c",
            "game_id": "game_02",
            "state": "stopped_early",
            "allocation_enabled": False,
            "stop_reason": "guardrail_breach: ggr below threshold",
        },
    ])

    assert view["summary"] == {
        "total": 2,
        "running": 1,
        "needs_action": 1,
        "draft": 0,
    }
    live, stopped = view["experiments"]
    assert live["health"] == "watch"
    assert live["total_exposed"] == 42
    assert stopped["health"] == "action"
    assert stopped["allocation_enabled"] is False
