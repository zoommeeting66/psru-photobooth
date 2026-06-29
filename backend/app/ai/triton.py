"""Triton backend — real models served by NVIDIA Triton Inference Server (GPU).

Pipeline: SAM 2 (segmentation) → SDXL + ControlNet (scene generation, conditioned
on the subject depth/pose) → IC-Light (relighting to match the scene) → IP-Adapter
(outfit). Requires a running Triton with these models loaded and
`tritonclient[http]` + `numpy` + `opencv-python-headless` installed
(requirements-ai.txt), on a GPU host.

The structure below is production-shaped; wire each `_infer_*` to your exported
model's input/output tensor names. It is intentionally not exercised by the CPU
test suite (no GPU/Triton in CI).
"""
from __future__ import annotations

import io

from PIL import Image

from ..config import get_settings
from .base import AIBackend, RenderRequest

settings = get_settings()


class TritonBackend(AIBackend):
    name = "triton"
    gpu_node = "triton"

    def __init__(self) -> None:
        try:
            import tritonclient.http as http  # noqa: F401
        except ImportError as e:  # pragma: no cover - GPU host only
            raise RuntimeError(
                "triton backend requires tritonclient — pip install -r requirements-ai.txt"
            ) from e
        import tritonclient.http as http

        self._http = http
        self._client = http.InferenceServerClient(url=settings.triton_url)

    # --- per-stage model calls (fill in tensor names for your exported models) ---
    def _infer(self, model: str, inputs: list, outputs: list):  # pragma: no cover
        return self._client.infer(model_name=model, inputs=inputs, outputs=outputs)

    def _segment(self, bgr):  # SAM 2 → alpha matte  # pragma: no cover
        raise NotImplementedError("map SAM2 I/O tensors")

    def _generate_scene(self, matte, prompt):  # SDXL+ControlNet  # pragma: no cover
        raise NotImplementedError("map SDXL+ControlNet I/O tensors")

    def _relight(self, img, scene):  # IC-Light  # pragma: no cover
        raise NotImplementedError("map IC-Light I/O tensors")

    def _outfit(self, img, outfit):  # IP-Adapter  # pragma: no cover
        raise NotImplementedError("map IP-Adapter I/O tensors")

    def render(self, req: RenderRequest) -> bytes:  # pragma: no cover - GPU host
        import cv2
        import numpy as np

        arr = np.frombuffer(req.capture_bytes, np.uint8)
        bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)

        matte = self._segment(bgr)
        scene = self._generate_scene(matte, req.scene_prompt or req.scene_name)
        lit = self._relight(scene, req.scene_name)
        final = self._outfit(lit, req.outfit_name) if req.outfit_name else lit

        rgb = cv2.cvtColor(final, cv2.COLOR_BGR2RGB)
        buf = io.BytesIO()
        Image.fromarray(rgb).save(buf, format="PNG")
        return buf.getvalue()
