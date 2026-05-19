from pathlib import Path

from fastapi import HTTPException, status
from PIL import Image, ImageOps

from app.config import Settings
from app.schemas.responses import (
    ImageCompressionResponse,
    ImageCompressionResult,
    ImageCompressionSettings,
    ImageUploadFileRecord,
)
from app.services.image_upload_service import ImageUploadService
from app.utils.file_utils import dedupe_filename, sanitize_filename


class ImageProcessor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.upload_service = ImageUploadService(settings)
        self.upload_root = settings.storage_root / "uploads"
        self.processed_root = settings.storage_root / "processed"

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
            image = self._resize_if_needed(image, settings)
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

    def _resize_if_needed(self, image: Image.Image, settings: ImageCompressionSettings) -> Image.Image:
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
