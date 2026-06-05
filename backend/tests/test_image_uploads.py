import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient
from PIL import Image

from app.config import get_settings
from app.main import app
from app.services.image_processor import ImageProcessor


client = TestClient(app)


class FakeCropClient:
    def generate_image_metadata(self, image_path: Path, prompt: str) -> str:
        return """
        {
          "target_width": 600,
          "target_height": 400,
          "subject": "person wearing red",
          "bounding_box": {
            "x": 0.05,
            "y": 0.30,
            "width": 0.20,
            "height": 0.40
          },
          "confidence": 0.92,
          "reason": "The requested subject is on the left side of the image."
        }
        """


class FailingCropClient:
    def generate_image_metadata(self, image_path: Path, prompt: str) -> str:
        raise RuntimeError("vision model unavailable")


def make_image_bytes(format_name: str = "PNG") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (16, 16), color=(42, 84, 126)).save(buffer, format=format_name)
    return buffer.getvalue()


def make_split_image_bytes() -> bytes:
    image = Image.new("RGB", (1000, 1000), color=(20, 60, 180))
    for x in range(0, 300):
        for y in range(0, 1000):
            image.putpixel((x, y), (220, 20, 20))
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def make_zip(entries: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def make_docx(text: str) -> bytes:
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>"
        + text
        + "</w:t></w:r></w:p></w:body></w:document>"
    )
    return make_zip({"word/document.xml": document_xml.encode("utf-8")})


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


def test_create_image_job_with_single_image() -> None:
    response = client.post(
        "/api/jobs/images",
        files=[("files", ("Class Photo!!.png", make_image_bytes(), "image/png"))],
    )

    assert response.status_code == 201
    body = response.json()
    cleanup_job(body["id"])

    assert body["type"] == "image"
    assert body["status"] == "pending"
    assert len(body["files"]) == 1
    assert body["files"][0]["stored_filename"] == "class-photo.png"
    assert body["files"][0]["source"] == "upload"


def test_create_image_job_with_zip_images() -> None:
    archive = make_zip(
        {
            "folder/Hero Image.png": make_image_bytes(),
            "nested/Hero Image.png": make_image_bytes(),
        }
    )
    response = client.post(
        "/api/jobs/images",
        files=[("files", ("images.zip", archive, "application/zip"))],
    )

    assert response.status_code == 201
    body = response.json()
    cleanup_job(body["id"])

    filenames = [file["stored_filename"] for file in body["files"]]
    assert filenames == ["hero-image.png", "hero-image-2.png"]
    assert all(file["source"] == "zip" for file in body["files"])
    assert all(file["source_archive"] == "images.zip" for file in body["files"])


def test_get_job_and_files_after_upload() -> None:
    upload_response = client.post(
        "/api/jobs/images",
        files=[("files", ("sample.png", make_image_bytes(), "image/png"))],
    )
    body = upload_response.json()

    try:
        job_response = client.get(f"/api/jobs/{body['id']}")
        files_response = client.get(f"/api/jobs/{body['id']}/files")
    finally:
        cleanup_job(body["id"])

    assert job_response.status_code == 200
    assert job_response.json()["file_count"] == 1
    assert files_response.status_code == 200
    assert files_response.json()["files"][0]["original_filename"] == "sample.png"


def test_brand_context_starts_empty_for_image_job() -> None:
    upload_response = client.post(
        "/api/jobs/images",
        files=[("files", ("sample.png", make_image_bytes(), "image/png"))],
    )
    body = upload_response.json()

    try:
        response = client.get(f"/api/jobs/{body['id']}/brand-context")
    finally:
        cleanup_job(body["id"])

    assert response.status_code == 200
    assert response.json()["documents"] == []
    assert response.json()["combined_text"] == ""


def test_upload_txt_brand_context() -> None:
    upload_response = client.post(
        "/api/jobs/images",
        files=[("files", ("sample.png", make_image_bytes(), "image/png"))],
    )
    body = upload_response.json()

    try:
        response = client.post(
            f"/api/jobs/{body['id']}/brand-context",
            files=[
                (
                    "files",
                    (
                        "brand voice.txt",
                        b"We help students learn with calm, direct language.",
                        "text/plain",
                    ),
                )
            ],
        )
        stored_response = client.get(f"/api/jobs/{body['id']}/brand-context")
    finally:
        cleanup_job(body["id"])

    assert response.status_code == 200
    assert response.json()["documents"][0]["stored_filename"] == "brand-voice.txt"
    assert "calm, direct language" in response.json()["combined_text"]
    assert stored_response.json()["combined_text"] == response.json()["combined_text"]


