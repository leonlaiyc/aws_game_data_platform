from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_modules_open_with_architecture_and_operation_views():
    html = (ROOT / "demo_console" / "index.html").read_text(encoding="utf-8")

    assert html.count('data-mode="architecture"') == 4
    assert html.count('data-mode="interface"') == 4
    assert html.count('data-panel="architecture"') == 4
    assert "gold_hourly_kpi" in html
    assert "gold_hourly_monitoring_features" in html
    assert html.count('class="system-map') == 4
    assert "THE FOUNDATION" in html
    assert "One event, three outputs" in html


def test_m1_is_hourly_monitoring_not_a_manual_scan_tool():
    html = (ROOT / "demo_console" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "demo_console" / "app.js").read_text(encoding="utf-8")

    assert "每小時活躍使用者" in html
    assert 'id="hourly-chart"' in html
    assert "PoC snapshot · Synthetic hourly data" in html
    assert "執行異常掃描" not in html
    assert "run-anomaly" not in html
    assert "run-anomaly" not in script
    assert "每小時資料處理量" in html
    assert 'id="open-first-look"' in html


def test_m3_architecture_and_default_report_match_the_hourly_flow():
    html = (ROOT / "demo_console" / "index.html").read_text(encoding="utf-8")

    m3 = html[html.index('id="m3"'):html.index('id="m2"')]
    assert m3.index("Athena") < m3.index("Bedrock")
    assert "PoC snapshot · Hourly demo" in m3
    assert "2 vs 9.3" in m3
    assert "SQS Audit" in m3


def test_m2_shows_identity_checks_and_both_decision_branches():
    html = (ROOT / "demo_console" / "index.html").read_text(encoding="utf-8")

    m2 = html[html.index('id="m2"'):html.index('id="m4"')]
    for expected in (
        "IAM",
        "Initial SRM",
        "Exposure SRM",
        "Hourly Guardrail",
        "Continue",
        "Auto-stop",
        'id="experiment-detail"',
    ):
        assert expected in m2


def test_m4_is_integration_support_with_answer_and_refusal_scenarios():
    html = (ROOT / "demo_console" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "demo_console" / "app.js").read_text(encoding="utf-8")

    m4 = html[html.index('id="m4"'):]
    assert "整合支援" in m4
    assert m4.count("data-demo-question=") == 2
    assert "正常整合問題" in m4
    assert "範圍外問題" in m4
    assert "OUT_OF_SCOPE" in script
    assert "model not invoked" in script
    assert "文件助理" not in html


def test_public_console_copy_uses_neutral_metric_names():
    html = (ROOT / "demo_console" / "index.html").read_text(encoding="utf-8")

    for disallowed in ("投注", "下注", "賭", "博弈", "客服"):
        assert disallowed not in html
