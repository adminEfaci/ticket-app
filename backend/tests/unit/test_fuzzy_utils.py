import pytest
from datetime import date, datetime, timedelta
from backend.utils.fuzzy_utils import FuzzyMatchUtils


class TestFuzzyMatchUtils:
    """Test suite for fuzzy matching utilities"""
    
    def test_levenshtein_distance_identical_strings(self):
        """Test Levenshtein distance for identical strings"""
        distance = FuzzyMatchUtils.levenshtein_distance("hello", "hello")
        assert distance == 0
    
    def test_levenshtein_distance_empty_strings(self):
        """Test Levenshtein distance with empty strings"""
        assert FuzzyMatchUtils.levenshtein_distance("", "") == 0
        assert FuzzyMatchUtils.levenshtein_distance("hello", "") == 5
        assert FuzzyMatchUtils.levenshtein_distance("", "world") == 5
    
    def test_levenshtein_distance_different_strings(self):
        """Test Levenshtein distance for different strings"""
        # Single character difference
        assert FuzzyMatchUtils.levenshtein_distance("cat", "bat") == 1
        # Multiple differences
        assert FuzzyMatchUtils.levenshtein_distance("kitten", "sitting") == 3
        # Complete difference
        assert FuzzyMatchUtils.levenshtein_distance("abc", "xyz") == 3
    
    def test_similarity_ratio_identical(self):
        """Test similarity ratio for identical strings"""
        ratio = FuzzyMatchUtils.similarity_ratio("hello", "hello")
        assert ratio == 1.0
    
    def test_similarity_ratio_empty_strings(self):
        """Test similarity ratio with empty strings"""
        assert FuzzyMatchUtils.similarity_ratio("", "") == 1.0
        assert FuzzyMatchUtils.similarity_ratio("hello", "") == 0.0
        assert FuzzyMatchUtils.similarity_ratio("", "world") == 0.0
    
    def test_similarity_ratio_case_insensitive(self):
        """Test that similarity ratio is case insensitive"""
        ratio = FuzzyMatchUtils.similarity_ratio("Hello", "hello")
        assert ratio == 1.0
        
        ratio = FuzzyMatchUtils.similarity_ratio("ABC123", "abc123")
        assert ratio == 1.0
    
    def test_normalize_ticket_number(self):
        """Test ticket number normalization"""
        # Basic normalization
        assert FuzzyMatchUtils.normalize_ticket_number("  ABC123  ") == "ABC123"
        assert FuzzyMatchUtils.normalize_ticket_number("abc-123") == "ABC123"
        assert FuzzyMatchUtils.normalize_ticket_number("A_B_C/123") == "ABC123"
        
        # Empty/None handling
        assert FuzzyMatchUtils.normalize_ticket_number("") == ""
        assert FuzzyMatchUtils.normalize_ticket_number(None) == ""
        
        # Multiple spaces and separators
        assert FuzzyMatchUtils.normalize_ticket_number("A B C - 1 2 3") == "ABC123"
    
    def test_fuzzy_ticket_match_exact(self):
        """Test fuzzy ticket matching for exact matches"""
        is_match, similarity = FuzzyMatchUtils.fuzzy_ticket_match("ABC123", "ABC123")
        assert is_match is True
        assert similarity == 1.0
        
        # Case insensitive exact match
        is_match, similarity = FuzzyMatchUtils.fuzzy_ticket_match("abc123", "ABC123")
        assert is_match is True
        assert similarity == 1.0
    
    def test_fuzzy_ticket_match_with_separators(self):
        """Test fuzzy ticket matching ignoring separators"""
        is_match, similarity = FuzzyMatchUtils.fuzzy_ticket_match("ABC-123", "ABC123")
        assert is_match is True
        assert similarity == 1.0
        
        is_match, similarity = FuzzyMatchUtils.fuzzy_ticket_match("A_B_C/123", "ABC123")
        assert is_match is True
        assert similarity == 1.0
    
    def test_fuzzy_ticket_match_ocr_errors(self):
        """Test fuzzy ticket matching with common OCR errors"""
        # O/0 confusion
        is_match, similarity = FuzzyMatchUtils.fuzzy_ticket_match("ABC12O", "ABC120")
        assert is_match is True
        assert similarity >= 0.8
        
        # I/1/L confusion
        is_match, similarity = FuzzyMatchUtils.fuzzy_ticket_match("ABC1I3", "ABC123")
        assert is_match is True
        assert similarity >= 0.8
        
        # B/8 confusion
        is_match, similarity = FuzzyMatchUtils.fuzzy_ticket_match("AB8123", "ABB123")
        assert is_match is True
        assert similarity >= 0.8
    
    def test_fuzzy_ticket_match_threshold(self):
        """Test fuzzy ticket matching with different thresholds"""
        # Test with default threshold (0.8)
        is_match, similarity = FuzzyMatchUtils.fuzzy_ticket_match("ABC123", "XYZ789")
        assert is_match is False
        assert similarity < 0.8
        
        # Test with lower threshold
        is_match, similarity = FuzzyMatchUtils.fuzzy_ticket_match("ABC123", "ABC789", threshold=0.5)
        assert similarity >= 0.5
    
    def test_fuzzy_ticket_match_empty_strings(self):
        """Test fuzzy ticket matching with empty strings"""
        is_match, similarity = FuzzyMatchUtils.fuzzy_ticket_match("", "")
        assert is_match is False
        assert similarity == 0.0
        
        is_match, similarity = FuzzyMatchUtils.fuzzy_ticket_match("ABC123", "")
        assert is_match is False
        assert similarity == 0.0
    
    def test_normalize_reference(self):
        """Test reference normalization"""
        # Basic normalization
        assert FuzzyMatchUtils.normalize_reference("Customer Ref 123") == "CUSTOMER REF 123"
        assert FuzzyMatchUtils.normalize_reference("  ref.123,test  ") == "REF123TEST"
        
        # Punctuation removal
        assert FuzzyMatchUtils.normalize_reference("REF:123;TEST!") == "REF123TEST"
        
        # Empty handling
        assert FuzzyMatchUtils.normalize_reference("") == ""
        assert FuzzyMatchUtils.normalize_reference(None) == ""
    
    def test_fuzzy_reference_match_exact(self):
        """Test fuzzy reference matching for exact matches"""
        is_match, similarity = FuzzyMatchUtils.fuzzy_reference_match("Customer 123", "Customer 123")
        assert is_match is True
        assert similarity == 1.0
    
    def test_fuzzy_reference_match_partial(self):
        """Test fuzzy reference matching for partial matches"""
        # Containment should give high score
        is_match, similarity = FuzzyMatchUtils.fuzzy_reference_match("Customer 123", "Customer 123 Extra")
        assert is_match is True
        assert similarity == 0.9
        
        is_match, similarity = FuzzyMatchUtils.fuzzy_reference_match("Short Ref", "This is a Short Ref with more text")
        assert is_match is True
        assert similarity == 0.9
    
    def test_fuzzy_reference_match_threshold(self):
        """Test fuzzy reference matching with threshold"""
        # Test with default threshold (0.7)
        is_match, similarity = FuzzyMatchUtils.fuzzy_reference_match("Customer A", "Customer B")
        # This should have moderate similarity but may not reach threshold
        
        # Test with lower threshold
        is_match, similarity = FuzzyMatchUtils.fuzzy_reference_match("Customer A", "Customer B", threshold=0.5)
        assert similarity >= 0.5
    
    def test_weight_within_tolerance_exact(self):
        """Test weight tolerance for exact matches"""
        is_within, similarity = FuzzyMatchUtils.weight_within_tolerance(10.0, 10.0)
        assert is_within is True
        assert similarity == 1.0
    
    def test_weight_within_tolerance_close(self):
        """Test weight tolerance for close values"""
        # Within tolerance (0.5)
        is_within, similarity = FuzzyMatchUtils.weight_within_tolerance(10.0, 10.3)
        assert is_within is True
        assert similarity >= 0.5
        
        # At boundary
        is_within, similarity = FuzzyMatchUtils.weight_within_tolerance(10.0, 10.5)
        assert is_within is True
        assert similarity >= 0.5
    
    def test_weight_within_tolerance_outside(self):
        """Test weight tolerance for values outside tolerance"""
        is_within, similarity = FuzzyMatchUtils.weight_within_tolerance(10.0, 11.0)
        assert is_within is False
        assert 0.0 <= similarity < 0.5
    
    def test_weight_within_tolerance_none_values(self):
        """Test weight tolerance with None values"""
        is_within, similarity = FuzzyMatchUtils.weight_within_tolerance(None, 10.0)
        assert is_within is False
        assert similarity == 0.0
        
        is_within, similarity = FuzzyMatchUtils.weight_within_tolerance(10.0, None)
        assert is_within is False
        assert similarity == 0.0
    
    def test_weight_within_tolerance_custom(self):
        """Test weight tolerance with custom tolerance"""
        is_within, similarity = FuzzyMatchUtils.weight_within_tolerance(10.0, 12.0, tolerance=2.5)
        assert is_within is True
        assert similarity >= 0.5
    
    def test_date_within_tolerance_same_day(self):
        """Test date tolerance for same day"""
        test_date = date(2023, 1, 15)
        is_within, similarity = FuzzyMatchUtils.date_within_tolerance(test_date, test_date)
        assert is_within is True
        assert similarity == 1.0
    
    def test_date_within_tolerance_one_day(self):
        """Test date tolerance for one day difference"""
        date1 = date(2023, 1, 15)
        date2 = date(2023, 1, 16)
        
        is_within, similarity = FuzzyMatchUtils.date_within_tolerance(date1, date2)
        assert is_within is True
        assert similarity >= 0.8
    
    def test_date_within_tolerance_outside(self):
        """Test date tolerance for dates outside tolerance"""
        date1 = date(2023, 1, 15)
        date2 = date(2023, 1, 18)  # 3 days difference
        
        is_within, similarity = FuzzyMatchUtils.date_within_tolerance(date1, date2)
        assert is_within is False
        assert 0.0 <= similarity < 0.8
    
    def test_date_within_tolerance_datetime_objects(self):
        """Test date tolerance with datetime objects"""
        dt1 = datetime(2023, 1, 15, 10, 30)
        dt2 = datetime(2023, 1, 15, 16, 45)  # Same day, different time
        
        is_within, similarity = FuzzyMatchUtils.date_within_tolerance(dt1, dt2)
        assert is_within is True
        assert similarity == 1.0
    
    def test_date_within_tolerance_none_values(self):
        """Test date tolerance with None values"""
        test_date = date(2023, 1, 15)
        
        is_within, similarity = FuzzyMatchUtils.date_within_tolerance(None, test_date)
        assert is_within is False
        assert similarity == 0.0
        
        is_within, similarity = FuzzyMatchUtils.date_within_tolerance(test_date, None)
        assert is_within is False
        assert similarity == 0.0
    
    def test_date_within_tolerance_custom(self):
        """Test date tolerance with custom tolerance"""
        date1 = date(2023, 1, 15)
        date2 = date(2023, 1, 18)  # 3 days difference
        
        is_within, similarity = FuzzyMatchUtils.date_within_tolerance(date1, date2, tolerance_days=3)
        assert is_within is True
        assert similarity >= 0.8
    
    def test_ocr_error_adjustment_perfect_match_after_correction(self):
        """Test OCR error adjustment finds perfect match after correction"""
        # This tests the internal _adjust_for_ocr_errors method indirectly
        is_match, similarity = FuzzyMatchUtils.fuzzy_ticket_match("ABC1O3", "ABC103")  # O -> 0
        assert similarity >= 0.9  # Should be very high after OCR correction
        
        is_match, similarity = FuzzyMatchUtils.fuzzy_ticket_match("A8C123", "ABC123")  # 8 -> B
        assert similarity >= 0.9
    
    def test_multiple_ocr_errors(self):
        """Test handling of multiple OCR errors in the same string"""
        is_match, similarity = FuzzyMatchUtils.fuzzy_ticket_match("A8C1O3", "ABC103")
        assert similarity >= 0.8  # Should handle multiple OCR errors
    
    def test_edge_cases(self):
        """Test various edge cases"""
        # Very similar strings
        is_match, similarity = FuzzyMatchUtils.fuzzy_ticket_match("ABC123", "ABC124")
        assert 0.7 <= similarity <= 0.95
        
        # Completely different strings
        is_match, similarity = FuzzyMatchUtils.fuzzy_ticket_match("ABC123", "XYZ789")
        assert similarity < 0.5
        
        # Single character strings
        is_match, similarity = FuzzyMatchUtils.fuzzy_ticket_match("A", "A")
        assert similarity == 1.0
        
        is_match, similarity = FuzzyMatchUtils.fuzzy_ticket_match("A", "B")
        assert similarity < 0.8