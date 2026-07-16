import json
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from app.config import get_settings
from app.main import app
from app.schemas.responses import ImageContextUpdateRequest, ImageMetadataUpdateRequest
from app.services.ai_metadata_service import AiMetadataService
from app.services.job_context_service import JobContextService


client = TestClient(app)


class UnusedAiClient:
    def generate_image_metadata(self, image_path: Path, prompt: str) -> str:
        raise AssertionError("Purpose approval tests do not call image generation.")

    def generate_text(self, prompt: str) -> str:
        raise AssertionError("Purpose approval tests do not call text generation.")


def make_image_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (16, 16), color=(42, 84, 126)).save(buffer, format="PNG")
    return buffer.getvalue()


def create_image_job() -> dict:
    response = client.post(
        "/api/jobs/images",
        files=[("files", ("Context Image.png", make_image_bytes(), "image/png"))],
    )
    assert response.status_code == 201
    return response.json()


def cleanup_job(job_id: str) -> None:
    for job_dir in [
        get_settings().storage_root / "uploads" / job_id,
        get_settings().storage_root / "processed" / job_id,
        get_settings().storage_root / "exports" / job_id,
        get_settings().storage_root / "temp" / job_id,
    ]:
        if not job_dir.exists():
            continue
        for path in sorted(job_dir.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        job_dir.rmdir()


def write_metadata(job_id: str, image_id: str, *, alt_text: str = "Existing alt text.") -> None:
    job_file = get_settings().storage_root / "uploads" / job_id / "job.json"
    data = json.loads(job_file.read_text())
    original_filename = data["files"][0]["original_filename"]
    data["image_metadata"] = {
        "job_id": job_id,
        "provider": "ollama",
        "model": "test-model",
        "vision_model": "vision-model",
        "language_model": "language-model",
        "results": [
            {
                "id": image_id,
                "original_filename": original_filename,
                "suggested_filename": "context-image",
                "alt_text": alt_text,
                "caption": "Context image caption.",
                "confidence": 0.8,
                "status": "needs_review",
                "error_message": "",
            }
        ],
    }
    job_file.write_text(json.dumps(data, indent=2))


def test_new_image_job_uses_schema_version_two_defaults() -> None:
    body = create_image_job()
    try:
        assert body["schema_version"] == 2
        assert body["page_context"]["language"] == "en-CA"
        assert body["page_context"]["updated_at"] is None
        assert body["image_contexts"] == {}
    finally:
        cleanup_job(body["id"])


def test_legacy_job_without_context_loads_safe_defaults() -> None:
    body = create_image_job()
    image_id = body["files"][0]["id"]
    job_file = get_settings().storage_root / "uploads" / body["id"] / "job.json"
    data = json.loads(job_file.read_text())
    data.pop("schema_version")
    data.pop("page_context")
    data.pop("image_contexts")
    job_file.write_text(json.dumps(data, indent=2))

    try:
        page_response = client.get(f"/api/jobs/{body['id']}/page-context")
        image_response = client.get(f"/api/jobs/{body['id']}/images/{image_id}/context")
    finally:
        cleanup_job(body["id"])

    assert page_response.status_code == 200
    assert page_response.json()["schema_version"] == 2
    assert page_response.json()["page_context"]["page_title"] == ""
    assert image_response.status_code == 200
    assert image_response.json()["image_context"]["purpose"] == "unknown"
    assert image_response.json()["image_context"]["purpose_confirmed"] is False


def test_page_and_image_context_round_trip() -> None:
    body = create_image_job()
    image_id = body["files"][0]["id"]
    try:
        page_response = client.put(
            f"/api/jobs/{body['id']}/page-context",
            json={
                "page_title": "Primary Care Services",
                "section_heading": "What to Expect",
                "nearby_text": "Our clinicians discuss symptoms and care options.",
                "page_url": "https://example.invalid/services/primary-care",
                "audience": "Prospective patients",
                "language": "en-CA",
            },
        )
        image_response = client.put(
            f"/api/jobs/{body['id']}/images/{image_id}/context",
            json={
                "purpose": "functional",
                "purpose_confirmed": True,
                "suggested_purpose": "informative",
                "purpose_confidence": 0.72,
                "link_destination": "/book-an-appointment",
                "functional_action": "Book an appointment",
                "notes": "The image is used as the booking link.",
            },
        )
        stored_page = client.get(f"/api/jobs/{body['id']}/page-context")
        stored_image = client.get(f"/api/jobs/{body['id']}/images/{image_id}/context")
    finally:
        cleanup_job(body["id"])

    assert page_response.status_code == 200
    assert page_response.json()["page_context"]["updated_at"]
    assert stored_page.json()["page_context"]["page_title"] == "Primary Care Services"
    assert image_response.status_code == 200
    assert image_response.json()["image_context"]["purpose_source"] == "human_confirmed"
    assert stored_image.json()["image_context"]["functional_action"] == "Book an appointment"


def test_image_context_rejects_inconsistent_confirmation_evidence() -> None:
    body = create_image_job()
    image_id = body["files"][0]["id"]
    try:
        unknown_response = client.put(
            f"/api/jobs/{body['id']}/images/{image_id}/context",
            json={"purpose": "unknown", "purpose_confirmed": True},
        )
        confidence_response = client.put(
            f"/api/jobs/{body['id']}/images/{image_id}/context",
            json={"purpose": "informative", "purpose_confidence": 0.8},
        )
    finally:
        cleanup_job(body["id"])

    assert unknown_response.status_code == 400
    assert unknown_response.json()["code"] == "CONTEXT_VALIDATION_FAILED"
    assert "Unknown image purpose" in unknown_response.json()["message"]
    assert unknown_response.json()["field"] == "purpose_confirmed"
    assert unknown_response.json()["retryable"] is False
    assert unknown_response.json()["request_id"] == unknown_response.headers["x-request-id"]
    assert confidence_response.status_code == 400
    assert "suggested purpose" in confidence_response.json()["message"]
    assert confidence_response.json()["field"] == "purpose_confidence"


@pytest.mark.parametrize(
    "purpose",
    ["informative", "decorative", "functional", "text", "complex", "redundant", "unknown"],
)
def test_image_context_supports_the_full_seven_state_taxonomy(purpose: str) -> None:
    body = create_image_job()
    image_id = body["files"][0]["id"]
    try:
        response = client.put(
            f"/api/jobs/{body['id']}/images/{image_id}/context",
            json={"purpose": purpose, "purpose_confirmed": purpose != "unknown"},
        )
    finally:
        cleanup_job(body["id"])

    assert response.status_code == 200
    assert response.json()["image_context"]["purpose"] == purpose


def test_decorative_image_accepts_empty_alt_when_context_mode_is_enabled() -> None:
    body = create_image_job()
    image_id = body["files"][0]["id"]
    settings = get_settings().model_copy(update={"context_metadata_enabled": True})
    context_service = JobContextService(settings)
    metadata_service = AiMetadataService(settings, client=UnusedAiClient())
    write_metadata(body["id"], image_id)
    context_service.update_image_context(
        body["id"],
        image_id,
        ImageContextUpdateRequest(purpose="decorative", purpose_confirmed=True),
    )

    try:
        result = metadata_service.update_image_metadata(
            body["id"],
            image_id,
            ImageMetadataUpdateRequest(
                suggested_filename="context-image",
                alt_text="",
                caption="Context image caption.",
                status="accepted",
            ),
        )
    finally:
        cleanup_job(body["id"])

    assert result.status == "accepted"
    assert result.alt_text == ""


@pytest.mark.parametrize(
    ("context", "alt_text", "message"),
    [
        ({"purpose": "unknown", "purpose_confirmed": False}, "Description.", "human-confirmed"),
        ({"purpose": "informative", "purpose_confirmed": True}, "", "non-empty alt text"),
        ({"purpose": "decorative", "purpose_confirmed": True}, "Description.", "empty alt text"),
        ({"purpose": "functional", "purpose_confirmed": True}, "Opens booking.", "action or link"),
        ({"purpose": "complex", "purpose_confirmed": True}, "Quarterly sales chart.", "long description"),
    ],
)
def test_purpose_aware_approval_rejects_invalid_state(
    context: dict[str, object],
    alt_text: str,
    message: str,
) -> None:
    body = create_image_job()
    image_id = body["files"][0]["id"]
    settings = get_settings().model_copy(update={"context_metadata_enabled": True})
    context_service = JobContextService(settings)
    metadata_service = AiMetadataService(settings, client=UnusedAiClient())
    write_metadata(body["id"], image_id, alt_text=alt_text)
    context_service.update_image_context(body["id"], image_id, ImageContextUpdateRequest.model_validate(context))

    try:
        with pytest.raises(HTTPException) as exc:
            metadata_service.accept_image_metadata(body["id"], image_id)
    finally:
        cleanup_job(body["id"])

    assert exc.value.status_code == 400
    assert message in str(exc.value.detail)
