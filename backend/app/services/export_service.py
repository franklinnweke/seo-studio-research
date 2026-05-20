from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import HTTPException, status

from app.config import Settings
from app.services.image_upload_service import ImageUploadService


class ExportService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.upload_service = ImageUploadService(settings)
        self.processed_root = settings.storage_root / "processed"
        self.exports_root = settings.storage_root / "exports"

    def create_processed_images_zip(self, job_id: str) -> Path:
        self.upload_service.read_job(job_id)

        processed_images_dir = self.processed_root / job_id / "images"
        if not processed_images_dir.exists() or not processed_images_dir.is_dir():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Processed images not found. Process the image job before exporting ZIP.",
            )

        image_paths = sorted(path for path in processed_images_dir.iterdir() if path.is_file())
        if not image_paths:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Processed images not found. Process the image job before exporting ZIP.",
            )

        export_dir = self.exports_root / job_id
        export_dir.mkdir(parents=True, exist_ok=True)
        zip_path = export_dir / "processed-images.zip"

        with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
            for image_path in image_paths:
                archive.write(image_path, arcname=f"images/{image_path.name}")

        return zip_path
