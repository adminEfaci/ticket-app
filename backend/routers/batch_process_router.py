from typing import List, Optional
from uuid import UUID
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session

from ..models.ticket import TicketRead, TicketParsingResult
from ..models.batch import ProcessingBatch
from ..models.user import UserRole
from ..services.xls_parser_service import XlsParserService
from ..services.ticket_mapper import TicketMapper
from ..services.ticket_validator import TicketValidator
from ..services.ticket_service import TicketService
from ..services.batch_service import BatchService
from ..services.storage_service import StorageService
from ..services.audit_service import AuditService
from ..middleware.auth_middleware import authenticated_required, get_current_user
from ..core.database import get_session
import logging
import os
from datetime import date

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/batches", tags=["batch-processing"])

# Service dependencies
def get_storage_service() -> StorageService:
    upload_path = os.getenv("UPLOAD_PATH", "/data/batches")
    return StorageService(upload_path)

def get_batch_service(
    db: Session = Depends(get_session),
    storage: StorageService = Depends(get_storage_service)
) -> BatchService:
    return BatchService(db, storage)

def get_ticket_service(db: Session = Depends(get_session)) -> TicketService:
    return TicketService(db)

def get_audit_service(db: Session = Depends(get_session)) -> AuditService:
    return AuditService(db)

@router.post("/{batch_id}/parse", response_model=TicketParsingResult)
async def parse_batch_tickets(
    batch_id: UUID,
    request: Request,
    current_user: dict = Depends(authenticated_required()),
    batch_service: BatchService = Depends(get_batch_service),
    ticket_service: TicketService = Depends(get_ticket_service),
    audit_service: AuditService = Depends(get_audit_service),
    db: Session = Depends(get_session)
):
    """
    Parse XLS file for a batch and extract tickets
    
    Only processors, managers, and admins can trigger parsing
    """
    client_ip = request.client.host if request.client else "unknown"
    user_id = current_user["user_id"]
    user_role = UserRole(current_user["role"])
    
    # Check permissions - only staff can parse
    if user_role not in [UserRole.PROCESSOR, UserRole.MANAGER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to parse batches"
        )
    
    try:
        # Get batch and validate it can be parsed
        batch = batch_service.get_batch_by_id(batch_id, user_id, user_role)
        if not batch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Batch not found or access denied"
            )
        
        # Check if batch is in the right state for parsing
        if batch.status.value != "PENDING":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Batch must be in PENDING status to parse (current: {batch.status})"
            )
        
        # Find XLS file in batch directory
        batch_dir = Path(os.getenv("UPLOAD_PATH", "/data/batches")) / str(batch_id)
        xls_files = list(batch_dir.glob("*.xls"))
        
        if not xls_files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No XLS file found in batch directory"
            )
        
        xls_file_path = xls_files[0]  # Use first XLS file found
        xls_filename = xls_file_path.name
        
        # Log parsing start
        audit_service.log_ticket_parsing_started(
            user_id=UUID(user_id),
            batch_id=batch_id,
            ip_address=client_ip,
            xls_filename=xls_filename
        )
        
        # Mark batch as being parsed
        batch_service.start_batch_parsing(batch_id)
        
        # Initialize services
        parser_service = XlsParserService()
        mapper_service = TicketMapper()
        validator_service = TicketValidator()
        
        # Step 1: Parse XLS file
        logger.info(f"Starting parsing of {xls_file_path} for batch {batch_id}")
        ticket_dtos, parse_errors = parser_service.parse_xls_file(xls_file_path)
        
        if not ticket_dtos and not parse_errors:
            error_msg = "No tickets found in XLS file"
            batch_service.mark_batch_parsing_failed(batch_id, error_msg)
            audit_service.log_ticket_parsing_failed(
                user_id=UUID(user_id),
                batch_id=batch_id,
                ip_address=client_ip,
                error_message=error_msg,
                xls_filename=xls_filename
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # Step 2: Map DTOs to TicketCreate objects
        upload_date = batch.uploaded_at.date() if batch.uploaded_at else date.today()
        mapped_tickets, mapping_errors = mapper_service.map_tickets_batch(
            ticket_dtos, batch_id, upload_date
        )
        
        # Step 3: Validate tickets
        validated_tickets, validation_errors = validator_service.validate_tickets_batch(
            mapped_tickets, upload_date
        )
        
        # Combine all errors
        all_errors = parse_errors + mapping_errors + validation_errors
        
        # Step 4: Save results
        parsing_result = ticket_service.process_parsing_results(
            batch_id, validated_tickets, all_errors
        )
        
        # Step 5: Update batch with results
        updated_batch = batch_service.update_batch_with_parsing_results(batch_id, parsing_result)
        
        # Log completion
        audit_service.log_ticket_parsing_completed(
            user_id=UUID(user_id),
            batch_id=batch_id,
            ip_address=client_ip,
            tickets_parsed=parsing_result.tickets_parsed,
            tickets_valid=parsing_result.tickets_valid,
            tickets_invalid=parsing_result.tickets_invalid,
            duplicates_detected=parsing_result.duplicates_detected
        )
        
        # Log validation errors if any
        if all_errors:
            error_details = [
                {
                    "ticket_number": error.ticket_number,
                    "row_number": error.row_number,
                    "reason": error.reason
                }
                for error in all_errors
            ]
            audit_service.log_ticket_validation_errors(
                user_id=UUID(user_id),
                batch_id=batch_id,
                ip_address=client_ip,
                validation_errors=error_details
            )
        
        # Log duplicates if any
        duplicates = [error.ticket_number for error in all_errors 
                     if error.ticket_number and "duplicate" in error.reason.lower()]
        if duplicates:
            audit_service.log_duplicate_tickets_detected(
                user_id=UUID(user_id),
                batch_id=batch_id,
                ip_address=client_ip,
                duplicate_tickets=duplicates
            )
        
        logger.info(f"Parsing completed for batch {batch_id}: {parsing_result.tickets_valid} valid tickets")
        return parsing_result
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Parsing failed: {str(e)}"
        logger.error(f"Batch parsing failed for {batch_id}: {error_msg}")
        
        # Mark batch as failed
        batch_service.mark_batch_parsing_failed(batch_id, error_msg)
        
        # Log failure
        audit_service.log_ticket_parsing_failed(
            user_id=UUID(user_id),
            batch_id=batch_id,
            ip_address=client_ip,
            error_message=error_msg,
            xls_filename=xls_files[0].name if 'xls_files' in locals() and xls_files else None
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )

@router.get("/{batch_id}/tickets", response_model=List[TicketRead])
async def get_batch_tickets(
    batch_id: UUID,
    include_invalid: bool = False,
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(authenticated_required()),
    batch_service: BatchService = Depends(get_batch_service),
    ticket_service: TicketService = Depends(get_ticket_service)
):
    """
    Get tickets for a specific batch
    """
    user_id = current_user["user_id"]
    user_role = UserRole(current_user["role"])
    
    # Verify batch access
    batch = batch_service.get_batch_by_id(batch_id, user_id, user_role)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found or access denied"
        )
    
    # Get tickets
    tickets = ticket_service.get_tickets_by_batch(
        batch_id, user_id, user_role, include_invalid, skip, limit
    )
    
    return [TicketRead.model_validate(ticket) for ticket in tickets]

