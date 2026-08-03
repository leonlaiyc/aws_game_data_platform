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
SCREEN_WIDTH, SCREEN_HEIGHT = 1728, 972
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
    capture: str | None = None
    click: tuple[int, int] | None = None
    card_title: str | None = None
    card_subtitle: str | None = None
    accent: str = TEAL


SCENES = (
    Scene(0, 15, "01 · 異常監控", "今天截至 13:00 的累積活躍人數為 2,180；過去 30 天相同時間平均為 3,650。", "m1-initial.png", accent=CORAL),
    Scene(15, 25, "01 · 異常監控", "系統已在 11:00 告警，負責人將處理狀態更新為排查中。", "m1-result.png", accent=CORAL),
    Scene(25, 40, "02 · 實驗治理", "中央控制台同時呈現執行中、需要處理與草稿實驗。", "m2-all.png", accent=AMBER),
    Scene(40, 53, "02 · 實驗治理", "SRM 先檢查分流；通過後才看 Guardrail，失敗時停止實驗並關閉 Allocation。", "m2-action.png", accent=CORAL),
    Scene(53, 65, "03 · 分析助理", "營運人員直接詢問：今天人數為何突然掉這麼多？", "m3-initial.png"),
    Scene(65, 78, "03 · 分析助理", "回答只呈現 30 天比較、下降幅度與目前排查進度，原因未確認。", "m3-result.png"),
    Scene(78, 88, "03 · 分析助理", "追問明天是否恢復時，系統說明沒有經過驗證的預測模型，不猜測答案。", "m3-forecast.png", accent=CORAL),
    Scene(88, 99, "04 · 整合支援", "合作夥伴直接貼上完整 Token API Request 與 400 錯誤回應。", "m4-input.png"),
    Scene(99, 110, "04 · 整合支援", "助理依文件找出 Content-Type 錯誤，並指出缺少 grant_type。", "m4-result.png"),
    Scene(110, 120, "04 · 整合支援", "參展資訊不在整合知識庫中；系統不編造答案，改為引導聯絡業務窗口。", "m4-out-of-scope.png", accent=CORAL),
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


def add_footer(draw: ImageDraw.ImageDraw, scene: Scene) -> None:
    top = SCREEN_HEIGHT
    draw.rectangle((0, top, WIDTH, HEIGHT), fill="#071420")
    draw.line((0, top, WIDTH, top), fill=LINE, width=2)
    draw.text((SCREEN_X, top + 18), scene.chapter, font=font(22, True), fill=scene.accent)
    caption_font = font(31, True)
    caption_lines = fit_text(draw, scene.caption, caption_font, WIDTH - SCREEN_X * 2 - 280)
    for index, line in enumerate(caption_lines[:2]):
        draw.text((SCREEN_X + 300, top + 13 + index * 39), line, font=caption_font, fill=INK)
    progress = scene.end / 120
    draw.rectangle((0, HEIGHT - 8, WIDTH, HEIGHT), fill="#162c3d")
    draw.rectangle((0, HEIGHT - 8, round(WIDTH * progress), HEIGHT), fill=scene.accent)


def render_capture(scene: Scene) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    image.paste(capture_image(scene.capture or ""), (SCREEN_X, 0))
    draw = ImageDraw.Draw(image)
    if scene.click:
        add_cursor(draw, scene.click, scene.accent)
    add_footer(draw, scene)
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
    add_footer(draw, scene)
    return image


def timestamp(seconds: float, srt: bool) -> str:
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    separator = "," if srt else "."
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def write_captions() -> None:
    srt_lines: list[str] = []
    vtt_lines = ["WEBVTT", ""]
    for index, scene in enumerate(SCENES, start=1):
        srt_lines.extend((str(index), f"{timestamp(scene.start, True)} --> {timestamp(scene.end, True)}", scene.caption, ""))
        vtt_lines.extend((f"{timestamp(scene.start, False)} --> {timestamp(scene.end, False)}", scene.caption, ""))
    (OUTPUT_DIR / "demo-overview.zh-TW.srt").write_text("\n".join(srt_lines), encoding="utf-8")
    (OUTPUT_DIR / "demo-overview.zh-TW.vtt").write_text("\n".join(vtt_lines), encoding="utf-8")


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
        output = OUTPUT_DIR / "demo-overview.zh-TW.mp4"
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
