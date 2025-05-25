from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlmodel import Session, select
from datetime import date
import logging

from ..models.ticket import Ticket, TicketCreate, TicketRead, TicketUpdate, TicketErrorLog, TicketParsingResult
from ..models.user import UserRole

logger = logging.getLogger(__name__)

class TicketService:
    """
    Service for ticket database operations and business logic
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_ticket(self, ticket_data: TicketCreate) -> Ticket:
        """
        Create a new ticket in the database
        
        Args:
            ticket_data: Ticket creation data
            
        Returns:
            Created ticket
        """
        ticket = Ticket.model_validate(ticket_data.model_dump())
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)
        return ticket
    
    def create_tickets_batch(self, tickets_data: List[TicketCreate]) -> List[Ticket]:
        """
        Create multiple tickets in a single transaction
        
        Args:
            tickets_data: List of ticket creation data
            
        Returns:
            List of created tickets
        """
        tickets = []
        try:
            for ticket_data in tickets_data:
                ticket = Ticket.model_validate(ticket_data.model_dump())
                self.db.add(ticket)
                tickets.append(ticket)
            
            self.db.commit()
            
            # Refresh all tickets to get generated IDs
            for ticket in tickets:
                self.db.refresh(ticket)
            
            logger.info(f"Successfully created {len(tickets)} tickets")
            return tickets
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create tickets batch: {str(e)}")
            raise
    
    def get_ticket_by_id(self, ticket_id: UUID, user_id: str, user_role: UserRole) -> Optional[Ticket]:
        """
        Get a ticket by ID with access control
        
        Args:
            ticket_id: Ticket ID
            user_id: Requesting user ID
            user_role: Requesting user role
            
        Returns:
            Ticket if found and accessible, None otherwise
        """
        query = select(Ticket).where(Ticket.id == ticket_id)
        
        # Apply access control
        if user_role == UserRole.CLIENT:
            # Clients can only see their own tickets
            query = query.where(Ticket.client_id == user_id)
        
        return self.db.exec(query).first()
    
    def get_tickets_by_batch(
        self, 
        batch_id: UUID, 
        user_id: str, 
        user_role: UserRole,
        include_invalid: bool = False,
        skip: int = 0,
        limit: int = 100
    ) -> List[Ticket]:
        """
        Get tickets for a specific batch
        
        Args:
            batch_id: Processing batch ID
            user_id: Requesting user ID
            user_role: Requesting user role
            include_invalid: Whether to include tickets with errors
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of tickets
        """
        query = select(Ticket).where(Ticket.batch_id == batch_id)
        
        # Apply access control
        if user_role == UserRole.CLIENT:
            query = query.where(Ticket.client_id == user_id)
        
        # Note: include_invalid parameter doesn't apply since Ticket model doesn't have error tracking
        # Errors are tracked separately in TicketErrorLog
        
        query = query.offset(skip).limit(limit)
        return self.db.exec(query).all()
    
    def update_ticket(self, ticket_id: UUID, update_data: TicketUpdate, user_id: str, user_role: UserRole) -> Optional[Ticket]:
        """
        Update a ticket with access control
        
        Args:
            ticket_id: Ticket ID
            update_data: Update data
            user_id: Requesting user ID
            user_role: Requesting user role
            
        Returns:
            Updated ticket if successful, None if not found or no access
        """
        ticket = self.get_ticket_by_id(ticket_id, user_id, user_role)
        if not ticket:
            return None
        
        # Only admins and managers can update tickets
        if user_role not in [UserRole.ADMIN, UserRole.MANAGER]:
            return None
        
        # Apply updates
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(ticket, field, value)
        
        self.db.commit()
        self.db.refresh(ticket)
        return ticket
    
    def delete_ticket(self, ticket_id: UUID, user_id: str, user_role: UserRole) -> bool:
        """
        Soft delete a ticket (mark as non-billable)
        
        Args:
            ticket_id: Ticket ID
            user_id: Requesting user ID
            user_role: Requesting user role
            
        Returns:
            True if deleted, False if not found or no access
        """
        ticket = self.get_ticket_by_id(ticket_id, user_id, user_role)
        if not ticket:
            return False
        
        # Only admins and managers can delete tickets
        if user_role not in [UserRole.ADMIN, UserRole.MANAGER]:
            return False
        
        # Soft delete by marking as non-billable
        ticket.is_billable = False
        
        self.db.commit()
        return True
    
    def get_batch_ticket_stats(self, batch_id: UUID) -> Dict[str, Any]:
        """
        Get statistics for tickets in a batch
        
        Args:
            batch_id: Processing batch ID
            
        Returns:
            Dictionary with ticket statistics
        """
        from sqlmodel import func
        
        # Total tickets
        total_tickets = self.db.exec(
            select(func.count(Ticket.id)).where(Ticket.batch_id == batch_id)
        ).first() or 0
        
        # Note: All tickets in the Ticket table are valid
        # Invalid tickets are tracked separately in TicketErrorLog
        valid_tickets = total_tickets
        
        # Invalid tickets would be in TicketErrorLog (not implemented here)
        invalid_tickets = 0
        
        # Billable tickets
        billable_tickets = self.db.exec(
            select(func.count(Ticket.id)).where(
                Ticket.batch_id == batch_id,
                Ticket.is_billable
            )
        ).first() or 0
        
        # Status breakdown
        status_breakdown = {}
        for status in ["ORIGINAL", "REPRINT", "VOID"]:
            count = self.db.exec(
                select(func.count(Ticket.id)).where(
                    Ticket.batch_id == batch_id,
                    Ticket.status == status
                )
            ).first() or 0
            status_breakdown[status.lower()] = count
        
        # Weight statistics for valid tickets
        weight_stats = self.db.exec(
            select(
                func.sum(Ticket.net_weight),
                func.avg(Ticket.net_weight),
                func.min(Ticket.net_weight),
                func.max(Ticket.net_weight)
            ).where(
                Ticket.batch_id == batch_id,
                Ticket.net_weight > 0
            )
        ).first()
        
        total_weight = weight_stats[0] if weight_stats and weight_stats[0] else 0
        avg_weight = weight_stats[1] if weight_stats and weight_stats[1] else 0
        min_weight = weight_stats[2] if weight_stats and weight_stats[2] else 0
        max_weight = weight_stats[3] if weight_stats and weight_stats[3] else 0
        
        return {
            "total_tickets": total_tickets,
            "valid_tickets": valid_tickets,
            "invalid_tickets": invalid_tickets,
            "billable_tickets": billable_tickets,
            "status_breakdown": status_breakdown,
            "weight_stats": {
                "total_weight": float(total_weight) if total_weight else 0,
                "average_weight": float(avg_weight) if avg_weight else 0,
                "min_weight": float(min_weight) if min_weight else 0,
                "max_weight": float(max_weight) if max_weight else 0
            }
        }
    
    def save_parsing_errors(self, batch_id: UUID, error_logs: List[TicketErrorLog]) -> List[Ticket]:
        """
        Save parsing errors as invalid tickets for audit trail
        
        Args:
            batch_id: Processing batch ID
            error_logs: List of error logs
            
        Returns:
            List of created error tickets
        """
        error_tickets = []
        
        try:
            for error_log in error_logs:
                # Create a ticket record for the error
                error_ticket = Ticket(
                    batch_id=batch_id,
                    ticket_number=error_log.ticket_number or f"ERROR_ROW_{error_log.row_number}",
                    reference="PARSE_ERROR",
                    status="VOID",
                    net_weight=0.0,
                    entry_date=date.today(),
                    is_billable=False,
                    note=f"Parse error: {error_log.error_message}"  # Store error in note field
                )
                
                self.db.add(error_ticket)
                error_tickets.append(error_ticket)
            
            self.db.commit()
            
            for ticket in error_tickets:
                self.db.refresh(ticket)
            
            logger.info(f"Saved {len(error_tickets)} parsing error records")
            return error_tickets
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to save parsing errors: {str(e)}")
            raise
    
    def process_parsing_results(
        self, 
        batch_id: UUID, 
        valid_tickets: List[TicketCreate], 
        error_logs: List[TicketErrorLog]
    ) -> TicketParsingResult:
        """
        Process parsing results by saving valid tickets and error logs
        
        Args:
            batch_id: Processing batch ID
            valid_tickets: List of valid tickets to save
            error_logs: List of parsing errors
            
        Returns:
            Parsing result summary
        """
        try:
            # Save valid tickets
            created_tickets = []
            if valid_tickets:
                created_tickets = self.create_tickets_batch(valid_tickets)
            
            # Save error logs as invalid tickets
            error_tickets = []
            if error_logs:
                error_tickets = self.save_parsing_errors(batch_id, error_logs)
            
            # Create summary
            result = TicketParsingResult(
                tickets_parsed=len(valid_tickets) + len(error_logs),
                tickets_valid=len(created_tickets),
                tickets_invalid=len(error_tickets),
                duplicates_detected=len([e for e in error_logs if "duplicate" in e.error_message.lower()]),
                errors=[
                    {
                        "ticket_number": error.ticket_number,
                        "row_number": error.row_number,
                        "reason": error.error_message
                    }
                    for error in error_logs
                ]
            )
            
            logger.info(f"Processing complete: {result.tickets_valid} valid, {result.tickets_invalid} invalid")
            return result
            
        except Exception as e:
            logger.error(f"Failed to process parsing results: {str(e)}")
            raise
    
    async def get_tickets_by_client(
        self,
        client_id: UUID,
        skip: int = 0,
        limit: int = 100,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> List[TicketRead]:
        """Get tickets for a specific client with optional date filtering"""
        query = select(Ticket).where(Ticket.client_id == client_id)
        
        # Apply date filters if provided
        if date_from:
            query = query.where(Ticket.entry_date >= date_from)
        if date_to:
            query = query.where(Ticket.entry_date <= date_to)
        
        # Apply pagination and ordering
        query = query.order_by(Ticket.entry_date.desc(), Ticket.entry_time.desc())
        query = query.offset(skip).limit(limit)
        
        tickets = self.db.exec(query).all()
        
        # Convert to TicketRead models
        return [TicketRead.model_validate(ticket) for ticket in tickets]