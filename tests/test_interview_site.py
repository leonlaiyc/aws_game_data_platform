"""Static acceptance checks for the GitHub Pages interview demo."""

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


def test_interview_site_is_self_contained_bilingual_and_publishable() -> None:
    html = (SITE / "index.html").read_text(encoding="utf-8")
    javascript = (SITE / "app.js").read_text(encoding="utf-8")

    parser = _SiteParser()
    parser.feed(html)

    assert len(parser.ids) == len(set(parser.ids)), "HTML ids must be unique"
    assert {"overview", "story", "modules", "decisions", "proof"} <= set(parser.ids)
    assert "http://" not in html
    assert "http://" not in javascript

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
