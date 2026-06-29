"""Branding Engine — composes the final branded image + thumbnail + QR.

Phase 1 renders a representative branded canvas with PIL (no GPU). It applies
the PSRU frame, logo placeholder, event title, running image number, the
mandatory "AI-generated" watermark, and a QR code. The same compositor will
sit at the end of the real diffusion pipeline in Phase 2.
"""
from __future__ import annotations

import io

import qrcode
from PIL import Image, ImageDraw, ImageFont

PSRU_GREEN = (14, 122, 75)
PSRU_GREEN_DEEP = (6, 61, 38)
GOLD = (201, 162, 39)
WHITE = (255, 255, 255)


def _font(size: int):
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _gradient(w: int, h: int) -> Image.Image:
    base = Image.new("RGB", (w, h), PSRU_GREEN_DEEP)
    top = Image.new("RGB", (w, h), PSRU_GREEN)
    mask = Image.new("L", (w, h))
    md = mask.load()
    for y in range(h):
        for x in range(0, w, 4):  # coarse step keeps it fast
            v = int(255 * (1 - (x + y) / (w + h)))
            for dx in range(4):
                if x + dx < w:
                    md[x + dx, y] = v
    return Image.composite(top, base, mask)


def apply_branding(
    base_png: bytes,
    *,
    scene_name: str,
    event_title: str,
    image_no: str,
    outfit_name: str | None,
    share_url: str,
    show_qr: bool = True,
) -> tuple[bytes, bytes]:
    """Overlay PSRU branding onto an AI-composited base image.

    `base_png` is the scene+subject image produced by an AI backend (app/ai/*).
    Returns (final_png_bytes, thumb_png_bytes).
    """
    img = Image.open(io.BytesIO(base_png)).convert("RGB")
    width, height = img.size
    d = ImageDraw.Draw(img, "RGBA")
    cx, cy = width // 2, int(height * 0.46)

    # top branding bar
    d.rectangle([0, 0, width, 70], fill=(6, 61, 38, 180))
    d.rectangle([24, 16, 64, 56], fill=GOLD)
    d.text((44, 36), "P", font=_font(30), fill=PSRU_GREEN_DEEP, anchor="mm")
    d.text((80, 36), event_title, font=_font(24), fill=WHITE, anchor="lm")
    d.text((width - 24, 36), scene_name, font=_font(20), fill=GOLD, anchor="rm")

    # bottom bar
    d.rectangle([0, height - 64, width, height], fill=(6, 61, 38, 180))
    tagline = "PSRU Next & New For All"
    if outfit_name:
        tagline += f"  ·  {outfit_name}"
    d.text((24, height - 32), tagline, font=_font(20), fill=WHITE, anchor="lm")
    d.text((width - 24, height - 32), f"No. {image_no}", font=_font(20),
           fill=GOLD, anchor="rm")

    # mandatory transparency watermark (visible)
    d.text((cx, cy), "PSRU · AI-generated", font=_font(40),
           fill=(255, 255, 255, 35), anchor="mm")

    # QR
    if show_qr and share_url:
        qr = qrcode.make(share_url).convert("RGB").resize((120, 120))
        img.paste(qr, (width - 150, height - 64 - 140))

    final_buf = io.BytesIO()
    img.save(final_buf, format="PNG")

    thumb = img.copy()
    thumb.thumbnail((360, 270))
    thumb_buf = io.BytesIO()
    thumb.save(thumb_buf, format="PNG")

    return final_buf.getvalue(), thumb_buf.getvalue()


def make_qr(data: str) -> bytes:
    buf = io.BytesIO()
    qrcode.make(data).save(buf, format="PNG")
    return buf.getvalue()
