from datetime import datetime, date
from ..utils.datetime_utils import utcnow_naive
from typing import Optional, Literal, List, Dict, Any
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Relationship
from pydantic import field_validator

class TicketBase(SQLModel):
    ticket_number: str = Field(max_length=50, index=True)
    reference: str = Field(max_length=100)
    note: Optional[str] = Field(None, max_length=500)  # Descriptive notes from reference field
    vehicle: Optional[str] = Field(None, max_length=50)  # Vehicle identifier
    license: Optional[str] = Field(None, max_length=50)  # License plate
    gross_weight: Optional[float] = Field(None, ge=0.0, le=200.0)  # tonnes
    tare_weight: Optional[float] = Field(None, ge=0.0, le=200.0)   # tonnes
    net_weight: float = Field(ge=0.0, le=200.0)  # tonnes
    status: str = Field(max_length=20)
    entry_date: date  # Entry date of the ticket
    entry_time: Optional[str] = Field(None, max_length=20)  # Entry time (e.g., "11:04 AM")
    exit_date: Optional[date] = None  # Exit date of the ticket
    exit_time: Optional[str] = Field(None, max_length=20)  # Exit time
    material: str = Field(default="CONST. & DEMO.", max_length=100)  # Material type
    attendant: Optional[str] = Field(None, max_length=100)  # Attendant name
    is_billable: bool = Field(default=True)  # Whether ticket should be billed
    rate_per_tonne: Optional[float] = Field(None, ge=10.0, le=100.0)  # Rate applied to this ticket
    
    # Image related fields
    image_path: Optional[str] = Field(None, max_length=500)  # Path to extracted ticket image
    pdf_page_number: Optional[int] = Field(None, ge=1)  # PDF page number where ticket was found
    pdf_source_file: Optional[str] = Field(None, max_length=500)  # Source PDF filename
    image_extracted: bool = Field(default=False)  # Whether image was successfully extracted
    match_quality: Optional[float] = Field(None, ge=0.0, le=1.0)  # Quality of CSV-PDF match (0-1)
    ocr_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)  # OCR confidence score (0-1)
    
    @field_validator('net_weight', mode='before')
    @classmethod
    def validate_net_weight(cls, v, info):
        """Validate net weight constraints"""
        if v is not None:
            # Basic range validation - more specific validation in status validator
            if v < 0.0 or v > 100.0:
                raise ValueError("Net weight must be between 0.0 and 100.0 tonnes")
        return v

    @field_validator('status', mode='after')
    @classmethod 
    def validate_void_status(cls, v, info):
        """Validate VOID ticket constraints"""
        values = info.data if info.data else {}
        net_weight = values.get('net_weight', 0)
        
        if v == "VOID":
            if net_weight != 0:
                raise ValueError("VOID tickets must have net_weight = 0")
        # Note: Other weight validations are done in TicketValidator service
        return v

class Ticket(TicketBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    batch_id: UUID = Field(foreign_key="processingbatch.id", index=True)
    client_id: Optional[UUID] = Field(default=None, foreign_key="clients.id", index=True)
    created_at: datetime = Field(default_factory=utcnow_naive)
    updated_at: datetime = Field(default_factory=utcnow_naive)
    
    # Relationships
    client: Optional["Client"] = Relationship(back_populates="tickets")

class TicketCreate(TicketBase):
    batch_id: UUID
    client_id: Optional[UUID] = None  # Client ID linked via reference

class TicketRead(TicketBase):
    id: UUID
    batch_id: UUID
    client_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

class TicketUpdate(SQLModel):
    reference: Optional[str] = None
    note: Optional[str] = None
    vehicle: Optional[str] = None
    license: Optional[str] = None
    status: Optional[str] = None
    gross_weight: Optional[float] = None
    tare_weight: Optional[float] = None
    net_weight: Optional[float] = None
    entry_date: Optional[date] = None
    entry_time: Optional[str] = None
    exit_date: Optional[date] = None
    exit_time: Optional[str] = None
    material: Optional[str] = None
    attendant: Optional[str] = None
    is_billable: Optional[bool] = None
    client_id: Optional[UUID] = None
    rate_per_tonne: Optional[float] = None
    image_path: Optional[str] = None
    pdf_page_number: Optional[int] = None
    pdf_source_file: Optional[str] = None
    image_extracted: Optional[bool] = None
    match_quality: Optional[float] = None
    ocr_confidence: Optional[float] = None

class TicketDTO(SQLModel):
    """Data Transfer Object for raw ticket data before validation"""
    ticket_number: Optional[str] = None
    reference: Optional[str] = None
    note: Optional[str] = None
    vehicle: Optional[str] = None
    license: Optional[str] = None
    status: Optional[str] = None
    gross_weight: Optional[float] = None
    tare_weight: Optional[float] = None
    net_weight: Optional[float] = None
    entry_date: Optional[date] = None
    entry_time: Optional[str] = None
    exit_date: Optional[date] = None
    exit_time: Optional[str] = None
    material: Optional[str] = None
    attendant: Optional[str] = None
    row_number: Optional[int] = None
    raw_data: Optional[str] = None  # JSON string

class TicketParsingResult(SQLModel):
    """Result of ticket parsing operation"""
    tickets_parsed: int
    tickets_valid: int
    tickets_invalid: int
    duplicates_detected: int = 0
    created_tickets: List[Any] = []
    error_tickets: List[Any] = []

class TicketErrorLog(SQLModel, table=True):
    """Individual ticket parsing error"""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    batch_id: UUID = Field(foreign_key="processingbatch.id", index=True)
    ticket_number: Optional[str] = None
    row_number: int
    error_type: str = Field(max_length=50)
    error_message: str = Field(max_length=500)
    raw_data: Optional[str] = None  # JSON string
    created_at: datetime = Field(default_factory=utcnow_naive)


# Forward reference import to avoid circular dependency
from backend.models.client import Client