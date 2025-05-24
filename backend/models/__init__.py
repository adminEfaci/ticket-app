from .user import User, UserCreate, UserRead, UserUpdate, UserLogin, UserRole as UserRole
from .session import Session
from .audit_log import AuditLog
from .batch import ProcessingBatch, ProcessingBatchCreate, ProcessingBatchRead, ProcessingBatchUpdate, BatchStatus as BatchStatus
from .ticket import Ticket, TicketCreate, TicketRead, TicketUpdate, TicketDTO, TicketParsingResult, TicketErrorLog
from .ticket_image import TicketImage, TicketImageCreate, TicketImageRead, TicketImageUpdate, ImageExtractionResult, ImageErrorLog
from .client import (
    Client, ClientCreate, ClientRead, ClientUpdate,
    ClientReference, ClientReferenceCreate, ClientReferenceRead, ClientReferenceUpdate,
    ClientRate, ClientRateCreate, ClientRateRead, ClientRateUpdate,
    InvoiceFormat as InvoiceFormat, ClientHierarchy, ClientAssignmentResult, ClientStatistics
)

# Rebuild all Pydantic models to resolve forward references
def rebuild_models():
    """Rebuild all Pydantic models to resolve forward references"""
    User.model_rebuild()
    UserCreate.model_rebuild()
    UserRead.model_rebuild()
    UserUpdate.model_rebuild()
    UserLogin.model_rebuild()
    Session.model_rebuild()
    AuditLog.model_rebuild()
    ProcessingBatch.model_rebuild()
    ProcessingBatchCreate.model_rebuild()
    ProcessingBatchRead.model_rebuild()
    ProcessingBatchUpdate.model_rebuild()
    Ticket.model_rebuild()
    TicketCreate.model_rebuild()
    TicketRead.model_rebuild()
    TicketUpdate.model_rebuild()
    TicketDTO.model_rebuild()
    TicketParsingResult.model_rebuild()
    TicketErrorLog.model_rebuild()
    TicketImage.model_rebuild()
    TicketImageCreate.model_rebuild()
    TicketImageRead.model_rebuild()
    TicketImageUpdate.model_rebuild()
    ImageExtractionResult.model_rebuild()
    ImageErrorLog.model_rebuild()
    Client.model_rebuild()
    ClientCreate.model_rebuild()
    ClientRead.model_rebuild()
    ClientUpdate.model_rebuild()
    ClientReference.model_rebuild()
    ClientReferenceCreate.model_rebuild()
    ClientReferenceRead.model_rebuild()
    ClientReferenceUpdate.model_rebuild()
    ClientRate.model_rebuild()
    ClientRateCreate.model_rebuild()
    ClientRateRead.model_rebuild()
    ClientRateUpdate.model_rebuild()
    ClientHierarchy.model_rebuild()
    ClientAssignmentResult.model_rebuild()
    ClientStatistics.model_rebuild()

# Call rebuild to resolve any forward reference issues
rebuild_models()