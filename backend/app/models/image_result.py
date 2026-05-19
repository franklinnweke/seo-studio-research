from pydantic import BaseModel


class ImageResult(BaseModel):
    id: str
    job_id: str
    original_filename: str
    new_filename: str
    alt_text: str = ""
    caption: str = ""
    status: str = "pending"
