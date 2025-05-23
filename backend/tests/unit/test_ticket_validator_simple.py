import pytest
from datetime import date, timedelta
from uuid import uuid4

from backend.services.ticket_validator import TicketValidator
from backend.models.ticket import TicketCreate


class TestTicketValidatorSimple:
    
    @pytest.fixture
    def validator(self):
        return TicketValidator()
    
    @pytest.fixture
    def valid_ticket(self):
        return TicketCreate(
            batch_id=uuid4(),
            ticket_number="T12345",
            reference="REF001",
            status="ORIGINAL",
            gross_weight=10.0,
            tare_weight=2.0,
            net_weight=8.0,
            entry_date=date.today()
        )
    
    def test_validate_valid_ticket(self, validator, valid_ticket):
        """Test validation of a completely valid ticket"""
        upload_date = date.today()
        error = validator.validate_ticket(valid_ticket, upload_date)
        
        assert error is None

    def test_validate_missing_ticket_number(self, validator, valid_ticket):
        """Test validation fails for missing ticket number"""
        valid_ticket.ticket_number = ""
        upload_date = date.today()
        
        error = validator.validate_ticket(valid_ticket, upload_date)
        
        assert error is not None
        assert "ticket number" in error.lower()

    def test_validate_missing_reference(self, validator, valid_ticket):
        """Test validation with missing reference - should be valid since reference is optional"""
        valid_ticket.reference = ""
        upload_date = date.today()
        
        error = validator.validate_ticket(valid_ticket, upload_date)
        
        # Reference is optional, so this should be valid
        assert error is None

    def test_validate_net_weight_too_low(self, validator, valid_ticket):
        """Test validation fails for net weight below minimum"""
        valid_ticket.net_weight = 0.005  # Below 0.01 minimum
        upload_date = date.today()
        
        error = validator.validate_ticket(valid_ticket, upload_date)
        
        assert error is not None
        assert "net weight" in error.lower()

    def test_validate_net_weight_too_high(self, validator, valid_ticket):
        """Test validation fails for net weight above maximum"""
        valid_ticket.net_weight = 150.0  # Above 100.0 maximum
        upload_date = date.today()
        
        error = validator.validate_ticket(valid_ticket, upload_date)
        
        assert error is not None
        assert "net weight" in error.lower()

    def test_validate_date_too_old(self, validator, valid_ticket):
        """Test validation fails for date too far in the past"""
        valid_ticket.entry_date = date.today() - timedelta(days=50)  # More than 30 days ago
        upload_date = date.today()
        
        error = validator.validate_ticket(valid_ticket, upload_date)
        
        assert error is not None
        assert "date" in error.lower()

    def test_validate_date_too_future(self, validator, valid_ticket):
        """Test validation fails for date too far in the future"""
        valid_ticket.entry_date = date.today() + timedelta(days=50)  # More than 30 days ahead
        upload_date = date.today()
        
        error = validator.validate_ticket(valid_ticket, upload_date)
        
        assert error is not None
        assert "date" in error.lower()

    def test_validate_void_ticket_with_weight(self, validator, valid_ticket):
        """Test validation fails for VOID ticket with non-zero weight"""
        valid_ticket.status = "VOID"
        valid_ticket.net_weight = 5.0  # Should be 0 for VOID
        upload_date = date.today()
        
        error = validator.validate_ticket(valid_ticket, upload_date)
        
        assert error is not None
        assert "VOID" in error and "net_weight" in error

    def test_validate_valid_void_ticket(self, validator, valid_ticket):
        """Test validation passes for valid VOID ticket"""
        valid_ticket.status = "VOID"
        valid_ticket.net_weight = 0.0  # Correct for VOID
        upload_date = date.today()
        
        error = validator.validate_ticket(valid_ticket, upload_date)
        
        assert error is None

    def test_validate_weight_calculation_within_tolerance(self, validator, valid_ticket):
        """Test validation passes when weight calculation is within tolerance"""
        valid_ticket.gross_weight = 10.0
        valid_ticket.tare_weight = 2.0
        valid_ticket.net_weight = 8.01  # Slightly off but within tolerance
        upload_date = date.today()
        
        error = validator.validate_ticket(valid_ticket, upload_date)
        
        assert error is None

    def test_validate_weight_calculation_outside_tolerance(self, validator, valid_ticket):
        """Test validation fails when weight calculation is outside tolerance"""
        valid_ticket.gross_weight = 10.0
        valid_ticket.tare_weight = 2.0
        valid_ticket.net_weight = 7.0  # Too far off (should be 8.0)
        upload_date = date.today()
        
        error = validator.validate_ticket(valid_ticket, upload_date)
        
        assert error is not None
        assert "does not match" in error.lower() or "weight calculation" in error.lower()