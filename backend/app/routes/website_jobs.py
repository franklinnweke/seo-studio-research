from fastapi import APIRouter

from app.schemas.responses import LinkListResponse, PageListResponse


router = APIRouter()


@router.get(
    "/{job_id}/pages",
    response_model=PageListResponse,
    summary="List crawled pages",
    description=(
        "Returns pages discovered for a website job. Phase 8 will populate this "
        "after same-domain crawling and content extraction."
    ),
)
def list_pages(job_id: str) -> PageListResponse:
    return PageListResponse(job_id=job_id, pages=[])


@router.get(
    "/{job_id}/links",
    response_model=LinkListResponse,
    summary="List checked links",
    description=(
        "Returns link check results for a website job. Phase 9 will populate this "
        "with internal and external link status data."
    ),
)
def list_links(job_id: str) -> LinkListResponse:
    return LinkListResponse(job_id=job_id, links=[])


@router.get(
    "/{job_id}/broken-links",
    response_model=LinkListResponse,
    summary="List broken links",
    description=(
        "Returns broken links for a website job. Phase 9 will include status codes, "
        "source pages, timeout handling, and internal/external classification."
    ),
)
def list_broken_links(job_id: str) -> LinkListResponse:
    return LinkListResponse(job_id=job_id, links=[])
