"""Render the two-minute operation-only demo from browser captures.

The source screenshots in demo_console/recording are produced by operating the
localhost console. Architecture views are intentionally excluded: this video
shows only the four user-facing functions and their governed outcomes.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
CAPTURE_DIR = ROOT / "demo_console" / "recording"
OUTPUT_DIR = ROOT / "site" / "video"
WIDTH, HEIGHT = 1920, 1080
SCREEN_WIDTH, SCREEN_HEIGHT = WIDTH, HEIGHT
SCREEN_X = (WIDTH - SCREEN_WIDTH) // 2
FPS = 24

BG = "#030b13"
INK = "#f3f7fb"
MUTED = "#9aafc3"
TEAL = "#3dd6c6"
AMBER = "#f5b942"
CORAL = "#ff6b72"
LINE = "#29425a"
FONT_REGULAR = Path("C:/Windows/Fonts/msjh.ttc")
FONT_BOLD = Path("C:/Windows/Fonts/msjhbd.ttc")


@dataclass(frozen=True)
class Scene:
    start: float
    end: float
    chapter: str
    caption: str
    caption_en: str
    capture: str | None = None
    click: tuple[int, int] | None = None
    card_title: str | None = None
    card_subtitle: str | None = None
    accent: str = TEAL


SCENES = (
    Scene(0, 9, "01 · 異常監控", "上午 11:00，系統偵測到 site_b 活躍人數低於正常範圍。", "At 11:00 AM, the system detects that site_b's active-user count is below its normal range.", "m1-initial.png", accent=CORAL),
    Scene(9, 17, "01 · 異常監控", "系統建立告警證據，並透過 SNS 發布值班通知。", "The system records the alert evidence and sends an on-call notification through SNS.", "m1-initial.png", accent=CORAL),
    Scene(17, 25, "01 · 異常監控", "值班人員開始排查，事件進入處理中（排查中）。", "The on-call engineer begins investigating, and the incident moves to Investigating.", "m1-result.png", accent=CORAL),
    Scene(25, 35, "02 · 分析助理", "下午 1:00，業務看到人數下降，直接詢問：今天人數為何掉這麼多？", "At 1:00 PM, the business team sees the decline and asks: Why did today's user count fall so much?", "m3-initial.png"),
    Scene(35, 50, "02 · 分析助理", "助理比較今天 124 人與過去 30 天平均 177 人，並說明 11:00 已告警、技術人員正在排查。", "The assistant compares today's 124 users with the 30-day average of 177, then explains that an alert fired at 11:00 and engineers are investigating.", "m3-result.png"),
    Scene(50, 60, "02 · 分析助理", "再問明天是否恢復時，助理說明尚無經過驗證的預測模型，不猜測未來。", "When asked whether usage will recover tomorrow, the assistant says there is no validated forecast model and does not speculate.", "m3-forecast.png", accent=CORAL),
    Scene(60, 75, "03 · 實驗治理", "管理者能在同一畫面掌握每個實驗的進度、健康狀態、流量與配置。", "Managers can monitor every experiment's progress, health, traffic, and configuration in one view.", "m2-all.png", accent=AMBER),
    Scene(75, 90, "03 · 實驗治理", "若觸發預先設定的 SRM 或 Guardrail 停止條件，系統會自動停止實驗並關閉流量配置。", "If a predefined SRM or guardrail stop condition is triggered, the system automatically stops the experiment and disables its traffic allocation.", "m2-action.png", accent=CORAL),
    Scene(90, 100, "04 · 整合支援", "合作夥伴直接貼上完整 Token API Request 與 400 錯誤回應。", "The partner pastes the complete Token API request and its 400 error response.", "m4-input.png"),
    Scene(100, 110, "04 · 整合支援", "助理依文件找出 Content-Type 錯誤，並指出缺少 grant_type。", "Using the documentation, the assistant identifies an incorrect Content-Type and a missing grant_type.", "m4-result.png"),
    Scene(110, 120, "04 · 整合支援", "參展資訊不在整合知識庫中；系統不編造答案，改為引導聯絡業務窗口。", "Exhibition details are outside the integration knowledge base, so the system does not invent an answer and directs the partner to a sales contact.", "m4-out-of-scope.png", accent=CORAL),
)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), size)


def fit_text(draw: ImageDraw.ImageDraw, text: str, chosen_font, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for character in text:
        candidate = current + character
        if current and draw.textlength(candidate, font=chosen_font) > max_width:
            lines.append(current)
            current = character
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def capture_image(filename: str) -> Image.Image:
    path = CAPTURE_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing real browser capture: {path}")
    image = Image.open(path).convert("RGB")
    if image.size != (1280, 720):
        raise ValueError(f"Unexpected capture size for {path}: {image.size}")
    return image.resize((SCREEN_WIDTH, SCREEN_HEIGHT), Image.Resampling.LANCZOS)


def add_cursor(draw: ImageDraw.ImageDraw, point: tuple[int, int], accent: str) -> None:
    x = SCREEN_X + round(point[0] * SCREEN_WIDTH / 1280)
    y = round(point[1] * SCREEN_HEIGHT / 720)
    draw.ellipse((x - 28, y - 28, x + 28, y + 28), outline=accent, width=5)
    draw.ellipse((x - 13, y - 13, x + 13, y + 13), fill=accent)
    draw.polygon(((x + 12, y + 14), (x + 39, y + 43), (x + 22, y + 48)), fill=INK)


def render_capture(scene: Scene) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    image.paste(capture_image(scene.capture or ""), (SCREEN_X, 0))
    draw = ImageDraw.Draw(image)
    if scene.click:
        add_cursor(draw, scene.click, scene.accent)
    return image


def render_card(scene: Scene) -> Image.Image:
    background = capture_image("m1-result.png")
    background = ImageEnhance.Brightness(background).enhance(0.25)
    background = background.filter(ImageFilter.GaussianBlur(9))
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    image.paste(background, (SCREEN_X, 0))
    overlay = Image.new("RGBA", image.size, (3, 11, 19, 175))
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((185, 190, 1735, 820), radius=35, fill="#071725", outline=scene.accent, width=3)
    draw.rounded_rectangle((250, 256, 332, 338), radius=19, fill=scene.accent)
    draw.text((276, 251), "L", font=font(56, True), fill=BG)
    draw.text((365, 260), "AWS GAME DATA PLATFORM", font=font(28, True), fill=MUTED)
    draw.text((250, 405), scene.card_title or "", font=font(62, True), fill=INK)
    draw.text((252, 505), scene.card_subtitle or "", font=font(33), fill=MUTED)
    draw.line((250, 600, 1668, 600), fill=LINE, width=2)
    draw.text((250, 640), "LIVE AWS · ap-northeast-1", font=font(24, True), fill=scene.accent)
    draw.text((1668, 640), "LEON LAI · 2026", font=font(24, True), fill=INK, anchor="ra")
    return image


def timestamp(seconds: float, srt: bool) -> str:
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    separator = "," if srt else "."
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def write_captions() -> None:
    for language, caption_field in (("zh-TW", "caption"), ("en", "caption_en")):
        srt_lines: list[str] = []
        vtt_lines = ["WEBVTT", ""]
        for index, scene in enumerate(SCENES, start=1):
            caption = getattr(scene, caption_field)
            srt_lines.extend((str(index), f"{timestamp(scene.start, True)} --> {timestamp(scene.end, True)}", caption, ""))
            vtt_lines.extend((f"{timestamp(scene.start, False)} --> {timestamp(scene.end, False)}", caption, ""))
        (OUTPUT_DIR / f"demo-overview.{language}.srt").write_text("\n".join(srt_lines), encoding="utf-8")
        (OUTPUT_DIR / f"demo-overview.{language}.vtt").write_text("\n".join(vtt_lines), encoding="utf-8")


def resolve_ffmpeg() -> str:
    if executable := shutil.which("ffmpeg"):
        return executable
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_captions()
    with tempfile.TemporaryDirectory(prefix="leon-operation-demo-") as temp_name:
        temp = Path(temp_name)
        manifest_lines: list[str] = []
        last_frame: Path | None = None
        for index, scene in enumerate(SCENES):
            frame = temp / f"scene-{index:02d}.png"
            rendered = render_card(scene) if scene.card_title else render_capture(scene)
            rendered.save(frame, optimize=True)
            manifest_lines.extend((f"file '{frame.as_posix()}'", f"duration {scene.end - scene.start:.3f}"))
            last_frame = frame
            if index == 0:
                rendered.resize((1280, 720), Image.Resampling.LANCZOS).save(OUTPUT_DIR / "demo-poster.png", optimize=True)
        if last_frame:
            manifest_lines.append(f"file '{last_frame.as_posix()}'")
        manifest = temp / "scenes.txt"
        manifest.write_text("\n".join(manifest_lines), encoding="utf-8")
        output = OUTPUT_DIR / "demo-overview.mp4"
        subprocess.run(
            [
                resolve_ffmpeg(), "-y", "-f", "concat", "-safe", "0", "-i", str(manifest),
                "-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264", "-preset", "slow",
                "-crf", "25", "-movflags", "+faststart", "-t", "120", "-an", str(output),
            ],
            check=True,
        )
    print(f"Rendered operation demo: {output}")


if __name__ == "__main__":
    main()
