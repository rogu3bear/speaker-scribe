#!/usr/bin/env python
"""Generate assets/AppIcon.icns.

The icon is drawn from code rather than committed as an opaque binary, so it can
be reviewed, recoloured, and rebuilt from the same brand values the UI uses.

    uv run --extra ml python scripts/make-icon.py

Depends only on numpy, zlib and the macOS iconutil.
"""

from __future__ import annotations

import shutil
import struct
import subprocess
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"

# Straight from src/App.css so the icon and the UI cannot drift apart.
TEAL_LIGHT = (0x17, 0x8B, 0x80)
TEAL_DARK = (0x0B, 0x4F, 0x4B)
AMBER = (0xE0, 0x8A, 0x1E)
WHITE = (0xFF, 0xFF, 0xFF)

# A waveform that visibly changes hands: four bars in one voice, three in
# another. Speaker turns are the thing this app exists to find.
BARS = [0.30, 0.58, 0.88, 0.46, 0.98, 0.66, 0.34]
SPEAKER_TWO_FROM = 4


def rounded_rect(grid_x, grid_y, cx, cy, half_w, half_h, radius):
    """Signed-distance coverage of a rounded rectangle, antialiased."""
    dx = np.abs(grid_x - cx) - (half_w - radius)
    dy = np.abs(grid_y - cy) - (half_h - radius)
    outside = np.hypot(np.maximum(dx, 0), np.maximum(dy, 0))
    inside = np.minimum(np.maximum(dx, dy), 0)
    distance = outside + inside - radius
    return np.clip(0.5 - distance, 0.0, 1.0)


def compose(base, coverage, colour):
    """Alpha-composite a flat colour onto an RGBA float canvas."""
    alpha = coverage[..., None]
    base[..., :3] = base[..., :3] * (1 - alpha) + np.array(colour, dtype=float) * alpha
    base[..., 3] = np.maximum(base[..., 3], coverage)


def draw(size: int) -> np.ndarray:
    y, x = np.mgrid[0:size, 0:size].astype(float)
    canvas = np.zeros((size, size, 4), dtype=float)

    # Apple leaves a margin around the artwork; the squircle radius is a little
    # under a quarter of the tile.
    inset = size * 0.086
    tile = size - 2 * inset
    centre = size / 2
    plate = rounded_rect(x, y, centre, centre, tile / 2, tile / 2, tile * 0.2237)

    gradient = np.clip((y - inset) / tile, 0, 1)[..., None]
    tint = np.array(TEAL_LIGHT, dtype=float) * (1 - gradient) + np.array(
        TEAL_DARK, dtype=float
    ) * gradient
    canvas[..., :3] = tint
    canvas[..., 3] = plate

    count = len(BARS)
    span = tile * 0.62
    bar_w = span / (count * 1.85)
    pitch = span / count
    first = centre - span / 2 + pitch / 2

    for index, height in enumerate(BARS):
        colour = WHITE if index < SPEAKER_TWO_FROM else AMBER
        half_h = max(bar_w * 0.62, tile * 0.30 * height)
        bar = rounded_rect(
            x, y, first + index * pitch, centre, bar_w / 2, half_h, bar_w / 2
        )
        compose(canvas, bar * plate, colour)

    # Coverage is tracked 0..1 while compositing; PNG wants 0..255.
    canvas[..., 3] *= 255
    return np.clip(canvas, 0, 255).astype(np.uint8)


def write_png(path: Path, pixels: np.ndarray) -> None:
    height, width = pixels.shape[:2]
    raw = b"".join(b"\x00" + pixels[row].tobytes() for row in range(height))

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    if shutil.which("iconutil") is None:
        raise SystemExit("iconutil not found; this script needs macOS")

    ASSETS.mkdir(exist_ok=True)
    iconset = ASSETS / "AppIcon.iconset"
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir()

    for base in (16, 32, 128, 256, 512):
        write_png(iconset / f"icon_{base}x{base}.png", draw(base))
        write_png(iconset / f"icon_{base}x{base}@2x.png", draw(base * 2))

    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(ASSETS / "AppIcon.icns")],
        check=True,
    )
    shutil.rmtree(iconset)
    print(f"wrote {ASSETS / 'AppIcon.icns'}")

    # A large preview, handy for a README or a store listing.
    write_png(ASSETS / "AppIcon-1024.png", draw(1024))
    print(f"wrote {ASSETS / 'AppIcon-1024.png'}")


if __name__ == "__main__":
    main()
