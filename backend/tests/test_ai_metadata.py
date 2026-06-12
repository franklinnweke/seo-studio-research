import json
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from app.config import get_settings
from app.main import app
from app.services.ai_metadata_service import AiMetadataService


client = TestClient(app)


class FakeAiClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls = 0
        self.prompts: list[str] = []

    def generate_image_metadata(self, image_path: Path, prompt: str) -> str:
        assert image_path.exists()
        self.calls += 1
        self.prompts.append(prompt)
        return self.responses.pop(0)


def make_image_bytes(width: int = 16, height: int = 16) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), color=(42, 84, 126)).save(buffer, format="PNG")
    return buffer.getvalue()


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


def create_image_job() -> dict:
    response = client.post(
        "/api/jobs/images",
        files=[("files", ("Hero Image!!.png", make_image_bytes(), "image/png"))],
    )
    assert response.status_code == 201
    return response.json()


def test_generate_single_image_metadata_persists_result() -> None:
    body = create_image_job()
    file_id = body["files"][0]["id"]
    service = AiMetadataService(
        get_settings(),
        client=FakeAiClient(
            [
                '{"filename":"Blue Hero Image","alt_text":"Blue square graphic.","caption":"A blue square graphic.","confidence":0.87}'
            ]
        ),
    )

    try:
        result = service.generate_single_image_metadata(body["id"], file_id)
        stored = service.list_image_metadata(body["id"])
    finally:
        cleanup_job(body["id"])

    assert result.status == "needs_review"
    assert result.suggested_filename == "blue-hero-image"
    assert result.alt_text == "Blue square graphic."
    assert stored.results[0].id == file_id


def test_ai_metadata_retries_invalid_json_once() -> None:
    body = create_image_job()
    service = AiMetadataService(
        get_settings(),
        client=FakeAiClient(
            [
                "Here is a caption, not JSON.",
                '{"filename":"retry-name","alt_text":"Retry alt text.","caption":"Retry caption.","confidence":0.5}',
            ]
        ),
    )

    try:
        response = service.generate_all_image_metadata(body["id"])
    finally:
        cleanup_job(body["id"])

    assert response.results[0].suggested_filename == "retry-name"
    assert response.results[0].status == "needs_review"


def test_ai_metadata_prompt_includes_brand_context() -> None:
    body = create_image_job()
    job_file = get_settings().storage_root / "uploads" / body["id"] / "job.json"
    data = json.loads(job_file.read_text())
    data["brand_context"] = {
        "job_id": body["id"],
        "documents": [],
        "combined_text": "Use a warm tutoring brand voice for students.",
        "max_chars": 8000,
    }
    job_file.write_text(json.dumps(data, indent=2))
    fake_client = FakeAiClient(
        [
            '{"filename":"student-study-guide","alt_text":"Blue square graphic.","caption":"A blue square graphic.","confidence":0.7}'
        ]
    )
    service = AiMetadataService(get_settings(), client=fake_client)

    try:
        response = service.generate_all_image_metadata(body["id"])
    finally:
        cleanup_job(body["id"])

    assert response.results[0].suggested_filename == "student-study-guide"
    assert "Use a warm tutoring brand voice" in fake_client.prompts[0]
    assert "Do not claim visible details from the brand context" in fake_client.prompts[0]


def test_ai_metadata_fails_cleanly_when_json_retry_fails() -> None:
    body = create_image_job()
    service = AiMetadataService(
        get_settings(),
        client=FakeAiClient(
            [
                "This is not JSON.",
                "",
            ]
        ),
    )

    try:
        response = service.generate_all_image_metadata(body["id"])
    finally:
        cleanup_job(body["id"])

    result = response.results[0]
    assert result.status == "failed"
    assert result.suggested_filename == "hero-image"
    assert result.alt_text == ""
    assert result.confidence == 0.0
    assert "AI response was not valid JSON after retry" in result.error_message


def test_generate_single_image_metadata_persists_failed_result() -> None:
    body = create_image_job()
    file_id = body["files"][0]["id"]
    service = AiMetadataService(
        get_settings(),
        client=FakeAiClient(
            [
                "not JSON",
                "still not JSON",
            ]
        ),
    )

    try:
        result = service.generate_single_image_metadata(body["id"], file_id)
        stored = service.list_image_metadata(body["id"])
    finally:
        cleanup_job(body["id"])

    assert result.status == "failed"
    assert result.error_message
    assert stored.results[0].status == "failed"


def test_preview_image_respects_max_width() -> None:
    body = client.post(
        "/api/jobs/images",
        files=[("files", ("wide.png", make_image_bytes(width=2400, height=1200), "image/png"))],
    ).json()
    service = AiMetadataService(get_settings(), client=FakeAiClient([]))
    source_path = get_settings().storage_root / "uploads" / body["id"] / body["files"][0]["relative_path"]
    preview_path: Path | None = None

    try:
        preview_path = service._create_preview(body["id"], source_path)
        with Image.open(preview_path) as image:
            assert image.width <= get_settings().ai_preview_max_width
    finally:
        if preview_path:
            preview_path.unlink(missing_ok=True)
        cleanup_job(body["id"])


def test_image_metadata_endpoint_returns_missing_image_404() -> None:
    body = create_image_job()

    try:
        response = client.post(f"/api/jobs/{body['id']}/images/file_missing/metadata")
    finally:
        cleanup_job(body["id"])

    assert response.status_code == 404


def test_image_metadata_csv_export_includes_selected_seo_fields() -> None:
    body = create_image_job()
    file_id = body["files"][0]["id"]
    job_file = get_settings().storage_root / "uploads" / body["id"] / "job.json"
    data = json.loads(job_file.read_text())
    data["image_metadata"] = {
        "job_id": body["id"],
        "provider": "ollama",
        "model": "moondream",
        "results": [
            {
                "id": file_id,
                "original_filename": "Hero Image!!.png",
                "suggested_filename": "blue-hero-image",
                "alt_text": "Blue square graphic.",
                "caption": "A blue square graphic.",
                "confidence": 0.87,
                "status": "needs_review",
                "error_message": "",
            }
        ],
    }
    job_file.write_text(json.dumps(data, indent=2))

    try:
        response = client.get(
            f"/api/jobs/{body['id']}/images/metadata.csv",
            params=[
                ("fields", "original_filename"),
                ("fields", "suggested_filename"),
                ("fields", "alt_text"),
                ("fields", "download_filename"),
            ],
        )
    finally:
        cleanup_job(body["id"])

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert f'{body["id"]}-image-metadata.csv' in response.headers["content-disposition"]
    lines = response.text.strip().splitlines()
    assert lines[0] == "original_filename,suggested_filename,alt_text,download_filename"
    assert "Hero Image!!.png,blue-hero-image,Blue square graphic.,blue-hero-image.png" in lines[1]


def test_image_metadata_csv_export_rejects_unknown_fields() -> None:
    body = create_image_job()

    try:
        response = client.get(
            f"/api/jobs/{body['id']}/images/metadata.csv",
            params={"fields": "not_a_field"},
        )
    finally:
        cleanup_job(body["id"])

    assert response.status_code == 400
    assert "Unsupported CSV field" in response.json()["detail"]
