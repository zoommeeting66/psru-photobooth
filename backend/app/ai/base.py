"""AI backend interface + shared pipeline stages."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

# Ordered pipeline stages (mirrors docs/04-ai-workflow.md). `needs_bio` stages are
# skipped when the user did not give biometric consent. "branding" runs after these.
STAGES: list[tuple[str, str, bool]] = [
    ("segmentation", "Segmentation (SAM 2)", False),
    ("face_pose", "Face & Pose", True),
    ("scene_generate", "Scene Generate (SDXL)", False),
    ("relight", "Relighting (IC-Light)", False),
    ("perspective", "Perspective Match", False),
    ("beauty", "Beauty Enhance", False),
    ("outfit", "AI Outfit", False),
]


@dataclass
class RenderRequest:
    capture_bytes: bytes
    scene_name: str
    scene_prompt: Optional[str] = None      # positive prompt for diffusion backends
    scene_asset_key: Optional[str] = None   # background/HDRI key (cv/triton)
    outfit_name: Optional[str] = None
    fx: dict = field(default_factory=dict)
    biometric_ok: bool = False
    width: int = 1200
    height: int = 900


class AIBackend(ABC):
    """Produces the composited base image (scene + subject). Branding is added later.

    `render` is synchronous and may be CPU/GPU heavy; the orchestrator runs it via
    `asyncio.to_thread(...)` so the event loop is never blocked.
    """

    name: str = "base"
    gpu_node: str = "cpu"

    @abstractmethod
    def render(self, req: RenderRequest) -> bytes:
        """Return PNG bytes of the composited base image (scene + subject)."""
        raise NotImplementedError
