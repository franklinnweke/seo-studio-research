from pydantic import BaseModel


class PageResult(BaseModel):
    id: str
    job_id: str
    url: str
    status_code: int | None = None
    current_title: str = ""
    current_meta_description: str = ""
    summary: str = ""
    suggested_title: str = ""
    meta_description: str = ""
    status: str = "pending"
