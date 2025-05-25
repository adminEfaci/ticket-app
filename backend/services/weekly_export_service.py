import logging
from datetime import date, timedelta
from typing import List, Dict, Optional, Tuple
from uuid import UUID
from sqlmodel import Session, select

from ..models.ticket import Ticket
from ..models.client import Client
from ..models.export import (
    WeeklyGrouping, ClientGrouping, ReferenceGrouping,
    ExportValidation, ExportRequest
)
from ..services.client_service import ClientService
from ..services.rate_service import RateService
from ..services.audit_service import AuditService, AuditEventType

logger = logging.getLogger(__name__)


class WeeklyExportService:
    """Service for handling weekly ticket exports"""
    
    def __init__(self, db: Session):
        self.db = db
        self.client_service = ClientService(db)
        self.rate_service = RateService(db)
        self.audit_service = AuditService(db)
    
    def get_week_range(self, date_input: date) -> Tuple[date, date]:
        """
        Get Monday-Saturday week range for a given date
        
        Args:
            date_input: Any date within the week
            
        Returns:
            Tuple of (week_start, week_end)
        """
        # Find the Monday of the week
        days_since_monday = date_input.weekday()
        week_start = date_input - timedelta(days=days_since_monday)
        
        # Saturday is 5 days after Monday
        week_end = week_start + timedelta(days=5)
        
        return week_start, week_end
    
    def get_tickets_for_export(
        self, 
        start_date: date, 
        end_date: Optional[date] = None,
        client_ids: Optional[List[UUID]] = None
    ) -> List[Ticket]:
        """
        Get all REPRINT tickets for export within date range
        
        Args:
            start_date: Start date for export
            end_date: End date for export (inclusive)
            client_ids: Optional list of client IDs to filter
            
        Returns:
            List of tickets matching criteria
        """
        query = select(Ticket).where(
            Ticket.status == "REPRINT",
            Ticket.is_billable,
            Ticket.entry_date >= start_date
        )
        
        if end_date:
            query = query.where(Ticket.entry_date <= end_date)
        
        if client_ids:
            query = query.where(Ticket.client_id.in_(client_ids))
        
        # Order by entry_date, client_id, reference for consistent grouping
        query = query.order_by(
            Ticket.entry_date,
            Ticket.client_id,
            Ticket.reference,
            Ticket.ticket_number
        )
        
        tickets = self.db.exec(query).all()
        
        logger.info(f"Found {len(tickets)} REPRINT tickets for export between {start_date} and {end_date}")
        return tickets
    
    def validate_export_data(
        self, 
        tickets: List[Ticket],
        require_images: bool = True
    ) -> ExportValidation:
        """
        Validate tickets for export
        
        Args:
            tickets: List of tickets to validate
            require_images: Whether to require all tickets have images
            
        Returns:
            ExportValidation result
        """
        validation = ExportValidation(
            is_valid=True,
            total_tickets=len(tickets),
            matched_images=0,
            missing_images=0,
            duplicate_tickets=[],
            validation_errors=[],
            match_percentage=0.0
        )
        
        if not tickets:
            validation.validation_errors.append("No tickets found for export")
            validation.is_valid = False
            return validation
        
        # Check for duplicate ticket numbers
        ticket_numbers = [t.ticket_number for t in tickets]
        duplicates = [num for num in ticket_numbers if ticket_numbers.count(num) > 1]
        validation.duplicate_tickets = list(set(duplicates))
        
        if validation.duplicate_tickets:
            validation.validation_errors.append(
                f"Found {len(validation.duplicate_tickets)} duplicate ticket numbers"
            )
            validation.is_valid = False
        
        # Validate each ticket
        for ticket in tickets:
            # Check required fields
            if not ticket.entry_date:
                validation.validation_errors.append(
                    f"Ticket {ticket.ticket_number} missing entry_date"
                )
                validation.is_valid = False
            
            if not ticket.client_id:
                validation.validation_errors.append(
                    f"Ticket {ticket.ticket_number} not assigned to client"
                )
                validation.is_valid = False
            
            if ticket.net_weight <= 0:
                validation.validation_errors.append(
                    f"Ticket {ticket.ticket_number} has invalid weight: {ticket.net_weight}"
                )
                validation.is_valid = False
            
            # Check image
            if ticket.image_path and ticket.image_extracted:
                validation.matched_images += 1
            else:
                validation.missing_images += 1
                if require_images:
                    validation.validation_errors.append(
                        f"Ticket {ticket.ticket_number} missing image"
                    )
                    validation.is_valid = False
        
        # Calculate match percentage
        validation.match_percentage = (
            (validation.matched_images / validation.total_tickets * 100) 
            if validation.total_tickets > 0 else 0
        )
        
        logger.info(
            f"Validation complete: {validation.total_tickets} tickets, "
            f"{validation.match_percentage:.1f}% with images"
        )
        
        return validation
    
    async def group_tickets_by_week(
        self, 
        tickets: List[Ticket]
    ) -> Dict[str, WeeklyGrouping]:
        """
        Group tickets by week, then client, then reference
        
        Args:
            tickets: List of tickets to group
            
        Returns:
            Dictionary of week_key -> WeeklyGrouping
        """
        week_groups: Dict[str, WeeklyGrouping] = {}
        
        for ticket in tickets:
            if not ticket.entry_date or not ticket.client_id:
                continue
            
            # Get week range
            week_start, week_end = self.get_week_range(ticket.entry_date)
            week_key = week_start.isoformat()
            
            # Get client info first to check if we should process
            client = self.db.get(Client, ticket.client_id)
            if not client:
                logger.warning(f"Client {ticket.client_id} not found for ticket {ticket.ticket_number}")
                continue
            
            # Get rate for this client and date
            rate = await self.rate_service.get_effective_rate(
                client_id=client.id,
                effective_date=ticket.entry_date
            )
            
            if not rate:
                logger.warning(
                    f"No rate found for client {client.name} on {ticket.entry_date}"
                )
                continue
            
            # Initialize week group if needed
            if week_key not in week_groups:
                week_groups[week_key] = WeeklyGrouping(
                    week_start=week_start,
                    week_end=week_end,
                    client_groups={},
                    total_tickets=0,
                    total_tonnage=0.0,
                    total_amount=0.0
                )
            
            week_group = week_groups[week_key]
            
            client_key = str(client.id)
            
            # Initialize client group if needed
            if client_key not in week_group.client_groups:
                week_group.client_groups[client_key] = ClientGrouping(
                    client_id=client.id,
                    client_name=client.name,
                    reference_groups={},
                    total_tickets=0,
                    total_tonnage=0.0,
                    total_amount=0.0,
                    rate_per_tonne=rate.rate_per_tonne
                )
            
            client_group = week_group.client_groups[client_key]
            
            # Initialize reference group if needed
            reference = ticket.reference or "NO_REF"
            if reference not in client_group.reference_groups:
                client_group.reference_groups[reference] = ReferenceGrouping(
                    reference=reference,
                    tickets=[],
                    ticket_count=0,
                    total_tonnage=0.0,
                    subtotal=0.0
                )
            
            ref_group = client_group.reference_groups[reference]
            
            # Add ticket to reference group
            ticket_data = {
                "ticket_number": ticket.ticket_number,
                "entry_date": ticket.entry_date.isoformat(),
                "net_weight": round(ticket.net_weight, 2),
                "rate": client_group.rate_per_tonne,
                "amount": round(ticket.net_weight * client_group.rate_per_tonne, 2),
                "image_path": ticket.image_path,
                "note": ticket.note
            }
            
            ref_group.tickets.append(ticket_data)
            ref_group.ticket_count += 1
            ref_group.total_tonnage = round(ref_group.total_tonnage + ticket.net_weight, 2)
            ref_group.subtotal = round(ref_group.total_tonnage * client_group.rate_per_tonne, 2)
            
            # Update client totals
            client_group.total_tickets += 1
            client_group.total_tonnage = round(client_group.total_tonnage + ticket.net_weight, 2)
            client_group.total_amount = round(
                client_group.total_tonnage * client_group.rate_per_tonne, 2
            )
            
            # Update week totals
            week_group.total_tickets += 1
            week_group.total_tonnage = round(week_group.total_tonnage + ticket.net_weight, 2)
            week_group.total_amount = round(
                week_group.total_amount + ticket_data["amount"], 2
            )
        
        logger.info(f"Grouped tickets into {len(week_groups)} weeks")
        return week_groups
    
    async def log_export_operation(
        self,
        user_id: UUID,
        export_request: ExportRequest,
        validation: ExportValidation,
        week_groups: Dict[str, WeeklyGrouping],
        success: bool,
        error_message: Optional[str] = None
    ):
        """Log the export operation to audit log"""
        
        # Calculate totals
        total_clients = sum(
            len(wg.client_groups) for wg in week_groups.values()
        )
        total_amount = sum(
            wg.total_amount for wg in week_groups.values()
        )
        
        # Create detailed metadata
        metadata = {
            "export_type": export_request.export_type,
            "date_range": {
                "start": export_request.start_date.isoformat(),
                "end": export_request.end_date.isoformat() if export_request.end_date else None
            },
            "validation": {
                "total_tickets": validation.total_tickets,
                "matched_images": validation.matched_images,
                "match_percentage": validation.match_percentage,
                "duplicate_count": len(validation.duplicate_tickets)
            },
            "summary": {
                "weeks": len(week_groups),
                "total_clients": total_clients,
                "total_tonnage": sum(wg.total_tonnage for wg in week_groups.values()),
                "total_amount": total_amount
            },
            "forced": export_request.force_export,
            "error": error_message
        }
        
        await self.audit_service.log_event(
            event_type=AuditEventType.UPLOAD_SUCCESS,
            user_id=user_id,
            details=str({
                "entity_type": "WeeklyExport",
                "entity_id": str(export_request.start_date),
                "status": "success" if success else "failed",
                "metadata": metadata
            })
        )