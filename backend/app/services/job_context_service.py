from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.config import Settings
from app.errors import ApiError
from app.schemas.responses import (
    ImageContext,
    ImageContextResponse,
    ImageContextUpdateRequest,
    PageContext,
    PageContextResponse,
    PageContextUpdateRequest,
)
from app.services.image_upload_service import ImageUploadService


class JobContextService:
    SCHEMA_VERSION = 2

    def __init__(self, settings: Settings) -> None:
        self.upload_service = ImageUploadService(settings)

    def get_page_context(self, job_id: str) -> PageContextResponse:
        self.upload_service.read_job(job_id)
        data = self.upload_service.read_job_data(job_id)
        return PageContextResponse(
            job_id=job_id,
            page_context=self._page_context_from_data(data),
        )

    def update_page_context(self, job_id: str, request: PageContextUpdateRequest) -> PageContextResponse:
        self.upload_service.read_job(job_id)
        data = self._normalized_job_data(job_id)
        page_context = PageContext(
            **request.model_dump(),
            updated_at=datetime.now(timezone.utc),
        )
        data["page_context"] = page_context.model_dump(mode="json")
        self.upload_service.write_job_data(job_id, data)
        return PageContextResponse(job_id=job_id, page_context=page_context)

    def get_image_context(self, job_id: str, image_id: str) -> ImageContextResponse:
        self._require_image(job_id, image_id)
        data = self.upload_service.read_job_data(job_id)
        return ImageContextResponse(
            job_id=job_id,
            image_id=image_id,
            image_context=self._image_context_from_data(data, image_id),
        )

    def update_image_context(
        self,
        job_id: str,
        image_id: str,
        request: ImageContextUpdateRequest,
    ) -> ImageContextResponse:
        self._require_image(job_id, image_id)
        if request.purpose_confirmed and request.purpose == "unknown":
            raise ApiError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="CONTEXT_VALIDATION_FAILED",
                message="Unknown image purpose cannot be marked as human-confirmed.",
                field="purpose_confirmed",
            )
        if request.purpose_confidence is not None and request.suggested_purpose is None:
            raise ApiError(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="CONTEXT_VALIDATION_FAILED",
                message="Purpose confidence requires a suggested purpose.",
                field="purpose_confidence",
            )

        data = self._normalized_job_data(job_id)
        image_context = ImageContext(
            **request.model_dump(),
            purpose_source="human_confirmed" if request.purpose_confirmed else "unconfirmed",
            updated_at=datetime.now(timezone.utc),
        )
        image_contexts = data["image_contexts"]
        assert isinstance(image_contexts, dict)
        image_contexts[image_id] = image_context.model_dump(mode="json")
        self.upload_service.write_job_data(job_id, data)
        return ImageContextResponse(
            job_id=job_id,
            image_id=image_id,
            image_context=image_context,
        )

    def _normalized_job_data(self, job_id: str) -> dict[str, Any]:
        data = self.upload_service.read_job_data(job_id)
        data["schema_version"] = self.SCHEMA_VERSION
        page_context = self._page_context_from_data(data)
        data["page_context"] = page_context.model_dump(mode="json")
        if not isinstance(data.get("image_contexts"), dict):
            data["image_contexts"] = {}
        return data

    @staticmethod
    def _page_context_from_data(data: dict[str, Any]) -> PageContext:
        value = data.get("page_context")
        return PageContext.model_validate(value) if isinstance(value, dict) else PageContext()

    @staticmethod
    def _image_context_from_data(data: dict[str, Any], image_id: str) -> ImageContext:
        contexts = data.get("image_contexts")
        if not isinstance(contexts, dict):
            return ImageContext()
        value = contexts.get(image_id)
        return ImageContext.model_validate(value) if isinstance(value, dict) else ImageContext()

    def _require_image(self, job_id: str, image_id: str) -> None:
        job = self.upload_service.read_job(job_id)
        if not any(file_record.id == image_id for file_record in job.files):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image file not found.")
