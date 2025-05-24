import pytest
from unittest.mock import Mock, patch

from backend.services.xls_parser_service import XlsParserService

class TestXlsParserServiceFixed:
    """Fixed XLS parser tests with proper mocking"""
    
    @pytest.fixture
    def parser_service(self):
        return XlsParserService()
    
    @pytest.fixture
    def mock_sheet_data(self):
        """Helper to create properly mocked sheet data"""
        def create_mock(rows_data):
            sheet = Mock()
            sheet.nrows = len(rows_data)
            sheet.ncols = len(rows_data[0]) if rows_data else 0
            
            # Mock row_values
            sheet.row_values = Mock(side_effect=lambda idx: rows_data[idx] if idx < len(rows_data) else [])
            
            # Mock cell access
            def cell_value(row, col):
                if row < len(rows_data) and col < len(rows_data[row]):
                    return rows_data[row][col]
                return None
            
            # Mock for ExcelUtils.get_cell_value
            def get_cell_value_mock(s, r, c):
                return cell_value(r, c)
            
            # Mock for ExcelUtils.get_row_data
            def get_row_data_mock(s, r):
                if r < len(rows_data):
                    return {i: v for i, v in enumerate(rows_data[r]) if v}
                return {}
            
            return sheet, get_cell_value_mock, get_row_data_mock
        
        return create_mock
    
    def test_parse_success(self, parser_service, mock_sheet_data):
        """Test successful parsing"""
        rows = [
            ["Ticket Number", "Reference", "Gross Weight", "Tare Weight", "Net Weight", "Status", "Entry Date"],
            ["T001", "#007", 10500.0, 2000.0, 8500.0, "COMPLETE", "2024-01-15"],
            ["T002", "MM1001", 15000.0, 3000.0, 12000.0, "COMPLETE", "2024-01-16"],
            ["T003", "T-202", 0.0, 0.0, 0.0, "VOID", "2024-01-17"]
        ]
        
        sheet, get_cell_mock, get_row_mock = mock_sheet_data(rows)
        workbook = Mock()
        workbook.sheet_by_index.return_value = sheet
        workbook.datemode = 0
        
        with patch('backend.services.xls_parser_service.xlrd.open_workbook', return_value=workbook), \
             patch.object(parser_service.excel_utils, 'get_cell_value', side_effect=get_cell_mock), \
             patch.object(parser_service.excel_utils, 'get_row_data', side_effect=get_row_mock), \
             patch.object(parser_service.excel_utils, 'find_header_row', return_value=0):
            
            tickets, errors = parser_service.parse_xls_file("test.xls")
            
            assert len(tickets) == 3
            assert len(errors) == 0
            
            # Check first ticket
            assert tickets[0].ticket_number == "T001"
            assert tickets[0].reference == "#007"
            assert tickets[0].gross_weight == 10500.0
            assert tickets[0].net_weight == 8500.0
            
            # Check VOID ticket
            assert tickets[2].status == "VOID"
            assert tickets[2].net_weight == 0.0
    
    def test_parse_with_empty_rows(self, parser_service, mock_sheet_data):
        """Test parsing with empty rows"""
        rows = [
            ["Ticket Number", "Reference", "Net Weight", "Status"],
            ["T001", "REF001", 8500.0, "COMPLETE"],
            ["", "", "", ""],  # Empty row - should be skipped
            ["T002", "REF002", 12000.0, "COMPLETE"]
        ]
        
        sheet, get_cell_mock, get_row_mock = mock_sheet_data(rows)
        workbook = Mock()
        workbook.sheet_by_index.return_value = sheet
        workbook.datemode = 0
        
        with patch('backend.services.xls_parser_service.xlrd.open_workbook', return_value=workbook), \
             patch.object(parser_service.excel_utils, 'get_cell_value', side_effect=get_cell_mock), \
             patch.object(parser_service.excel_utils, 'get_row_data', side_effect=get_row_mock), \
             patch.object(parser_service.excel_utils, 'find_header_row', return_value=0):
            
            tickets, errors = parser_service.parse_xls_file("test.xls")
            
            assert len(tickets) == 2  # Empty row skipped
            assert tickets[0].ticket_number == "T001"
            assert tickets[1].ticket_number == "T002"
    
    def test_parse_with_invalid_data(self, parser_service, mock_sheet_data):
        """Test parsing with invalid data"""
        rows = [
            ["Ticket Number", "Reference", "Net Weight", "Status"],
            ["T001", "REF001", 8500.0, "COMPLETE"],
            ["", "REF002", 12000.0, "COMPLETE"],  # Missing ticket number
            ["T003", "REF003", "invalid", "COMPLETE"]  # Invalid weight
        ]
        
        sheet, get_cell_mock, get_row_mock = mock_sheet_data(rows)
        workbook = Mock()
        workbook.sheet_by_index.return_value = sheet
        workbook.datemode = 0
        
        with patch('backend.services.xls_parser_service.xlrd.open_workbook', return_value=workbook), \
             patch.object(parser_service.excel_utils, 'get_cell_value', side_effect=get_cell_mock), \
             patch.object(parser_service.excel_utils, 'get_row_data', side_effect=get_row_mock), \
             patch.object(parser_service.excel_utils, 'find_header_row', return_value=0):
            
            tickets, errors = parser_service.parse_xls_file("test.xls")
            
            assert len(tickets) >= 1  # At least T001 should be valid
            assert tickets[0].ticket_number == "T001"
            assert len(errors) >= 1  # Should have errors for invalid rows
    
    def test_column_mapping_detection(self, parser_service, mock_sheet_data):
        """Test column mapping detection with different headers"""
        rows = [
            ["Ticket #", "Ref", "Net Weight", "Status"],  # Headers that match the detection logic
            ["T001", "REF001", 8500.0, "COMPLETE"]
        ]
        
        sheet, get_cell_mock, get_row_mock = mock_sheet_data(rows)
        
        with patch.object(parser_service.excel_utils, 'get_cell_value', side_effect=get_cell_mock):
            mapping = parser_service._detect_column_mapping(sheet, 0)
            
            assert 'ticket_number' in mapping
            assert 'reference' in mapping
            assert 'net_weight' in mapping
            assert 'status' in mapping
    
    def test_file_not_found(self, parser_service):
        """Test handling of file not found"""
        with patch('backend.services.xls_parser_service.xlrd.open_workbook', side_effect=FileNotFoundError("File not found")):
            tickets, errors = parser_service.parse_xls_file("nonexistent.xls")
            
            assert len(tickets) == 0
            assert len(errors) == 1
            assert "File not found" in errors[0].error_message
    
    def test_multi_row_format_detection(self, parser_service, mock_sheet_data):
        """Test detection of multi-row format"""
        # Multi-row format like APRIL 14 2025.xls
        rows = [
            ["TICKET #", "0001"],
            ["In:", "14/04/2025 08:30:45", "Out:", "14/04/2025 08:45:30"],
            ["Vehicle:", "ABC-123", "Material:", "Sand"],
            ["Reference:", "#007 SAND EX SEVEN HILLS"],
            ["Gross:", "25000", "Tare:", "10000", "Net:", "15000"],
            ["", ""],  # Empty row
            ["TICKET #", "0002"]
        ]
        
        sheet, get_cell_mock, get_row_mock = mock_sheet_data(rows)
        workbook = Mock()
        workbook.sheet_by_index.return_value = sheet
        workbook.datemode = 0
        
        # This should detect it needs multi-row parser
        with patch('backend.services.xls_parser_service.xlrd.open_workbook', return_value=workbook), \
             patch.object(parser_service.excel_utils, 'get_cell_value', side_effect=get_cell_mock):
            
            # Check if it detects the multi-row format
            header_row = parser_service.excel_utils.find_header_row(sheet)
            # In multi-row format, there's no traditional header row
            assert header_row is None or header_row > 5