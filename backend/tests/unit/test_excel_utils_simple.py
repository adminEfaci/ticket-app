import pytest
from backend.utils.excel_utils import ExcelUtils


class TestExcelUtilsSimple:
    
    @pytest.fixture
    def excel_utils(self):
        return ExcelUtils()

    def test_parse_weight_value_numbers(self, excel_utils):
        # Test basic numbers
        assert excel_utils.parse_weight_value(10.5) == 10.5
        assert excel_utils.parse_weight_value(100) == 100.0
        
        # Test kg to tonnes conversion
        assert excel_utils.parse_weight_value(1500) == 1.5  # kg to tonnes conversion
        assert excel_utils.parse_weight_value(2000) == 2.0
        
        # Test small numbers (should stay as is)
        assert excel_utils.parse_weight_value(5.5) == 5.5
        assert excel_utils.parse_weight_value(50) == 50.0

    def test_parse_weight_value_text(self, excel_utils):
        # Test text with units
        assert excel_utils.parse_weight_value("5.5 tonnes") == 5.5
        assert excel_utils.parse_weight_value("1500 kg") == 1.5
        assert excel_utils.parse_weight_value("10.0 T") == 10.0
        
        # Test invalid values
        assert excel_utils.parse_weight_value("invalid") is None
        assert excel_utils.parse_weight_value("") is None
        assert excel_utils.parse_weight_value(None) is None

    def test_clean_text_value_normal(self, excel_utils):
        # Test text cleaning
        assert excel_utils.clean_text_value("  hello world  ") == "hello world"
        assert excel_utils.clean_text_value("multiple   spaces") == "multiple spaces"
        assert excel_utils.clean_text_value("") is None
        assert excel_utils.clean_text_value(None) is None
        assert excel_utils.clean_text_value(123) == "123"

    def test_parse_date_value_text_formats(self, excel_utils):
        from datetime import date
        
        # Test various date formats that are supported
        assert excel_utils.parse_date_value("2024-01-15") == date(2024, 1, 15)
        assert excel_utils.parse_date_value("15/01/2024") == date(2024, 1, 15)
        
        # Test invalid dates
        assert excel_utils.parse_date_value("invalid") is None
        assert excel_utils.parse_date_value("") is None
        assert excel_utils.parse_date_value(None) is None

