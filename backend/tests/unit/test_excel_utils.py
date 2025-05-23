import pytest
import tempfile
import xlrd
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import date

from backend.utils.excel_utils import ExcelUtils


class TestExcelUtils:
    
    @pytest.fixture
    def excel_utils(self):
        return ExcelUtils()
    
    def test_clean_text_value_normal(self, excel_utils):
        """Test cleaning normal text values"""
        assert excel_utils.clean_text_value("  Hello World  ") == "Hello World"
        assert excel_utils.clean_text_value("Multiple   Spaces") == "Multiple Spaces"
        assert excel_utils.clean_text_value("") is None
        assert excel_utils.clean_text_value(None) is None
        assert excel_utils.clean_text_value("   ") is None
    
    def test_parse_weight_value_numbers(self, excel_utils):
        """Test parsing weight values from numbers"""
        assert excel_utils.parse_weight_value(5.5) == 5.5
        assert excel_utils.parse_weight_value(10) == 10.0
        assert excel_utils.parse_weight_value(1500) == 1.5  # kg to tonnes conversion
        assert excel_utils.parse_weight_value(None) is None
    
    def test_parse_weight_value_text(self, excel_utils):
        """Test parsing weight values from text with units"""
        assert excel_utils.parse_weight_value("5.5 tonnes") == 5.5
        assert excel_utils.parse_weight_value("1500 kg") == 1.5
        assert excel_utils.parse_weight_value("10.2T") == 10.2
        assert excel_utils.parse_weight_value("invalid") is None
        assert excel_utils.parse_weight_value("") is None
    
    def test_parse_date_value_date_object(self, excel_utils):
        """Test parsing date from date object"""
        test_date = date(2023, 5, 15)
        result = excel_utils.parse_date_value(test_date)
        assert result == test_date
    
    def test_parse_date_value_text_formats(self, excel_utils):
        """Test parsing date from various text formats"""
        # Test different date formats
        assert excel_utils.parse_date_value("2023-05-15") == date(2023, 5, 15)
        assert excel_utils.parse_date_value("15/05/2023") == date(2023, 5, 15)
        assert excel_utils.parse_date_value("05/15/2023") == date(2023, 5, 15)
        assert excel_utils.parse_date_value("15-05-2023") == date(2023, 5, 15)
        assert excel_utils.parse_date_value("20230515") == date(2023, 5, 15)
        assert excel_utils.parse_date_value("invalid_date") is None
        assert excel_utils.parse_date_value("") is None
    
    @patch('xlrd.open_workbook')
    def test_open_xls_file_success(self, mock_open, excel_utils):
        """Test successful XLS file opening"""
        mock_workbook = Mock()
        mock_open.return_value = mock_workbook
        
        result = excel_utils.open_xls_file("/path/to/test.xls")
        
        assert result == mock_workbook
        mock_open.assert_called_once_with("/path/to/test.xls")
    
    @patch('xlrd.open_workbook')
    def test_open_xls_file_failure(self, mock_open, excel_utils):
        """Test XLS file opening failure"""
        mock_open.side_effect = Exception("File not found")
        
        with pytest.raises(ValueError, match="Cannot open XLS file"):
            excel_utils.open_xls_file("/path/to/nonexistent.xls")
    
    def test_get_worksheet_success(self, excel_utils):
        """Test getting worksheet by index"""
        mock_workbook = Mock()
        mock_sheet = Mock()
        mock_workbook.sheet_by_index.return_value = mock_sheet
        
        result = excel_utils.get_worksheet(mock_workbook, 0)
        
        assert result == mock_sheet
        mock_workbook.sheet_by_index.assert_called_once_with(0)
    
    def test_get_worksheet_failure(self, excel_utils):
        """Test getting worksheet failure"""
        mock_workbook = Mock()
        mock_workbook.sheet_by_index.side_effect = Exception("Invalid sheet index")
        
        with pytest.raises(ValueError, match="Cannot access sheet"):
            excel_utils.get_worksheet(mock_workbook, 5)
    
    def test_get_cell_value_different_types(self, excel_utils):
        """Test getting cell values of different types"""
        mock_sheet = Mock()
        
        # Test empty cell
        mock_cell = Mock()
        mock_cell.ctype = xlrd.XL_CELL_EMPTY
        mock_sheet.cell.return_value = mock_cell
        result = excel_utils.get_cell_value(mock_sheet, 0, 0)
        assert result is None
        
        # Test text cell
        mock_cell = Mock()
        mock_cell.ctype = xlrd.XL_CELL_TEXT
        mock_cell.value = "  Test Text  "
        mock_sheet.cell.return_value = mock_cell
        result = excel_utils.get_cell_value(mock_sheet, 0, 0)
        assert result == "Test Text"
        
        # Test number cell
        mock_cell = Mock()
        mock_cell.ctype = xlrd.XL_CELL_NUMBER
        mock_cell.value = 42.5
        mock_sheet.cell.return_value = mock_cell
        result = excel_utils.get_cell_value(mock_sheet, 0, 0)
        assert result == 42.5
        
        # Test boolean cell
        mock_cell = Mock()
        mock_cell.ctype = xlrd.XL_CELL_BOOLEAN
        mock_cell.value = 1
        mock_sheet.cell.return_value = mock_cell
        result = excel_utils.get_cell_value(mock_sheet, 0, 0)
        assert result is True
    
    def test_get_row_data(self, excel_utils):
        """Test getting all data from a row"""
        mock_sheet = Mock()
        mock_sheet.ncols = 3
        
        # Mock cell values
        cell_values = ["A1", 42, None]
        
        # Mock the static method properly
        with patch('backend.utils.excel_utils.ExcelUtils.get_cell_value') as mock_get_cell:
            mock_get_cell.side_effect = lambda sheet, row, col: cell_values[col] if col < len(cell_values) else None
            result = excel_utils.get_row_data(mock_sheet, 0)
        
        expected = {0: "A1", 1: 42}  # None values should be excluded
        assert result == expected
    
    def test_find_header_row(self, excel_utils):
        """Test finding header row by keywords"""
        mock_sheet = Mock()
        mock_sheet.nrows = 5
        mock_sheet.ncols = 4
        
        # Mock header row at index 1
        def mock_get_cell_value(sheet, row, col):
            if row == 1:
                headers = ["Ticket Number", "Reference", "Weight", "Date"]
                return headers[col] if col < len(headers) else None
            return f"Data{row}{col}"
        
        with patch('backend.utils.excel_utils.ExcelUtils.get_cell_value', side_effect=mock_get_cell_value):
            result = excel_utils.find_header_row(mock_sheet)
        
        assert result == 1
    
    def test_find_header_row_not_found(self, excel_utils):
        """Test when header row is not found"""
        mock_sheet = Mock()
        mock_sheet.nrows = 5
        mock_sheet.ncols = 4
        
        # Mock no header-like content
        def mock_get_cell_value(sheet, row, col):
            return f"Data{row}{col}"
        
        with patch.object(excel_utils, 'get_cell_value', side_effect=mock_get_cell_value):
            result = excel_utils.find_header_row(mock_sheet)
        
        assert result is None
    
    def test_detect_data_start_row(self, excel_utils):
        """Test detecting where data starts"""
        mock_sheet = Mock()
        
        # With header row
        result = excel_utils.detect_data_start_row(mock_sheet, header_row=2)
        assert result == 3
        
        # Without header row
        result = excel_utils.detect_data_start_row(mock_sheet, header_row=None)
        assert result == 1
    
    def test_is_empty_row(self, excel_utils):
        """Test checking if row is empty"""
        mock_sheet = Mock()
        mock_sheet.ncols = 3
        
        # Test empty row
        def mock_get_cell_value_empty(sheet, row, col):
            return None
        
        with patch('backend.utils.excel_utils.ExcelUtils.get_cell_value', side_effect=mock_get_cell_value_empty):
            result = excel_utils.is_empty_row(mock_sheet, 0)
        assert result is True
        
        # Test row with data
        def mock_get_cell_value_data(sheet, row, col):
            return "Data" if col == 1 else None
        
        with patch('backend.utils.excel_utils.ExcelUtils.get_cell_value', side_effect=mock_get_cell_value_data):
            result = excel_utils.is_empty_row(mock_sheet, 0)
        assert result is False
    
    def test_detect_ticket_number_column_by_header(self, excel_utils):
        """Test detecting ticket number column by header"""
        mock_sheet = Mock()
        mock_sheet.ncols = 4
        mock_sheet.nrows = 10
        
        # Mock header with ticket number column
        def mock_get_cell_value(sheet, row, col):
            if row == 0:  # Header row
                headers = ["ID", "Ticket Number", "Reference", "Weight"]
                return headers[col] if col < len(headers) else None
            return None
        
        with patch('backend.utils.excel_utils.ExcelUtils.get_cell_value', side_effect=mock_get_cell_value):
            result = excel_utils.detect_ticket_number_column(mock_sheet, header_row=0)
        
        assert result == 1
    
    def test_detect_ticket_number_column_by_pattern(self, excel_utils):
        """Test detecting ticket number column by data pattern"""
        mock_sheet = Mock()
        mock_sheet.ncols = 3
        mock_sheet.nrows = 6
        
        # Mock data where column 1 has ticket-like values
        def mock_get_cell_value(sheet, row, col):
            if col == 1 and row >= 1:  # Ticket column
                return f"T{row:05d}"
            elif col == 0 and row >= 1:  # Non-ticket column (too short)
                return str(row)  # "1", "2", etc - too short to match pattern
            elif col == 2 and row >= 1:  # Another non-ticket column
                return f"Item {row}"
            return None
        
        with patch('backend.utils.excel_utils.ExcelUtils.get_cell_value', side_effect=mock_get_cell_value):
            with patch('backend.utils.excel_utils.ExcelUtils.detect_data_start_row', return_value=1):
                result = excel_utils.detect_ticket_number_column(mock_sheet, header_row=None)
        
        assert result == 1