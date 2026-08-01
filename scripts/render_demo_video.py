"""Render the two-minute, subtitle-first portfolio demo as a web-ready MP4.

The renderer deliberately turns verified AWS evidence into large presentation
cards instead of recording a tiny terminal. It emits the MP4, poster, WebVTT,
and SRT from one cue list so the website and downloadable captions cannot
drift apart.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "site" / "video"
WIDTH, HEIGHT = 1920, 1080
FPS = 24

NIGHT = "#061d20"
NIGHT_2 = "#0a292d"
INK = "#f5f0e8"
MUTED = "#a8bdba"
TEAL = "#26d2c5"
AMBER = "#e7ad3c"
CORAL = "#f26b5e"
LINE = "#315054"

FONT_REGULAR = Path("C:/Windows/Fonts/msjh.ttc")
FONT_BOLD = Path("C:/Windows/Fonts/msjhbd.ttc")


@dataclass(frozen=True)
class Cue:
    start: float
    end: float
    chapter: str
    kicker: str
    title: str
    caption: str
    cards: tuple[tuple[str, str, str], ...]
    status: str
    accent: str = TEAL


CUES = (
    Cue(0, 5, "00", "AWS GAME DATA PLATFORM", "兩分鐘，看懂四個營運工作流", "以 Serverless 為主的雲端架構，讓系統處理重複工作，讓人保留關鍵決策。", (("4", "核心工作流", "Detect · Investigate · Experiment · Support"),), "VERIFIED POC", AMBER),
    Cue(5, 13, "M1", "01 · DETECT", "營運異常不再等待人工發現", "每日資料發布後，EventBridge 觸發 Lambda，讀取 Athena Gold KPI 並依固定規則檢查。", (("INPUT", "site_b · 2026-06-10", "最新完整發布日"), ("RULE", "DAU 低於 EWMA 3σ", "確定性門檻")), "TRIGGERED", CORAL),
    Cue(13, 22, "M1", "01 · DETECT", "DAU 91，基準 204.45", "系統發布 SNS 告警，同時把實際值、基準與證據窗口保存到 S3。", (("91", "實際 DAU", "actual"), ("204.45", "EWMA 基準", "baseline"), ("3.9σ", "偏離程度", "alert")), "ALERT · EVIDENCE PRESERVED", CORAL),
    Cue(22, 30, "M1", "01 · DETECT", "已知風險訊號保留可解釋證據", "6 個 scripted ring players 全數進入 REVIEW_REQUIRED；系統不替人宣判。", (("6 / 6", "進入人工審查", "shared device + cash-out ratio"),), "HUMAN REVIEW REQUIRED", AMBER),
    Cue(30, 38, "M3", "02 · INVESTIGATE", "受治理的問題，直接取得可核對答案", "問題只會對應 allow-listed SQL 模板；不生成任意 SQL。", (("891.83 USD", "site_a 最近一週 GGR", "Athena direct check: MATCH"),), "ANSWERABLE", TEAL),
    Cue(38, 47, "M3", "02 · INVESTIGATE", "同一個異常，自動產生 first-look", "SNS 告警觸發分析，整理七日基準、遊戲拆分與共變動訊號。", (("-55.73%", "DAU vs 7 日均值", "91 vs 205.57"), ("-13.36%", "GGR vs 7 日均值", "54.57 vs 62.98")), "REPORT STORED & DELIVERED", TEAL),
    Cue(47, 55, "M3", "02 · INVESTIGATE", "分析師從重算數字，改成判斷根因", "系統提供證據與下一步；營運脈絡、根因與處置仍由人決定。", (("SYSTEM", "整理基準與關聯", "repeatable evidence"), ("HUMAN", "判斷根因與行動", "operating context")), "GOVERNED HANDOFF", AMBER),
    Cue(55, 66, "M2", "03 · EXPERIMENT OPS", "正常結果仍需警告，不只看顯著性", "正向實驗完成分析，但系統同步標記小樣本與異常大的效果量。", (("+431.58%", "treatment lift", "p = 0.000108"), ("2", "品質警告", "SMALL_SAMPLE · LARGE_EFFECT")), "ANALYZED · REVIEW CAVEATS", TEAL),
    Cue(66, 78, "M2", "03 · EXPERIMENT OPS", "Guardrail breach 立即停止實驗", "實驗組 GGR 跌破 0 美元門檻；系統保留停止原因，不再執行分析與 readout。", (("-101.61", "treatment GGR", "threshold ≥ 0"), ("STOPPED", "early", "analysis skipped")), "GUARDRAIL BREACH", CORAL),
    Cue(78, 90, "M2", "03 · EXPERIMENT OPS", "Live SRM 失衡，立即關閉分配", "100 筆真實曝光形成 99/1 偏斜；系統停止實驗，後續玩家只回 control。", (("99 / 1", "observed exposure split", "declared 50 / 50"), ("OFF", "allocation enabled", "late decision: control-only")), "STOPPED_EARLY · COST < $0.01", CORAL),
    Cue(90, 100, "M4", "04 · SUPPORT", "先澄清，再回答", "環境敏感問題缺少 sandbox／production 時，系統先要求補充，不猜答案。", (("NEEDS", "CLARIFICATION", "environment missing"), ("ANSWERED", "文件足夠才回覆", "RAG-style context")), "SELF-SERVICE", TEAL),
    Cue(100, 108, "M4", "04 · SUPPORT", "文件不足，建立可追蹤案件", "需要工程判斷的問題會建立 OPEN ticket，而不是帶著零散上下文一路升級。", (("OPEN", "durable work item", "question + trigger + audience"),), "HUMAN ESCALATION", AMBER),
    Cue(108, 115, "M4", "04 · SUPPORT", "模型洩漏由程式邊界攔下", "即使模型回傳內部文件識別碼，validator 仍會 fail safe，外部使用者收到安全替代回覆。", (("FAILED_SAFE", "code validator", "internal identifier detected"), ("NONE", "identifier exposed", "audit stays internal")), "LEAKAGE BLOCKED", CORAL),
    Cue(115, 120, "✓", "VERIFIED AWS POC", "系統處理重複，人負責判斷", "完整程式碼、架構取捨、成本模型與驗證證據，皆收錄於公開專案。", (("AWS", "Serverless · Data · AI", "cost and tenant boundaries included"),), "LEON LAI · 2026", AMBER),
)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def rounded(draw: ImageDraw.ImageDraw, box, radius=24, fill=NIGHT_2, outline=LINE, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def wrapped(draw: ImageDraw.ImageDraw, text: str, chosen_font, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        if current and draw.textlength(candidate, font=chosen_font) > max_width:
            lines.append(current)
            current = char
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def draw_text_block(draw, xy, text, chosen_font, fill, max_width, spacing=14):
    x, y = xy
    for line in wrapped(draw, text, chosen_font, max_width):
        draw.text((x, y), line, font=chosen_font, fill=fill)
        y += chosen_font.size + spacing
    return y


def render(cue: Cue, index: int) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), NIGHT)
    draw = ImageDraw.Draw(image)

    for y in range(HEIGHT):
        ratio = y / HEIGHT
        color = (
            int(6 + ratio * 3),
            int(29 + ratio * 13),
            int(32 + ratio * 14),
        )
        draw.line((0, y, WIDTH, y), fill=color)
    draw.ellipse((1420, -280, 2140, 440), fill="#0c3a3d")
    draw.ellipse((-300, 790, 420, 1510), fill="#092d31")

    rounded(draw, (70, 58, 146, 134), radius=18, fill=AMBER, outline=AMBER)
    draw.text((93, 61), "L", font=font(52, True), fill=NIGHT)
    draw.text((168, 70), "LEON LAI", font=font(29, True), fill=INK)
    draw.text((168, 106), "AWS GAME DATA PLATFORM", font=font(18, True), fill=MUTED)

    timeline = (("M1", 5), ("M3", 30), ("M2", 55), ("M4", 90))
    x0, track_y, track_w = 900, 93, 900
    draw.line((x0, track_y, x0 + track_w, track_y), fill=LINE, width=4)
    for label, start in timeline:
        x = x0 + int(track_w * start / 115)
        active = cue.start >= start
        draw.ellipse((x - 9, track_y - 9, x + 9, track_y + 9), fill=cue.accent if active else LINE)
        draw.text((x - 18, track_y + 20), label, font=font(18, True), fill=INK if active else MUTED)

    draw.text((84, 200), cue.kicker, font=font(24, True), fill=cue.accent)
    title_y = draw_text_block(draw, (84, 248), cue.title, font(62, True), INK, 1170, 16)
    draw_text_block(draw, (88, title_y + 20), cue.caption, font(31), MUTED, 1540, 12)

    card_count = len(cue.cards)
    gap = 26
    card_w = (1752 - gap * (card_count - 1)) // card_count
    card_y0, card_y1 = 600, 874
    for card_index, (value, label, note) in enumerate(cue.cards):
        left = 84 + card_index * (card_w + gap)
        right = left + card_w
        rounded(draw, (left, card_y0, right, card_y1), radius=26, fill="#0b3034", outline=LINE, width=2)
        draw.rectangle((left, card_y0, left + 8, card_y1), fill=cue.accent)
        draw.text((left + 40, card_y0 + 38), value, font=font(56, True), fill=cue.accent)
        draw.text((left + 40, card_y0 + 120), label, font=font(30, True), fill=INK)
        draw_text_block(draw, (left + 40, card_y0 + 176), note, font(22), MUTED, card_w - 80, 8)

    rounded(draw, (84, 916, 1836, 1013), radius=18, fill="#102f32", outline=cue.accent, width=2)
    draw.text((112, 939), cue.status, font=font(26, True), fill=cue.accent)
    draw.text((1810, 939), f"{int(cue.start):02d}–{int(cue.end):02d}s", font=font(20, True), fill=MUTED, anchor="ra")

    progress = cue.end / 120
    draw.rectangle((0, HEIGHT - 10, WIDTH, HEIGHT), fill="#17383b")
    draw.rectangle((0, HEIGHT - 10, int(WIDTH * progress), HEIGHT), fill=cue.accent)
    return image


def timestamp(seconds: float, srt: bool) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    separator = "," if srt else "."
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def write_captions() -> None:
    srt_lines: list[str] = []
    vtt_lines = ["WEBVTT", ""]
    for index, cue in enumerate(CUES, start=1):
        subtitle = f"{cue.title}｜{cue.caption}"
        srt_lines.extend([
            str(index),
            f"{timestamp(cue.start, True)} --> {timestamp(cue.end, True)}",
            subtitle,
            "",
        ])
        vtt_lines.extend([
            f"{timestamp(cue.start, False)} --> {timestamp(cue.end, False)}",
            subtitle,
            "",
        ])
    (OUTPUT_DIR / "demo-overview.zh-TW.srt").write_text("\n".join(srt_lines), encoding="utf-8")
    (OUTPUT_DIR / "demo-overview.zh-TW.vtt").write_text("\n".join(vtt_lines), encoding="utf-8")


def resolve_ffmpeg() -> str:
    if executable := shutil.which("ffmpeg"):
        return executable
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as error:
        raise RuntimeError("Install requirements-video.txt before rendering") from error


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_captions()
    poster = render(CUES[0], 0)
    poster.save(OUTPUT_DIR / "demo-poster.png", optimize=True)

    with tempfile.TemporaryDirectory(prefix="aurora-demo-video-") as temp_name:
        temp = Path(temp_name)
        manifest_lines: list[str] = []
        for index, cue in enumerate(CUES):
            frame = temp / f"frame-{index:02d}.png"
            render(cue, index).save(frame, optimize=True)
            manifest_lines.extend([
                f"file '{frame.as_posix()}'",
                f"duration {cue.end - cue.start:.3f}",
            ])
        manifest_lines.append(f"file '{frame.as_posix()}'")
        manifest = temp / "frames.txt"
        manifest.write_text("\n".join(manifest_lines), encoding="utf-8")

        output = OUTPUT_DIR / "demo-overview.zh-TW.mp4"
        command = [
            resolve_ffmpeg(),
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(manifest),
            "-vf", f"fps={FPS},format=yuv420p",
            "-c:v", "libx264",
            "-preset", "slow",
            "-crf", "27",
            "-movflags", "+faststart",
            "-t", "120",
            "-an",
            str(output),
        ]
        subprocess.run(command, check=True)

    print(f"Rendered {OUTPUT_DIR / 'demo-overview.zh-TW.mp4'}")


if __name__ == "__main__":
    main()
