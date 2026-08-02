from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_modules_open_with_architecture_and_operation_views():
    html = (ROOT / "demo_console" / "index.html").read_text(encoding="utf-8")

    assert html.count('data-mode="architecture"') == 4
    assert html.count('data-mode="interface"') == 4
    assert html.count('data-panel="architecture"') == 4
    assert "gold_hourly_kpi" in html
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


def test_public_console_copy_uses_neutral_metric_names():
    html = (ROOT / "demo_console" / "index.html").read_text(encoding="utf-8")

    for disallowed in ("投注", "下注", "賭", "博弈", "客服"):
        assert disallowed not in html
