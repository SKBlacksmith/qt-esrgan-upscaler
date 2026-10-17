# SPDX-FileCopyrightText: 2026 Sergey Kuznetsov (SKBlacksmith)
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate the application icon: monochrome 'window in a window' (1:2:4).

Three nested windows, the inner ones anchored to the bottom-right corner almost
flush, so the icon reads as picture-in-picture / zooming into a stack.

Sizes 32 px and up use all three levels; 16-24 px use a simplified two-level
form with heavier strokes, because a third level degrades into a dot.

Requires cairosvg (development only):
    uv run --with cairosvg python tools/make_icons.py
"""

from __future__ import annotations

import os
from pathlib import Path

BASE = "#1a1a1a"
ROOT = Path(__file__).resolve().parent.parent
PACKAGING = ROOT / "packaging"
SIZES_FULL = (32, 48, 64, 128, 256, 512)
SIZES_SMALL = (16, 22, 24)


def _rect(x, y, w, h, sw, dots=False, bar=True, dot_scale=1.0):
    rx = w * 0.09
    parts = [
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{rx:.2f}" '
        f'fill="none" stroke="{BASE}" stroke-width="{sw:.2f}"/>'
    ]
    if bar:
        bar_h = h * 0.20
        parts.append(
            f'<line x1="{x:.2f}" y1="{y + bar_h:.2f}" x2="{x + w:.2f}" y2="{y + bar_h:.2f}" '
            f'stroke="{BASE}" stroke-width="{max(3.0, sw * 0.55):.2f}"/>'
        )
        if dots:
            d = w * 0.022 * dot_scale
            for i in range(3):
                parts.append(
                    f'<circle cx="{x + rx * 0.9 + i * d * 3.2:.2f}" cy="{y + bar_h / 2:.2f}" '
                    f'r="{d:.2f}" fill="{BASE}"/>'
                )
    return "".join(parts)


def pip_svg(levels: int = 3, strokes=(12, 9, 7), dots: bool = True,
            bars=(True, True, True)) -> str:
    """Three (or two) nested windows, inner ones anchored bottom-right."""
    geo = {
        3: ((48.0, 106.0, 416.0, 300.0), (240.0, 240.0, 208.0, 150.0), (330.0, 301.0, 104.0, 75.0)),
        2: ((48.0, 106.0, 416.0, 300.0), (240.0, 240.0, 208.0, 150.0)),
    }[levels]
    parts = []
    for i, (x, y, w, h) in enumerate(geo):
        parts.append(_rect(x, y, w, h, strokes[i], dots=dots and i == 0, bar=bars[i]))
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" '
            'viewBox="0 0 512 512">' + "".join(parts) + "</svg>")


def main() -> None:
    import cairosvg

    full = pip_svg(3)
    small = pip_svg(2, strokes=(44, 40), dots=False, bars=(True, False))
    (PACKAGING / "qt-esrgan-upscaler.svg").write_text(full + "\n")

    for size in SIZES_FULL + SIZES_SMALL:
        svg = small if size in SIZES_SMALL else full
        out = PACKAGING / "icons" / "hicolor" / f"{size}x{size}" / "apps" / "qt-esrgan-upscaler.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        cairosvg.svg2png(bytestring=svg.encode(), write_to=str(out),
                         output_width=size, output_height=size)
        print(f"{size:>3}px  {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
