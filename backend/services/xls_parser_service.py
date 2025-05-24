from pathlib import Path
from typing import List, Dict, Optional, Union, Tuple
from datetime import date
from uuid import UUID
import re
import logging
import json

from ..utils.excel_utils import ExcelUtils
from ..models.ticket import TicketDTO, TicketErrorLog
from .multi_row_xls_parser import MultiRowXlsParser

logger = logging.getLogger(__name__)

class XlsParserService:
    """
    Service for parsing legacy .xls files and extracting ticket data
    """
    
    def __init__(self):
        self.excel_utils = ExcelUtils()
        self.multi_row_parser = MultiRowXlsParser()
    
    def parse_xls_file(self, file_path: Union[str, Path]) -> Tuple[List[TicketDTO], List[TicketErrorLog]]:
        """
        Parse an XLS file and extract ticket data
        
        Args:
            file_path: Path to the .xls file
            
        Returns:
            Tuple of (tickets, errors)
        """
        try:
            workbook = self.excel_utils.open_xls_file(file_path)
            sheet = self.excel_utils.get_worksheet(workbook)
            
            # Detect if this is a multi-row format
            if self._is_multi_row_format(sheet):
                logger.info("Detected multi-row ticket format, using MultiRowXlsParser")
                return self.multi_row_parser.parse_xls_file(file_path)
            
            # Detect structure
            header_row = self.excel_utils.find_header_row(sheet)
            data_start_row = self.excel_utils.detect_data_start_row(sheet, header_row)
            column_mapping = self._detect_column_mapping(sheet, header_row)
            
            logger.info(f"Parsing XLS: header_row={header_row}, data_start={data_start_row}, columns={column_mapping}")
            
            # Extract tickets
            tickets = []
            errors = []
            
            for row_idx in range(data_start_row, sheet.nrows):
                if self.excel_utils.is_empty_row(sheet, row_idx):
                    continue
                
                try:
                    ticket_dto = self._extract_ticket_from_row(
                        sheet, row_idx, column_mapping, workbook.datemode
                    )
                    if ticket_dto:
                        tickets.append(ticket_dto)
                except Exception as e:
                    raw_data = self.excel_utils.get_row_data(sheet, row_idx)
                    error_log = TicketErrorLog(
                        batch_id=UUID('00000000-0000-0000-0000-000000000000'),  # Placeholder
                        ticket_number=None,
                        row_number=row_idx + 1,  # 1-based for user display
                        error_type="PARSING_ERROR",
                        error_message=f"Row parsing error: {str(e)}",
                        raw_data=json.dumps(raw_data) if isinstance(raw_data, dict) else raw_data
                    )
                    errors.append(error_log)
                    logger.warning(f"Error parsing row {row_idx + 1}: {str(e)}")
            
            logger.info(f"Extracted {len(tickets)} tickets with {len(errors)} errors")
            return tickets, errors
            
        except Exception as e:
            error_log = TicketErrorLog(
                batch_id=UUID('00000000-0000-0000-0000-000000000000'),  # Placeholder
                ticket_number=None,
                row_number=0,
                error_type="FILE_ERROR",
                error_message=f"Cannot open XLS file: {str(e)}",
                raw_data=json.dumps({"file_path": str(file_path)})
            )
            logger.error(f"Failed to parse XLS file {file_path}: {str(e)}")
            return [], [error_log]
    
    def _detect_column_mapping(self, sheet, header_row: Optional[int]) -> Dict[str, int]:
        """
        Detect which columns contain which ticket fields
        
        Args:
            sheet: xlrd Sheet object
            header_row: Header row index if found
            
        Returns:
            Dictionary mapping field names to column indices
        """
        mapping = {}
        
        if header_row is not None:
            # Use header row to detect columns
            for col in range(sheet.ncols):
                header_value = self.excel_utils.get_cell_value(sheet, header_row, col)
                if header_value:
                    header_text = str(header_value).lower().strip()
                    
                    # Map headers to field names
                    if any(word in header_text for word in ['ticket', 'no', 'number']):
                        if 'ticket' in header_text:
                            mapping['ticket_number'] = col
                    elif any(word in header_text for word in ['reference', 'ref']):
                        mapping['reference'] = col
                    elif 'status' in header_text:
                        mapping['status'] = col
                    elif 'gross' in header_text and 'weight' in header_text:
                        mapping['gross_weight'] = col
                    elif 'tare' in header_text and 'weight' in header_text:
                        mapping['tare_weight'] = col
                    elif 'net' in header_text and 'weight' in header_text:
                        mapping['net_weight'] = col
                    elif any(word in header_text for word in ['vehicle', 'truck', 'rego']):
                        mapping['vehicle'] = col
                    elif any(word in header_text for word in ['date', 'entry']):
                        mapping['entry_date'] = col
                    elif 'client' in header_text:
                        mapping['client_id'] = col
        
        # Fallback: try to detect columns by data patterns
        data_start = self.excel_utils.detect_data_start_row(sheet, header_row)
        
        # Detect ticket number column if not found
        if 'ticket_number' not in mapping:
            ticket_col = self.excel_utils.detect_ticket_number_column(sheet, header_row)
            if ticket_col is not None:
                mapping['ticket_number'] = ticket_col
        
        # Use heuristics for other columns if headers weren't clear
        if len(mapping) < 3:  # If we didn't find enough columns from headers
            mapping.update(self._detect_columns_by_pattern(sheet, data_start))
        
        return mapping
    
    def _detect_columns_by_pattern(self, sheet, data_start: int) -> Dict[str, int]:
        """
        Detect columns by analyzing data patterns
        
        Args:
            sheet: xlrd Sheet object
            data_start: Row where data starts
            
        Returns:
            Dictionary mapping field names to column indices
        """
        mapping = {}
        sample_rows = min(10, sheet.nrows - data_start)
        
        for col in range(sheet.ncols):
            col_pattern = self._analyze_column_pattern(sheet, col, data_start, sample_rows)
            
            if col_pattern == 'ticket_number' and 'ticket_number' not in mapping:
                mapping['ticket_number'] = col
            elif col_pattern == 'weight' and 'net_weight' not in mapping:
                # Assume first weight column is net weight
                mapping['net_weight'] = col
            elif col_pattern == 'date' and 'entry_date' not in mapping:
                mapping['entry_date'] = col
            elif col_pattern == 'status' and 'status' not in mapping:
                mapping['status'] = col
        
        return mapping
    
    def _analyze_column_pattern(self, sheet, col: int, data_start: int, sample_rows: int) -> Optional[str]:
        """
        Analyze a column's data pattern to guess its content type
        
        Args:
            sheet: xlrd Sheet object
            col: Column index
            data_start: Row where data starts
            sample_rows: Number of rows to sample
            
        Returns:
            Detected pattern type or None
        """
        values = []
        for row in range(data_start, data_start + sample_rows):
            if row >= sheet.nrows:
                break
            value = self.excel_utils.get_cell_value(sheet, row, col)
            if value is not None:
                values.append(value)
        
        if not values:
            return None
        
        # Analyze patterns
        numeric_count = sum(1 for v in values if isinstance(v, (int, float)))
        text_count = sum(1 for v in values if isinstance(v, str))
        date_count = sum(1 for v in values if isinstance(v, date))
        
        # Check for ticket number pattern (alphanumeric)
        if text_count > 0:
            ticket_like = sum(1 for v in values 
                             if isinstance(v, str) and re.match(r'^[A-Za-z0-9][A-Za-z0-9\-_]{2,20}$', str(v)))
            if ticket_like / len(values) > 0.7:
                return 'ticket_number'
        
        # Check for status pattern
        if text_count > 0:
            status_words = {'ORIGINAL', 'REPRINT', 'VOID', 'ACTIVE', 'CANCELLED'}
            status_like = sum(1 for v in values 
                             if isinstance(v, str) and str(v).upper() in status_words)
            if status_like / len(values) > 0.5:
                return 'status'
        
        # Check for weight pattern (numeric values in reasonable range)
        if numeric_count > 0:
            weight_like = sum(1 for v in values 
                             if isinstance(v, (int, float)) and 0.1 <= v <= 200.0)
            if weight_like / len(values) > 0.7:
                return 'weight'
        
        # Check for date pattern
        if date_count > 0 or numeric_count > 0:
            # Excel dates are often stored as numbers
            if date_count / len(values) > 0.5:
                return 'date'
        
        return None
    
    def _extract_ticket_from_row(
        self, 
        sheet, 
        row_idx: int, 
        column_mapping: Dict[str, int],
        datemode: int
    ) -> Optional[TicketDTO]:
        """
        Extract a ticket from a single row
        
        Args:
            sheet: xlrd Sheet object
            row_idx: Row index
            column_mapping: Column mapping dictionary
            datemode: Excel workbook date mode
            
        Returns:
            TicketDTO object or None if row is invalid
        """
        raw_data = self.excel_utils.get_row_data(sheet, row_idx)
        
        # Extract ticket number (required)
        ticket_number = None
        if 'ticket_number' in column_mapping:
            ticket_number = self.excel_utils.get_cell_value(sheet, row_idx, column_mapping['ticket_number'])
            ticket_number = self.excel_utils.clean_text_value(ticket_number)
        
        # Skip row if no ticket number
        if not ticket_number:
            return None
        
        # Extract other fields
        reference = None
        if 'reference' in column_mapping:
            reference = self.excel_utils.get_cell_value(sheet, row_idx, column_mapping['reference'])
            reference = self.excel_utils.clean_text_value(reference)
        
        status = None
        if 'status' in column_mapping:
            status = self.excel_utils.get_cell_value(sheet, row_idx, column_mapping['status'])
            status = self.excel_utils.clean_text_value(status)
        
        gross_weight = None
        if 'gross_weight' in column_mapping:
            gross_weight = self.excel_utils.get_cell_value(sheet, row_idx, column_mapping['gross_weight'])
        
        tare_weight = None
        if 'tare_weight' in column_mapping:
            tare_weight = self.excel_utils.get_cell_value(sheet, row_idx, column_mapping['tare_weight'])
        
        net_weight = None
        if 'net_weight' in column_mapping:
            net_weight = self.excel_utils.get_cell_value(sheet, row_idx, column_mapping['net_weight'])
        
        vehicle = None
        if 'vehicle' in column_mapping:
            vehicle = self.excel_utils.get_cell_value(sheet, row_idx, column_mapping['vehicle'])
            vehicle = self.excel_utils.clean_text_value(vehicle)
        
        entry_date = None
        if 'entry_date' in column_mapping:
            entry_date = self.excel_utils.get_cell_value(sheet, row_idx, column_mapping['entry_date'])
        
        client_id = None
        if 'client_id' in column_mapping:
            client_id = self.excel_utils.get_cell_value(sheet, row_idx, column_mapping['client_id'])
            client_id = self.excel_utils.clean_text_value(client_id)
        
        return TicketDTO(
            ticket_number=ticket_number,
            reference=reference,
            status=status,
            gross_weight=gross_weight,
            tare_weight=tare_weight,
            net_weight=net_weight,
            vehicle=vehicle,
            entry_date=entry_date,
            row_number=row_idx + 1,  # 1-based for user display
            raw_data=json.dumps(raw_data) if isinstance(raw_data, dict) else raw_data
        )
    
    def detect_ticket_boundaries(self, sheet) -> List[Tuple[int, int]]:
        """
        Detect ticket boundaries in multi-row format (if needed for complex layouts)
        
        Args:
            sheet: xlrd Sheet object
            
        Returns:
            List of (start_row, end_row) tuples for each ticket
        """
        # This is a placeholder for more complex multi-row ticket detection
        # For now, assume each row is a separate ticket
        boundaries = []
        header_row = self.excel_utils.find_header_row(sheet)
        data_start = self.excel_utils.detect_data_start_row(sheet, header_row)
        
        for row in range(data_start, sheet.nrows):
            if not self.excel_utils.is_empty_row(sheet, row):
                boundaries.append((row, row))
        
        return boundaries
    
    def _is_multi_row_format(self, sheet) -> bool:
        """
        Detect if the XLS file uses multi-row format (like APRIL 14 2025.xls)
        
        Args:
            sheet: xlrd Sheet object
            
        Returns:
            True if multi-row format detected
        """
        # Check first few rows for 'TICKET #' pattern
        ticket_count = 0
        for row in range(min(20, sheet.nrows)):
            cell_value = self.excel_utils.get_cell_value(sheet, row, 0)
            if cell_value and str(cell_value).strip().upper() == 'TICKET #':
                ticket_count += 1
                if ticket_count >= 2:
                    # Found multiple 'TICKET #' entries, it's multi-row format
                    return True
        return False