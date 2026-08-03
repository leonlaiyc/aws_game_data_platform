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
    assert "Evidence and status" in html


def test_m1_is_hourly_monitoring_not_a_manual_scan_tool():
    html = (ROOT / "demo_console" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "demo_console" / "app.js").read_text(encoding="utf-8")

    assert "今日累積活躍人數" in html
    assert "過去 30 個完整日期" in html
    assert 'id="hourly-chart"' in html
    assert "PoC snapshot · Synthetic hourly data" in html
    assert "執行異常掃描" not in html
    assert "run-anomaly" not in html
    assert "run-anomaly" not in script
    assert "今日累積處理量" in html
    assert 'id="start-investigation"' in html
    assert "排查中" in script
    assert 'id="open-first-look"' in html


def test_m3_architecture_and_default_report_match_the_hourly_flow():
    html = (ROOT / "demo_console" / "index.html").read_text(encoding="utf-8")

    m3 = html[html.index('id="m3"'):html.index('id="m2"')]
    assert m3.index("Athena") < m3.index("Bedrock")
    assert "營運分析助理" in m3
    assert "全部授權站點" in m3
    assert "Unsupported Forecast" in m3
    assert 'id="analytics-form"' in m3


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
    assert m4.count("data-support-scenario=") == 2
    assert "API 呼叫失敗" in m4
    assert "知識庫沒有答案" in m4
    assert 'id="chat-input"' in m4
    assert "/oauth/token" in script
    assert "invalid_request" in script
    assert "XX 展覽" in script
    assert "OUT_OF_SCOPE" in script
    assert "model not invoked" in script
    assert "文件助理" not in html


def test_public_console_copy_uses_neutral_metric_names():
    html = (ROOT / "demo_console" / "index.html").read_text(encoding="utf-8")

    for disallowed in ("投注", "下注", "賭", "博弈", "客服"):
        assert disallowed not in html


def test_operation_video_follows_the_cross_module_incident_story():
    source = (ROOT / "scripts" / "render_operation_demo.py").read_text(encoding="utf-8")

    chapters = (
        '"01 · 異常監控"',
        '"02 · 分析助理"',
        '"03 · 實驗治理"',
        '"04 · 整合支援"',
    )
    assert [source.index(chapter) for chapter in chapters] == sorted(
        source.index(chapter) for chapter in chapters
    )
    for expected in ("上午 11:00", "SNS 發布值班通知", "下午 1:00", "自動停止實驗"):
        assert expected in source
