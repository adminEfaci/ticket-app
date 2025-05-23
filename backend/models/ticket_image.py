from datetime import datetime
from ..utils.datetime_utils import utcnow_naive
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field


class TicketImageBase(SQLModel):
    page_number: int = Field(ge=1)
    image_path: str = Field(max_length=500)
    ticket_number: Optional[str] = Field(None, max_length=50)
    ocr_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    valid: bool = Field(default=True)
    error_reason: Optional[str] = Field(None, max_length=500)


class TicketImage(TicketImageBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    batch_id: UUID = Field(foreign_key="processingbatch.id", index=True)
    created_at: datetime = Field(default_factory=utcnow_naive)


class TicketImageCreate(TicketImageBase):
    batch_id: UUID


class TicketImageRead(TicketImageBase):
    id: UUID
    batch_id: UUID
    created_at: datetime


class TicketImageUpdate(SQLModel):
    ticket_number: Optional[str] = None
    ocr_confidence: Optional[float] = None
    valid: Optional[bool] = None
    error_reason: Optional[str] = None


class ImageExtractionResult(SQLModel):
    """Result of PDF image extraction operation"""
    pages_processed: int
    images_extracted: int
    images_failed: int
    ocr_low_confidence: int
    quality_failed: int
    extraction_errors: list[str]


class ImageErrorLog(SQLModel):
    """Individual image extraction error"""
    batch_id: UUID
    page_number: int
    error_type: str
    error_message: str
    timestamp: datetime = Field(default_factory=utcnow_naive)