def test_upload_docx_brand_context_extracts_text() -> None:
    upload_response = client.post(
        "/api/jobs/images",
        files=[("files", ("sample.png", make_image_bytes(), "image/png"))],
    )
    body = upload_response.json()

    try:
        response = client.post(
            f"/api/jobs/{body['id']}/brand-context",
            files=[
                (
                    "files",
                    (
                        "brand.docx",
                        make_docx("Friendly education brand for parents and students."),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ),
                )
            ],
        )
    finally:
        cleanup_job(body["id"])

    assert response.status_code == 200
    assert "Friendly education brand" in response.json()["combined_text"]


def test_rejects_unsupported_brand_context_file() -> None:
    upload_response = client.post(
        "/api/jobs/images",
        files=[("files", ("sample.png", make_image_bytes(), "image/png"))],
    )
    body = upload_response.json()

    try:
        response = client.post(
            f"/api/jobs/{body['id']}/brand-context",
            files=[("files", ("brand.csv", b"name,value", "text/csv"))],
        )
    finally:
        cleanup_job(body["id"])

    assert response.status_code == 400
    assert "not supported" in response.json()["detail"]


def test_rejects_unsupported_upload() -> None:
    response = client.post(
        "/api/jobs/images",
        files=[("files", ("notes.txt", b"hello", "text/plain"))],
    )

    assert response.status_code == 400
    assert "not supported" in response.json()["detail"]


def test_rejects_unsafe_zip_path() -> None:
    archive = make_zip({"../evil.png": make_image_bytes()})

    response = client.post(
        "/api/jobs/images",
        files=[("files", ("unsafe.zip", archive, "application/zip"))],
    )

    assert response.status_code == 400
    assert "Unsafe ZIP entry path" in response.json()["detail"]


def test_rejects_fake_image_file() -> None:
    response = client.post(
        "/api/jobs/images",
        files=[("files", ("fake.png", b"not actually an image", "image/png"))],
    )

    assert response.status_code == 400
    assert "not a valid image" in response.json()["detail"]


def test_process_image_job_with_default_compression() -> None:
    upload_response = client.post(
        "/api/jobs/images",
        files=[("files", ("sample.jpg", make_image_bytes("JPEG"), "image/jpeg"))],
    )
    body = upload_response.json()

    try:
        process_response = client.post(f"/api/jobs/{body['id']}/process", json={})
        job_response = client.get(f"/api/jobs/{body['id']}")
    finally:
        cleanup_job(body["id"])

    assert process_response.status_code == 200
    process_body = process_response.json()
    assert process_body["status"] == "processed"
    assert process_body["settings"]["quality"] == 80
    assert process_body["settings"]["resize_mode"] == "none"
    assert process_body["settings"]["strip_metadata"] is True
    assert len(process_body["results"]) == 1
    assert process_body["results"][0]["processed_size_bytes"] > 0
    assert process_body["results"][0]["new_format"] == "jpg"
    assert process_body["results"][0]["width"] == 16
    assert process_body["results"][0]["height"] == 16
    assert job_response.json()["status"] == "processed"


def test_download_processed_image() -> None:
    upload_response = client.post(
        "/api/jobs/images",
        files=[("files", ("sample.jpg", make_image_bytes("JPEG"), "image/jpeg"))],
    )
    body = upload_response.json()

    try:
        process_response = client.post(f"/api/jobs/{body['id']}/process", json={})
        filename = process_response.json()["results"][0]["processed_filename"]
        download_response = client.get(f"/api/jobs/{body['id']}/processed/{filename}")
    finally:
        cleanup_job(body["id"])

    assert download_response.status_code == 200
    assert download_response.headers["content-disposition"].startswith("attachment;")
    assert len(download_response.content) > 0


