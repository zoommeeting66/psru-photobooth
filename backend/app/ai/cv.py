"""CPU backend — real person segmentation + scene compositing (no GPU).

Uses OpenCV GrabCut to cut the subject from the captured photo and alpha-composites
it onto a generated scene background. This is a genuine CV pipeline that runs on a
CPU; production swaps GrabCut for SAM 2 and the gradient background for SDXL via the
`triton` backend. Requires `opencv-python-headless` + `numpy` (requirements-ai.txt).
"""
from __future__ import annotations

import io

from PIL import Image

from .base import AIBackend, RenderRequest
from .mock import _gradient


class CVBackend(AIBackend):
    name = "cv"
    gpu_node = "cpu"

    def render(self, req: RenderRequest) -> bytes:
        import cv2
        import numpy as np

        w, h = req.width, req.height

        # 1) load capture → BGR
        arr = np.frombuffer(req.capture_bytes, np.uint8)
        cap = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if cap is None:  # unreadable upload → fall back to a plain subject card
            cap = np.full((h, w, 3), (60, 90, 70), np.uint8)
        cap = cv2.resize(cap, (w, h))

        # 2) segmentation (GrabCut with a centered foreground rectangle)
        mask = np.zeros((h, w), np.uint8)
        rect = (int(w * 0.18), int(h * 0.08), int(w * 0.64), int(h * 0.9))
        bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
        try:
            cv2.grabCut(cap, mask, rect, bgd, fgd, 5, cv2.GC_INIT_WITH_RECT)
            fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
        except cv2.error:
            fg = np.zeros((h, w), np.uint8)
            cv2.rectangle(fg, (rect[0], rect[1]), (rect[0] + rect[2], rect[1] + rect[3]), 255, -1)
        fg = cv2.GaussianBlur(fg, (7, 7), 0)  # soften edges

        # 3) scene background (gradient placeholder; SDXL in triton backend)
        bg = np.array(_gradient(w, h))[:, :, ::-1].copy()  # RGB→BGR

        # 4) alpha composite subject over background
        alpha = (fg.astype(np.float32) / 255.0)[:, :, None]
        cap_rgb = cap.astype(np.float32)
        bg_rgb = bg.astype(np.float32)
        out = (cap_rgb * alpha + bg_rgb * (1 - alpha)).astype(np.uint8)

        out_rgb = cv2.cvtColor(out, cv2.COLOR_BGR2RGB)
        buf = io.BytesIO()
        Image.fromarray(out_rgb).save(buf, format="PNG")
        return buf.getvalue()
