from pydantic import BaseModel, Field
from datetime import date
from enum import Enum
from uuid import UUID

class JobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class IngestRequest(BaseModel):
    """The payload the client sends to the API."""
    ticker: str = Field(..., max_length=10, examples=["AAPL"])
    target_date: date = Field(..., examples=["2026-04-24"])
    transcript_url: str = Field(..., examples=["https://www.fool.com/..."])

class JobResponse(BaseModel):
    """The immediate response from the API."""
    job_id: UUID
    status: JobStatus
    message: str