def test_download_image_with_metadata_filename_falls_back_to_original() -> None:
    upload_response = client.post(
        "/api/jobs/images",
        files=[("files", ("Sample Hero.JPG", make_image_bytes("JPEG"), "image/jpeg"))],
    )
    body = upload_response.json()
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
                "original_filename": "Sample Hero.JPG",
                "suggested_filename": "ai-suggested-name",
                "alt_text": "Sample hero image.",
                "caption": "Sample hero image.",
                "confidence": 0.5,
                "status": "needs_review",
                "error_message": "",
            }
        ],
    }
    job_file.write_text(json.dumps(data, indent=2))

    try:
        download_response = client.get(f"/api/jobs/{body['id']}/images/{file_id}/download")
    finally:
        cleanup_job(body["id"])

    assert download_response.status_code == 200
    assert "ai-suggested-name.jpg" in download_response.headers["content-disposition"]
    assert len(download_response.content) > 0


def test_download_image_prefers_processed_output_and_query_filename() -> None:
    upload_response = client.post(
        "/api/jobs/images",
        files=[("files", ("sample.jpg", make_image_bytes("JPEG"), "image/jpeg"))],
    )
    body = upload_response.json()
    file_id = body["files"][0]["id"]

    try:
        client.post(f"/api/jobs/{body['id']}/process", json={"output_format": "webp"})
        download_response = client.get(
            f"/api/jobs/{body['id']}/images/{file_id}/download",
            params={"filename": "Custom Download Name!!.png"},
        )
    finally:
        cleanup_job(body["id"])

    assert download_response.status_code == 200
    assert "custom-download-name.webp" in download_response.headers["content-disposition"]
    with Image.open(BytesIO(download_response.content)) as image:
        assert image.format == "WEBP"


def test_export_processed_images_zip() -> None:
    upload_response = client.post(
        "/api/jobs/images",
        files=[
            ("files", ("first.jpg", make_image_bytes("JPEG"), "image/jpeg")),
            ("files", ("second.png", make_image_bytes("PNG"), "image/png")),
        ],
    )
    body = upload_response.json()

    try:
        client.post(f"/api/jobs/{body['id']}/process", json={"output_format": "webp"})
        export_response = client.get(f"/api/jobs/{body['id']}/export.zip")
    finally:
        cleanup_job(body["id"])

    assert export_response.status_code == 200
    assert export_response.headers["content-type"] == "application/zip"
    with ZipFile(BytesIO(export_response.content)) as archive:
        assert archive.namelist() == ["images/first.webp", "images/second.webp"]


def test_rejects_processed_download_path_traversal() -> None:
    response = client.get("/api/jobs/job_missing/processed/../secret.jpg")

    assert response.status_code in {400, 404}


def test_process_image_job_with_resize() -> None:
    buffer = BytesIO()
    Image.new("RGB", (2400, 1200), color=(42, 84, 126)).save(buffer, format="JPEG")
    upload_response = client.post(
        "/api/jobs/images",
        files=[("files", ("wide.jpg", buffer.getvalue(), "image/jpeg"))],
    )
    body = upload_response.json()

    try:
        process_response = client.post(
            f"/api/jobs/{body['id']}/process",
            json={"resize_mode": "max_1200", "quality": 80, "strip_metadata": True},
        )
    finally:
        cleanup_job(body["id"])

    assert process_response.status_code == 200
    result = process_response.json()["results"][0]
    assert result["width"] == 1200
    assert result["height"] == 600


def test_process_image_job_with_exact_crop() -> None:
    buffer = BytesIO()
    Image.new("RGB", (1200, 800), color=(42, 84, 126)).save(buffer, format="JPEG")
    upload_response = client.post(
        "/api/jobs/images",
        files=[("files", ("wide.jpg", buffer.getvalue(), "image/jpeg"))],
    )
    body = upload_response.json()

    try:
        process_response = client.post(
            f"/api/jobs/{body['id']}/process",
            json={
                "resize_mode": "exact",
                "target_width": 600,
                "target_height": 400,
                "output_format": "webp",
            },
        )
    finally:
        cleanup_job(body["id"])

    assert process_response.status_code == 200
    result = process_response.json()["results"][0]
    assert result["width"] == 600
    assert result["height"] == 400
    assert result["new_format"] == "webp"


