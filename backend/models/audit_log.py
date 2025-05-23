from datetime import datetime
from ..utils.datetime_utils import utcnow_naive
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, JSON, Column

class AuditLogBase(SQLModel):
    user_id: UUID = Field(foreign_key="user.id", index=True)
    action: str = Field(max_length=100, index=True)
    entity: Optional[str] = Field(None, max_length=50)
    entity_id: Optional[UUID] = Field(None, index=True)
    ip_address: str = Field(max_length=45)
    details: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

class AuditLog(AuditLogBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    timestamp: datetime = Field(default_factory=utcnow_naive, index=True)

class AuditLogCreate(AuditLogBase):
    pass

class AuditLogRead(AuditLogBase):
    id: UUID
    timestamp: datetime