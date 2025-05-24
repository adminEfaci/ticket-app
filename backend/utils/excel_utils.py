import xlrd
from pathlib import Path
from typing import Dict, Any, Optional, Union
from xlrd.sheet import Sheet
import re
from datetime import datetime, date

class ExcelUtils:
    """Utility functions for working with legacy .xls files"""
    
    @staticmethod
    def open_xls_file(file_path: Union[str, Path]) -> xlrd.book.Book:
        """
        Safely open an XLS file using xlrd
        
        Args:
            file_path: Path to the .xls file
            
        Returns:
            xlrd.book.Book object
            
        Raises:
            ValueError: If file cannot be opened or is not valid XLS
        """
        try:
            return xlrd.open_workbook(str(file_path))
        except Exception as e:
            raise ValueError(f"Cannot open XLS file: {str(e)}")
    
    @staticmethod
    def get_worksheet(workbook: xlrd.book.Book, sheet_index: int = 0) -> Sheet:
        """
        Get worksheet by index
        
        Args:
            workbook: xlrd workbook object
            sheet_index: Index of the sheet (default: 0)
            
        Returns:
            xlrd Sheet object
            
        Raises:
            ValueError: If sheet index is invalid
        """
        try:
            return workbook.sheet_by_index(sheet_index)
        except Exception as e:
            raise ValueError(f"Cannot access sheet at index {sheet_index}: {str(e)}")
    
    @staticmethod
    def get_cell_value(sheet: Sheet, row: int, col: int) -> Any:
        """
        Safely get cell value with type conversion
        
        Args:
            sheet: xlrd Sheet object
            row: Row index
            col: Column index
            
        Returns:
            Cell value (string, number, or None)
        """
        try:
            cell = sheet.cell(row, col)
            cell_type = cell.ctype
            
            # Handle different cell types
            if cell_type == xlrd.XL_CELL_EMPTY:
                return None
            elif cell_type == xlrd.XL_CELL_TEXT:
                return str(cell.value).strip()
            elif cell_type == xlrd.XL_CELL_NUMBER:
                return cell.value
            elif cell_type == xlrd.XL_CELL_DATE:
                # Convert Excel date to Python date
                date_tuple = xlrd.xldate_as_tuple(cell.value, sheet.book.datemode)
                return datetime(*date_tuple).date()
            elif cell_type == xlrd.XL_CELL_BOOLEAN:
                return bool(cell.value)
            else:
                return str(cell.value).strip() if cell.value else None
                
        except Exception:
            return None
    
    @staticmethod
    def get_row_data(sheet: Sheet, row_index: int) -> Dict[int, Any]:
        """
        Get all data from a specific row
        
        Args:
            sheet: xlrd Sheet object
            row_index: Row index to extract
            
        Returns:
            Dictionary mapping column index to cell value
        """
        row_data = {}
        for col in range(sheet.ncols):
            value = ExcelUtils.get_cell_value(sheet, row_index, col)
            if value is not None:
                row_data[col] = value
        return row_data
    
    @staticmethod
    def find_header_row(sheet: Sheet, max_rows: int = 20) -> Optional[int]:
        """
        Find the header row by looking for common ticket field names
        
        Args:
            sheet: xlrd Sheet object
            max_rows: Maximum rows to search for headers
            
        Returns:
            Row index of header row, or None if not found
        """
        header_keywords = [
            'ticket', 'number', 'reference', 'weight', 'net', 'gross', 
            'tare', 'date', 'status', 'vehicle', 'entry'
        ]
        
        for row in range(min(max_rows, sheet.nrows)):
            row_text = []
            for col in range(min(20, sheet.ncols)):  # Check first 20 columns
                cell_value = ExcelUtils.get_cell_value(sheet, row, col)
                if cell_value:
                    row_text.append(str(cell_value).lower())
            
            # Check if this row contains header-like content
            if len(row_text) >= 3:  # At least 3 columns with data
                matches = sum(1 for keyword in header_keywords 
                             if any(keyword in text for text in row_text))
                if matches >= 3:  # At least 3 keyword matches
                    return row
        
        return None
    
    @staticmethod
    def detect_data_start_row(sheet: Sheet, header_row: Optional[int] = None) -> int:
        """
        Detect where data rows start (after headers)
        
        Args:
            sheet: xlrd Sheet object
            header_row: Known header row index
            
        Returns:
            Row index where data starts
        """
        if header_row is not None:
            return header_row + 1
        
        # If no header found, assume data starts from row 1 (0-indexed)
        return 1
    
    @staticmethod
    def is_empty_row(sheet: Sheet, row_index: int) -> bool:
        """
        Check if a row is effectively empty
        
        Args:
            sheet: xlrd Sheet object
            row_index: Row index to check
            
        Returns:
            True if row is empty or contains only whitespace
        """
        for col in range(sheet.ncols):
            value = ExcelUtils.get_cell_value(sheet, row_index, col)
            if value and str(value).strip():
                return False
        return True
    
    @staticmethod
    def clean_text_value(value: Any) -> Optional[str]:
        """
        Clean and normalize text values from Excel cells
        
        Args:
            value: Raw cell value
            
        Returns:
            Cleaned string or None
        """
        if value is None:
            return None
        
        text = str(value).strip()
        if not text:
            return None
        
        # Remove extra whitespace and normalize
        text = re.sub(r'\s+', ' ', text)
        return text
    
    @staticmethod
    def parse_weight_value(value: Any) -> Optional[float]:
        """
        Parse weight values from Excel cells, handling various formats
        
        Args:
            value: Raw cell value (could be number, text with units, etc.)
            
        Returns:
            Weight as float in tonnes, or None if invalid
        """
        if value is None:
            return None
        
        if isinstance(value, (int, float)):
            weight = float(value)
            # Convert kg to tonnes if likely in kg (values > 1000)
            if weight > 1000:
                weight = weight / 1000
            return weight
        
        # Handle text values with units
        text = str(value).strip().upper()
        if not text:
            return None
        
        # Check if text looks like a weight value (starts with digit)
        if not re.match(r'^\s*\d', text):
            return None
        
        # Detect unit type before removing
        is_kg = 'KG' in text
        
        # Remove common weight units and extract number
        text = re.sub(r'(KG|TONNES?|T|LBS?|POUNDS?)', '', text)
        text = re.sub(r'[^\d.-]', '', text)  # Keep only digits, dots, and minus
        
        if not text:  # No digits found
            return None
        
        try:
            weight = float(text)
            
            # Convert kg to tonnes if explicitly marked as kg or if large number
            if is_kg or weight > 1000:
                weight = weight / 1000
            
            return weight
        except ValueError:
            return None
    
    @staticmethod
    def parse_date_value(value: Any, workbook_datemode: int = 0) -> Optional[date]:
        """
        Parse date values from Excel cells
        
        Args:
            value: Raw cell value
            workbook_datemode: Excel workbook date mode
            
        Returns:
            Python date object or None if invalid
        """
        if value is None:
            return None
        
        # If it's already a date
        if isinstance(value, date):
            return value
        
        # If it's an Excel date number
        if isinstance(value, (int, float)):
            try:
                date_tuple = xlrd.xldate_as_tuple(value, workbook_datemode)
                return datetime(*date_tuple).date()
            except xlrd.xldate.XLDateError:
                pass
        
        # Try to parse text date
        if isinstance(value, str):
            text = value.strip()
            # Common date formats
            date_formats = [
                '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y',
                '%Y%m%d', '%d.%m.%Y', '%Y.%m.%d'
            ]
            
            for fmt in date_formats:
                try:
                    return datetime.strptime(text, fmt).date()
                except ValueError:
                    continue
        
        return None
    
    @staticmethod
    def detect_ticket_number_column(sheet: Sheet, header_row: Optional[int] = None) -> Optional[int]:
        """
        Detect which column contains ticket numbers
        
        Args:
            sheet: xlrd Sheet object
            header_row: Header row index if known
            
        Returns:
            Column index for ticket numbers, or None
        """
        # Look for header indicators first
        if header_row is not None:
            for col in range(sheet.ncols):
                header_value = ExcelUtils.get_cell_value(sheet, header_row, col)
                if header_value:
                    header_text = str(header_value).lower()
                    if 'ticket' in header_text and 'number' in header_text:
                        return col
                    if header_text in ['ticket', 'ticket_no', 'ticketno']:
                        return col
        
        # Look for patterns in data (ticket numbers often start with letters)
        data_start = ExcelUtils.detect_data_start_row(sheet, header_row)
        for col in range(min(10, sheet.ncols)):  # Check first 10 columns
            ticket_like_count = 0
            sample_size = min(10, sheet.nrows - data_start)
            
            for row in range(data_start, data_start + sample_size):
                value = ExcelUtils.get_cell_value(sheet, row, col)
                if value:
                    text = str(value).strip()
                    # Check if it looks like a ticket number (alphanumeric, reasonable length)
                    if re.match(r'^[A-Za-z0-9][A-Za-z0-9\-_]{2,20}$', text):
                        ticket_like_count += 1
            
            # If most values in this column look like ticket numbers
            if ticket_like_count >= sample_size * 0.7:
                return col
        
        return None