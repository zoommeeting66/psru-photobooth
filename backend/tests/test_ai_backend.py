"""AI backend factory + mock backend (default; no GPU)."""
from app.ai import STAGES, get_backend
from app.ai.base import RenderRequest

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_default_backend_is_mock():
    b = get_backend()
    assert b.name == "mock"


def test_stages_shape():
    keys = [s[0] for s in STAGES]
    assert keys[0] == "segmentation" and "face_pose" in keys
    # face_pose is the biometric-gated stage
    assert any(needs_bio for _, _, needs_bio in STAGES)


def test_mock_render_returns_png():
    png = get_backend().render(
        RenderRequest(capture_bytes=b"", scene_name="หอประชุม", width=400, height=300)
    )
    assert png[:8] == PNG_MAGIC
