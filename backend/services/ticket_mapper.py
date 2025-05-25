from typing import Optional, List
from datetime import date
from uuid import UUID
import re
import logging

from ..models.ticket import TicketDTO, TicketCreate, TicketErrorLog
from ..utils.excel_utils import ExcelUtils

logger = logging.getLogger(__name__)

class TicketMapper:
    """
    Service to map raw TicketDTO objects to validated TicketCreate objects
    """
    
    def __init__(self):
        self.excel_utils = ExcelUtils()
    
    def map_dto_to_ticket(self, dto: TicketDTO, batch_id: UUID, upload_date: date) -> TicketCreate:
        """
        Convert a TicketDTO to a TicketCreate object with data cleaning and normalization
        
        Args:
            dto: Raw ticket data from XLS
            batch_id: ID of the processing batch
            upload_date: Date when the batch was uploaded (for date validation)
            
        Returns:
            TicketCreate object
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Clean and validate ticket number
        ticket_number = self._clean_ticket_number(dto.ticket_number)
        if not ticket_number:
            raise ValueError("Ticket number is required")
        
        # Parse reference and note
        reference, note = self._parse_reference_and_note(dto.reference)
        # Note: reference can be None if only descriptive text is provided
        
        # Normalize status
        status = self._normalize_status(dto.status)
        if not status:
            raise ValueError("Valid status is required (ORIGINAL, REPRINT, or VOID)")
        
        # Parse weights
        gross_weight = self._parse_weight(dto.gross_weight)
        tare_weight = self._parse_weight(dto.tare_weight)
        net_weight = self._parse_weight(dto.net_weight)
        
        if net_weight is None:
            raise ValueError("Net weight is required")
        
        # Parse entry date
        entry_date = self._parse_entry_date(dto.entry_date, upload_date)
        if not entry_date:
            raise ValueError("Valid entry date is required")
        
        # Clean vehicle and license
        vehicle = self._clean_vehicle(dto.vehicle)
        license = self._clean_text_field(dto.license, max_length=50)
        
        # Parse dates
        exit_date = self._parse_date(dto.exit_date) if dto.exit_date else None
        
        # Clean other fields
        attendant = self._clean_text_field(dto.attendant, max_length=100)
        material = self._clean_text_field(dto.material, max_length=100) or "CONST. & DEMO."
        entry_time = self._clean_text_field(dto.entry_time, max_length=20)
        exit_time = self._clean_text_field(dto.exit_time, max_length=20)
        
        # Determine billable status based on ticket status
        is_billable = status != "VOID"
        
        return TicketCreate(
            batch_id=batch_id,
            ticket_number=ticket_number,
            reference=reference or "",  # Empty string if no structured code found
            note=note,
            vehicle=vehicle,
            license=license,
            status=status,
            client_id=None,  # Client assignment happens later via reference matching
            gross_weight=gross_weight,
            tare_weight=tare_weight,
            net_weight=net_weight,
            entry_date=entry_date,
            entry_time=entry_time,
            exit_date=exit_date,
            exit_time=exit_time,
            material=material,
            attendant=attendant,
            is_billable=is_billable
        )
    
    def _clean_ticket_number(self, raw_ticket_number: Optional[str]) -> Optional[str]:
        """
        Clean and normalize ticket number
        
        Args:
            raw_ticket_number: Raw ticket number from XLS
            
        Returns:
            Cleaned ticket number or None
        """
        if not raw_ticket_number:
            return None
        
        # Convert to string and clean
        ticket_num = str(raw_ticket_number).strip().upper()
        
        # Remove any non-alphanumeric characters except hyphens and underscores
        ticket_num = re.sub(r'[^A-Z0-9\-_]', '', ticket_num)
        
        # Validate format (must be 3-20 characters, alphanumeric)
        if not re.match(r'^[A-Z0-9][A-Z0-9\-_]{2,19}$', ticket_num):
            return None
        
        return ticket_num
    
    def _parse_reference_and_note(self, raw_reference: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        """
        Parse reference field into structured reference code and descriptive note
        
        According to specs:
        - Extract structured codes: #007, #141, MM1001, etc.
        - Normalize prefixes: TOPPSMM1001 → MM1001
        - Separate descriptive notes from reference
        - Reference should contain only standardized codes
        - Note should contain any descriptive text
        
        Args:
            raw_reference: Raw reference from XLS
            
        Returns:
            Tuple of (reference_code, note)
        """
        if not raw_reference:
            return None, None
        
        # Convert to string and clean
        full_text = str(raw_reference).strip()
        
        if not full_text:
            return None, None
        
        reference_code = None
        note = full_text  # Default: entire text is note if no pattern found
        
        # Pattern 1: #NNN format (e.g., #007, #141)
        hash_pattern = re.match(r'^#(\d{1,4})\s*(.*)$', full_text)
        if hash_pattern:
            reference_code = hash_pattern.group(1)  # Extract number without #
            note = hash_pattern.group(2).strip() or None
            return reference_code, note
        
        # Pattern 2: MM followed by digits (e.g., MM1001)
        # Also handles prefixes like TOPPSMM1001
        mm_pattern = re.search(r'(MM\d{1,4})', full_text)
        if mm_pattern:
            reference_code = mm_pattern.group(1)
            # Remove the MM code from the text to get the note
            note_text = full_text.replace(mm_pattern.group(0), '').strip()
            # Also remove common prefixes
            note_text = re.sub(r'^TOPPS', '', note_text).strip()
            note = note_text if note_text else None
            return reference_code, note
        
        # Pattern 3: T-NNN format (e.g., T-202, T-104)
        t_pattern = re.match(r'^(T-\d{1,4})\s*(.*)$', full_text)
        if t_pattern:
            reference_code = t_pattern.group(1)
            note = t_pattern.group(2).strip() or None
            return reference_code, note
        
        # No pattern found - entire text is note
        return None, note if note else None
    
    def _clean_reference(self, raw_reference: Optional[str]) -> Optional[str]:
        """
        Clean and normalize reference field (legacy method for compatibility)
        
        Args:
            raw_reference: Raw reference from XLS
            
        Returns:
            Cleaned reference or None
        """
        reference, _ = self._parse_reference_and_note(raw_reference)
        return reference
    
    def _normalize_status(self, raw_status: Optional[str]) -> Optional[str]:
        """
        Normalize ticket status
        
        Args:
            raw_status: Raw status from XLS
            
        Returns:
            Normalized status or None
        """
        if not raw_status:
            return None
        
        status = str(raw_status).strip().upper()
        
        # Map common variations
        status_mapping = {
            'ORIGINAL': 'ORIGINAL',
            'ORIG': 'ORIGINAL',
            'NEW': 'ORIGINAL',
            'ACTIVE': 'ORIGINAL',
            'COMPLETE': 'ORIGINAL',  # Ticket has been completed
            'COMPLETED': 'ORIGINAL',
            'REPRINT': 'REPRINT',
            'REISSUE': 'REPRINT',
            'DUPLICATE': 'REPRINT',
            'VOID': 'VOID',
            'CANCELLED': 'VOID',
            'CANCELED': 'VOID',
            'INVALID': 'VOID'
        }
        
        return status_mapping.get(status)
    
    def _parse_weight(self, raw_weight: Optional[str]) -> Optional[float]:
        """
        Parse weight value from string, handling various formats
        
        Args:
            raw_weight: Raw weight value from XLS
            
        Returns:
            Weight in tonnes or None
        """
        if raw_weight is None:
            return None
        
        try:
            # If it's already a number
            if isinstance(raw_weight, (int, float)):
                weight = float(raw_weight)
            else:
                # Parse from string
                weight = self.excel_utils.parse_weight_value(raw_weight)
                if weight is None:
                    return None
            
            # Validate range (0 to 200 tonnes)
            if weight < 0 or weight > 200.0:
                return None
            
            # Round to 3 decimal places
            return round(weight, 3)
            
        except (ValueError, TypeError):
            return None
    
    def _parse_entry_date(self, raw_date: Optional[str], upload_date: date) -> Optional[date]:
        """
        Parse entry date with validation against upload date
        
        Args:
            raw_date: Raw date from XLS
            upload_date: Date when batch was uploaded
            
        Returns:
            Parsed date or None
        """
        if not raw_date:
            return None
        
        try:
            # If it's already a date
            if isinstance(raw_date, date):
                parsed_date = raw_date
            else:
                parsed_date = self.excel_utils.parse_date_value(raw_date)
                if not parsed_date:
                    return None
            
            # Validate date is within ±30 days of upload
            delta = abs((parsed_date - upload_date).days)
            if delta > 30:
                return None
            
            return parsed_date
            
        except (ValueError, TypeError):
            return None
    
    def _clean_vehicle(self, raw_vehicle: Optional[str]) -> Optional[str]:
        """
        Clean vehicle field
        
        Args:
            raw_vehicle: Raw vehicle from XLS
            
        Returns:
            Cleaned vehicle or None
        """
        if not raw_vehicle:
            return None
        
        vehicle = str(raw_vehicle).strip().upper()
        
        # Remove extra whitespace
        vehicle = re.sub(r'\s+', ' ', vehicle)
        
        # Validate length
        if len(vehicle) > 50:
            vehicle = vehicle[:50]
        
        if len(vehicle) < 1:
            return None
        
        return vehicle
    
    def _clean_text_field(self, raw_text: Optional[str], max_length: int = 100) -> Optional[str]:
        """
        Clean and normalize a text field
        
        Args:
            raw_text: Raw text value
            max_length: Maximum allowed length
            
        Returns:
            Cleaned text or None
        """
        if not raw_text:
            return None
        
        text = str(raw_text).strip()
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Validate length
        if len(text) > max_length:
            text = text[:max_length]
        
        if len(text) < 1:
            return None
        
        return text
    
    def _parse_date(self, raw_date: Optional[str]) -> Optional[date]:
        """
        Parse a date value without validation against upload date
        
        Args:
            raw_date: Raw date value
            
        Returns:
            Parsed date or None
        """
        if not raw_date:
            return None
        
        try:
            if isinstance(raw_date, date):
                return raw_date
            else:
                return self.excel_utils.parse_date_value(raw_date)
        except (ValueError, TypeError):
            return None
    
    
    def map_tickets_batch(
        self, 
        dtos: List[TicketDTO], 
        batch_id: UUID, 
        upload_date: date
    ) -> tuple[List[TicketCreate], List[TicketErrorLog]]:
        """
        Map a batch of TicketDTOs to TicketCreate objects
        
        Args:
            dtos: List of raw ticket DTOs
            batch_id: ID of the processing batch
            upload_date: Date when batch was uploaded
            
        Returns:
            Tuple of (valid_tickets, error_logs)
        """
        valid_tickets = []
        error_logs = []
        
        for dto in dtos:
            try:
                ticket = self.map_dto_to_ticket(dto, batch_id, upload_date)
                valid_tickets.append(ticket)
            except ValueError as e:
                # Use proper TicketErrorLog fields so downstream processing
                # can access `error_message` without errors
                error_log = TicketErrorLog(
                    ticket_number=dto.ticket_number,
                    row_number=dto.row_number or 0,
                    error_type="MAPPING_ERROR",
                    error_message=f"Mapping error: {str(e)}",
                    raw_data=dto.raw_data,
                )
                error_logs.append(error_log)
                logger.warning(
                    f"Failed to map ticket {dto.ticket_number}: {str(e)}"
                )
        
        return valid_tickets, error_logs