from typing import List, Set, Optional
from datetime import date, datetime
import logging

from ..models.ticket import TicketCreate, TicketErrorLog

logger = logging.getLogger(__name__)

class TicketValidator:
    """
    Service for validating ticket data against business rules
    """
    
    def __init__(self):
        self.valid_statuses = {"ORIGINAL", "REPRINT", "VOID"}
        self.min_weight = 0.01  # tonnes (10 kg minimum)
        self.max_weight = 100.0  # tonnes
        self.weight_tolerance = 0.05  # 5% tolerance for net = gross - tare
    
    def validate_ticket(self, ticket: TicketCreate, upload_date: date) -> Optional[str]:
        """
        Validate a single ticket against business rules
        
        Args:
            ticket: Ticket to validate
            upload_date: Date when batch was uploaded
            
        Returns:
            Error message if validation fails, None if valid
        """
        # Required fields validation
        if not ticket.ticket_number or not ticket.ticket_number.strip():
            return "Ticket number is required"
        
        # Reference is optional (can be empty if no pattern found)
        # The reference parser handles this
        
        if not ticket.status:
            return "Status is required"
        
        if ticket.entry_date is None:
            return "Entry date is required"
        
        if ticket.net_weight is None:
            return "Net weight is required"
        
        # Status validation
        if ticket.status not in self.valid_statuses:
            return f"Invalid status '{ticket.status}'. Must be one of: {', '.join(self.valid_statuses)}"
        
        # Weight validation
        weight_error = self._validate_weights(ticket)
        if weight_error:
            return weight_error
        
        # Date validation
        date_error = self._validate_entry_date(ticket.entry_date, upload_date)
        if date_error:
            return date_error
        
        # VOID ticket specific validation
        if ticket.status == "VOID":
            void_error = self._validate_void_ticket(ticket)
            if void_error:
                return void_error
        
        return None
    
    def _validate_weights(self, ticket: TicketCreate) -> Optional[str]:
        """
        Validate weight-related business rules
        
        Args:
            ticket: Ticket to validate
            
        Returns:
            Error message if validation fails, None if valid
        """
        net_weight = ticket.net_weight
        
        # Net weight range validation (allow 0 for VOID tickets)
        if ticket.status == "VOID":
            if net_weight != 0:
                return "VOID tickets must have net_weight = 0"
        else:
            if net_weight < self.min_weight or net_weight > self.max_weight:
                return f"Net weight must be between {self.min_weight} and {self.max_weight} tonnes"
        
        # If we have gross and tare weights, validate the calculation (skip for VOID tickets)
        # Only check if net weight is in valid range first
        if (ticket.status != "VOID" and 
            ticket.gross_weight is not None and 
            ticket.tare_weight is not None and
            self.min_weight <= net_weight <= self.max_weight):
            calculated_net = ticket.gross_weight - ticket.tare_weight
            
            # Check if net = gross - tare within tolerance
            if abs(net_weight - calculated_net) > (calculated_net * self.weight_tolerance):
                return f"Net weight ({net_weight}) does not match gross - tare ({calculated_net}) within {self.weight_tolerance*100}% tolerance"
        
        # Individual weight validations
        if ticket.gross_weight is not None:
            if ticket.gross_weight < 0 or ticket.gross_weight > 200.0:
                return "Gross weight must be between 0 and 200 tonnes"
        
        if ticket.tare_weight is not None:
            if ticket.tare_weight < 0 or ticket.tare_weight > 200.0:
                return "Tare weight must be between 0 and 200 tonnes"
            
            # Tare should not exceed gross
            if ticket.gross_weight is not None and ticket.tare_weight > ticket.gross_weight:
                return "Tare weight cannot exceed gross weight"
        
        return None
    
    def _validate_entry_date(self, entry_date: date, upload_date: date) -> Optional[str]:
        """
        Validate entry date is within acceptable range
        
        Args:
            entry_date: Entry date from ticket
            upload_date: Date when batch was uploaded
            
        Returns:
            Error message if validation fails, None if valid
        """
        # Check if date is within ±30 days of upload
        delta = abs((entry_date - upload_date).days)
        if delta > 30:
            return f"Entry date must be within ±30 days of upload date. Entry: {entry_date}, Upload: {upload_date}"
        
        # Check if date is not in the future (beyond upload date + 1 day for timezone tolerance)
        if entry_date > upload_date and (entry_date - upload_date).days > 1:
            return f"Entry date cannot be in the future. Entry: {entry_date}, Upload: {upload_date}"
        
        return None
    
    def _validate_void_ticket(self, ticket: TicketCreate) -> Optional[str]:
        """
        Validate VOID ticket specific rules
        
        Args:
            ticket: Ticket to validate
            
        Returns:
            Error message if validation fails, None if valid
        """
        # VOID tickets must have net_weight = 0
        if ticket.net_weight != 0:
            return "VOID tickets must have net_weight = 0"
        
        # Note: is_billable field is not part of current ticket model
        
        return None
    
    def validate_batch_duplicates(self, tickets: List[TicketCreate]) -> List[TicketErrorLog]:
        """
        Check for duplicate ticket numbers within the same batch
        
        Args:
            tickets: List of tickets to check
            
        Returns:
            List of error logs for duplicate tickets
        """
        seen_tickets: Set[str] = set()
        duplicates = []
        
        for i, ticket in enumerate(tickets):
            ticket_number = ticket.ticket_number.upper()
            
            if ticket_number in seen_tickets:
                error_log = TicketErrorLog(
                    batch_id=tickets[0].batch_id,  # Use batch_id from first ticket
                    ticket_number=ticket.ticket_number,
                    row_number=i + 1,  # Approximate row number
                    error_type="DUPLICATE",
                    error_message=f"Duplicate ticket number '{ticket_number}' found in batch"
                )
                duplicates.append(error_log)
            else:
                seen_tickets.add(ticket_number)
        
        return duplicates
    
    def validate_tickets_batch(
        self, 
        tickets: List[TicketCreate], 
        upload_date: date
    ) -> tuple[List[TicketCreate], List[TicketErrorLog]]:
        """
        Validate a batch of tickets
        
        Args:
            tickets: List of tickets to validate
            upload_date: Date when batch was uploaded
            
        Returns:
            Tuple of (valid_tickets, error_logs)
        """
        valid_tickets = []
        error_logs = []
        
        # Check for duplicates first
        duplicate_errors = self.validate_batch_duplicates(tickets)
        error_logs.extend(duplicate_errors)
        
        # Get set of duplicate ticket numbers to exclude
        duplicate_numbers = {error.ticket_number.upper() for error in duplicate_errors if error.ticket_number}
        
        # Validate individual tickets
        for i, ticket in enumerate(tickets):
            # Skip if this ticket number is a duplicate
            if ticket.ticket_number.upper() in duplicate_numbers:
                continue
            
            validation_error = self.validate_ticket(ticket, upload_date)
            
            if validation_error:
                error_log = TicketErrorLog(
                    batch_id=ticket.batch_id,
                    ticket_number=ticket.ticket_number,
                    row_number=i + 1,  # Approximate row number
                    error_type="VALIDATION_ERROR",
                    error_message=f"Validation error: {validation_error}"
                )
                error_logs.append(error_log)
                logger.warning(f"Ticket validation failed for {ticket.ticket_number}: {validation_error}")
            else:
                valid_tickets.append(ticket)
        
        logger.info(f"Validated {len(tickets)} tickets: {len(valid_tickets)} valid, {len(error_logs)} errors")
        return valid_tickets, error_logs
    
    def get_validation_summary(self, valid_count: int, error_logs: List[TicketErrorLog]) -> dict:
        """
        Get a summary of validation results
        
        Args:
            valid_count: Number of valid tickets
            error_logs: List of validation errors
            
        Returns:
            Summary dictionary
        """
        total_tickets = valid_count + len(error_logs)
        
        # Categorize errors
        error_categories = {}
        duplicates = 0
        
        for error in error_logs:
            if error.error_type == "DUPLICATE":
                duplicates += 1
            else:
                # Extract error category from error_message
                if ":" in error.error_message:
                    category = error.error_message.split(":")[0].strip()
                else:
                    category = "Other"
                
                error_categories[category] = error_categories.get(category, 0) + 1
        
        return {
            "total_tickets": total_tickets,
            "valid_tickets": valid_count,
            "invalid_tickets": len(error_logs),
            "duplicates_detected": duplicates,
            "error_categories": error_categories,
            "validation_rate": (valid_count / total_tickets * 100) if total_tickets > 0 else 0
        }