def test_process_image_job_with_fit_inside_padding() -> None:
    buffer = BytesIO()
    Image.new("RGB", (1200, 800), color=(42, 84, 126)).save(buffer, format="JPEG")
    upload_response = client.post(
        "/api/jobs/images",
        files=[("files", ("wide.jpg", buffer.getvalue(), "image/jpeg"))],
    )
    body = upload_response.json()

    try:
        process_response = client.post(
            f"/api/jobs/{body['id']}/process",
            json={
                "resize_mode": "fit_inside",
                "target_width": 600,
                "target_height": 600,
                "output_format": "png",
            },
        )
    finally:
        cleanup_job(body["id"])

    assert process_response.status_code == 200
    result = process_response.json()["results"][0]
    assert result["width"] == 600
    assert result["height"] == 600


def test_resize_instruction_parser_extracts_settings() -> None:
    upload_response = client.post(
        "/api/jobs/images",
        files=[("files", ("sample.jpg", make_image_bytes("JPEG"), "image/jpeg"))],
    )
    body = upload_response.json()

    try:
        response = client.post(
            f"/api/jobs/{body['id']}/resize-instructions",
            json={"instruction": "Resize into 600 x 400 WEBP files at quality 90."},
        )
    finally:
        cleanup_job(body["id"])

    assert response.status_code == 200
    settings = response.json()["settings"]
    assert settings["resize_mode"] == "exact"
    assert settings["target_width"] == 600
    assert settings["target_height"] == 400
    assert settings["output_format"] == "webp"
    assert settings["quality"] == 90


def test_crop_review_marks_mismatched_ratio() -> None:
    buffer = BytesIO()
    Image.new("RGB", (1200, 800), color=(42, 84, 126)).save(buffer, format="JPEG")
    upload_response = client.post(
        "/api/jobs/images",
        files=[("files", ("wide.jpg", buffer.getvalue(), "image/jpeg"))],
    )
    body = upload_response.json()

    try:
        response = client.post(
            f"/api/jobs/{body['id']}/resize-review",
            json={"resize_mode": "exact", "target_width": 600, "target_height": 600},
        )
    finally:
        cleanup_job(body["id"])

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["needs_review"] is True
    assert item["focus_x"] == 0.5
    assert item["focus_y"] == 0.5


def test_resize_instruction_can_request_ai_crop_box() -> None:
    upload_response = client.post(
        "/api/jobs/images",
        files=[("files", ("people.jpg", make_split_image_bytes(), "image/jpeg"))],
    )
    body = upload_response.json()
    file_id = body["files"][0]["id"]
    processor = ImageProcessor(get_settings(), client=FakeCropClient())

    try:
        response = processor.parse_resize_instruction(
            body["id"],
            "crop a 600 x 400 image showing only the person wearing red",
        )
    finally:
        cleanup_job(body["id"])

    assert response.settings.resize_mode == "exact"
    assert response.settings.target_width == 600
    assert response.settings.target_height == 400
    assert file_id in response.settings.crop_boxes
    assert response.settings.crop_subjects[file_id] == "person wearing red"
    assert response.settings.crop_confidences[file_id] == 0.92
    assert any("AI suggested a crop" in note for note in response.notes)
    assert response.warnings == []


def test_resize_instruction_ai_crop_failure_returns_warning() -> None:
    upload_response = client.post(
        "/api/jobs/images",
        files=[("files", ("people.jpg", make_split_image_bytes(), "image/jpeg"))],
    )
    body = upload_response.json()
    file_id = body["files"][0]["id"]
    processor = ImageProcessor(get_settings(), client=FailingCropClient())

    try:
        response = processor.parse_resize_instruction(
            body["id"],
            "crop a 600 x 400 image showing only the person wearing red",
        )
    finally:
        cleanup_job(body["id"])

    assert response.settings.resize_mode == "exact"
    assert response.settings.target_width == 600
    assert response.settings.target_height == 400
    assert file_id not in response.settings.crop_boxes
    assert any("AI crop suggestion failed" in warning for warning in response.warnings)


