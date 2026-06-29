"""AI Orchestrator — runs a render job through the pipeline.

Stages run on the selected AI backend (`app/ai/`): ``mock`` (default, no GPU),
``cv`` (OpenCV/CPU segmentation + compositing), or ``triton`` (real SAM2 /
SDXL+ControlNet / IC-Light / IP-Adapter on a GPU host). The backend produces the
composited scene+subject image; the Branding Engine then overlays PSRU branding.
Per-stage progress is published to the WebSocket hub regardless of backend.
"""
from __future__ import annotations

import asyncio
import secrets
from datetime import timedelta

from . import branding, storage
from .ai import STAGES as AI_STAGES, get_backend
from .ai.base import RenderRequest
from .config import get_settings
from .events import hub
from .db import SessionLocal, new_uuid, utcnow
from .models import (
    AIPrompt,
    BrandingTemplate,
    Capture,
    Event,
    Output,
    Outfit,
    RenderJob,
    Scene,
    Session,
)

settings = get_settings()

# Display stages = AI stages + the Branding Engine (for progress reporting)
STAGES = list(AI_STAGES) + [("branding", "Branding Engine", False)]


class GuardrailError(Exception):
    """Raised when content guardrails reject a job (→ HTTP 422)."""


def _snapshot(job: RenderJob, output_id: str | None = None) -> dict:
    return {
        "id": job.id,
        "status": job.status,
        "progress": job.progress,
        "stage": job.stage,
        "pipeline_steps": dict(job.pipeline_steps or {}),
        "output_id": output_id,
        "error": job.error,
    }


def check_guardrails(scene: Scene, fx: dict) -> None:
    # Symbolic-restricted scenes are allowed but constrained; deepfake/
    # impersonation requests are rejected outright.
    if fx.get("impersonate") or fx.get("deepfake"):
        raise GuardrailError("impersonation_not_allowed")


async def run_render_job(job_id: str, biometric_ok: bool = False) -> None:
    """Background/worker task: advance a job to completion and create its Output."""
    backend = get_backend()
    is_mock = backend.name == "mock"
    delay = (settings.pipeline_stage_delay_ms / 1000.0) if is_mock else 0.0
    started = utcnow()
    total = len(STAGES)

    async with SessionLocal() as db:
        job = await db.get(RenderJob, job_id)
        if job is None:
            return
        capture = await db.get(Capture, job.capture_id)
        scene = await db.get(Scene, job.scene_id) if job.scene_id else None
        outfit = await db.get(Outfit, job.outfit_id) if job.outfit_id else None
        prompt = (
            await db.get(AIPrompt, scene.ai_prompt_id)
            if scene and scene.ai_prompt_id
            else None
        )

        try:
            if scene is not None:
                check_guardrails(scene, job.fx or {})

            job.status = "running"
            job.gpu_node = backend.gpu_node
            steps: dict = {}

            # 1) AI stages — progress markers (real heavy work happens in 2)
            for i, (key, label, needs_bio) in enumerate(AI_STAGES, start=1):
                if needs_bio and not biometric_ok:
                    steps[key] = {"status": "skipped", "reason": "no_biometric_consent"}
                else:
                    if delay:
                        await asyncio.sleep(delay)
                    steps[key] = {"status": "done"}
                job.stage = label
                job.progress = int(i / total * 100)
                job.pipeline_steps = dict(steps)
                await db.commit()
                hub.publish(job.id, _snapshot(job))

            # 2) run the backend (off the event loop — may be CPU/GPU heavy)
            req = RenderRequest(
                capture_bytes=storage.read_bytes(capture.storage_key) if capture else b"",
                scene_name=scene.name if scene else "PSRU",
                scene_prompt=prompt.positive_prompt if prompt else None,
                scene_asset_key=scene.thumbnail_key if scene else None,
                outfit_name=outfit.name if outfit else None,
                fx=job.fx or {},
                biometric_ok=biometric_ok,
            )
            base_png = await asyncio.to_thread(backend.render, req)

            # 3) Branding Engine overlay
            session = await db.get(Session, capture.session_id) if capture else None
            event = (
                await db.get(Event, session.event_id)
                if session and session.event_id
                else None
            )
            event_title = event.name if event else "PSRU Virtual Photo Booth"
            branding_tpl = (
                await db.get(BrandingTemplate, job.branding_id)
                if job.branding_id
                else None
            )
            show_qr = branding_tpl.show_qr if branding_tpl else True

            image_no = f"{secrets.randbelow(9999):04d}"
            share_token = secrets.token_urlsafe(12)
            share_url = f"{settings.public_base_url.rstrip('/')}/s/{share_token}"

            final_bytes, thumb_bytes = branding.apply_branding(
                base_png,
                scene_name=scene.name if scene else "PSRU",
                event_title=event_title,
                image_no=image_no,
                outfit_name=outfit.name if outfit else None,
                share_url=share_url,
                show_qr=show_qr,
            )

            out_id = new_uuid()
            final_key = f"outputs/{out_id}/final.png"
            thumb_key = f"outputs/{out_id}/thumb.png"
            storage.save_bytes(final_key, final_bytes)
            storage.save_bytes(thumb_key, thumb_bytes)

            db.add(Output(
                id=out_id,
                render_job_id=job.id,
                branding_id=job.branding_id,
                image_no=image_no,
                final_key=final_key,
                thumb_key=thumb_key,
                formats={"png": final_key},
                share_token=share_token,
                expires_at=utcnow() + timedelta(days=settings.output_ttl_days),
            ))

            steps["branding"] = {"status": "done"}
            job.status = "succeeded"
            job.progress = 100
            job.stage = "completed"
            job.pipeline_steps = dict(steps)
            job.duration_ms = int((utcnow() - started).total_seconds() * 1000)
            await db.commit()
            hub.publish(job.id, _snapshot(job, output_id=out_id))

        except GuardrailError as e:
            job.status = "failed"
            job.error = f"guardrail:{e}"
            await db.commit()
            hub.publish(job.id, _snapshot(job))
        except Exception as e:  # noqa: BLE001 — record any stage failure
            job.status = "failed"
            job.error = str(e)
            await db.commit()
            hub.publish(job.id, _snapshot(job))
