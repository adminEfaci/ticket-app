from datetime import datetime, date
from typing import Optional, List, TYPE_CHECKING
from uuid import UUID, uuid4
from enum import Enum

from sqlmodel import SQLModel, Field, Relationship
from pydantic import field_validator, model_validator
from ..utils.datetime_utils import utcnow_naive

if TYPE_CHECKING:
    from .ticket import Ticket


class InvoiceFormat(str, Enum):
    """Supported invoice formats"""
    CSV = "csv"
    XLSX = "xlsx"
    PDF = "pdf"
    ODOO = "odoo"


class ClientBase(SQLModel):
    name: str = Field(min_length=1, max_length=200, description="Client company name")
    parent_id: Optional[UUID] = Field(default=None, foreign_key="clients.id", description="Parent client for hierarchy")
    billing_email: str = Field(description="Primary billing contact email")
    billing_contact_name: Optional[str] = Field(default=None, max_length=100, description="Billing contact person name")
    billing_phone: Optional[str] = Field(default=None, max_length=20, description="Billing contact phone")
    invoice_format: InvoiceFormat = Field(default=InvoiceFormat.CSV, description="Preferred invoice format")
    invoice_frequency: str = Field(default="weekly", description="Invoice frequency (weekly, monthly)")
    credit_terms_days: int = Field(default=30, ge=1, le=365, description="Payment terms in days")
    active: bool = Field(default=True, description="Whether client is active")
    notes: Optional[str] = Field(default=None, max_length=1000, description="Internal notes about client")
    
    @field_validator('billing_email')
    @classmethod
    def validate_email(cls, v):
        """Validate email format"""
        import re
        if not v:
            raise ValueError('Billing email is required')
        # Basic email validation
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('Invalid email format')
        return v


class Client(ClientBase, table=True):
    __tablename__ = "clients"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow_naive)
    updated_at: Optional[datetime] = Field(default=None)
    created_by: Optional[UUID] = Field(default=None, foreign_key="user.id")
    
    # Relationships
    parent: Optional["Client"] = Relationship(
        back_populates="subcontractors",
        sa_relationship_kwargs={"remote_side": "Client.id"}
    )
    subcontractors: List["Client"] = Relationship(back_populates="parent")
    references: List["ClientReference"] = Relationship(back_populates="client")
    rates: List["ClientRate"] = Relationship(back_populates="client")
    tickets: List["Ticket"] = Relationship(back_populates="client")


class ClientCreate(ClientBase):
    pass


class ClientRead(ClientBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[UUID] = None
    
    # Include counts for related entities
    reference_count: Optional[int] = None
    rate_count: Optional[int] = None
    subcontractor_count: Optional[int] = None


class ClientUpdate(SQLModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    parent_id: Optional[UUID] = None
    billing_email: Optional[str] = None
    billing_contact_name: Optional[str] = Field(default=None, max_length=100)
    billing_phone: Optional[str] = Field(default=None, max_length=20)
    invoice_format: Optional[InvoiceFormat] = None
    invoice_frequency: Optional[str] = None
    credit_terms_days: Optional[int] = Field(default=None, ge=1, le=365)
    active: Optional[bool] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


class ClientReferenceBase(SQLModel):
    client_id: UUID = Field(foreign_key="clients.id", index=True)
    pattern: str = Field(min_length=1, max_length=200, description="Reference pattern to match")
    is_regex: bool = Field(default=False, description="Whether pattern is a regex")
    is_fuzzy: bool = Field(default=False, description="Whether to use fuzzy matching")
    priority: int = Field(default=100, ge=1, le=1000, description="Match priority (lower = higher priority)")
    active: bool = Field(default=True, description="Whether pattern is active")
    description: Optional[str] = Field(default=None, max_length=500, description="Description of this pattern")
    
    @field_validator('pattern', mode='after')
    @classmethod
    def validate_pattern(cls, v, info):
        """Validate pattern based on type"""
        if not v or not v.strip():
            raise ValueError("Pattern cannot be empty")
        
        return v.strip()
    
    @model_validator(mode='after')
    def validate_regex_pattern(self):
        """Validate regex pattern compiles if is_regex is True"""
        if self.is_regex and self.pattern:
            import re
            try:
                re.compile(self.pattern)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern: {e}")
        return self


class ClientReference(ClientReferenceBase, table=True):
    __tablename__ = "client_references"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow_naive)
    created_by: Optional[UUID] = Field(default=None, foreign_key="user.id")
    
    # Relationships
    client: Client = Relationship(back_populates="references")


class ClientReferenceCreate(ClientReferenceBase):
    pass


class ClientReferenceRead(ClientReferenceBase):
    id: UUID
    created_at: datetime
    created_by: Optional[UUID] = None


class ClientReferenceUpdate(SQLModel):
    pattern: Optional[str] = Field(default=None, min_length=1, max_length=200)
    is_regex: Optional[bool] = None
    is_fuzzy: Optional[bool] = None
    priority: Optional[int] = Field(default=None, ge=1, le=1000)
    active: Optional[bool] = None
    description: Optional[str] = Field(default=None, max_length=500)


class ClientRateBase(SQLModel):
    client_id: UUID = Field(foreign_key="clients.id", index=True)
    rate_per_tonne: float = Field(ge=10.0, le=100.0, description="Rate per tonne ($10-$100)")
    effective_from: date = Field(description="Date this rate becomes effective")
    effective_to: Optional[date] = Field(default=None, description="Date this rate expires (null = indefinite)")
    approved_by: Optional[UUID] = Field(default=None, foreign_key="user.id", description="Admin who approved this rate")
    notes: Optional[str] = Field(default=None, max_length=500, description="Notes about this rate change")
    
    @field_validator('effective_to')
    @classmethod
    def validate_effective_to(cls, v, info):
        """Ensure effective_to is after effective_from"""
        if v and 'effective_from' in info.data and info.data['effective_from']:
            if v <= info.data['effective_from']:
                raise ValueError("effective_to must be after effective_from")
        return v


class ClientRate(ClientRateBase, table=True):
    __tablename__ = "client_rates"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow_naive)
    approved_at: Optional[datetime] = Field(default=None, description="When this rate was approved")
    
    # Relationships
    client: Client = Relationship(back_populates="rates")


class ClientRateCreate(ClientRateBase):
    pass


class ClientRateRead(ClientRateBase):
    id: UUID
    created_at: datetime
    approved_at: Optional[datetime] = None


class ClientRateUpdate(SQLModel):
    rate_per_tonne: Optional[float] = Field(default=None, ge=10.0, le=100.0)
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=500)


class ClientHierarchy(SQLModel):
    """Model for representing client hierarchy"""
    client: ClientRead
    subcontractors: List["ClientHierarchy"] = []
    depth: int = 0


class ClientAssignmentResult(SQLModel):
    """Result of client assignment process"""
    client_id: Optional[UUID] = None
    client_name: Optional[str] = None
    matched_pattern: Optional[str] = None
    match_type: Optional[str] = None  # "exact", "regex", "fuzzy"
    confidence: Optional[float] = None
    rate_per_tonne: Optional[float] = None
    effective_rate_date: Optional[date] = None


class ClientStatistics(SQLModel):
    """Statistics for a client"""
    client_id: UUID
    total_tickets: int
    total_weight: float
    total_revenue: float
    avg_rate: float
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None
    last_activity: Optional[datetime] = None