def test_process_image_job_uses_ai_crop_box() -> None:
    upload_response = client.post(
        "/api/jobs/images",
        files=[("files", ("people.jpg", make_split_image_bytes(), "image/jpeg"))],
    )
    body = upload_response.json()
    file_id = body["files"][0]["id"]
    processor = ImageProcessor(get_settings(), client=FakeCropClient())
    instruction_response = processor.parse_resize_instruction(
        body["id"],
        "crop a 600 x 400 image showing only the person wearing red",
    )

    try:
        process_response = client.post(
            f"/api/jobs/{body['id']}/process",
            json=instruction_response.settings.model_dump(),
        )
        filename = process_response.json()["results"][0]["processed_filename"]
        processed_path = get_settings().storage_root / "processed" / body["id"] / "images" / filename
        with Image.open(processed_path) as processed_image:
            pixel = processed_image.convert("RGB").getpixel((processed_image.width // 4, processed_image.height // 2))
    finally:
        cleanup_job(body["id"])

    assert process_response.status_code == 200
    result = process_response.json()["results"][0]
    assert result["id"] == file_id
    assert result["width"] == 600
    assert result["height"] == 400
    assert pixel[0] > pixel[2]


def test_process_image_job_converts_to_webp() -> None:
    upload_response = client.post(
        "/api/jobs/images",
        files=[("files", ("sample.jpg", make_image_bytes("JPEG"), "image/jpeg"))],
    )
    body = upload_response.json()

    try:
        process_response = client.post(
            f"/api/jobs/{body['id']}/process",
            json={"output_format": "webp", "quality": 80},
        )
    finally:
        cleanup_job(body["id"])

    assert process_response.status_code == 200
    result = process_response.json()["results"][0]
    assert result["processed_filename"] == "sample.webp"
    assert result["original_format"] == "jpg"
    assert result["new_format"] == "webp"


def test_process_image_job_dedupes_converted_filenames() -> None:
    upload_response = client.post(
        "/api/jobs/images",
        files=[
            ("files", ("sample.jpg", make_image_bytes("JPEG"), "image/jpeg")),
            ("files", ("sample.png", make_image_bytes("PNG"), "image/png")),
        ],
    )
    body = upload_response.json()

    try:
        process_response = client.post(
            f"/api/jobs/{body['id']}/process",
            json={"output_format": "webp", "quality": 80},
        )
    finally:
        cleanup_job(body["id"])

    assert process_response.status_code == 200
    filenames = [result["processed_filename"] for result in process_response.json()["results"]]
    assert filenames == ["sample.webp", "sample-2.webp"]


def test_process_image_job_applies_filename_override_cleanup() -> None:
    upload_response = client.post(
        "/api/jobs/images",
        files=[("files", ("IMG 123 Final!!.jpg", make_image_bytes("JPEG"), "image/jpeg"))],
    )
    body = upload_response.json()
    file_id = body["files"][0]["id"]

    try:
        process_response = client.post(
            f"/api/jobs/{body['id']}/process",
            json={
                "output_format": "webp",
                "quality": 80,
                "filename_overrides": {file_id: "Custom Hero Name!!.png"},
            },
        )
    finally:
        cleanup_job(body["id"])

    assert process_response.status_code == 200
    result = process_response.json()["results"][0]
    assert result["processed_filename"] == "custom-hero-name.webp"
    assert result["new_format"] == "webp"


def test_process_image_job_flattens_png_transparency_to_jpg() -> None:
    buffer = BytesIO()
    image = Image.new("RGBA", (16, 16), color=(255, 0, 0, 0))
    image.save(buffer, format="PNG")
    upload_response = client.post(
        "/api/jobs/images",
        files=[("files", ("transparent.png", buffer.getvalue(), "image/png"))],
    )
    body = upload_response.json()

    try:
        process_response = client.post(
            f"/api/jobs/{body['id']}/process",
            json={"output_format": "jpg", "quality": 80},
        )
        filename = process_response.json()["results"][0]["processed_filename"]
        download_response = client.get(f"/api/jobs/{body['id']}/processed/{filename}")
    finally:
        cleanup_job(body["id"])

    assert process_response.status_code == 200
    assert process_response.json()["results"][0]["new_format"] == "jpg"
    assert download_response.status_code == 200
    with Image.open(BytesIO(download_response.content)) as processed:
        assert processed.mode == "RGB"