@router.get("/{batch_id}/parse-status")
async def get_batch_parse_status(
    batch_id: UUID,
    current_user: dict = Depends(authenticated_required()),
    batch_service: BatchService = Depends(get_batch_service)
):
    """
    Get parsing status for a batch
    """
    user_id = current_user["user_id"]
    user_role = UserRole(current_user["role"])
    
    # Verify batch access
    batch = batch_service.get_batch_by_id(batch_id, user_id, user_role)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found or access denied"
        )
    
    return batch_service.get_batch_parsing_status(batch_id)

@router.get("/{batch_id}/tickets/{ticket_id}", response_model=TicketRead)
async def get_ticket_details(
    batch_id: UUID,
    ticket_id: UUID,
    current_user: dict = Depends(authenticated_required()),
    ticket_service: TicketService = Depends(get_ticket_service)
):
    """
    Get details for a specific ticket
    """
    user_id = current_user["user_id"]
    user_role = UserRole(current_user["role"])
    
    ticket = ticket_service.get_ticket_by_id(ticket_id, user_id, user_role)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found or access denied"
        )
    
    # Verify ticket belongs to the specified batch
    if ticket.batch_id != batch_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ticket does not belong to specified batch"
        )
    
    return TicketRead.model_validate(ticket)

@router.delete("/{batch_id}/tickets/{ticket_id}")
async def delete_ticket(
    batch_id: UUID,
    ticket_id: UUID,
    request: Request,
    current_user: dict = Depends(authenticated_required()),
    ticket_service: TicketService = Depends(get_ticket_service),
    audit_service: AuditService = Depends(get_audit_service)
):
    """
    Soft delete a ticket (mark as invalid)
    
    Only managers and admins can delete tickets
    """
    client_ip = request.client.host if request.client else "unknown"
    user_id = current_user["user_id"]
    user_role = UserRole(current_user["role"])
    
    # Check permissions
    if user_role not in [UserRole.MANAGER, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to delete tickets"
        )
    
    # Get ticket first for audit logging
    ticket = ticket_service.get_ticket_by_id(ticket_id, user_id, user_role)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found or access denied"
        )
    
    # Verify ticket belongs to the specified batch
    if ticket.batch_id != batch_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ticket does not belong to specified batch"
        )
    
    # Delete ticket
    success = ticket_service.delete_ticket(ticket_id, user_id, user_role)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete ticket"
        )
    
    # Log deletion
    audit_service.log_ticket_deleted(
        user_id=UUID(user_id),
        ticket_id=ticket_id,
        ip_address=client_ip,
        ticket_number=ticket.ticket_number,
        reason=f"Deleted by {user_role.value}"
    )
    
    return {"message": "Ticket deleted successfully"}

@router.get("/{batch_id}/statistics")
async def get_batch_ticket_statistics(
    batch_id: UUID,
    current_user: dict = Depends(authenticated_required()),
    batch_service: BatchService = Depends(get_batch_service),
    ticket_service: TicketService = Depends(get_ticket_service)
):
    """
    Get detailed statistics for tickets in a batch
    """
    user_id = current_user["user_id"]
    user_role = UserRole(current_user["role"])
    
    # Verify batch access
    batch = batch_service.get_batch_by_id(batch_id, user_id, user_role)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found or access denied"
        )
    
    # Get ticket statistics
    stats = ticket_service.get_batch_ticket_stats(batch_id)
    
    # Add batch-level information
    stats["batch_info"] = {
        "batch_id": str(batch_id),
        "status": batch.status,
        "uploaded_at": batch.uploaded_at.isoformat() if batch.uploaded_at else None,
        "xls_filename": batch.xls_filename,
        "pdf_filename": batch.pdf_filename
    }
    
    return stats