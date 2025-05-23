from datetime import datetime
from ..utils.datetime_utils import utcnow_naive
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field


class MatchResultBase(SQLModel):
    ticket_id: UUID = Field(foreign_key="ticket.id", index=True)
    image_id: UUID = Field(foreign_key="ticketimage.id", index=True)
    confidence: float = Field(ge=0.0, le=100.0, description="Match confidence percentage (0-100)")
    accepted: bool = Field(default=False, description="Whether the match has been accepted")
    reviewed: bool = Field(default=False, description="Whether the match has been manually reviewed")
    flagged: bool = Field(default=False, description="Whether the match is flagged for attention")
    reason: Optional[str] = Field(default=None, description="Reason for the match result or rejection")
    score_breakdown: Optional[str] = Field(default=None, description="JSON string of detailed scoring breakdown")
    match_method: Optional[str] = Field(default="automatic", description="Method used for matching (automatic/manual)")


class MatchResult(MatchResultBase, table=True):
    __tablename__ = "match_results"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow_naive)
    updated_at: Optional[datetime] = Field(default=None)
    reviewed_by: Optional[UUID] = Field(default=None, foreign_key="user.id")
    reviewed_at: Optional[datetime] = Field(default=None)


class MatchResultCreate(MatchResultBase):
    pass


class MatchResultRead(MatchResultBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None


class MatchResultUpdate(SQLModel):
    accepted: Optional[bool] = None
    reviewed: Optional[bool] = None
    flagged: Optional[bool] = None
    reason: Optional[str] = None
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None


class MatchResultSummary(SQLModel):
    """Summary statistics for match results in a batch"""
    total_matches: int
    auto_accepted: int
    needs_review: int
    rejected: int
    confidence_avg: float
    confidence_min: float
    confidence_max: float


class MatchDecision(SQLModel):
    """Request model for manual match decisions"""
    accepted: bool
    reason: Optional[str] = None