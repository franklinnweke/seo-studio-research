from pydantic import BaseModel


class BrokenLinkResult(BaseModel):
    id: str
    job_id: str
    source_page: str
    target_url: str
    link_text: str = ""
    status_code: int | None = None
    status_category: str = "unknown"
    is_internal: bool = False
    error_message: str = ""
