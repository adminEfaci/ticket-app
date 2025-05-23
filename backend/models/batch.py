from datetime import datetime
from ..utils.datetime_utils import utcnow_naive
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, JSON, Column
from enum import Enum

class BatchStatus(str, Enum):
    PENDING = "pending"
    VALIDATING = "validating"
    READY = "ready"
    ERROR = "error"

class ProcessingBatchBase(SQLModel):
    created_by: UUID = Field(foreign_key="user.id", index=True)
    client_id: Optional[UUID] = Field(None, foreign_key="user.id", index=True)  # For client users
    status: BatchStatus = Field(default=BatchStatus.PENDING, index=True)
    xls_filename: str = Field(max_length=255)
    pdf_filename: str = Field(max_length=255)
    file_hash: Optional[str] = Field(None, max_length=64, index=True)  # sha256 hash
    error_reason: Optional[str] = Field(None, max_length=500)
    stats: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

class ProcessingBatch(ProcessingBatchBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    uploaded_at: datetime = Field(default_factory=utcnow_naive, index=True)
    processed_at: Optional[datetime] = Field(default=None)

class ProcessingBatchCreate(ProcessingBatchBase):
    pass

class ProcessingBatchRead(ProcessingBatchBase):
    id: UUID
    uploaded_at: datetime
    processed_at: Optional[datetime]

class ProcessingBatchUpdate(SQLModel):
    status: Optional[BatchStatus] = None
    error_reason: Optional[str] = None
    processed_at: Optional[datetime] = None
    stats: Optional[Dict[str, Any]] = None