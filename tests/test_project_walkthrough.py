"""Static acceptance checks for the GitHub Pages project walkthrough."""

from __future__ import annotations

import re
import struct
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"


class _SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.references: list[str] = []
        self.translation_keys: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if element_id := attributes.get("id"):
            self.ids.append(element_id)
        if translation_key := attributes.get("data-i18n"):
            self.translation_keys.add(translation_key)
        for name in ("href", "src"):
            if reference := attributes.get(name):
                self.references.append(reference)


def test_project_walkthrough_is_self_contained_bilingual_and_publishable() -> None:
    html = (SITE / "index.html").read_text(encoding="utf-8")
    javascript = (SITE / "app.js").read_text(encoding="utf-8")
    stylesheet = (SITE / "styles.css").read_text(encoding="utf-8")

    parser = _SiteParser()
    parser.feed(html)

    assert len(parser.ids) == len(set(parser.ids)), "HTML ids must be unique"
    expected_sections = [
        "overview",
        "problems",
        "architecture",
        "workflows",
        "demo",
        "decisions",
        "learnings",
        "evidence",
    ]
    assert set(expected_sections) <= set(parser.ids)
    assert [parser.ids.index(section) for section in expected_sections] == sorted(
        parser.ids.index(section) for section in expected_sections
    )
    assert "http://" not in html
    assert "http://" not in javascript
    assert "Leon Lai" in html
    assert {
        "problemsTitle",
        "architectureTitle",
        "workflowsTitle",
        "demoTitle",
        "decisionsTitle",
        "learningsTitle",
        "evidenceTitle",
    } <= parser.translation_keys
    assert {
        "beforeLabel",
        "systemLabel",
        "humanLabel",
        "wf1OpsLabel",
        "wf3ScopeLabel",
        "wf2StateLabel",
        "wf4RagLabel",
    } <= (
        parser.translation_keys
    )
    assert re.findall(r'data-demo="(m[1-4])"', html) == ["m1", "m3", "m2", "m4"]
    assert "IAM_ALLOWED_PRINCIPALS" in html
    assert "2026-06-10" in html
    assert "DAU 91" in html
    assert "2026-06-12" in html
    for obsolete_copy in (
        "Aurora Games",
        "Experiment safely",
        "安全跑實驗",
        "CORE PRIORITY",
        "不逐項背服務",
        "不是心得，而是",
        "未知套利手法",
        "實作邊界",
        "中央 registry",
        "負責人以簽名 API",
        "Only when judgement is required",
        "service-examples",
        "這些問題是在建置與驗證這個 PoC 時發現",
    ):
        assert obsolete_copy not in html
        assert obsolete_copy not in javascript

    for required_copy in (
        "實驗需要有正規的自動化與治理流程",
        "DynamoDB 保存當下最新狀態",
        "尚未保存每次狀態變更的完整不可竄改事件紀錄",
        "尚未串接 Email、Slack 或 CRM 通知",
        "每 24 小時",
        "Dashboard 每 15 秒",
        "RAG-style",
        "系統設計取捨與成本最佳化",
        "目前的省錢／輕量做法",
        "工程驗證與架構文件",
        "測試通過率（100%）",
        "本專案的核心價值在於",
    ):
        assert required_copy in html
        assert required_copy in javascript

    evidence_cards = html.split('<div class="evidence-grid reveal">', 1)[1].split(
        "</div>", 1
    )[0]
    assert evidence_cards.count("<article>") == 2

    for readability_rule in (
        ".workflow-grid p {\n  margin: 0;\n  color: var(--ink-soft);\n  font-size: 0.98rem;",
        ".workflow-grid small {\n  display: block;\n  margin-bottom: 12px;\n  color: var(--teal);\n  font-family: var(--mono);\n  font-size: 1.06rem;",
        ".architecture-node span {\n  margin-top: 5px;\n  color: rgba(255, 255, 255, 0.58);\n  font-size: 0.9rem;",
        ".section-heading p:last-child {\n  max-width: 760px;\n  margin-bottom: 0;\n  color: var(--ink-soft);\n  font-size: 1.45rem;",
        "font-size: 1.14rem;",
        "font-size: 1.05rem;",
    ):
        assert readability_rule in stylesheet

    for reference in parser.references:
        if reference.startswith("#"):
            assert reference[1:] in parser.ids, f"Missing anchor target: {reference}"
        elif reference.startswith("https://"):
            continue
        else:
            path = (SITE / reference.split("?", 1)[0].split("#", 1)[0]).resolve()
            assert path.is_relative_to(SITE.resolve())
            assert path.is_file(), f"Missing local asset: {reference}"

    for key in parser.translation_keys:
        definitions = re.findall(rf"^\s{{4}}{re.escape(key)}:", javascript, re.MULTILINE)
        assert len(definitions) == 2, f"{key!r} must exist once in each language"

    image = SITE / "og.png"
    assert image.stat().st_size < 2_500_000
    with image.open("rb") as file:
        header = file.read(24)
    assert header[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", header[16:24])
    assert width >= 1200 and 1.8 < width / height < 2.0
