#!/usr/bin/env python3
"""Composite raw viewport captures into macOS App window frames.

Input: 2x viewport captures (2880x1800) from headless Chrome.
Output: same file name in this directory (GTM/images/) with a macOS title
bar (traffic lights + centered title), rounded corners and a hairline
border, matching the Enterprise Light design system in design.md.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
IMAGES = ROOT / "images"

SCALE = 2  # raw captures are 2x
BAR_H = 52 * SCALE
RADIUS = 10 * SCALE
TITLE_SIZE = 13 * SCALE

BAR_RGB = (240, 240, 243)      # matches design.md surface tone
BAR_LINE = (216, 216, 221)
BORDER = (198, 198, 206)
TITLE_RGB = (86, 86, 94)
LIGHTS = [(255, 95, 87), (254, 188, 46), (40, 200, 64)]

JOBS = [
    ("console-raw.png", "console.png", "FDE Scope — Engagement Console"),
    ("overview-raw.png", "overview.png", "FDE Scope"),
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for cand in ("/System/Library/Fonts/SFNS.ttf", "/System/Library/Fonts/Helvetica.ttc"):
        try:
            return ImageFont.truetype(cand, size)
        except OSError:
            continue
    return ImageFont.load_default()


def compose(raw: Path, out: Path, title: str) -> None:
    shot = Image.open(raw).convert("RGB")
    w, h = shot.size
    canvas = Image.new("RGBA", (w, h + BAR_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    # window body + title bar, then rounded-corner mask
    canvas.paste(shot, (0, BAR_H))
    draw.rectangle([0, 0, w, BAR_H], fill=BAR_RGB)
    draw.line([0, BAR_H, w, BAR_H], fill=BAR_LINE, width=SCALE)

    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h + BAR_H - 1], RADIUS, fill=255)
    canvas.putalpha(mask)

    # hairline window border
    border = ImageDraw.Draw(canvas)
    border.rounded_rectangle(
        [0, 0, w - 1, h + BAR_H - 1], RADIUS, outline=BORDER + (255,), width=SCALE
    )

    # traffic lights
    cy = BAR_H // 2
    d = 12 * SCALE
    for i, rgb in enumerate(LIGHTS):
        cx = (20 + i * 20) * SCALE
        border.ellipse([cx - d // 2, cy - d // 2, cx + d // 2, cy + d // 2], fill=rgb)
        border.ellipse(
            [cx - d // 2, cy - d // 2, cx + d // 2, cy + d // 2],
            outline=tuple(max(0, c - 35) for c in rgb) + (200,),
            width=SCALE,
        )

    # centered window title
    font = _font(TITLE_SIZE)
    tw = draw.textlength(title, font=font)
    ty = cy - TITLE_SIZE // 2 - SCALE
    draw.text(((w - tw) / 2, ty), title, font=font, fill=TITLE_RGB + (255,))

    canvas.save(out)
    print(f"wrote {out} {canvas.size}")


def main() -> None:
    for raw_name, out_name, title in JOBS:
        compose(IMAGES / raw_name, IMAGES / out_name, title)


if __name__ == "__main__":
    main()
