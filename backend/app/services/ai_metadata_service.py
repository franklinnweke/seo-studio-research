import json
import logging
import re
import csv
from io import StringIO
from time import perf_counter
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
from fastapi import HTTPException, status
from PIL import Image, ImageOps
from pydantic import BaseModel, Field, ValidationError

from app.ai.ollama_client import OllamaClient
from app.ai.prompts import (
    IMAGE_METADATA_BRAND_CONTEXT_BLOCK,
    IMAGE_METADATA_PROMPT,
    IMAGE_METADATA_RETRY_PROMPT,
)
from app.config import Settings
from app.schemas.responses import (
    ImageContext,
    ImageMetadataBulkAcceptRequest,
    ImageMetadataListResponse,
    ImageMetadataResult,
    ImageMetadataUpdateRequest,
    ImageUploadFileRecord,
)
from app.services.image_upload_service import ImageUploadService
from app.utils.file_utils import dedupe_filename, sanitize_filename
from app.utils.slugify import slugify


logger = logging.getLogger(__name__)


class ImageMetadataClient(Protocol):
    def generate_image_metadata(self, image_path: Path, prompt: str) -> str:
        ...

    def generate_text(self, prompt: str) -> str:
        ...


class AiImageMetadataPayload(BaseModel):
    filename: str = Field(min_length=1)
    alt_text: str = Field(min_length=1)
    caption: str = Field(min_length=1)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class AiMetadataService:
    CSV_FIELD_LABELS: dict[str, str] = {
        "image_id": "image_id",
        "original_filename": "original_filename",
        "suggested_filename": "suggested_filename",
        "download_filename": "download_filename",
        "source_path": "source_path",
        "processed_filename": "processed_filename",
        "processed_path": "processed_path",
        "download_path": "download_path",
        "alt_text": "alt_text",
        "caption": "caption",
        "confidence": "confidence",
        "metadata_status": "metadata_status",
        "error_message": "error_message",
        "content_type": "content_type",
        "size_bytes": "size_bytes",
        "source": "source",
        "source_archive": "source_archive",
    }

    def __init__(self, settings: Settings, client: ImageMetadataClient | None = None) -> None:
        self.settings = settings
        self.upload_service = ImageUploadService(settings)
        self.upload_root = settings.storage_root / "uploads"
        self.processed_root = settings.storage_root / "processed"
        self.exports_root = settings.storage_root / "exports"
        self.temp_root = settings.storage_root / "temp"
        self.injected_client = client
        self.vision_client = client or OllamaClient(
            settings.ollama_base_url,
            settings.vision_model,
            settings.ollama_timeout_seconds,
        )
        self.language_client = client or OllamaClient(
            settings.ollama_base_url,
            settings.language_model,
            settings.ollama_timeout_seconds,
        )

    def close(self) -> None:
        if self.injected_client is not None:
            return
        if isinstance(self.vision_client, OllamaClient):
            self.vision_client.close()
        if isinstance(self.language_client, OllamaClient):
            self.language_client.close()

    def list_image_metadata(self, job_id: str) -> ImageMetadataListResponse:
        self.upload_service.read_job(job_id)
        data = self.upload_service.read_job_data(job_id)
        return self._response_from_job_data(job_id, data)

    def export_image_metadata_csv(self, job_id: str, fields: list[str] | None = None) -> str:
        job = self.upload_service.read_job(job_id)
        job_data = self.upload_service.read_job_data(job_id)
        selected_fields = self._csv_fields(fields)
        metadata_by_id = {
            result.id: result
            for result in self._response_from_job_data(job_id, job_data).results
        }
        processed_by_id = self._processed_results_by_id(job_data)

        output = StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=selected_fields,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()

        for file_record in job.files:
            metadata = metadata_by_id.get(file_record.id)
            processed = processed_by_id.get(file_record.id)
            row = self._csv_row(job_id, file_record, metadata, processed)
            writer.writerow({field: row[field] for field in selected_fields})

        return output.getvalue()

    def create_image_metadata_zip(self, job_id: str, image_ids: list[str] | None) -> Path:
        if not image_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one image_id is required.",
            )

        job = self.upload_service.read_job(job_id)
        requested_ids = list(dict.fromkeys(image_ids))
        files_by_id = {file_record.id: file_record for file_record in job.files}
        missing_ids = [image_id for image_id in requested_ids if image_id not in files_by_id]
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Image file(s) not found: {', '.join(missing_ids)}",
            )

        job_data = self.upload_service.read_job_data(job_id)
        metadata_by_id = {
            result.id: result
            for result in self._response_from_job_data(job_id, job_data).results
        }
        processed_by_id = self._processed_results_by_id(job_data)
        selected_fields = self._metadata_zip_csv_fields()
        report = StringIO()
        writer = csv.DictWriter(
            report,
            fieldnames=selected_fields,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()

        export_dir = self.exports_root / job_id
        export_dir.mkdir(parents=True, exist_ok=True)
        zip_path = export_dir / "selected-image-metadata.zip"
        used_archive_names: set[str] = set()

        with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
            for image_id in requested_ids:
                file_record = files_by_id[image_id]
                metadata = metadata_by_id.get(image_id)
                processed = processed_by_id.get(image_id)
                row = self._csv_row(job_id, file_record, metadata, processed)
                writer.writerow({field: row[field] for field in selected_fields})

                image_path = self._metadata_download_source_path(job_id, file_record, processed)
                archive_name = dedupe_filename(str(row["download_filename"]), used_archive_names)
                archive.write(image_path, arcname=f"images/{archive_name}")

            archive.writestr("report.csv", report.getvalue())

        return zip_path

    def generate_all_image_metadata(self, job_id: str) -> ImageMetadataListResponse:
        job = self.upload_service.read_job(job_id)
        brand_context = self._brand_context_for_job(job_id)
        results: list[ImageMetadataResult] = []
        for file_record in job.files:
            try:
                result = self._generate_for_file(job_id, file_record, brand_context)
            except Exception as exc:
                result = self._failed_result(file_record, exc)
            results.append(result)

        response = ImageMetadataListResponse(
            job_id=job_id,
            provider=self.settings.ai_provider,
            model=self._metadata_model_label(),
            vision_model=self.settings.vision_model,
            language_model=self.settings.language_model,
            results=results,
        )
        self._write_metadata_response(response)
        return response

    def generate_single_image_metadata(self, job_id: str, image_id: str) -> ImageMetadataResult:
        job = self.upload_service.read_job(job_id)
        file_record = next((record for record in job.files if record.id == image_id), None)
        if not file_record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image file not found.")

        brand_context = self._brand_context_for_job(job_id)
        try:
            result = self._generate_for_file(job_id, file_record, brand_context)
        except Exception as exc:
            result = self._failed_result(file_record, exc)
        current = self.list_image_metadata(job_id)
        next_results = [existing for existing in current.results if existing.id != image_id]
        next_results.append(result)
        self._write_metadata_response(
            ImageMetadataListResponse(
                job_id=job_id,
                provider=self.settings.ai_provider,
                model=self._metadata_model_label(),
                vision_model=self.settings.vision_model,
                language_model=self.settings.language_model,
                results=next_results,
            )
        )
        return result

    def update_image_metadata(
        self,
        job_id: str,
        image_id: str,
        request: ImageMetadataUpdateRequest,
    ) -> ImageMetadataResult:
        self.upload_service.read_job(job_id)
        current = self.list_image_metadata(job_id)
        current_result = self._result_by_id(current, image_id)
        image_context = self._image_context(job_id, image_id)
        next_result = self._merge_review_update(current_result, request, image_context)
        self._replace_metadata_result(job_id, current, next_result)
        return next_result

    def accept_image_metadata(self, job_id: str, image_id: str) -> ImageMetadataResult:
        self.upload_service.read_job(job_id)
        current = self.list_image_metadata(job_id)
        current_result = self._result_by_id(current, image_id)
        next_result = self._accepted_result(current_result, self._image_context(job_id, image_id))
        self._replace_metadata_result(job_id, current, next_result)
        return next_result

    def accept_all_image_metadata(
        self,
        job_id: str,
        request: ImageMetadataBulkAcceptRequest,
    ) -> ImageMetadataListResponse:
        self.upload_service.read_job(job_id)
        current = self.list_image_metadata(job_id)
        requested_ids = list(dict.fromkeys(request.image_ids))
        missing_ids = [
            image_id for image_id in requested_ids if not any(result.id == image_id for result in current.results)
        ]
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Metadata result(s) not found: {', '.join(missing_ids)}",
            )

        accepted_ids = set(requested_ids)
        next_results = [
            self._accepted_result(result, self._image_context(job_id, result.id))
            if result.id in accepted_ids
            else result
            for result in current.results
        ]
        response = ImageMetadataListResponse(
            job_id=current.job_id,
            provider=current.provider,
            model=current.model,
            vision_model=current.vision_model,
            language_model=current.language_model,
            results=next_results,
        )
        self._write_metadata_response(response)
        return response

    def _generate_for_file(
        self,
        job_id: str,
        file_record: ImageUploadFileRecord,
        brand_context: str,
    ) -> ImageMetadataResult:
        source_path = self.upload_root / job_id / file_record.relative_path
        if not source_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Uploaded file is missing: {file_record.relative_path}",
            )

        preview_path = self._create_preview(job_id, source_path)
        try:
            payload = self._request_metadata(preview_path, brand_context)
        finally:
            preview_path.unlink(missing_ok=True)

        return ImageMetadataResult(
            id=file_record.id,
            original_filename=file_record.original_filename,
            suggested_filename=slugify(payload.filename),
            alt_text=payload.alt_text.strip(),
            caption=payload.caption.strip(),
            confidence=payload.confidence,
            status="needs_review",
        )

    def _create_preview(self, job_id: str, source_path: Path) -> Path:
        preview_dir = self.temp_root / job_id
        preview_dir.mkdir(parents=True, exist_ok=True)
        preview_path = preview_dir / f"preview-{uuid4().hex[:12]}.jpg"

        with Image.open(source_path) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail(
                (self.settings.ai_preview_max_width, self.settings.ai_preview_max_width),
                Image.Resampling.LANCZOS,
            )
            if image.mode not in {"RGB", "L"}:
                image = image.convert("RGB")
            image.save(preview_path, format="JPEG", quality=85, optimize=True)

        return preview_path

    def _request_metadata(self, preview_path: Path, brand_context: str) -> AiImageMetadataPayload:
        if self.injected_client is not None:
            return self._request_metadata_single_model(preview_path, brand_context)

        visual_description = self._request_visual_description(preview_path)
        return self._request_language_metadata(visual_description, brand_context)

    def _request_metadata_single_model(self, preview_path: Path, brand_context: str) -> AiImageMetadataPayload:
        errors: list[str] = []
        prompts = (
            ("main", self._metadata_prompt(IMAGE_METADATA_PROMPT, brand_context)),
            ("json_retry", self._metadata_prompt(IMAGE_METADATA_RETRY_PROMPT, brand_context)),
        )
        for attempt_name, prompt in prompts:
            started_at = perf_counter()
            try:
                logger.info(
                    "Requesting AI image metadata attempt=%s model=%s timeout_seconds=%s",
                    attempt_name,
                    self.settings.vision_model,
                    self.settings.ollama_timeout_seconds,
                )
                content = self.vision_client.generate_image_metadata(preview_path, prompt)
                payload = self._parse_metadata_payload(content)
                logger.info(
                    "AI image metadata attempt succeeded attempt=%s model=%s duration_seconds=%.2f",
                    attempt_name,
                    self.settings.vision_model,
                    perf_counter() - started_at,
                )
                return payload
            except (ValueError, ValidationError, json.JSONDecodeError) as exc:
                errors.append(str(exc))
                logger.warning(
                    "AI image metadata attempt returned invalid JSON attempt=%s model=%s duration_seconds=%.2f error=%s",
                    attempt_name,
                    self.settings.vision_model,
                    perf_counter() - started_at,
                    exc,
                )
                continue
            except httpx.HTTPError as exc:
                logger.warning(
                    "AI image metadata request failed attempt=%s model=%s duration_seconds=%.2f error=%s",
                    attempt_name,
                    self.settings.vision_model,
                    perf_counter() - started_at,
                    exc,
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Ollama request failed: {exc}",
                ) from exc

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI response was not valid JSON after retry. {'; '.join(errors)}",
        )

    def _request_visual_description(self, preview_path: Path) -> str:
        prompt = (
            "Describe only the visible image content in 3-5 short factual phrases. "
            "Mention people, objects, setting, colors, and readable text only if visible. "
            "Do not write SEO metadata."
        )
        started_at = perf_counter()
        try:
            logger.info(
                "Requesting AI visual facts model=%s timeout_seconds=%s",
                self.settings.vision_model,
                self.settings.ollama_timeout_seconds,
            )
            content = self.vision_client.generate_image_metadata(
                preview_path,
                prompt,
                options={"num_predict": 120},
            )
            description = self._clean_description(content)
            if not description:
                raise ValueError("Vision model returned an empty visual description.")
            logger.info(
                "AI visual facts succeeded model=%s duration_seconds=%.2f",
                self.settings.vision_model,
                perf_counter() - started_at,
            )
            return description
        except httpx.HTTPError as exc:
            logger.warning(
                "AI visual facts request failed model=%s duration_seconds=%.2f error=%s",
                self.settings.vision_model,
                perf_counter() - started_at,
                exc,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Ollama vision request failed: {exc}",
            ) from exc

    def _request_language_metadata(self, visual_description: str, brand_context: str) -> AiImageMetadataPayload:
        errors: list[str] = []
        timeout_seconds = min(self.settings.ai_language_timeout_seconds, self.settings.ollama_timeout_seconds)
        prompts = (
            ("main", self._language_metadata_prompt(visual_description, brand_context)),
            ("json_retry", self._language_metadata_retry_prompt(visual_description, brand_context)),
        )
        for attempt_name, prompt in prompts:
            started_at = perf_counter()
            try:
                logger.info(
                    "Requesting AI language metadata attempt=%s model=%s timeout_seconds=%s",
                    attempt_name,
                    self.settings.language_model,
                    timeout_seconds,
                )
                content = self.language_client.generate_text(
                    prompt,
                    timeout_seconds=timeout_seconds,
                    options={"num_predict": 320},
                )
                payload = self._parse_metadata_payload(content)
                logger.info(
                    "AI language metadata attempt succeeded attempt=%s model=%s duration_seconds=%.2f",
                    attempt_name,
                    self.settings.language_model,
                    perf_counter() - started_at,
                )
                return payload
            except (ValueError, ValidationError, json.JSONDecodeError) as exc:
                errors.append(str(exc))
                logger.warning(
                    "AI language metadata returned invalid JSON attempt=%s model=%s duration_seconds=%.2f error=%s",
                    attempt_name,
                    self.settings.language_model,
                    perf_counter() - started_at,
                    exc,
                )
                continue
            except httpx.HTTPError as exc:
                logger.warning(
                    "AI language metadata request failed attempt=%s model=%s duration_seconds=%.2f error=%s",
                    attempt_name,
                    self.settings.language_model,
                    perf_counter() - started_at,
                    exc,
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Ollama language request failed: {exc}",
                ) from exc

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI language response was not valid JSON after retry. {'; '.join(errors)}",
        )

    def _parse_metadata_payload(self, content: str) -> AiImageMetadataPayload:
        data = json.loads(self._extract_json_object(content))
        if not isinstance(data, dict):
            raise ValueError("AI metadata response must be a JSON object.")

        normalized: dict[str, Any] = {
            "filename": data.get("filename", ""),
            "alt_text": data.get("alt_text", ""),
            "caption": data.get("caption", ""),
            "confidence": data.get("confidence", 0.0),
        }
        return AiImageMetadataPayload.model_validate(normalized)

    def _extract_json_object(self, content: str) -> str:
        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
            stripped = re.sub(r"\s*```$", "", stripped)

        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("AI response did not contain a JSON object.")
        return stripped[start : end + 1]

    def _clean_description(self, content: str) -> str:
        description = content.strip()
        if description.startswith("```"):
            description = re.sub(r"^```(?:text)?\s*", "", description, flags=re.IGNORECASE)
            description = re.sub(r"\s*```$", "", description)
        description = re.sub(r"\s+", " ", description).strip()
        return description[:240].strip()

    def _brand_context_for_job(self, job_id: str) -> str:
        data = self.upload_service.read_job_data(job_id)
        brand_context = data.get("brand_context")
        if not isinstance(brand_context, dict):
            return ""
        combined_text = brand_context.get("combined_text", "")
        if not isinstance(combined_text, str):
            return ""
        return combined_text[: self.settings.max_brand_context_chars].strip()

    def _metadata_prompt(self, base_prompt: str, brand_context: str) -> str:
        if not brand_context:
            return base_prompt
        return (
            base_prompt.rstrip()
            + IMAGE_METADATA_BRAND_CONTEXT_BLOCK.format(brand_context=brand_context)
        )

    def _language_metadata_prompt(self, visual_description: str, brand_context: str) -> str:
        prompt = f"""/no_think
You are generating SEO-friendly image metadata from verified visual facts.

Return only valid JSON.

Verified visual facts:
{visual_description}

Rules:
1. Use only the verified visual facts for visible image details.
2. Generate concise accessible alt text.
3. Generate an SEO-friendly filename under 50 characters.
4. Generate a short natural caption as one sentence.
5. Avoid keyword stuffing.
6. Use lowercase hyphenated filenames.
7. Do not include the file extension in the filename.
8. Do not repeat the same object, color, or phrase.

Return:
{{
  "filename": "",
  "alt_text": "",
  "caption": "",
  "confidence": 0.0
}}
"""
        return self._metadata_prompt(prompt, brand_context)

    def _language_metadata_retry_prompt(self, visual_description: str, brand_context: str) -> str:
        prompt = f"""/no_think
Return only valid JSON for image metadata.

Verified visual facts:
{visual_description}

Required JSON shape:
{{
  "filename": "concise-lowercase-filename",
  "alt_text": "Concise accessible alt text under 125 characters.",
  "caption": "Short natural caption without repeated phrases.",
  "confidence": 0.0
}}
"""
        return self._metadata_prompt(prompt, brand_context)

    def _metadata_model_label(self) -> str:
        if self.injected_client is not None:
            return self.settings.ollama_model
        return f"{self.settings.vision_model} + {self.settings.language_model}"

    def _write_metadata_response(self, response: ImageMetadataListResponse) -> None:
        data = self.upload_service.read_job_data(response.job_id)
        data["image_metadata"] = response.model_dump()
        self.upload_service.write_job_data(response.job_id, data)

    def _failed_result(self, file_record: ImageUploadFileRecord, exc: Exception) -> ImageMetadataResult:
        return ImageMetadataResult(
            id=file_record.id,
            original_filename=file_record.original_filename,
            suggested_filename=slugify(Path(file_record.stored_filename).stem),
            alt_text="",
            caption="",
            confidence=0.0,
            status="failed",
            error_message=self._public_error_message(exc),
        )

    def _result_by_id(self, response: ImageMetadataListResponse, image_id: str) -> ImageMetadataResult:
        for result in response.results:
            if result.id == image_id:
                return result
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metadata result not found for this image.",
        )

    def _replace_metadata_result(
        self,
        job_id: str,
        current: ImageMetadataListResponse,
        next_result: ImageMetadataResult,
    ) -> None:
        replaced = False
        next_results: list[ImageMetadataResult] = []
        for result in current.results:
            if result.id == next_result.id:
                next_results.append(next_result)
                replaced = True
            else:
                next_results.append(result)
        if not replaced:
            next_results.append(next_result)
        self._write_metadata_response(
            ImageMetadataListResponse(
                job_id=job_id,
                provider=current.provider,
                model=current.model,
                vision_model=current.vision_model,
                language_model=current.language_model,
                results=next_results,
            )
        )

    def _merge_review_update(
        self,
        current_result: ImageMetadataResult,
        request: ImageMetadataUpdateRequest,
        image_context: ImageContext,
    ) -> ImageMetadataResult:
        suggested_filename = slugify(request.suggested_filename)
        alt_text = request.alt_text.strip()
        caption = request.caption.strip()
        if not suggested_filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Suggested filename must contain letters or numbers after sanitization.",
            )
        if not alt_text and not self.settings.context_metadata_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Alt text cannot be empty.",
            )
        if not caption:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Caption cannot be empty.",
            )

        changed = any(
            [
                suggested_filename != current_result.suggested_filename,
                alt_text != current_result.alt_text,
                caption != current_result.caption,
            ]
        )
        next_status = request.status or current_result.status
        if request.status is None and changed and current_result.status in {"accepted", "failed"}:
            next_status = "needs_review"

        result = ImageMetadataResult(
            id=current_result.id,
            original_filename=current_result.original_filename,
            suggested_filename=suggested_filename,
            alt_text=alt_text,
            caption=caption,
            confidence=current_result.confidence,
            status=next_status,
            error_message="" if next_status != "failed" else current_result.error_message,
        )
        if next_status == "accepted" and self.settings.context_metadata_enabled:
            self._validate_purpose_approval(result, image_context)
        return result

    def _accepted_result(self, current_result: ImageMetadataResult, image_context: ImageContext) -> ImageMetadataResult:
        if current_result.status == "failed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed metadata rows must be regenerated or edited before approval.",
            )
        if not current_result.suggested_filename.strip() or not current_result.caption.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename and caption are required before approval.",
            )

        if self.settings.context_metadata_enabled:
            self._validate_purpose_approval(current_result, image_context)
        elif not current_result.alt_text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Alt text is required before approval.",
            )

        return ImageMetadataResult(
            id=current_result.id,
            original_filename=current_result.original_filename,
            suggested_filename=current_result.suggested_filename,
            alt_text=current_result.alt_text,
            caption=current_result.caption,
            confidence=current_result.confidence,
            status="accepted",
            error_message="",
        )

    def _validate_purpose_approval(self, result: ImageMetadataResult, image_context: ImageContext) -> None:
        if not image_context.purpose_confirmed or image_context.purpose == "unknown":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image purpose must be human-confirmed before approval.",
            )

        alt_text = result.alt_text.strip()
        if image_context.purpose in {"decorative", "redundant"}:
            if alt_text:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{image_context.purpose.capitalize()} images must use empty alt text.",
                )
        elif not alt_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{image_context.purpose.capitalize()} images require non-empty alt text.",
            )

        if image_context.purpose == "functional" and not (
            image_context.functional_action.strip() or image_context.link_destination.strip()
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Functional images require an action or link destination before approval.",
            )

        if image_context.purpose == "complex" and not (
            image_context.long_description_available or image_context.complex_description_acknowledged
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Complex images require a long description or explicit reviewer acknowledgement.",
            )

    def _image_context(self, job_id: str, image_id: str) -> ImageContext:
        data = self.upload_service.read_job_data(job_id)
        contexts = data.get("image_contexts")
        if not isinstance(contexts, dict):
            return ImageContext()
        value = contexts.get(image_id)
        return ImageContext.model_validate(value) if isinstance(value, dict) else ImageContext()

    def _response_from_job_data(self, job_id: str, data: dict[str, Any]) -> ImageMetadataListResponse:
        metadata = data.get("image_metadata")
        if isinstance(metadata, dict):
            return ImageMetadataListResponse.model_validate(metadata)
        return ImageMetadataListResponse(
            job_id=job_id,
            provider=self.settings.ai_provider,
            model=self._metadata_model_label(),
            vision_model=self.settings.vision_model,
            language_model=self.settings.language_model,
            results=[],
        )

    def _public_error_message(self, exc: Exception) -> str:
        if isinstance(exc, HTTPException):
            return str(exc.detail)
        return str(exc) or "Metadata generation failed."

    def _csv_fields(self, fields: list[str] | None) -> list[str]:
        if not fields:
            return list(self.CSV_FIELD_LABELS)

        selected: list[str] = []
        invalid: list[str] = []
        for field in fields:
            normalized = field.strip()
            if not normalized:
                continue
            if normalized not in self.CSV_FIELD_LABELS:
                invalid.append(normalized)
                continue
            if normalized not in selected:
                selected.append(normalized)

        if invalid:
            accepted = ", ".join(self.CSV_FIELD_LABELS)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported CSV field(s): {', '.join(invalid)}. Accepted fields: {accepted}.",
            )
        if not selected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one CSV field must be selected.",
            )
        return selected

    def _metadata_zip_csv_fields(self) -> list[str]:
        return [
            "original_filename",
            "suggested_filename",
            "download_filename",
            "alt_text",
            "caption",
            "confidence",
            "metadata_status",
            "content_type",
            "size_bytes",
            "download_path",
        ]

    def _processed_results_by_id(self, job_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
        compression = job_data.get("compression")
        if not isinstance(compression, dict):
            return {}
        results = compression.get("results")
        if not isinstance(results, list):
            return {}
        return {
            str(result["id"]): result
            for result in results
            if isinstance(result, dict) and result.get("id")
        }

    def _csv_row(
        self,
        job_id: str,
        file_record: ImageUploadFileRecord,
        metadata: ImageMetadataResult | None,
        processed: dict[str, Any] | None,
    ) -> dict[str, str | int | float]:
        processed_filename = str(processed.get("processed_filename", "")) if processed else ""
        processed_relative_path = str(processed.get("relative_path", "")) if processed else ""
        extension = Path(processed_filename or file_record.stored_filename).suffix
        metadata_filename = metadata.suggested_filename if metadata and metadata.suggested_filename else None
        download_filename = self._download_filename(
            metadata_filename=metadata_filename,
            fallback_filename=processed_filename or file_record.stored_filename,
            extension=extension,
        )

        return {
            "image_id": file_record.id,
            "original_filename": file_record.original_filename,
            "suggested_filename": metadata.suggested_filename if metadata else "",
            "download_filename": download_filename,
            "source_path": f"uploads/{job_id}/{file_record.relative_path}",
            "processed_filename": processed_filename,
            "processed_path": f"processed/{job_id}/{processed_relative_path}" if processed_relative_path else "",
            "download_path": f"/api/jobs/{job_id}/images/{file_record.id}/download",
            "alt_text": metadata.alt_text if metadata else "",
            "caption": metadata.caption if metadata else "",
            "confidence": metadata.confidence if metadata else "",
            "metadata_status": metadata.status if metadata else "pending",
            "error_message": metadata.error_message if metadata else "",
            "content_type": file_record.content_type,
            "size_bytes": file_record.size_bytes,
            "source": file_record.source,
            "source_archive": file_record.source_archive or "",
        }

    def _metadata_download_source_path(
        self,
        job_id: str,
        file_record: ImageUploadFileRecord,
        processed: dict[str, Any] | None,
    ) -> Path:
        processed_relative_path = str(processed.get("relative_path", "")) if processed else ""
        if processed_relative_path:
            processed_path = self.processed_root / job_id / processed_relative_path
            if processed_path.exists() and processed_path.is_file():
                return processed_path

        upload_path = self.upload_root / job_id / file_record.relative_path
        if upload_path.exists() and upload_path.is_file():
            return upload_path

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Image file is missing: {file_record.original_filename}",
        )

    def _download_filename(
        self,
        metadata_filename: str | None,
        fallback_filename: str,
        extension: str,
    ) -> str:
        selected = metadata_filename or fallback_filename
        sanitized = sanitize_filename(selected)
        stem = Path(sanitized).stem or Path(fallback_filename).stem
        return f"{stem}{extension.lower()}"
