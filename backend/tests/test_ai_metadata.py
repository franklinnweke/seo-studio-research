import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient
from PIL import Image

from app.config import get_settings
from app.main import app
from app.schemas.responses import ImageMetadataBulkAcceptRequest, ImageMetadataUpdateRequest
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

    def generate_text(self, prompt: str) -> str:
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


def test_update_image_metadata_persists_reviewed_fields() -> None:
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
        service.generate_single_image_metadata(body["id"], file_id)
        updated = service.update_image_metadata(
            body["id"],
            file_id,
            request=ImageMetadataUpdateRequest(
                suggested_filename="Reviewed Hero",
                alt_text="Reviewed alt text.",
                caption="Reviewed caption.",
            ),
        )
        stored = service.list_image_metadata(body["id"])
    finally:
        cleanup_job(body["id"])

    assert updated.suggested_filename == "reviewed-hero"
    assert updated.alt_text == "Reviewed alt text."
    assert updated.caption == "Reviewed caption."
    assert stored.results[0].suggested_filename == "reviewed-hero"


def test_updating_accepted_image_metadata_returns_row_to_review() -> None:
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
        service.generate_single_image_metadata(body["id"], file_id)
        accepted = service.accept_image_metadata(body["id"], file_id)
        updated = service.update_image_metadata(
            body["id"],
            file_id,
            request=ImageMetadataUpdateRequest(
                suggested_filename=accepted.suggested_filename,
                alt_text="Updated alt text after approval.",
                caption=accepted.caption,
            ),
        )
    finally:
        cleanup_job(body["id"])

    assert accepted.status == "accepted"
    assert updated.status == "needs_review"


def test_accept_image_metadata_persists_accepted_status() -> None:
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
        service.generate_single_image_metadata(body["id"], file_id)
        accepted = service.accept_image_metadata(body["id"], file_id)
        stored = service.list_image_metadata(body["id"])
    finally:
        cleanup_job(body["id"])

    assert accepted.status == "accepted"
    assert stored.results[0].status == "accepted"


def test_accept_all_image_metadata_updates_only_requested_rows() -> None:
    upload_response = client.post(
        "/api/jobs/images",
        files=[
            ("files", ("First Hero.png", make_image_bytes(), "image/png")),
            ("files", ("Second Hero.png", make_image_bytes(), "image/png")),
        ],
    )
    body = upload_response.json()
    first_id = body["files"][0]["id"]
    second_id = body["files"][1]["id"]
    service = AiMetadataService(
        get_settings(),
        client=FakeAiClient(
            [
                '{"filename":"first-hero","alt_text":"First hero.","caption":"First caption.","confidence":0.8}',
                '{"filename":"second-hero","alt_text":"Second hero.","caption":"Second caption.","confidence":0.8}',
            ]
        ),
    )

    try:
        service.generate_all_image_metadata(body["id"])
        response = service.accept_all_image_metadata(
            body["id"],
            request=ImageMetadataBulkAcceptRequest(image_ids=[first_id]),
        )
    finally:
        cleanup_job(body["id"])

    results = {item.id: item for item in response.results}
    assert results[first_id].status == "accepted"
    assert results[second_id].status == "needs_review"


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


def test_update_image_metadata_endpoint_persists_changes() -> None:
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
                "suggested_filename": "hero-image",
                "alt_text": "Original alt text.",
                "caption": "Original caption.",
                "confidence": 0.87,
                "status": "needs_review",
                "error_message": "",
            }
        ],
    }
    job_file.write_text(json.dumps(data, indent=2))

    try:
        response = client.patch(
            f"/api/jobs/{body['id']}/images/{file_id}",
            json={
                "suggested_filename": "Reviewed Hero",
                "alt_text": "Reviewed alt text.",
                "caption": "Reviewed caption.",
            },
        )
    finally:
        cleanup_job(body["id"])

    assert response.status_code == 200
    payload = response.json()
    assert payload["suggested_filename"] == "reviewed-hero"
    assert payload["status"] == "needs_review"


