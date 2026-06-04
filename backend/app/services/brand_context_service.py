import re
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from fastapi import HTTPException, UploadFile, status

from app.config import Settings
from app.schemas.responses import BrandContextDocument, BrandContextResponse
from app.services.image_upload_service import ImageUploadService
from app.utils.file_utils import dedupe_filename, sanitize_filename


SUPPORTED_BRAND_CONTEXT_EXTENSIONS = {".txt", ".docx", ".pdf"}


class BrandContextService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.upload_service = ImageUploadService(settings)
        self.upload_root = settings.storage_root / "uploads"

    def get_brand_context(self, job_id: str) -> BrandContextResponse:
        self.upload_service.read_job(job_id)
        data = self.upload_service.read_job_data(job_id)
        return self._response_from_job_data(job_id, data)

    async def upload_brand_context(self, job_id: str, uploads: list[UploadFile]) -> BrandContextResponse:
        self.upload_service.read_job(job_id)
        if not uploads:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one brand context document is required.",
            )

        data = self.upload_service.read_job_data(job_id)
        current = self._response_from_job_data(job_id, data)
        documents_dir = self.upload_root / job_id / "brand-context"
        documents_dir.mkdir(parents=True, exist_ok=True)

        used_names = {document.stored_filename for document in current.documents}
        next_documents = list(current.documents)
        text_parts = [current.combined_text] if current.combined_text else []

        for upload in uploads:
            original_filename = upload.filename or "brand-context"
            extension = Path(original_filename).suffix.lower()
            if extension not in SUPPORTED_BRAND_CONTEXT_EXTENSIONS:
                accepted = ", ".join(sorted(SUPPORTED_BRAND_CONTEXT_EXTENSIONS))
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{original_filename} is not supported. Accepted extensions: {accepted}.",
                )

            content = await upload.read()
            self._validate_file_size(original_filename, len(content))
            extracted_text = self._extract_text(original_filename, extension, content)
            if not extracted_text:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{original_filename} did not contain extractable text.",
                )

            stored_filename = dedupe_filename(sanitize_filename(original_filename), used_names)
            (documents_dir / stored_filename).write_bytes(content)
            next_documents.append(
                BrandContextDocument(
                    id=f"brand_{uuid4().hex[:12]}",
                    original_filename=original_filename,
                    stored_filename=stored_filename,
                    content_type=upload.content_type or self._content_type_for_extension(extension),
                    size_bytes=len(content),
                    extracted_chars=len(extracted_text),
                )
            )
            text_parts.append(extracted_text)

        combined_text = self._truncate_context("\n\n".join(part for part in text_parts if part.strip()))
        response = BrandContextResponse(
            job_id=job_id,
            documents=next_documents,
            combined_text=combined_text,
            max_chars=self.settings.max_brand_context_chars,
        )
        data["brand_context"] = response.model_dump()
        self.upload_service.write_job_data(job_id, data)
        return response

    def _response_from_job_data(self, job_id: str, data: dict) -> BrandContextResponse:
        brand_context = data.get("brand_context")
        if isinstance(brand_context, dict):
            return BrandContextResponse.model_validate(brand_context)
        return BrandContextResponse(
            job_id=job_id,
            documents=[],
            combined_text="",
            max_chars=self.settings.max_brand_context_chars,
        )

    def _validate_file_size(self, filename: str, size: int) -> None:
        if size <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{filename} is empty.")
        if size > self.settings.max_brand_context_file_size_bytes:
            limit_mb = self.settings.max_brand_context_file_size_bytes // (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{filename} exceeds the {limit_mb}MB size limit.",
            )

    def _extract_text(self, filename: str, extension: str, content: bytes) -> str:
        if extension == ".txt":
            return self._normalize_text(content.decode("utf-8", errors="ignore"))
        if extension == ".docx":
            return self._extract_docx_text(filename, content)
        if extension == ".pdf":
            return self._extract_pdf_text(filename, content)
        return ""

    def _extract_docx_text(self, filename: str, content: bytes) -> str:
        try:
            with ZipFile(BytesIO(content)) as archive:
                document_xml = archive.read("word/document.xml").decode("utf-8", errors="ignore")
        except (BadZipFile, KeyError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{filename} is not a readable DOCX file.",
            ) from exc

        text_nodes = re.findall(r"<w:t[^>]*>(.*?)</w:t>", document_xml)
        return self._normalize_text(" ".join(re.sub(r"<[^>]+>", "", node) for node in text_nodes))

    def _extract_pdf_text(self, filename: str, content: bytes) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PDF brand context extraction requires the pypdf package.",
            ) from exc

        try:
            reader = PdfReader(BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{filename} is not a readable PDF file.",
            ) from exc
        return self._normalize_text(text)

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _truncate_context(self, text: str) -> str:
        normalized = self._normalize_text(text)
        return normalized[: self.settings.max_brand_context_chars].strip()

    def _content_type_for_extension(self, extension: str) -> str:
        return {
            ".txt": "text/plain",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".pdf": "application/pdf",
        }[extension]
