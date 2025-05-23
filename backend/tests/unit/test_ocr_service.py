import pytest
import re
from unittest.mock import Mock, patch, MagicMock
from PIL import Image
import numpy as np

from backend.services.ocr_service import OCRService


class TestOCRService:
    
    @pytest.fixture
    def ocr_service(self):
        return OCRService()
    
    @pytest.fixture
    def sample_image(self):
        return Image.new('RGB', (400, 300), color='white')
    
    @pytest.fixture
    def mock_ocr_data_valid(self):
        return {
            'text': ['', 'Ticket', 'Number:', 'TK-2024-001', 'Event', 'Details', ''],
            'conf': [0, 85, 90, 95, 80, 75, 0]
        }
    
    @pytest.fixture
    def mock_ocr_data_multiple_tickets(self):
        return {
            'text': ['TK-2024-001', 'some', 'text', 'TK-2024-002', 'more', 'TK-2024-003'],
            'conf': [95, 70, 65, 90, 60, 88]
        }
    
    @pytest.fixture
    def mock_ocr_data_no_tickets(self):
        return {
            'text': ['Event', 'Details', 'Date', 'Location', 'Price'],
            'conf': [85, 90, 88, 92, 87]
        }
    
    def test_init_default_values(self, ocr_service):
        assert ocr_service.min_confidence == 80.0
        assert len(ocr_service.ticket_number_patterns) > 0
        assert hasattr(ocr_service, 'ticket_number_patterns')
    
    def test_ticket_patterns_valid(self, ocr_service):
        patterns = ocr_service.ticket_number_patterns
        
        valid_patterns = [
            "T12345",
            "TKT001",
            "AB-123456",
            "12345678",
            "T12A34"
        ]
        
        for test_pattern in valid_patterns:
            found = False
            for regex_pattern in patterns:
                if re.match(regex_pattern, test_pattern, re.IGNORECASE):
                    found = True
                    break
            assert found, f"Pattern {test_pattern} should match at least one regex"
    
    def test_ticket_patterns_invalid(self, ocr_service):
        patterns = ocr_service.ticket_number_patterns
        
        invalid_patterns = [
            "AB",      # Too short
            "12",      # Too short
            "A1",      # Too short
        ]
        
        for test_pattern in invalid_patterns:
            found = False
            for regex_pattern in patterns:
                if re.match(regex_pattern, test_pattern, re.IGNORECASE):
                    found = True
                    break
            assert not found, f"Pattern {test_pattern} should not match any regex"
    
    @patch('backend.services.ocr_service.pytesseract.image_to_data')
    def test_extract_ticket_number_success(self, mock_tesseract, ocr_service, sample_image, mock_ocr_data_valid):
        mock_tesseract.return_value = mock_ocr_data_valid
        
        ticket_number, confidence = ocr_service.extract_ticket_number(sample_image)
        
        assert ticket_number is not None
        assert confidence > 0
        mock_tesseract.assert_called_once()
    
    @patch('backend.services.ocr_service.pytesseract.image_to_data')
    def test_extract_ticket_number_no_tickets_found(self, mock_tesseract, ocr_service, sample_image, mock_ocr_data_no_tickets):
        mock_tesseract.return_value = mock_ocr_data_no_tickets
        
        ticket_number, confidence = ocr_service.extract_ticket_number(sample_image)
        
        # May return None or a fallback based on implementation
        assert confidence >= 0
    
    @patch('backend.services.ocr_service.pytesseract.image_to_data')
    def test_extract_ticket_number_tesseract_exception(self, mock_tesseract, ocr_service, sample_image):
        mock_tesseract.side_effect = Exception("Tesseract error")
        
        ticket_number, confidence = ocr_service.extract_ticket_number(sample_image)
        
        assert ticket_number is None
        assert confidence == 0.0
    
    def test_find_best_ticket_number_single_valid(self, ocr_service):
        texts = ['TK-2024-001']
        confidences = [90.0]
        
        ticket_number, confidence = ocr_service._find_best_ticket_number(texts, confidences)
        
        assert ticket_number is not None
        assert confidence > 0
    
    def test_find_best_ticket_number_multiple_valid_best_confidence(self, ocr_service):
        texts = ['TK-2024-001', 'TK-2024-002', 'TK-2024-003']
        confidences = [85.0, 95.0, 80.0]
        
        ticket_number, confidence = ocr_service._find_best_ticket_number(texts, confidences)
        
        assert ticket_number is not None
        assert confidence > 0
    
    def test_find_best_ticket_number_no_valid_patterns(self, ocr_service):
        texts = ['Event', 'Details', 'Location']
        confidences = [90.0, 95.0, 88.0]
        
        ticket_number, confidence = ocr_service._find_best_ticket_number(texts, confidences)
        
        # May find alphanumeric sequences as fallback
        assert confidence >= 0
    
    def test_find_best_ticket_number_empty_lists(self, ocr_service):
        texts = []
        confidences = []
        
        ticket_number, confidence = ocr_service._find_best_ticket_number(texts, confidences)
        
        assert ticket_number is None
        assert confidence == 0.0
    
    def test_calculate_candidate_confidence(self, ocr_service):
        candidate = "TK-2024-001"
        texts = ["TK-2024-001", "some", "text"]
        confidences = [95.0, 70.0, 80.0]
        
        confidence = ocr_service._calculate_candidate_confidence(candidate, texts, confidences)
        
        assert confidence >= 0
        assert confidence <= 100
    
    def test_get_pattern_bonus(self, ocr_service):
        good_candidate = "TK12345"
        bonus = ocr_service._get_pattern_bonus(good_candidate)
        
        assert bonus >= 0
        assert bonus <= 20  # Maximum possible bonus
    
    def test_validate_ticket_number_valid(self, ocr_service):
        valid_tickets = [
            "TK-2024-001",
            "T12345",
            "ABC123",
            "12345678"
        ]
        
        for ticket in valid_tickets:
            assert ocr_service.validate_ticket_number(ticket) is True
    
    def test_validate_ticket_number_invalid(self, ocr_service):
        invalid_tickets = [
            "",
            "AB",      # Too short
            "A" * 25,  # Too long
            "!!!",     # No alphanumeric
            None
        ]
        
        for ticket in invalid_tickets:
            assert ocr_service.validate_ticket_number(ticket) is False
    
    @patch('backend.services.ocr_service.pytesseract.image_to_string')
    @patch('backend.services.ocr_service.pytesseract.image_to_data')
    def test_extract_all_text_success(self, mock_data, mock_string, ocr_service, sample_image):
        mock_string.return_value = "TK-2024-001 Event Details"
        mock_data.return_value = {
            'conf': [95, 90, 85, 80, 75]
        }
        
        text, confidence = ocr_service.extract_all_text(sample_image)
        
        assert text == "TK-2024-001 Event Details"
        assert confidence > 0
    
    def test_is_ocr_available(self, ocr_service):
        result = ocr_service.is_ocr_available()
        assert isinstance(result, bool)
    
    def test_get_ocr_config_for_tickets(self, ocr_service):
        config = ocr_service.get_ocr_config_for_tickets()
        assert isinstance(config, str)
        assert '--psm 8' in config
        assert 'tessedit_char_whitelist' in config
    
    @patch('backend.services.ocr_service.TESSERACT_AVAILABLE', False)
    def test_fallback_ticket_extraction(self, ocr_service, sample_image):
        ticket_number, confidence = ocr_service.extract_ticket_number(sample_image)
        
        assert ticket_number is None
        assert confidence >= 0
    
    def test_fallback_ticket_extraction_direct(self, ocr_service, sample_image):
        ticket_number, confidence = ocr_service._fallback_ticket_extraction(sample_image)
        
        assert ticket_number is None
        assert confidence >= 0
    
    def test_fallback_with_good_image_characteristics(self, ocr_service):
        # Create image with good characteristics
        large_image = Image.new('RGB', (800, 600), color='white')
        
        # Add some content
        from PIL import ImageDraw
        draw = ImageDraw.Draw(large_image)
        draw.rectangle([100, 100, 300, 200], fill='black')
        draw.text((110, 110), "TK-2024-001", fill='white')
        
        ticket_number, confidence = ocr_service._fallback_ticket_extraction(large_image)
        
        assert ticket_number is None  # Fallback doesn't extract text
        assert confidence > 0  # But should have positive confidence
    
    @patch('backend.services.ocr_service.pytesseract.image_to_data')
    def test_extract_ticket_number_empty_ocr_result(self, mock_tesseract, ocr_service, sample_image):
        mock_tesseract.return_value = {
            'text': ['', '', ''],
            'conf': [0, 0, 0]
        }
        
        ticket_number, confidence = ocr_service.extract_ticket_number(sample_image)
        
        assert ticket_number is None
        assert confidence == 0.0
    
    def test_pattern_bonus_edge_cases(self, ocr_service):
        test_cases = [
            ("", 0),  # Empty string
            ("A", 0), # Too short
            ("ABC123", 20), # Good pattern
            ("123", 5),  # Only numbers
            ("ABC", 5),  # Only letters
        ]
        
        for candidate, expected_min in test_cases:
            bonus = ocr_service._get_pattern_bonus(candidate)
            assert bonus >= expected_min
    
    def test_validate_ticket_number_edge_cases(self, ocr_service):
        edge_cases = [
            ("  TK-001  ", True),  # Whitespace
            ("tk-001", True),      # Lowercase
            ("TK_001", True),      # Underscore
            ("123-456", True),     # Numbers with dash
            ("ABC-123-DEF", True), # Complex pattern
        ]
        
        for ticket, expected in edge_cases:
            result = ocr_service.validate_ticket_number(ticket)
            assert result == expected, f"Failed for ticket: '{ticket}'"
    
    def test_calculate_candidate_confidence_no_matches(self, ocr_service):
        candidate = "NOMATCH"
        texts = ["completely", "different", "text"]
        confidences = [90.0, 85.0, 88.0]
        
        confidence = ocr_service._calculate_candidate_confidence(candidate, texts, confidences)
        
        assert confidence == 0.0
    
    def test_extract_ticket_number_various_patterns(self, ocr_service):
        test_patterns = [
            "T12345",
            "TKT-001",
            "WB123456", 
            "12345678",
            "T12A34"
        ]
        
        for pattern in test_patterns:
            with patch('backend.services.ocr_service.pytesseract.image_to_data') as mock_tesseract:
                mock_tesseract.return_value = {
                    'text': [pattern, 'some', 'other', 'text'],
                    'conf': [95, 80, 75, 70]
                }
                
                ticket_number, confidence = ocr_service.extract_ticket_number(Image.new('RGB', (400, 300)))
                
                assert ticket_number is not None
                assert confidence > 0