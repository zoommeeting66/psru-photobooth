"""Mock backend — no extra deps, no GPU.

Produces a representative scene gradient with a subject silhouette so the full
flow (capture → render → branded output) works anywhere. Swapped for `cv` or
`triton` for real segmentation/generation.
"""
from __future__ import annotations

import io

from PIL import Image, ImageDraw

from .base import AIBackend, RenderRequest

GREEN = (14, 122, 75)
GREEN_DEEP = (6, 61, 38)


def _gradient(w: int, h: int) -> Image.Image:
    base = Image.new("RGB", (w, h), GREEN_DEEP)
    top = Image.new("RGB", (w, h), GREEN)
    mask = Image.new("L", (w, h))
    px = mask.load()
    for y in range(h):
        for x in range(0, w, 4):  # coarse step keeps it fast
            v = int(255 * (1 - (x + y) / (w + h)))
            for dx in range(4):
                if x + dx < w:
                    px[x + dx, y] = v
    return Image.composite(top, base, mask)


class MockBackend(AIBackend):
    name = "mock"
    gpu_node = "mock-gpu-0"

    def render(self, req: RenderRequest) -> bytes:
        w, h = req.width, req.height
        img = _gradient(w, h)
        d = ImageDraw.Draw(img, "RGBA")
        cx, cy = w // 2, int(h * 0.46)
        d.ellipse([cx - 70, cy - 130, cx + 70, cy - 10], fill=(255, 255, 255, 40))
        d.ellipse([cx - 110, cy + 0, cx + 110, cy + 220], fill=(255, 255, 255, 30))
        d.text((cx, cy + 250), f"{req.scene_name} (mock)", fill=(255, 255, 255, 220),
               anchor="mm")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
