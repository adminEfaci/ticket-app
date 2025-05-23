import pytest
from datetime import date, datetime
from uuid import uuid4, UUID

from backend.services.ticket_mapper import TicketMapper
from backend.models.ticket import TicketDTO, TicketCreate


class TestTicketMapper:
    
    @pytest.fixture
    def mapper(self):
        return TicketMapper()
    
    @pytest.fixture
    def batch_id(self):
        return uuid4()
    
    @pytest.fixture
    def upload_date(self):
        return date(2024, 1, 15)
    
    @pytest.fixture
    def valid_dto(self):
        return TicketDTO(
            ticket_number="T001",
            reference="REF001",
            gross_weight=10.5,
            tare_weight=2.0,
            net_weight=8.5,
            status="COMPLETE",
            entry_date=date(2024, 1, 15)
        )

    def test_map_dto_to_ticket_valid(self, mapper, valid_dto, batch_id, upload_date):
        ticket = mapper.map_dto_to_ticket(valid_dto, batch_id, upload_date)
        
        assert isinstance(ticket, TicketCreate)
        assert ticket.ticket_number == "T001"
        assert ticket.reference == ""  # REF001 doesn't match structured patterns
        assert ticket.note == "REF001"  # So it goes to note field
        assert ticket.gross_weight == 10.5
        assert ticket.tare_weight == 2.0
        assert ticket.net_weight == 8.5
        assert ticket.status == "ORIGINAL"  # COMPLETE is mapped to ORIGINAL
        assert ticket.entry_date == date(2024, 1, 15)
        assert ticket.batch_id == batch_id

    def test_clean_ticket_number_standard(self, mapper):
        test_cases = [
            ("T001", "T001"),
            ("  T001  ", "T001"),
            ("t001", "T001"),
            ("TICKET-001", "TICKET-001"),
            ("T-001-ABC", "T-001-ABC"),
            ("", None),  # Empty string returns None
            (None, None)  # None returns None
        ]
        
        for input_val, expected in test_cases:
            result = mapper._clean_ticket_number(input_val)
            assert result == expected, f"Input: {input_val}, Expected: {expected}, Got: {result}"

    def test_clean_ticket_number_with_prefixes(self, mapper):
        test_cases = [
            ("TKT001", "TKT001"),
            ("TICKET_001", "TICKET_001"),
            ("WB001", "WB001"),  # Weighbridge ticket
            ("SCL-001", "SCL-001"),  # Scale ticket
        ]
        
        for input_val, expected in test_cases:
            result = mapper._clean_ticket_number(input_val)
            assert result == expected

    def test_clean_reference_standard(self, mapper):
        # _clean_reference now uses _parse_reference_and_note internally
        test_cases = [
            ("REF001", None),  # Not a structured code, goes to note
            ("  REF001  ", None),  # Not a structured code
            ("ref001", None),  # Not a structured code
            ("#007", "007"),  # Structured code, # stripped
            ("MM1001", "MM1001"),  # Structured code
            ("T-202", "T-202"),  # Structured code
            ("", None),
            (None, None),
            ("123456", None)  # Not a structured code
        ]
        
        for input_val, expected in test_cases:
            result = mapper._clean_reference(input_val)
            assert result == expected

    def test_clean_reference_with_special_chars(self, mapper):
        # These don't match structured patterns, so return None
        test_cases = [
            ("REF/001", None),
            ("REF-001", None),
            ("REF_001", None),
            ("REF.001", None),
            ("REF#001", None),
        ]
        
        for input_val, expected in test_cases:
            result = mapper._clean_reference(input_val)
            assert result == expected

    def test_normalize_status_valid(self, mapper):
        test_cases = [
            ("COMPLETE", "ORIGINAL"),  # COMPLETE maps to ORIGINAL
            ("complete", "ORIGINAL"),
            ("Complete", "ORIGINAL"),
            ("ORIGINAL", "ORIGINAL"),
            ("ACTIVE", "ORIGINAL"),
            ("VOID", "VOID"),
            ("void", "VOID"),
            ("CANCELLED", "VOID"),  # CANCELLED maps to VOID
            ("cancelled", "VOID"),
            ("REPRINT", "REPRINT"),
            ("DUPLICATE", "REPRINT"),
        ]
        
        for input_val, expected in test_cases:
            result = mapper._normalize_status(input_val)
            assert result == expected

    def test_normalize_status_variations(self, mapper):
        # Our mapper only recognizes specific statuses
        test_cases = [
            ("COMPLETED", "ORIGINAL"),  # Maps to ORIGINAL
            ("DONE", None),  # Not recognized
            ("FINISHED", None),  # Not recognized
            ("IN_PROGRESS", None),  # Not recognized
            ("PROCESSING", None),  # Not recognized
            ("WAITING", None),  # Not recognized
            ("CANCELED", "VOID"),  # Maps to VOID
            ("INVALID", "VOID"),  # Maps to VOID
            ("REJECTED", None),  # Not recognized
        ]
        
        for input_val, expected in test_cases:
            result = mapper._normalize_status(input_val)
            assert result == expected

    def test_normalize_status_unknown(self, mapper):
        unknown_statuses = ["UNKNOWN", "WEIRD_STATUS", "", None]
        
        for status in unknown_statuses:
            result = mapper._normalize_status(status)
            assert result is None  # Unknown statuses return None

    def test_parse_weight_valid(self, mapper):
        test_cases = [
            (10.0, 10.0),
            (15.5, 15.5),
            ("5.0", 5.0),
            ("100", 100.0),
            (0.0, 0.0),
            (200.0, 200.0),  # Max valid weight
        ]
        
        for input_val, expected in test_cases:
            result = mapper._parse_weight(input_val)
            assert abs(result - expected) < 0.001  # Float precision

    def test_parse_weight_edge_cases(self, mapper):
        # None and empty values
        assert mapper._parse_weight(None) is None
        assert mapper._parse_weight("") is None
        
        # Out of range values
        assert mapper._parse_weight(-1.0) is None  # Negative weight
        assert mapper._parse_weight(201.0) is None  # Over 200 tonnes
        assert mapper._parse_weight(200.1) is None  # Just over limit
        
        # Invalid string values
        assert mapper._parse_weight("invalid") is None
        assert mapper._parse_weight("abc123") is None

    def test_parse_entry_date_valid(self, mapper, upload_date):
        valid_dates = [
            date(2024, 1, 15),  # Same as upload date
            date(2024, 1, 1),   # Within 30 days before
            date(2024, 2, 14),  # Within 30 days after
        ]
        
        for test_date in valid_dates:
            result = mapper._parse_entry_date(test_date, upload_date)
            assert result == test_date

    def test_parse_entry_date_out_of_range(self, mapper, upload_date):
        invalid_dates = [
            date(2023, 12, 1),  # More than 30 days before
            date(2024, 3, 1),   # More than 30 days after
            date(2023, 1, 1),   # Way in the past
            date(2025, 1, 1),   # Way in the future
        ]
        
        for test_date in invalid_dates:
            result = mapper._parse_entry_date(test_date, upload_date)
            assert result is None  # Should return None for out of range dates

    def test_parse_entry_date_none(self, mapper, upload_date):
        result = mapper._parse_entry_date(None, upload_date)
        assert result is None

    def test_map_dto_with_missing_net_weight(self, mapper, batch_id, upload_date):
        dto = TicketDTO(
            ticket_number="T001",
            reference="REF001",
            gross_weight=10.5,
            tare_weight=2.0,
            net_weight=None,  # Missing net weight
            status="COMPLETE",
            entry_date=date(2024, 1, 15)
        )
        
        # Should raise error for missing net weight
        with pytest.raises(ValueError, match="Net weight is required"):
            mapper.map_dto_to_ticket(dto, batch_id, upload_date)

    def test_map_dto_with_inconsistent_weights(self, mapper, batch_id, upload_date):
        dto = TicketDTO(
            ticket_number="T001",
            reference="REF001",
            gross_weight=10.0,
            tare_weight=2.0,
            net_weight=9.0,  # Inconsistent: should be 8.0
            status="COMPLETE",
            entry_date=date(2024, 1, 15)
        )
        
        ticket = mapper.map_dto_to_ticket(dto, batch_id, upload_date)
        
        # Should use provided net weight, not calculated
        assert ticket.net_weight == 9.0
        assert ticket.gross_weight == 10.0
        assert ticket.tare_weight == 2.0

    def test_map_dto_void_ticket(self, mapper, batch_id, upload_date):
        dto = TicketDTO(
            ticket_number="T001",
            reference="REF001",
            gross_weight=10.0,
            tare_weight=2.0,
            net_weight=0.0,  # VOID tickets should have 0 net weight
            status="VOID",
            entry_date=date(2024, 1, 15)
        )
        
        ticket = mapper.map_dto_to_ticket(dto, batch_id, upload_date)
        
        assert ticket.status == "VOID"
        assert ticket.net_weight == 0.0
        assert ticket.gross_weight == 10.0
        assert ticket.tare_weight == 2.0
        assert ticket.is_billable is False  # VOID tickets are not billable

    def test_map_dto_with_minimal_data(self, mapper, batch_id, upload_date):
        dto = TicketDTO(
            ticket_number="T001",
            reference="",
            gross_weight=None,
            tare_weight=None,
            net_weight=5.0,
            status="ORIGINAL",  # Must provide valid status
            entry_date=upload_date  # Must provide valid date
        )
        
        ticket = mapper.map_dto_to_ticket(dto, batch_id, upload_date)
        
        assert ticket.ticket_number == "T001"
        assert ticket.reference == ""
        assert ticket.gross_weight is None
        assert ticket.tare_weight is None
        assert ticket.net_weight == 5.0
        assert ticket.status == "ORIGINAL"
        assert ticket.entry_date == upload_date
        assert ticket.batch_id == batch_id

    def test_map_dto_with_numeric_strings(self, mapper, batch_id, upload_date):
        # Test handling of numeric values that might come as strings from Excel
        dto = TicketDTO(
            ticket_number="12345",  # Numeric ticket number
            reference="67890",      # Numeric reference
            gross_weight=10.5,
            tare_weight=2.0,
            net_weight=8.5,
            status="COMPLETE",
            entry_date=date(2024, 1, 15)
        )
        
        ticket = mapper.map_dto_to_ticket(dto, batch_id, upload_date)
        
        assert ticket.ticket_number == "12345"
        assert ticket.reference == ""  # Numeric reference goes to note
        assert ticket.note == "67890"

    def test_map_dto_with_whitespace_trimming(self, mapper, batch_id, upload_date):
        dto = TicketDTO(
            ticket_number="  T001  ",
            reference="  REF001  ",
            gross_weight=10.5,
            tare_weight=2.0,
            net_weight=8.5,
            status="  COMPLETE  ",
            entry_date=date(2024, 1, 15)
        )
        
        ticket = mapper.map_dto_to_ticket(dto, batch_id, upload_date)
        
        assert ticket.ticket_number == "T001"
        assert ticket.note == "REF001"  # REF001 goes to note, not reference
        assert ticket.status == "ORIGINAL"  # COMPLETE is mapped to ORIGINAL

    def test_parse_entry_date_boundary_cases(self, mapper):
        upload_date = date(2024, 1, 15)
        
        # Exactly 30 days before and after
        exactly_30_before = date(2023, 12, 16)
        exactly_30_after = date(2024, 2, 14)
        
        # These should be valid (exactly at the boundary)
        assert mapper._parse_entry_date(exactly_30_before, upload_date) == exactly_30_before
        assert mapper._parse_entry_date(exactly_30_after, upload_date) == exactly_30_after
        
        # One day beyond the boundary should be invalid
        one_day_too_early = date(2023, 12, 15)
        one_day_too_late = date(2024, 2, 15)
        
        assert mapper._parse_entry_date(one_day_too_early, upload_date) is None
        assert mapper._parse_entry_date(one_day_too_late, upload_date) is None

    def test_map_batch_tickets(self, mapper, batch_id, upload_date):
        dtos = [
            TicketDTO(
                ticket_number="T001",
                reference="REF001",
                gross_weight=10.5,
                tare_weight=2.0,
                net_weight=8.5,
                status="COMPLETE",
                entry_date=date(2024, 1, 15)
            ),
            TicketDTO(
                ticket_number="T002",
                reference="REF002",
                gross_weight=15.0,
                tare_weight=3.0,
                net_weight=12.0,
                status="ORIGINAL",  # Use valid status
                entry_date=date(2024, 1, 16)
            ),
        ]
        
        tickets = [mapper.map_dto_to_ticket(dto, batch_id, upload_date) for dto in dtos]
        
        assert len(tickets) == 2
        assert all(isinstance(t, TicketCreate) for t in tickets)
        assert all(t.batch_id == batch_id for t in tickets)
        assert tickets[0].ticket_number == "T001"
        assert tickets[1].ticket_number == "T002"
    def test_parse_reference_and_note(self, mapper):
        """Test the new reference parsing logic"""
        test_cases = [
            ("#007 SAND EX SEVEN HILLS", "007", "SAND EX SEVEN HILLS"),
            ("MM1001 GRAVEL FROM QUARRY", "MM1001", "GRAVEL FROM QUARRY"),
            ("T-202", "T-202", None),
            ("T-123 TOPPS DELIVERY", "T-123", "TOPPS DELIVERY"),
            ("RANDOM TEXT", None, "RANDOM TEXT"),
            ("", None, None),
            (None, None, None),
        ]
        
        for input_val, expected_ref, expected_note in test_cases:
            ref, note = mapper._parse_reference_and_note(input_val)
            assert ref == expected_ref, f"Input: {input_val}, Expected ref: {expected_ref}, Got: {ref}"
            assert note == expected_note, f"Input: {input_val}, Expected note: {expected_note}, Got: {note}"
