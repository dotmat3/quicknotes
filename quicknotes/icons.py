"""Icona dell'app per finestra e area di notifica: foglio con righe di testo; pallino bianco su rosso mentre registra."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw

SIZES = (16, 20, 24, 32, 40, 48, 64, 256)


@lru_cache(maxsize=4)
def app_icon(recording: bool = False, size: int = 256) -> Image.Image:
    scale = 4  # disegnata piu' grande e poi ridotta: bordi morbidi
    s = size * scale
    u = s / 64  # unita' della griglia 64x64
    top, bottom = ((0xE5, 0x52, 0x3F), (0xB7, 0x2F, 0x26)) if recording else ((0xDF, 0x73, 0x50), (0xBB, 0x4A, 0x2F))
    gradient = Image.new("RGB", (1, s))
    for y in range(s):
        t = y / max(s - 1, 1)
        gradient.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    gradient = gradient.resize((s, s))
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((4 * u, 4 * u, 60 * u, 60 * u), radius=14 * u, fill=255)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    img.paste(gradient, (0, 0), mask)
    draw = ImageDraw.Draw(img)
    if recording:
        draw.ellipse((21 * u, 21 * u, 43 * u, 43 * u), fill="white")
    else:
        for y, w in ((21, 30), (31, 30), (41, 18)):
            draw.rounded_rectangle((17 * u, (y - 2.5) * u, (17 + w) * u, (y + 2.5) * u), radius=2.5 * u, fill="white")
    return img.resize((size, size), Image.LANCZOS)


def write_ico(path: Path, recording: bool = False) -> Path:
    """File .ico multi-risoluzione (per la barra del titolo e delle applicazioni di Windows)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    app_icon(recording).save(path, format="ICO", sizes=[(n, n) for n in SIZES])
    return path
