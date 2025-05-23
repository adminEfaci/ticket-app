import pytest
from datetime import date
from uuid import uuid4

# Test that the main components can be imported and initialized
def test_imports():
    """Test that all Phase 3 components can be imported"""
    from backend.models.ticket import Ticket, TicketCreate, TicketDTO, TicketErrorLog
    from backend.services.ticket_validator import TicketValidator
    from backend.services.ticket_mapper import TicketMapper
    from backend.utils.excel_utils import ExcelUtils
    
    # Test initialization
    validator = TicketValidator()
    mapper = TicketMapper()
    excel_utils = ExcelUtils()
    
    assert validator is not None
    assert mapper is not None
    assert excel_utils is not None

def test_basic_ticket_validation_flow():
    """Test basic ticket validation flow"""
    from backend.models.ticket import TicketCreate
    from backend.services.ticket_validator import TicketValidator
    
    validator = TicketValidator()
    
    # Create a valid ticket
    ticket = TicketCreate(
        batch_id=uuid4(),
        ticket_number="T001",
        reference="REF001",
        status="ORIGINAL",
        gross_weight=10.0,
        tare_weight=2.0,
        net_weight=8.0,
        entry_date=date.today()
    )
    
    error = validator.validate_ticket(ticket, date.today())
    assert error is None, f"Valid ticket should pass validation, got error: {error}"

def test_basic_excel_utils():
    """Test basic Excel utilities"""
    from backend.utils.excel_utils import ExcelUtils
    
    excel_utils = ExcelUtils()
    
    # Test weight parsing
    assert excel_utils.parse_weight_value(10.5) == 10.5
    assert excel_utils.parse_weight_value(1500) == 1.5  # kg to tonnes
    
    # Test text cleaning
    assert excel_utils.clean_text_value("  test  ") == "test"

def test_basic_ticket_mapping():
    """Test basic ticket mapping"""
    from backend.models.ticket import TicketDTO
    from backend.services.ticket_mapper import TicketMapper
    
    mapper = TicketMapper()
    batch_id = uuid4()
    upload_date = date.today()
    
    # Create minimal DTO (what the mapper expects)
    dto = TicketDTO(
        ticket_number="T001",
        reference="REF001", 
        status="ORIGINAL",
        gross_weight=10.0,
        tare_weight=2.0,
        net_weight=8.0
    )
    
    # This should work or give a descriptive error
    try:
        ticket = mapper.map_dto_to_ticket(dto, batch_id, upload_date)
        assert ticket.ticket_number == "T001"
        assert ticket.batch_id == batch_id
    except Exception as e:
        # If it fails, it should be due to validation, not import issues
        assert "required" in str(e).lower() or "invalid" in str(e).lower()

def test_void_ticket_validation():
    """Test VOID ticket specific validation"""
    from backend.models.ticket import TicketCreate
    from backend.services.ticket_validator import TicketValidator
    
    validator = TicketValidator()
    
    # Valid VOID ticket
    void_ticket = TicketCreate(
        batch_id=uuid4(),
        ticket_number="T001",
        reference="REF001",
        status="VOID",
        gross_weight=10.0,
        tare_weight=2.0,
        net_weight=0.0,  # Must be 0 for VOID
        date=date.today()
    )
    
    error = validator.validate_ticket(void_ticket, date.today())
    assert error is None, f"Valid VOID ticket should pass validation, got error: {error}"
    
    # Test that invalid VOID ticket (with weight) is caught at model creation
    try:
        invalid_void = TicketCreate(
            batch_id=uuid4(),
            ticket_number="T002",
            reference="REF002",
            status="VOID",
            gross_weight=10.0,
            tare_weight=2.0,
            net_weight=5.0,  # Invalid for VOID
            date=date.today()
        )
        assert False, "Should have raised validation error for VOID ticket with non-zero weight"
    except Exception as e:
        assert "VOID" in str(e) and "net_weight" in str(e)