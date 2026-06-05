import json
import logging
from pathlib import Path
import re
from time import perf_counter
from typing import Protocol
from uuid import uuid4

import httpx
from fastapi import HTTPException, status
from PIL import Image, ImageOps
from pydantic import BaseModel, Field, ValidationError

from app.ai.ollama_client import OllamaClient
from app.config import Settings
from app.schemas.responses import (
    CropBox,
    CropReviewItem,
    CropReviewResponse,
    ImageCompressionResponse,
    ImageCompressionResult,
    ImageCompressionSettings,
    ImageUploadFileRecord,
    ResizeInstructionResponse,
)
from app.services.image_upload_service import ImageUploadService
from app.utils.file_utils import dedupe_filename, sanitize_filename


logger = logging.getLogger(__name__)


class ImageCropClient(Protocol):
    def generate_image_metadata(self, image_path: Path, prompt: str) -> str:
        ...


class AiCropPayload(BaseModel):
    target_width: int | None = Field(default=None, ge=1)
    target_height: int | None = Field(default=None, ge=1)
    subject: str = ""
    bounding_box: CropBox
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""


class ImageProcessor:
    def __init__(self, settings: Settings, client: ImageCropClient | None = None) -> None:
        self.settings = settings
        self.upload_service = ImageUploadService(settings)
        self.upload_root = settings.storage_root / "uploads"
        self.processed_root = settings.storage_root / "processed"
        self.temp_root = settings.storage_root / "temp"
        self.client = client or OllamaClient(
            settings.ollama_base_url,
            settings.ollama_model,
            settings.ollama_timeout_seconds,
        )

    def compress_job(
        self,
        job_id: str,
        compression_settings: ImageCompressionSettings,
    ) -> ImageCompressionResponse:
        job = self.upload_service.read_job(job_id)
        if not job.files:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job has no images to process.")

        processed_dir = self.processed_root / job_id / "images"
        processed_dir.mkdir(parents=True, exist_ok=True)

        used_output_names: set[str] = set()
        results = [
            self._compress_file(
                job_id,
                file_record,
                compression_settings,
                processed_dir,
                used_output_names,
            )
            for file_record in job.files
        ]

        response = ImageCompressionResponse(
            job_id=job_id,
            status="processed",
            settings=compression_settings,
            results=results,
        )
        self.upload_service.write_job(response)
        return response

    def parse_resize_instruction(self, job_id: str, instruction: str) -> ResizeInstructionResponse:
        normalized = instruction.lower()
        settings = ImageCompressionSettings()
        notes: list[str] = []
        warnings: list[str] = []

        size_match = re.search(r"(\d{2,5})\s*(?:x|×|by)\s*(\d{2,5})", normalized)
        if size_match:
            settings.target_width = int(size_match.group(1))
            settings.target_height = int(size_match.group(2))
            settings.resize_mode = "exact"
            notes.append(f"Detected exact target size {settings.target_width} x {settings.target_height}.")

        for output_format in ("webp", "jpg", "png"):
            if output_format in normalized:
                settings.output_format = output_format  # type: ignore[assignment]
                notes.append(f"Detected output format {output_format.upper()}.")
                break

        if "fit" in normalized or "whole image" in normalized or "keep whole" in normalized:
            settings.resize_mode = "fit_inside"
            notes.append("Detected fit-inside behavior to preserve the whole image.")
        elif "crop" in normalized and settings.target_width and settings.target_height:
            settings.resize_mode = "exact"
            notes.append("Detected crop-to-exact behavior.")

        if "lossless" in normalized:
            settings.mode = "lossless"
            notes.append("Detected lossless compression.")

        quality_match = re.search(r"quality\s*(\d{1,3})", normalized)
        if quality_match:
            settings.quality = min(100, max(1, int(quality_match.group(1))))
            notes.append(f"Detected quality {settings.quality}.")

        if not notes:
            notes.append("No specific resize instruction detected; using RFC processing defaults.")

        if self._should_request_ai_crop(normalized, settings):
            ai_notes, ai_warnings = self._apply_ai_crop_suggestions(job_id, instruction, settings)
            notes.extend(ai_notes)
            warnings.extend(ai_warnings)

        return ResizeInstructionResponse(
            instruction=instruction,
            settings=settings,
            notes=notes,
            warnings=warnings,
        )

    def crop_review(self, job_id: str, settings: ImageCompressionSettings) -> CropReviewResponse:
        job = self.upload_service.read_job(job_id)
        target_width, target_height = self._target_size(settings)
        items: list[CropReviewItem] = []

        for file_record in job.files:
            source_path = self.upload_root / job_id / file_record.relative_path
            if not source_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Uploaded file is missing: {file_record.relative_path}",
                )

            with Image.open(source_path) as image:
                image = ImageOps.exif_transpose(image)
                source_ratio = image.width / image.height

            target_ratio = target_width / target_height
            ratio_delta = abs(source_ratio - target_ratio)
            needs_review = settings.resize_mode == "exact" and ratio_delta > 0.01
            crop_box = settings.crop_boxes.get(file_record.id)
            source = "ai" if crop_box else "center"
            focus_x = settings.crop_focus_x
            focus_y = settings.crop_focus_y
            confidence = settings.crop_confidences.get(file_record.id, 0.85 if crop_box else 0.5)
            if crop_box:
                focus_x = min(1.0, max(0.0, crop_box.x + (crop_box.width / 2)))
                focus_y = min(1.0, max(0.0, crop_box.y + (crop_box.height / 2)))

            items.append(
                CropReviewItem(
                    id=file_record.id,
                    original_filename=file_record.original_filename,
                    width=image.width,
                    height=image.height,
                    target_width=target_width,
                    target_height=target_height,
                    needs_review=needs_review or bool(crop_box),
                    focus_x=focus_x,
                    focus_y=focus_y,
                    confidence=confidence,
                    source=source,
                    crop_box=crop_box,
                    subject=settings.crop_subjects.get(file_record.id, ""),
                    reason=settings.crop_reasons.get(file_record.id, ""),
                )
            )

        return CropReviewResponse(
            job_id=job_id,
            target_width=target_width,
            target_height=target_height,
            items=items,
        )

    def processed_file_path(self, job_id: str, filename: str) -> Path:
        if Path(filename).name != filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid processed filename.")

        processed_path = self.processed_root / job_id / "images" / filename
        processed_root = (self.processed_root / job_id / "images").resolve()
        resolved_path = processed_path.resolve()

        if processed_root not in resolved_path.parents:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid processed filename.")

        if not resolved_path.exists() or not resolved_path.is_file():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processed file not found.")

        return resolved_path

    def image_download(self, job_id: str, image_id: str, filename: str | None = None) -> tuple[Path, str]:
        job = self.upload_service.read_job(job_id)
        file_record = next((record for record in job.files if record.id == image_id), None)
        if not file_record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image file not found.")

        job_data = self.upload_service.read_job_data(job_id)
        processed_result = self._processed_result_for_image(job_data, image_id)
        if processed_result:
            processed_filename = str(processed_result["processed_filename"])
            path = self.processed_file_path(job_id, processed_filename)
            return path, self._download_filename(
                requested_filename=filename,
                metadata_filename=self._metadata_filename_for_image(job_data, image_id),
                fallback_filename=processed_filename,
                extension=path.suffix,
            )

        source_path = self.upload_root / job_id / file_record.relative_path
        if not source_path.exists() or not source_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Uploaded file is missing: {file_record.relative_path}",
            )

        return source_path, self._download_filename(
            requested_filename=filename,
            metadata_filename=self._metadata_filename_for_image(job_data, image_id),
            fallback_filename=file_record.stored_filename,
            extension=source_path.suffix,
        )

    def _processed_result_for_image(self, job_data: dict, image_id: str) -> dict | None:
        compression = job_data.get("compression")
        if not isinstance(compression, dict):
            return None

        results = compression.get("results")
        if not isinstance(results, list):
            return None

        for result in results:
            if isinstance(result, dict) and result.get("id") == image_id and result.get("processed_filename"):
                return result
        return None

    def _metadata_filename_for_image(self, job_data: dict, image_id: str) -> str | None:
        metadata = job_data.get("image_metadata")
        if not isinstance(metadata, dict):
            return None

        results = metadata.get("results")
        if not isinstance(results, list):
            return None

        for result in results:
            if isinstance(result, dict) and result.get("id") == image_id and result.get("suggested_filename"):
                return str(result["suggested_filename"])
        return None

    def _download_filename(
        self,
        requested_filename: str | None,
        metadata_filename: str | None,
        fallback_filename: str,
        extension: str,
    ) -> str:
        selected = requested_filename or metadata_filename or fallback_filename
        sanitized = sanitize_filename(selected)
        stem = Path(sanitized).stem or Path(fallback_filename).stem
        return f"{stem}{extension.lower()}"

    def _compress_file(
        self,
        job_id: str,
        file_record: ImageUploadFileRecord,
        settings: ImageCompressionSettings,
        processed_dir: Path,
        used_output_names: set[str],
    ) -> ImageCompressionResult:
        source_path = self.upload_root / job_id / file_record.relative_path
        if not source_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Uploaded file is missing: {file_record.relative_path}",
            )

        processed_filename = self._processed_filename(file_record, settings, used_output_names)
        processed_path = processed_dir / processed_filename

        with Image.open(source_path) as image:
            image = ImageOps.exif_transpose(image)
            image = self._resize_if_needed(image, settings, file_record.id)
            save_kwargs = self._save_kwargs(image, processed_path, settings)
            image_to_save = self._prepare_for_save(image, processed_path)
            image_to_save.save(processed_path, **save_kwargs)

        processed_size = processed_path.stat().st_size
        original_size = source_path.stat().st_size
        reduction = 0.0
        if original_size > 0:
            reduction = round(((original_size - processed_size) / original_size) * 100, 2)

        with Image.open(processed_path) as processed_image:
            width, height = processed_image.size

        return ImageCompressionResult(
            id=file_record.id,
            original_filename=file_record.original_filename,
            stored_filename=file_record.stored_filename,
            processed_filename=processed_filename,
            relative_path=f"images/{processed_filename}",
            original_format=source_path.suffix.lower().lstrip("."),
            new_format=processed_path.suffix.lower().lstrip("."),
            original_size_bytes=original_size,
            processed_size_bytes=processed_size,
            reduction_percent=reduction,
            width=width,
            height=height,
            status="processed",
        )

    def _processed_filename(
        self,
        file_record: ImageUploadFileRecord,
        settings: ImageCompressionSettings,
        used_output_names: set[str],
    ) -> str:
        requested_name = settings.filename_overrides.get(file_record.id, file_record.stored_filename)
        sanitized_name = sanitize_filename(requested_name)
        extension = self._target_extension(file_record.stored_filename, settings)
        filename = f"{Path(sanitized_name).stem}{extension}"
        return dedupe_filename(filename, used_output_names)

    def _target_extension(self, stored_filename: str, settings: ImageCompressionSettings) -> str:
        if settings.output_format == "keep_original":
            return Path(stored_filename).suffix.lower()
        if settings.output_format == "jpg":
            return ".jpg"
        return f".{settings.output_format}"

    def _resize_if_needed(
        self,
        image: Image.Image,
        settings: ImageCompressionSettings,
        image_id: str | None = None,
    ) -> Image.Image:
        if settings.resize_mode == "exact":
            target_width, target_height = self._target_size(settings)
            crop_box = settings.crop_boxes.get(image_id or "")
            if crop_box:
                return self._resize_crop_box_exact(image, target_width, target_height, crop_box)
            return self._resize_crop_exact(image, target_width, target_height, settings)

        if settings.resize_mode == "fit_inside":
            target_width, target_height = self._target_size(settings)
            return self._resize_fit_inside(image, target_width, target_height, settings)

        max_width = None
        if settings.resize_mode == "max_1920":
            max_width = 1920
        elif settings.resize_mode == "max_1200":
            max_width = 1200
        elif settings.resize_mode == "custom":
            max_width = settings.custom_max_width

        if not max_width or image.width <= max_width:
            return image.copy()

        ratio = max_width / image.width
        new_height = max(1, round(image.height * ratio))
        return image.resize((max_width, new_height), Image.Resampling.LANCZOS)

    def _should_request_ai_crop(self, normalized_instruction: str, settings: ImageCompressionSettings) -> bool:
        if settings.resize_mode != "exact" or not settings.target_width or not settings.target_height:
            return False
        ai_terms = (
            "crop",
            "focus",
            "show",
            "showing",
            "person",
            "people",
            "wearing",
            "subject",
            "only",
        )
        return any(term in normalized_instruction for term in ai_terms)

    def _apply_ai_crop_suggestions(
        self,
        job_id: str,
        instruction: str,
        settings: ImageCompressionSettings,
    ) -> tuple[list[str], list[str]]:
        job = self.upload_service.read_job(job_id)
        notes: list[str] = []
        warnings: list[str] = []

        for file_record in job.files:
            source_path = self.upload_root / job_id / file_record.relative_path
            if not source_path.exists():
                continue

            preview_path = self._create_ai_preview(job_id, source_path)
            try:
                payload = self._request_ai_crop(preview_path, instruction, settings)
                with Image.open(source_path) as image:
                    image = ImageOps.exif_transpose(image)
                    crop_box = self._subject_box_to_crop_box(
                        payload.bounding_box,
                        image.width,
                        image.height,
                        settings.target_width or image.width,
                        settings.target_height or image.height,
                    )
                settings.crop_boxes[file_record.id] = crop_box
                settings.crop_subjects[file_record.id] = payload.subject
                settings.crop_reasons[file_record.id] = payload.reason
                settings.crop_confidences[file_record.id] = payload.confidence
                notes.append(
                    f"AI suggested a crop for {file_record.original_filename}"
                    f"{f' around {payload.subject}' if payload.subject else ''}."
                )
            except Exception as exc:
                logger.warning(
                    "AI crop suggestion failed job_id=%s image_id=%s error=%s",
                    job_id,
                    file_record.id,
                    exc,
                )
                warnings.append(
                    f"AI crop suggestion failed for {file_record.original_filename}; using center crop fallback."
                )
            finally:
                preview_path.unlink(missing_ok=True)

        return notes, warnings

    def _create_ai_preview(self, job_id: str, source_path: Path) -> Path:
        preview_dir = self.temp_root / job_id
        preview_dir.mkdir(parents=True, exist_ok=True)
        preview_path = preview_dir / f"crop-preview-{uuid4().hex[:12]}.jpg"

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

    def _request_ai_crop(
        self,
        preview_path: Path,
        instruction: str,
        settings: ImageCompressionSettings,
    ) -> AiCropPayload:
        prompt = self._ai_crop_prompt(instruction, settings)
        started_at = perf_counter()
        try:
            logger.info(
                "Requesting AI crop suggestion model=%s timeout_seconds=%s",
                self.settings.ollama_model,
                self.settings.ollama_timeout_seconds,
            )
            content = self.client.generate_image_metadata(preview_path, prompt)
            data = json.loads(self._extract_json_object(content))
            payload = AiCropPayload.model_validate(data)
            logger.info(
                "AI crop suggestion succeeded model=%s duration_seconds=%.2f",
                self.settings.ollama_model,
                perf_counter() - started_at,
            )
            return payload
        except (ValueError, ValidationError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI crop response was not valid JSON: {exc}",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Ollama crop request failed: {exc}",
            ) from exc

    def _ai_crop_prompt(self, instruction: str, settings: ImageCompressionSettings) -> str:
        return f"""You are helping crop an image for a website.

Return only valid JSON. Do not include markdown or commentary.

User instruction:
{instruction}

Target output size:
{settings.target_width} x {settings.target_height}

Identify the requested visible subject. Return a normalized bounding box around that subject in the source image.
Coordinates must be from 0.0 to 1.0, where x/y are the top-left corner and width/height are box size.
If the user asks for only one person or object, box only that requested subject.

Return:
{{
  "target_width": {settings.target_width},
  "target_height": {settings.target_height},
  "subject": "",
  "bounding_box": {{"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0}},
  "confidence": 0.0,
  "reason": ""
}}
"""

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

    def _subject_box_to_crop_box(
        self,
        subject_box: CropBox,
        image_width: int,
        image_height: int,
        target_width: int,
        target_height: int,
    ) -> CropBox:
        subject_left = subject_box.x * image_width
        subject_top = subject_box.y * image_height
        subject_width = max(1.0, subject_box.width * image_width)
        subject_height = max(1.0, subject_box.height * image_height)
        subject_center_x = subject_left + subject_width / 2
        subject_center_y = subject_top + subject_height / 2

        target_ratio = target_width / target_height
        margin = 1.18
        crop_width = subject_width * margin
        crop_height = subject_height * margin

        if crop_width / crop_height < target_ratio:
            crop_width = crop_height * target_ratio
        else:
            crop_height = crop_width / target_ratio

        crop_width = min(crop_width, image_width)
        crop_height = min(crop_height, image_height)
        left = subject_center_x - crop_width / 2
        top = subject_center_y - crop_height / 2
        left = min(max(0.0, left), max(0.0, image_width - crop_width))
        top = min(max(0.0, top), max(0.0, image_height - crop_height))

        return CropBox(
            x=left / image_width,
            y=top / image_height,
            width=crop_width / image_width,
            height=crop_height / image_height,
        )

    def _resize_crop_box_exact(
        self,
        image: Image.Image,
        target_width: int,
        target_height: int,
        crop_box: CropBox,
    ) -> Image.Image:
        left = round(crop_box.x * image.width)
        top = round(crop_box.y * image.height)
        right = round((crop_box.x + crop_box.width) * image.width)
        bottom = round((crop_box.y + crop_box.height) * image.height)

        left = min(max(0, left), image.width - 1)
        top = min(max(0, top), image.height - 1)
        right = min(max(left + 1, right), image.width)
        bottom = min(max(top + 1, bottom), image.height)

        cropped = image.crop((left, top, right, bottom))
        return cropped.resize((target_width, target_height), Image.Resampling.LANCZOS)

    def _target_size(self, settings: ImageCompressionSettings) -> tuple[int, int]:
        if not settings.target_width or not settings.target_height:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="target_width and target_height are required for exact and fit-inside resize modes.",
            )
        return settings.target_width, settings.target_height

    def _resize_crop_exact(
        self,
        image: Image.Image,
        target_width: int,
        target_height: int,
        settings: ImageCompressionSettings,
    ) -> Image.Image:
        if settings.prevent_upscaling and (image.width < target_width or image.height < target_height):
            return self._resize_fit_inside(image, target_width, target_height, settings)

        scale = max(target_width / image.width, target_height / image.height)
        resized_width = max(target_width, round(image.width * scale))
        resized_height = max(target_height, round(image.height * scale))
        resized = image.resize((resized_width, resized_height), Image.Resampling.LANCZOS)

        max_left = resized_width - target_width
        max_top = resized_height - target_height
        left = round(max_left * settings.crop_focus_x)
        top = round(max_top * settings.crop_focus_y)
        return resized.crop((left, top, left + target_width, top + target_height))

    def _resize_fit_inside(
        self,
        image: Image.Image,
        target_width: int,
        target_height: int,
        settings: ImageCompressionSettings,
    ) -> Image.Image:
        scale = min(target_width / image.width, target_height / image.height)
        if settings.prevent_upscaling:
            scale = min(scale, 1.0)

        fitted_width = max(1, round(image.width * scale))
        fitted_height = max(1, round(image.height * scale))
        fitted = image.resize((fitted_width, fitted_height), Image.Resampling.LANCZOS)

        background = Image.new("RGBA", (target_width, target_height), self._hex_to_rgba(settings.pad_color))
        if fitted.mode not in {"RGBA", "LA"}:
            fitted = fitted.convert("RGBA")
        left = (target_width - fitted_width) // 2
        top = (target_height - fitted_height) // 2
        background.alpha_composite(fitted, (left, top))
        return background

    def _hex_to_rgba(self, value: str) -> tuple[int, int, int, int]:
        stripped = value.lstrip("#")
        return (
            int(stripped[0:2], 16),
            int(stripped[2:4], 16),
            int(stripped[4:6], 16),
            255,
        )

    def _prepare_for_save(self, image: Image.Image, output_path: Path) -> Image.Image:
        extension = output_path.suffix.lower()
        if extension in {".jpg", ".jpeg"} and image.mode in {"RGBA", "LA", "P"}:
            rgba_image = image.convert("RGBA")
            background = Image.new("RGBA", rgba_image.size, (255, 255, 255, 255))
            background.alpha_composite(rgba_image)
            return background.convert("RGB")
        if extension in {".jpg", ".jpeg"} and image.mode not in {"RGB", "L"}:
            return image.convert("RGB")
        return image

    def _save_kwargs(
        self,
        image: Image.Image,
        output_path: Path,
        settings: ImageCompressionSettings,
    ) -> dict[str, object]:
        extension = output_path.suffix.lower()
        kwargs: dict[str, object] = {}

        if extension in {".jpg", ".jpeg"}:
            kwargs["format"] = "JPEG"
            kwargs["quality"] = settings.quality if settings.mode == "lossy" else 95
            kwargs["optimize"] = True
            kwargs["progressive"] = True
        elif extension == ".webp":
            kwargs["format"] = "WEBP"
            if settings.mode == "lossless":
                kwargs["lossless"] = True
            else:
                kwargs["quality"] = settings.quality
            kwargs["method"] = 6
        elif extension == ".png":
            kwargs["format"] = "PNG"
            kwargs["optimize"] = True
            kwargs["compress_level"] = 9 if settings.mode == "lossless" else 6

        if not settings.strip_metadata and "exif" in image.info:
            kwargs["exif"] = image.info["exif"]

        return kwargs
