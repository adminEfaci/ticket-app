"""
Parser for multi-row XLS format where each ticket spans multiple rows
"""
from pathlib import Path
from typing import List, Any, Optional, Union, Tuple
import logging

from ..utils.excel_utils import ExcelUtils
from ..models.ticket import TicketDTO, TicketErrorLog

logger = logging.getLogger(__name__)

class MultiRowXlsParser:
    """
    Parser for XLS files where each ticket spans multiple rows
    Based on the APRIL 14 2025.xls format
    """
    
    def __init__(self):
        self.excel_utils = ExcelUtils()
    
    def parse_xls_file(self, file_path: Union[str, Path]) -> Tuple[List[TicketDTO], List[TicketErrorLog]]:
        """
        Parse a multi-row XLS file and extract ticket data
        
        Args:
            file_path: Path to the .xls file
            
        Returns:
            Tuple of (tickets, errors)
        """
        try:
            workbook = self.excel_utils.open_xls_file(file_path)
            sheet = self.excel_utils.get_worksheet(workbook)
            
            # Find ticket boundaries
            ticket_boundaries = self._find_ticket_boundaries(sheet)
            logger.info(f"Found {len(ticket_boundaries)} tickets in multi-row format")
            
            # Extract tickets
            tickets = []
            errors = []
            
            for i, (start_row, ticket_num) in enumerate(ticket_boundaries):
                end_row = ticket_boundaries[i+1][0] if i+1 < len(ticket_boundaries) else sheet.nrows
                
                try:
                    ticket_dto = self._extract_ticket_from_rows(
                        sheet, start_row, end_row, workbook.datemode
                    )
                    if ticket_dto:
                        # Check if it's a VOID ticket
                        if ticket_dto.status and 'VOID' in ticket_dto.status.upper():
                            logger.info(f"Skipping VOID ticket {ticket_dto.ticket_number}")
                            continue
                        tickets.append(ticket_dto)
                except Exception as e:
                    error_log = TicketErrorLog(
                        ticket_number=str(ticket_num),
                        row_number=start_row + 1,  # 1-based for user display
                        error_type="parsing_error",
                        error_message=f"Multi-row parsing error: {str(e)}"
                    )
                    errors.append(error_log)
                    logger.warning(f"Error parsing ticket at row {start_row + 1}: {str(e)}")
            
            logger.info(f"Extracted {len(tickets)} valid tickets with {len(errors)} errors")
            return tickets, errors
            
        except Exception as e:
            error_log = TicketErrorLog(
                ticket_number=None,
                row_number=0,
                error_type="file_error",
                error_message=f"File parsing error: {str(e)}"
            )
            logger.error(f"Failed to parse XLS file {file_path}: {str(e)}")
            return [], [error_log]
    
    def _find_ticket_boundaries(self, sheet) -> List[Tuple[int, Any]]:
        """
        Find where each ticket starts in the multi-row format
        
        Args:
            sheet: xlrd Sheet object
            
        Returns:
            List of (row_index, ticket_number) tuples
        """
        boundaries = []
        
        for row in range(sheet.nrows):
            # Look for "TICKET #" in column 0
            cell_value = self.excel_utils.get_cell_value(sheet, row, 0)
            if cell_value and str(cell_value).strip().upper() == 'TICKET #':
                # Get ticket number from column 1
                ticket_num = self.excel_utils.get_cell_value(sheet, row, 1)
                if ticket_num:
                    boundaries.append((row, ticket_num))
        
        return boundaries
    
    def _extract_ticket_from_rows(self, sheet, start_row: int, end_row: int, datemode: int) -> Optional[TicketDTO]:
        """
        Extract a ticket from multiple rows
        
        Args:
            sheet: xlrd Sheet object
            start_row: First row of the ticket
            end_row: Row after the last row of the ticket
            datemode: Excel workbook date mode
            
        Returns:
            TicketDTO object or None if invalid
        """
        # Row 0: Header row with ticket number, status, etc.
        ticket_number = self._get_value_from_row(sheet, start_row, 1)  # Column 1
        status = self._get_value_from_row(sheet, start_row, 4)  # Column 4: REPRINT or VOID - REPRINT
        
        if not ticket_number:
            return None
        
        # Clean ticket number
        ticket_number = str(int(float(ticket_number))) if isinstance(ticket_number, float) else str(ticket_number)
        
        # Clean status
        if status:
            status = str(status).strip().upper()
            if 'VOID' in status:
                status = 'VOID'
            elif 'REPRINT' in status:
                status = 'REPRINT'
            else:
                status = 'REPRINT'  # Default
        else:
            status = 'REPRINT'
        
        # Extract fields from known positions
        attendant = self._get_value_after_label(sheet, start_row, end_row, 'ATTENDENT:', 'ATTENDANT:')
        vehicle = self._get_value_after_label(sheet, start_row, end_row, 'VEHICLE:')
        license_plate = self._get_value_after_label(sheet, start_row, end_row, 'LICENSE:')
        reference = self._get_value_after_label(sheet, start_row, end_row, 'REFERENCE:')
        
        # Extract dates - they appear in pairs (date, time)
        entry_date = None
        entry_time = None
        exit_date = None
        exit_time = None
        
        # Find ENTER: and EXIT: labels
        for row in range(start_row, end_row):
            for col in range(sheet.ncols):
                value = self.excel_utils.get_cell_value(sheet, row, col)
                if value:
                    value_str = str(value).strip().upper()
                    if value_str == 'ENTER:':
                        # Next two cells should be date and time
                        entry_date = self.excel_utils.get_cell_value(sheet, row, col + 1)
                        entry_time = self.excel_utils.get_cell_value(sheet, row, col + 2)
                    elif value_str == 'EXIT:':
                        exit_date = self.excel_utils.get_cell_value(sheet, row, col + 1)
                        exit_time = self.excel_utils.get_cell_value(sheet, row, col + 2)
        
        # Extract weights
        gross_weight = self._get_weight_value(sheet, start_row, end_row, 'GROSS')
        tare_weight = self._get_weight_value(sheet, start_row, end_row, 'TARE')
        net_weight = self._get_weight_value(sheet, start_row, end_row, 'NET')
        
        # Extract material from the table section (usually row 1 or 2 from start)
        material = None
        for row in range(start_row + 1, min(start_row + 3, end_row)):
            # Look for "CONST. & DEMO." or similar
            for col in range(sheet.ncols):
                value = self.excel_utils.get_cell_value(sheet, row, col)
                if value and 'CONST' in str(value).upper():
                    material = str(value).strip()
                    break
            if material:
                break
        
        # Convert weights from kg to tonnes
        if gross_weight is not None:
            gross_weight = gross_weight / 1000.0
        if tare_weight is not None:
            tare_weight = tare_weight / 1000.0
        if net_weight is not None:
            net_weight = net_weight / 1000.0
        
        # Format dates and times
        if isinstance(entry_date, (int, float)):
            entry_date = self.excel_utils.parse_date_value(entry_date, datemode)
        if isinstance(exit_date, (int, float)):
            exit_date = self.excel_utils.parse_date_value(exit_date, datemode)
        
        # Clean text fields
        vehicle = self.excel_utils.clean_text_value(vehicle)
        license_plate = self.excel_utils.clean_text_value(license_plate)
        reference = self.excel_utils.clean_text_value(reference)
        attendant = self.excel_utils.clean_text_value(attendant)
        
        return TicketDTO(
            ticket_number=ticket_number,
            reference=reference,
            status=status,
            vehicle=vehicle,
            license=license_plate,
            gross_weight=gross_weight,
            tare_weight=tare_weight,
            net_weight=net_weight,
            entry_date=entry_date,
            entry_time=self.excel_utils.clean_text_value(entry_time),
            exit_date=exit_date,
            exit_time=self.excel_utils.clean_text_value(exit_time),
            material=material or "CONST. & DEMO.",
            attendant=attendant,
            row_number=start_row + 1  # 1-based for user display
        )
    
    def _get_value_from_row(self, sheet, row: int, col: int) -> Any:
        """Get a value from a specific cell"""
        try:
            return self.excel_utils.get_cell_value(sheet, row, col)
        except:
            return None
    
    def _get_value_after_label(self, sheet, start_row: int, end_row: int, *labels: str) -> Any:
        """Find a label and return the value in the next cell"""
        for row in range(start_row, end_row):
            for col in range(sheet.ncols - 1):  # -1 to avoid index error
                value = self.excel_utils.get_cell_value(sheet, row, col)
                if value:
                    value_str = str(value).strip().upper()
                    for label in labels:
                        if value_str == label.upper():
                            # Return the next cell's value
                            return self.excel_utils.get_cell_value(sheet, row, col + 1)
        return None
    
    def _get_weight_value(self, sheet, start_row: int, end_row: int, weight_type: str) -> Optional[float]:
        """Extract weight value by type (GROSS, TARE, NET)"""
        for row in range(start_row, end_row):
            for col in range(sheet.ncols - 1):
                value = self.excel_utils.get_cell_value(sheet, row, col)
                if value and str(value).strip().upper() == weight_type.upper():
                    # Weight value is in the next column
                    weight_val = self.excel_utils.get_cell_value(sheet, row, col + 1)
                    if weight_val is not None:
                        try:
                            return float(weight_val)
                        except (ValueError, TypeError):
                            pass
        return None