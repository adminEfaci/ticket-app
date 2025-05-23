from datetime import date, datetime
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field
from pydantic import field_validator

from ..utils.datetime_utils import utcnow_naive


class ExportRequest(SQLModel):
    """Request model for export operations"""
    start_date: date
    end_date: Optional[date] = None
    client_ids: Optional[List[UUID]] = None
    export_type: str = Field(default="weekly")
    include_images: bool = True
    force_export: bool = False  # Override validation failures


class ExportValidation(SQLModel):
    """Validation result for export operation"""
    is_valid: bool
    total_tickets: int
    matched_images: int
    missing_images: int
    duplicate_tickets: List[str] = []
    validation_errors: List[str] = []
    match_percentage: float
    
    @property
    def has_critical_errors(self) -> bool:
        """Check if there are critical errors that should block export"""
        return self.match_percentage < 100.0 or len(self.duplicate_tickets) > 0


class WeeklyGrouping(SQLModel):
    """Weekly grouping of tickets"""
    week_start: date
    week_end: date
    client_groups: Dict[str, "ClientGrouping"] = {}
    total_tickets: int = 0
    total_tonnage: float = 0.0
    total_amount: float = 0.0


class ClientGrouping(SQLModel):
    """Client grouping within a week"""
    client_id: UUID
    client_name: str
    reference_groups: Dict[str, "ReferenceGrouping"] = {}
    total_tickets: int = 0
    total_tonnage: float = 0.0
    total_amount: float = 0.0
    rate_per_tonne: float


class ReferenceGrouping(SQLModel):
    """Reference grouping within a client"""
    reference: str
    tickets: List[Dict[str, Any]] = []
    ticket_count: int = 0
    total_tonnage: float = 0.0
    subtotal: float = 0.0


class InvoiceLineItem(SQLModel):
    """Line item for client invoice"""
    reference: str
    ticket_count: int
    total_weight: float  # tonnes
    rate: float  # per tonne
    amount: float  # total amount
    
    @field_validator('total_weight', 'amount')
    @classmethod
    def round_to_two_decimals(cls, v):
        """Ensure financial values are rounded to 2 decimals"""
        return round(float(v), 2)


class ClientInvoice(SQLModel):
    """Client invoice for a week"""
    client_id: UUID
    client_name: str
    week_start: date
    week_end: date
    line_items: List[InvoiceLineItem] = []
    total_tonnage: float = 0.0
    total_amount: float = 0.0
    invoice_date: date = Field(default_factory=date.today)
    
    @field_validator('total_tonnage', 'total_amount')
    @classmethod
    def round_totals(cls, v):
        """Ensure totals are rounded to 2 decimals"""
        return round(float(v), 2)


class WeeklyManifest(SQLModel):
    """Weekly summary manifest"""
    week_start: date
    week_end: date
    client_summaries: List[Dict[str, Any]] = []
    total_clients: int = 0
    total_tickets: int = 0
    total_tonnage: float = 0.0
    total_amount: float = 0.0
    generated_at: datetime = Field(default_factory=utcnow_naive)


class ExportAuditLog(SQLModel, table=True):
    """Audit log for export operations"""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    export_type: str
    start_date: date
    end_date: date
    user_id: UUID
    status: str  # success, failed, partial
    total_tickets: int
    total_clients: int
    total_amount: float
    validation_passed: bool
    validation_errors: Optional[str] = None  # JSON string
    export_metadata: Optional[str] = None  # JSON string
    file_path: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow_naive)


class ExportResult(SQLModel):
    """Result of export operation"""
    success: bool
    export_id: UUID
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    validation: ExportValidation
    error_message: Optional[str] = None
    audit_log_id: UUID