"""Generate dependency-free PNG app icons for the PWA (stdlib only)."""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "app" / "static" / "images"
OUT.mkdir(parents=True, exist_ok=True)


def png_chunk(tag: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def write_png(path: Path, width: int, pixels: bytearray) -> None:
    raw = b"".join(b"\x00" + bytes(pixels[y * width * 4:(y + 1) * width * 4])
                   for y in range(width))
    data = (b"\x89PNG\r\n\x1a\n"
            + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, width, 8, 6, 0, 0, 0))
            + png_chunk(b"IDAT", zlib.compress(raw, 9))
            + png_chunk(b"IEND", b""))
    path.write_bytes(data)


def icon(size: int, maskable: bool = False) -> bytearray:
    px = bytearray(size * size * 4)
    radius = 0 if maskable else int(size * 0.22)
    inset = 0 if maskable else int(size * 0.02)

    def set_pixel(x, y, color):
        if 0 <= x < size and 0 <= y < size:
            i = (y * size + x) * 4
            px[i:i + 4] = bytes(color)

    def rounded_inside(x, y):
        if maskable:
            return True
        r = radius
        cx = min(max(x, inset + r), size - 1 - inset - r)
        cy = min(max(y, inset + r), size - 1 - inset - r)
        return (x - cx) ** 2 + (y - cy) ** 2 <= r ** 2

    for y in range(size):
        for x in range(size):
            if not rounded_inside(x, y):
                set_pixel(x, y, (0, 0, 0, 0))
                continue
            t = (x + y) / (2 * size)
            color = (int(37 + 20 * t), int(99 + 40 * t), int(235 - 10 * t), 255)
            set_pixel(x, y, color)

    # White book with two pages and a centre spine.
    left, right = int(size * 0.20), int(size * 0.80)
    top, bottom = int(size * 0.34), int(size * 0.67)
    for y in range(top, bottom):
        for x in range(left, right):
            if rounded_inside(x, y):
                spine = abs(x - size // 2) <= max(1, size // 80)
                set_pixel(x, y, (37, 99, 235, 255) if spine else (255, 255, 255, 255))
    # Page lines.
    for line in range(3):
        y = int(size * (0.42 + line * 0.07))
        for x in range(int(size * 0.27), int(size * 0.45)):
            set_pixel(x, y, (147, 197, 253, 255))
        for x in range(int(size * 0.55), int(size * 0.73)):
            set_pixel(x, y, (147, 197, 253, 255))
    # Bookmark ribbon on the top-right page.
    bx = int(size * 0.68)
    for y in range(top - int(size * 0.10), top + 1):
        for x in range(bx, bx + max(2, int(size * 0.05))):
            set_pixel(x, y, (16, 185, 129, 255))
    return px


for size, name, maskable in [
    (192, "icon-192.png", False),
    (512, "icon-512.png", False),
    (512, "icon-maskable-512.png", True),
]:
    write_png(OUT / name, size, icon(size, maskable))
    print("Generated", OUT / name)