def test_accept_image_metadata_endpoint_marks_row_accepted() -> None:
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
                "suggested_filename": "hero-image",
                "alt_text": "Original alt text.",
                "caption": "Original caption.",
                "confidence": 0.87,
                "status": "needs_review",
                "error_message": "",
            }
        ],
    }
    job_file.write_text(json.dumps(data, indent=2))

    try:
        response = client.post(f"/api/jobs/{body['id']}/images/{file_id}/accept")
    finally:
        cleanup_job(body["id"])

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_accept_all_image_metadata_endpoint_marks_selected_rows_accepted() -> None:
    upload_response = client.post(
        "/api/jobs/images",
        files=[
            ("files", ("First Hero.png", make_image_bytes(), "image/png")),
            ("files", ("Second Hero.png", make_image_bytes(), "image/png")),
        ],
    )
    body = upload_response.json()
    first_id = body["files"][0]["id"]
    second_id = body["files"][1]["id"]
    job_file = get_settings().storage_root / "uploads" / body["id"] / "job.json"
    data = json.loads(job_file.read_text())
    data["image_metadata"] = {
        "job_id": body["id"],
        "provider": "ollama",
        "model": "moondream",
        "results": [
            {
                "id": first_id,
                "original_filename": "First Hero.png",
                "suggested_filename": "first-hero",
                "alt_text": "First alt text.",
                "caption": "First caption.",
                "confidence": 0.87,
                "status": "needs_review",
                "error_message": "",
            },
            {
                "id": second_id,
                "original_filename": "Second Hero.png",
                "suggested_filename": "second-hero",
                "alt_text": "Second alt text.",
                "caption": "Second caption.",
                "confidence": 0.77,
                "status": "needs_review",
                "error_message": "",
            },
        ],
    }
    job_file.write_text(json.dumps(data, indent=2))

    try:
        response = client.post(
            f"/api/jobs/{body['id']}/images/accept-all",
            json={"image_ids": [first_id]},
        )
    finally:
        cleanup_job(body["id"])

    assert response.status_code == 200
    results = {item["id"]: item for item in response.json()["results"]}
    assert results[first_id]["status"] == "accepted"
    assert results[second_id]["status"] == "needs_review"


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


def test_image_metadata_zip_export_includes_selected_images_and_report() -> None:
    upload_response = client.post(
        "/api/jobs/images",
        files=[
            ("files", ("First Hero.png", make_image_bytes(), "image/png")),
            ("files", ("Second Hero.png", make_image_bytes(), "image/png")),
        ],
    )
    body = upload_response.json()
    first_id = body["files"][0]["id"]
    second_id = body["files"][1]["id"]
    job_file = get_settings().storage_root / "uploads" / body["id"] / "job.json"
    data = json.loads(job_file.read_text())
    data["image_metadata"] = {
        "job_id": body["id"],
        "provider": "ollama",
        "model": "moondream",
        "results": [
            {
                "id": first_id,
                "original_filename": "First Hero.png",
                "suggested_filename": "first-blue-hero",
                "alt_text": "First blue hero.",
                "caption": "A first blue hero.",
                "confidence": 0.87,
                "status": "needs_review",
                "error_message": "",
            },
            {
                "id": second_id,
                "original_filename": "Second Hero.png",
                "suggested_filename": "second-blue-hero",
                "alt_text": "Second blue hero.",
                "caption": "A second blue hero.",
                "confidence": 0.81,
                "status": "needs_review",
                "error_message": "",
            },
        ],
    }
    job_file.write_text(json.dumps(data, indent=2))

    try:
        response = client.get(
            f"/api/jobs/{body['id']}/images/metadata.zip",
            params=[("image_ids", first_id)],
        )
    finally:
        cleanup_job(body["id"])

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert f'{body["id"]}-selected-image-metadata.zip' in response.headers["content-disposition"]
    with ZipFile(BytesIO(response.content)) as archive:
        assert sorted(archive.namelist()) == ["images/first-blue-hero.png", "report.csv"]
        report = archive.read("report.csv").decode("utf-8")

    assert "First Hero.png,first-blue-hero,first-blue-hero.png" in report
    assert "Second Hero.png" not in report


def test_image_metadata_zip_export_prefers_processed_images() -> None:
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
        process_response = client.post(f"/api/jobs/{body['id']}/process", json={"output_format": "webp"})
        response = client.get(
            f"/api/jobs/{body['id']}/images/metadata.zip",
            params=[("image_ids", file_id)],
        )
    finally:
        cleanup_job(body["id"])

    assert process_response.status_code == 200
    assert response.status_code == 200
    with ZipFile(BytesIO(response.content)) as archive:
        assert "images/blue-hero-image.webp" in archive.namelist()
        report = archive.read("report.csv").decode("utf-8")

    assert "Hero Image!!.png,blue-hero-image,blue-hero-image.webp" in report


def test_image_metadata_zip_export_rejects_unknown_image_id() -> None:
    body = create_image_job()

    try:
        response = client.get(
            f"/api/jobs/{body['id']}/images/metadata.zip",
            params=[("image_ids", "file_missing")],
        )
    finally:
        cleanup_job(body["id"])

    assert response.status_code == 404
    assert "file_missing" in response.json()["detail"]


def test_image_metadata_zip_export_requires_selected_image_ids() -> None:
    body = create_image_job()

    try:
        response = client.get(f"/api/jobs/{body['id']}/images/metadata.zip")
    finally:
        cleanup_job(body["id"])

    assert response.status_code == 400
    assert "At least one image_id" in response.json()["detail"]
