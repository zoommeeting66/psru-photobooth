"""AI render backends (pluggable).

Selected by `AI_BACKEND` (config):
- ``mock``   — no extra deps; simulated stages + placeholder composite (default)
- ``cv``     — OpenCV/CPU: real person segmentation (GrabCut) + scene compositing
               (`pip install -r requirements-ai.txt`; no GPU)
- ``triton`` — real diffusion/segmentation models served by NVIDIA Triton (GPU host)

All backends implement `AIBackend.render(...)` and report per-stage progress via a
callback, so the orchestrator (`app/pipeline.py`) and the WebSocket stay unchanged.
"""
from __future__ import annotations

from ..config import get_settings
from .base import AIBackend, STAGES

_settings = get_settings()
_backend: AIBackend | None = None


def get_backend() -> AIBackend:
    global _backend
    if _backend is None:
        name = (_settings.ai_backend or "mock").lower()
        if name == "triton":
            from .triton import TritonBackend

            _backend = TritonBackend()
        elif name == "cv":
            from .cv import CVBackend

            _backend = CVBackend()
        else:
            from .mock import MockBackend

            _backend = MockBackend()
    return _backend


__all__ = ["AIBackend", "STAGES", "get_backend"]
