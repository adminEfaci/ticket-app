from datetime import datetime, timedelta
from ..utils.datetime_utils import utcnow_naive
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field

class SessionBase(SQLModel):
    user_id: UUID = Field(foreign_key="user.id", index=True)
    ip_address: str = Field(max_length=45)
    user_agent: str = Field(max_length=500)
    token_hash: str = Field(index=True)

class Session(SessionBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    expires_at: datetime = Field(default_factory=lambda: utcnow_naive() + timedelta(hours=8))
    created_at: datetime = Field(default_factory=utcnow_naive)
    
    def is_expired(self) -> bool:
        return utcnow_naive() > self.expires_at

class SessionCreate(SessionBase):
    pass

class SessionRead(SessionBase):
    id: UUID
    expires_at: datetime
    created_at: datetime