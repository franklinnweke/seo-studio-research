from typing import Any, Literal

from pydantic import BaseModel, Field


JobType = Literal["image", "website"]
JobStatus = Literal["pending", "processing", "needs_review", "accepted", "failed"]


class Job(BaseModel):
    id: str
    type: JobType
    status: JobStatus = "pending"
    settings: dict[str, Any] = Field(default_factory=dict)
