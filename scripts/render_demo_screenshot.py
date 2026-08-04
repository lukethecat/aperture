#!/usr/bin/env python3
"""Render a terminal-style screenshot from demo output.

Usage:
    python scripts/render_demo_screenshot.py <input.txt> <output.png>
"""

import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Pillow is required: pip install Pillow") from exc


def render(input_path: Path, output_path: Path, width: int = 900, line_height: int = 20) -> None:
    text = input_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    padding = 24
    header = 36
    footer = 20
    height = header + len(lines) * line_height + footer + padding * 2

    # Dark terminal palette
    bg = (30, 30, 35)
    fg = (230, 230, 230)
    prompt_color = (100, 220, 130)
    accent_color = (255, 200, 80)

    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)

    # Try a monospace font, fall back to default
    font = ImageFont.load_default()
    for name in ("consola.ttf", "Consolas.ttf", "cour.ttf", "Courier New.ttf", "DejaVuSansMono.ttf"):
        try:
            font = ImageFont.truetype(name, 14)
            break
        except OSError:
            pass

    # Header bar
    draw.rectangle([0, 0, width, header], fill=(45, 45, 55))
    draw.text((padding, 10), "Aperture — 60 second demo", font=font, fill=accent_color)

    y = padding + header
    for raw_line in lines:
        line = raw_line.rstrip()
        if not line:
            y += line_height
            continue
        color = fg
        if line.startswith("$") or line.startswith("Step"):
            color = prompt_color
        if line.startswith("Aperture") and "demo" in line:
            color = accent_color
        draw.text((padding, y), line, font=font, fill=color)
        y += line_height

    img.save(output_path, "PNG")
    print(f"Saved screenshot to {output_path} ({width}x{height})")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(f"Usage: {sys.argv[0]} <input.txt> <output.png>")
    render(Path(sys.argv[1]), Path(sys.argv[2]))
