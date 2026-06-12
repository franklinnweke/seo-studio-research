import json
import logging
import re
import csv
from io import StringIO
from time import perf_counter
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

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
from app.schemas.responses import ImageMetadataListResponse, ImageMetadataResult, ImageUploadFileRecord
from app.services.image_upload_service import ImageUploadService
from app.utils.file_utils import sanitize_filename
from app.utils.slugify import slugify


logger = logging.getLogger(__name__)


class ImageMetadataClient(Protocol):
    def generate_image_metadata(self, image_path: Path, prompt: str) -> str:
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
        self.temp_root = settings.storage_root / "temp"
        self.client = client or OllamaClient(
            settings.ollama_base_url,
            settings.ollama_model,
            settings.ollama_timeout_seconds,
        )

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
            model=self.settings.ollama_model,
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
                model=self.settings.ollama_model,
                results=next_results,
            )
        )
        return result

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
                    self.settings.ollama_model,
                    self.settings.ollama_timeout_seconds,
                )
                content = self.client.generate_image_metadata(preview_path, prompt)
                payload = self._parse_metadata_payload(content)
                logger.info(
                    "AI image metadata attempt succeeded attempt=%s model=%s duration_seconds=%.2f",
                    attempt_name,
                    self.settings.ollama_model,
                    perf_counter() - started_at,
                )
                return payload
            except (ValueError, ValidationError, json.JSONDecodeError) as exc:
                errors.append(str(exc))
                logger.warning(
                    "AI image metadata attempt returned invalid JSON attempt=%s model=%s duration_seconds=%.2f error=%s",
                    attempt_name,
                    self.settings.ollama_model,
                    perf_counter() - started_at,
                    exc,
                )
                continue
            except httpx.HTTPError as exc:
                logger.warning(
                    "AI image metadata request failed attempt=%s model=%s duration_seconds=%.2f error=%s",
                    attempt_name,
                    self.settings.ollama_model,
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

    def _response_from_job_data(self, job_id: str, data: dict[str, Any]) -> ImageMetadataListResponse:
        metadata = data.get("image_metadata")
        if isinstance(metadata, dict):
            return ImageMetadataListResponse.model_validate(metadata)
        return ImageMetadataListResponse(
            job_id=job_id,
            provider=self.settings.ai_provider,
            model=self.settings.ollama_model,
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
