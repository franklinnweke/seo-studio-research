import json
import shutil
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError

from app.config import Settings
from app.schemas.responses import (
    ImageCompressionResponse,
    ImageJobCreateResponse,
    ImageUploadFileRecord,
    JobStatusResponse,
)
from app.utils.file_utils import dedupe_filename, sanitize_filename
from app.utils.validators import SUPPORTED_UPLOAD_EXTENSIONS, is_supported_image_extension
from app.utils.zip_utils import is_ignored_zip_entry, safe_zip_entry_name


class ImageUploadService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.upload_root = settings.storage_root / "uploads"

    async def create_job(self, uploads: list[UploadFile]) -> ImageJobCreateResponse:
        if not uploads:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one image or ZIP file is required.",
            )

        job_id = f"job_{uuid4().hex[:12]}"
        job_dir = self.upload_root / job_id
        images_dir = job_dir / "images"
        archives_dir = job_dir / "archives"
        images_dir.mkdir(parents=True, exist_ok=False)
        archives_dir.mkdir(parents=True, exist_ok=True)

        used_names: set[str] = set()
        records: list[ImageUploadFileRecord] = []

        try:
            for upload in uploads:
                await self._handle_upload(upload, records, used_names, images_dir, archives_dir)

            if not records:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No supported image files were found in the upload.",
                )

            if len(records) > self.settings.max_files_per_image_job:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Image jobs are limited to {self.settings.max_files_per_image_job} files.",
                )

            response = ImageJobCreateResponse(
                id=job_id,
                type="image",
                status="pending",
                accepted_extensions=sorted(SUPPORTED_UPLOAD_EXTENSIONS),
                files=records,
            )
            (job_dir / "job.json").write_text(response.model_dump_json(indent=2))
            return response
        except Exception:
            shutil.rmtree(job_dir, ignore_errors=True)
            raise

    def get_job(self, job_id: str) -> JobStatusResponse:
        job = self._read_job(job_id)
        return JobStatusResponse(
            id=job.id,
            type=job.type,
            status=job.status,
            file_count=len(job.files),
        )

    def list_files(self, job_id: str) -> list[ImageUploadFileRecord]:
        return self._read_job(job_id).files

    async def _handle_upload(
        self,
        upload: UploadFile,
        records: list[ImageUploadFileRecord],
        used_names: set[str],
        images_dir: Path,
        archives_dir: Path,
    ) -> None:
        original_filename = upload.filename or "upload"
        extension = Path(original_filename).suffix.lower()
        data = await upload.read()

        if extension == ".zip":
            self._validate_file_size(original_filename, len(data), self.settings.max_zip_file_size_bytes)
            archive_name = dedupe_filename(sanitize_filename(original_filename), used_names)
            (archives_dir / archive_name).write_bytes(data)
            self._extract_zip(data, original_filename, records, used_names, images_dir)
            return

        if not is_supported_image_extension(extension):
            self._raise_unsupported(original_filename)

        self._validate_file_size(original_filename, len(data), self.settings.max_upload_file_size_bytes)
        self._validate_image_bytes(original_filename, data)
        self._write_image_record(
            original_filename=original_filename,
            data=data,
            content_type=upload.content_type or self._content_type_for_extension(extension),
            source="upload",
            source_archive=None,
            records=records,
            used_names=used_names,
            images_dir=images_dir,
        )

    def _extract_zip(
        self,
        data: bytes,
        archive_filename: str,
        records: list[ImageUploadFileRecord],
        used_names: set[str],
        images_dir: Path,
    ) -> None:
        try:
            with ZipFile(BytesIO(data)) as archive:
                for info in archive.infolist():
                    if info.is_dir() or is_ignored_zip_entry(info.filename):
                        continue

                    entry_filename = safe_zip_entry_name(info)
                    extension = Path(entry_filename).suffix.lower()
                    if not is_supported_image_extension(extension):
                        self._raise_unsupported(entry_filename)

                    self._validate_file_size(
                        entry_filename,
                        info.file_size,
                        self.settings.max_upload_file_size_bytes,
                    )
                    image_data = archive.read(info)
                    self._validate_image_bytes(entry_filename, image_data)
                    self._write_image_record(
                        original_filename=entry_filename,
                        data=image_data,
                        content_type=self._content_type_for_extension(extension),
                        source="zip",
                        source_archive=archive_filename,
                        records=records,
                        used_names=used_names,
                        images_dir=images_dir,
                    )
        except BadZipFile as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{archive_filename} is not a readable ZIP file.",
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    def _write_image_record(
        self,
        original_filename: str,
        data: bytes,
        content_type: str,
        source: str,
        source_archive: str | None,
        records: list[ImageUploadFileRecord],
        used_names: set[str],
        images_dir: Path,
    ) -> None:
        stored_filename = dedupe_filename(sanitize_filename(original_filename), used_names)
        relative_path = f"images/{stored_filename}"
        (images_dir / stored_filename).write_bytes(data)
        records.append(
            ImageUploadFileRecord(
                id=f"file_{uuid4().hex[:12]}",
                original_filename=original_filename,
                stored_filename=stored_filename,
                relative_path=relative_path,
                content_type=content_type,
                size_bytes=len(data),
                source=source,  # type: ignore[arg-type]
                source_archive=source_archive,
            )
        )

    def read_job(self, job_id: str) -> ImageJobCreateResponse:
        return self._read_job(job_id)

    def write_job(self, job: ImageJobCreateResponse | ImageCompressionResponse) -> None:
        job_id = job.id if isinstance(job, ImageJobCreateResponse) else job.job_id
        job_file = self.upload_root / job_id / "job.json"
        if not job_file.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
        existing = json.loads(job_file.read_text())
        if isinstance(job, ImageCompressionResponse):
            existing["status"] = job.status
            existing["compression"] = job.model_dump()
            job_file.write_text(json.dumps(existing, indent=2))
            return

        job_file.write_text(job.model_dump_json(indent=2))

    def _read_job(self, job_id: str) -> ImageJobCreateResponse:
        job_file = self.upload_root / job_id / "job.json"
        if not job_file.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

        data = json.loads(job_file.read_text())
        return ImageJobCreateResponse.model_validate(data)

    def _validate_file_size(self, filename: str, size: int, limit: int) -> None:
        if size <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{filename} is empty.",
            )
        if size > limit:
            limit_mb = limit // (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{filename} exceeds the {limit_mb}MB size limit.",
            )

    def _validate_image_bytes(self, filename: str, data: bytes) -> None:
        try:
            with Image.open(BytesIO(data)) as image:
                image.verify()
        except (UnidentifiedImageError, OSError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{filename} is not a valid image file.",
            ) from exc

    def _raise_unsupported(self, filename: str) -> None:
        accepted = ", ".join(sorted(SUPPORTED_UPLOAD_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{filename} is not supported. Accepted extensions: {accepted}.",
        )

    def _content_type_for_extension(self, extension: str) -> str:
        return {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }.get(extension, "application/octet-stream")
