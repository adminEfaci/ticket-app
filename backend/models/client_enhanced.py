from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel

class ClientWithRate(BaseModel):
    """Client model with current rate included"""
    id: UUID
    name: str
    parent_id: Optional[UUID] = None
    billing_email: str
    billing_contact_name: Optional[str] = None
    billing_phone: Optional[str] = None
    invoice_format: str
    invoice_frequency: str
    credit_terms_days: int
    active: bool
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[UUID] = None
    
    # Include counts for related entities
    reference_count: Optional[int] = None
    rate_count: Optional[int] = None
    subcontractor_count: Optional[int] = None
    
    # Current rate
    current_rate: Optional[float] = None
    
    class Config:
        from_attributes = True