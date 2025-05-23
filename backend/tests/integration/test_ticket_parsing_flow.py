import pytest
import tempfile
import os
from pathlib import Path
from datetime import date, datetime
from uuid import uuid4
import xlwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database import get_db, Base
from backend.models.user import User, UserRole
from backend.models.batch import ProcessingBatch, BatchStatus
from backend.models.ticket import Ticket, TicketErrorLog
from backend.services.xls_parser_service import XLSParserService
from backend.services.ticket_mapper import TicketMapper
from backend.services.ticket_validator import TicketValidator
from backend.services.ticket_service import TicketService
from backend.utils.excel_utils import ExcelUtils


class TestTicketParsingIntegration:
    
    @pytest.fixture(scope="function")
    def db_engine(self):
        # Use in-memory SQLite for testing
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(bind=engine)
        return engine
    
    @pytest.fixture(scope="function")
    def db_session(self, db_engine):
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    @pytest.fixture(scope="function")
    def client(self, db_session):
        def override_get_db():
            try:
                yield db_session
            finally:
                pass
        
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as test_client:
            yield test_client
        app.dependency_overrides.clear()
    
    @pytest.fixture
    def test_user(self, db_session):
        user = User(
            username="testuser",
            email="test@example.com",
            hashed_password="$2b$12$hashedpassword",
            role=UserRole.PROCESSOR,
            is_active=True
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user
    
    @pytest.fixture
    def test_batch(self, db_session, test_user):
        batch = ProcessingBatch(
            filename="test_tickets.xls",
            original_filename="test_tickets.xls",
            file_size=1024,
            file_hash="test_hash",
            status=BatchStatus.UPLOADED,
            user_id=test_user.id,
            upload_date=date.today(),
            stats={}
        )
        db_session.add(batch)
        db_session.commit()
        db_session.refresh(batch)
        return batch
    
    @pytest.fixture
    def sample_xls_file(self):
        # Create a temporary XLS file with test data
        with tempfile.NamedTemporaryFile(suffix='.xls', delete=False) as tmp:
            workbook = xlwt.Workbook()
            sheet = workbook.add_sheet('Tickets')
            
            # Headers
            headers = ['Ticket Number', 'Reference', 'Gross Weight', 'Tare Weight', 'Net Weight', 'Status', 'Date']
            for col, header in enumerate(headers):
                sheet.write(0, col, header)
            
            # Test data
            test_data = [
                ['T001', 'REF001', 10.5, 2.0, 8.5, 'COMPLETE', '2024-01-15'],
                ['T002', 'REF002', 15.0, 3.0, 12.0, 'PENDING', '2024-01-16'],
                ['T003', 'REF003', 0.0, 0.0, 0.0, 'VOID', '2024-01-17'],
                ['T004', 'REF004', 20.0, 4.0, 16.0, 'COMPLETE', '2024-01-18'],
                ['', '', '', '', '', '', ''],  # Empty row (should be skipped)
                ['T005', 'REF005', 5.5, 1.0, 4.5, 'PENDING', '2024-01-19'],
            ]
            
            for row, data in enumerate(test_data, start=1):
                for col, value in enumerate(data):
                    sheet.write(row, col, value)
            
            workbook.save(tmp.name)
            yield tmp.name
        
        # Cleanup
        os.unlink(tmp.name)
    
    @pytest.fixture
    def invalid_xls_file(self):
        # Create XLS file with validation errors
        with tempfile.NamedTemporaryFile(suffix='.xls', delete=False) as tmp:
            workbook = xlwt.Workbook()
            sheet = workbook.add_sheet('Tickets')
            
            # Headers
            headers = ['Ticket Number', 'Reference', 'Gross Weight', 'Tare Weight', 'Net Weight', 'Status', 'Date']
            for col, header in enumerate(headers):
                sheet.write(0, col, header)
            
            # Test data with validation errors
            test_data = [
                ['T001', 'REF001', 10.5, 2.0, 8.5, 'COMPLETE', '2024-01-15'],  # Valid
                ['', 'REF002', 15.0, 3.0, 12.0, 'PENDING', '2024-01-16'],      # Missing ticket number
                ['T003', 'REF003', 150.0, 4.0, 146.0, 'COMPLETE', '2024-01-17'], # Weight > 100 tonnes
                ['T004', 'REF004', 0.0, 0.0, 5.0, 'VOID', '2024-01-18'],       # VOID with non-zero weight
                ['T005', 'REF005', 10.0, 2.0, 8.0, 'COMPLETE', '2023-01-01'],  # Date out of range
            ]
            
            for row, data in enumerate(test_data, start=1):
                for col, value in enumerate(data):
                    sheet.write(row, col, value)
            
            workbook.save(tmp.name)
            yield tmp.name
        
        # Cleanup
        os.unlink(tmp.name)

    def test_complete_parsing_flow_success(self, db_session, test_batch, sample_xls_file):
        # Initialize services
        excel_utils = ExcelUtils()
        parser_service = XLSParserService()
        mapper = TicketMapper()
        validator = TicketValidator()
        audit_service = None  # Mock for testing
        ticket_service = TicketService(db=db_session, audit_service=audit_service)
        
        upload_date = test_batch.upload_date
        
        # Step 1: Parse XLS file
        tickets_dto, parse_errors = parser_service.parse_xls_file(sample_xls_file)
        
        assert len(tickets_dto) == 5  # 5 valid ticket rows (excluding empty row)
        assert len(parse_errors) == 0  # No parsing errors expected
        
        # Step 2: Map DTOs to TicketCreate objects
        ticket_creates = []
        for dto in tickets_dto:
            ticket_create = mapper.map_dto_to_ticket(dto, test_batch.id, upload_date)
            ticket_creates.append(ticket_create)
        
        assert len(ticket_creates) == 5
        
        # Step 3: Validate tickets
        validated_tickets = []
        validation_errors = []
        
        for ticket_create in ticket_creates:
            error = validator.validate_ticket(ticket_create, upload_date)
            if error:
                validation_errors.append(error)
            else:
                validated_tickets.append(ticket_create)
        
        assert len(validated_tickets) == 5  # All should be valid
        assert len(validation_errors) == 0
        
        # Step 4: Check for duplicates within batch
        ticket_numbers = [t.ticket_number for t in validated_tickets]
        existing_duplicates = ticket_service.check_duplicate_tickets_in_batch(
            test_batch.id, ticket_numbers
        )
        
        assert len(existing_duplicates) == 0  # No existing duplicates
        
        # Step 5: Create tickets in database
        created_tickets = ticket_service.create_tickets_batch(validated_tickets)
        
        assert len(created_tickets) == 5
        assert all(isinstance(t, Ticket) for t in created_tickets)
        
        # Step 6: Verify tickets in database
        db_tickets = ticket_service.get_tickets_by_batch_id(test_batch.id)
        assert len(db_tickets) == 5
        
        # Verify specific ticket data
        ticket_t001 = next((t for t in db_tickets if t.ticket_number == "T001"), None)
        assert ticket_t001 is not None
        assert ticket_t001.reference == "REF001"
        assert ticket_t001.gross_weight == 10.5
        assert ticket_t001.net_weight == 8.5
        assert ticket_t001.status == "COMPLETE"
        
        # Verify VOID ticket
        ticket_t003 = next((t for t in db_tickets if t.ticket_number == "T003"), None)
        assert ticket_t003 is not None
        assert ticket_t003.status == "VOID"
        assert ticket_t003.net_weight == 0.0

    def test_complete_parsing_flow_with_errors(self, db_session, test_batch, invalid_xls_file):
        # Initialize services
        parser_service = XLSParserService()
        mapper = TicketMapper()
        validator = TicketValidator()
        audit_service = None
        ticket_service = TicketService(db=db_session, audit_service=audit_service)
        
        upload_date = test_batch.upload_date
        
        # Step 1: Parse XLS file
        tickets_dto, parse_errors = parser_service.parse_xls_file(invalid_xls_file)
        
        assert len(tickets_dto) == 5  # All rows parsed as DTOs
        
        # Step 2: Map and validate tickets
        validated_tickets = []
        all_errors = []
        
        for dto in tickets_dto:
            try:
                ticket_create = mapper.map_dto_to_ticket(dto, test_batch.id, upload_date)
                error = validator.validate_ticket(ticket_create, upload_date)
                
                if error:
                    all_errors.append(TicketErrorLog(
                        batch_id=test_batch.id,
                        row_number=1,  # Simplified for test
                        ticket_number=ticket_create.ticket_number or "UNKNOWN",
                        error_type="validation_error",
                        error_message=error,
                        raw_data={}
                    ))
                else:
                    validated_tickets.append(ticket_create)
                    
            except Exception as e:
                all_errors.append(TicketErrorLog(
                    batch_id=test_batch.id,
                    row_number=1,
                    ticket_number="UNKNOWN",
                    error_type="mapping_error",
                    error_message=str(e),
                    raw_data={}
                ))
        
        # Should have some valid tickets and some errors
        assert len(validated_tickets) > 0
        assert len(all_errors) > 0
        
        # Step 3: Process results
        parsing_result = ticket_service.process_parsing_results(
            test_batch.id, validated_tickets, all_errors
        )
        
        assert parsing_result.tickets_valid > 0
        assert parsing_result.tickets_invalid > 0
        assert parsing_result.tickets_parsed == parsing_result.tickets_valid + parsing_result.tickets_invalid
        
        # Step 4: Verify database state
        db_tickets = ticket_service.get_tickets_by_batch_id(test_batch.id)
        error_logs = ticket_service.get_error_logs_by_batch(test_batch.id)
        
        assert len(db_tickets) == parsing_result.tickets_valid
        assert len(error_logs) == parsing_result.tickets_invalid

    def test_duplicate_detection_within_batch(self, db_session, test_batch):
        # Create some existing tickets
        existing_tickets = [
            Ticket(
                ticket_number="T001",
                reference="REF001",
                gross_weight=10.5,
                tare_weight=2.0,
                net_weight=8.5,
                status="COMPLETE",
                date=date.today(),
                batch_id=test_batch.id
            ),
            Ticket(
                ticket_number="T002",
                reference="REF002",
                gross_weight=15.0,
                tare_weight=3.0,
                net_weight=12.0,
                status="PENDING",
                date=date.today(),
                batch_id=test_batch.id
            )
        ]
        
        db_session.add_all(existing_tickets)
        db_session.commit()
        
        # Test duplicate detection
        audit_service = None
        ticket_service = TicketService(db=db_session, audit_service=audit_service)
        
        test_ticket_numbers = ["T001", "T003", "T002", "T004"]
        duplicates = ticket_service.check_duplicate_tickets_in_batch(
            test_batch.id, test_ticket_numbers
        )
        
        assert "T001" in duplicates
        assert "T002" in duplicates
        assert "T003" not in duplicates
        assert "T004" not in duplicates

    def test_batch_statistics_calculation(self, db_session, test_batch):
        # Create test tickets with various statuses
        test_tickets = [
            Ticket(
                ticket_number="T001",
                reference="REF001",
                gross_weight=10.0,
                tare_weight=2.0,
                net_weight=8.0,
                status="COMPLETE",
                date=date.today(),
                batch_id=test_batch.id
            ),
            Ticket(
                ticket_number="T002",
                reference="REF002",
                gross_weight=15.0,
                tare_weight=3.0,
                net_weight=12.0,
                status="COMPLETE",
                date=date.today(),
                batch_id=test_batch.id
            ),
            Ticket(
                ticket_number="T003",
                reference="REF003",
                gross_weight=20.0,
                tare_weight=4.0,
                net_weight=16.0,
                status="PENDING",
                date=date.today(),
                batch_id=test_batch.id
            ),
            Ticket(
                ticket_number="T004",
                reference="REF004",
                gross_weight=10.0,
                tare_weight=2.0,
                net_weight=0.0,
                status="VOID",
                date=date.today(),
                batch_id=test_batch.id
            )
        ]
        
        db_session.add_all(test_tickets)
        db_session.commit()
        
        # Calculate statistics
        audit_service = None
        ticket_service = TicketService(db=db_session, audit_service=audit_service)
        stats = ticket_service.get_batch_statistics(test_batch.id)
        
        expected_stats = {
            "total_tickets": 4,
            "total_weight": 36.0,  # 8.0 + 12.0 + 16.0 + 0.0
            "status_breakdown": {
                "COMPLETE": {"count": 2, "weight": 20.0},
                "PENDING": {"count": 1, "weight": 16.0},
                "VOID": {"count": 1, "weight": 0.0}
            }
        }
        
        assert stats == expected_stats

    def test_weight_calculation_and_validation(self, db_session, test_batch):
        mapper = TicketMapper()
        validator = TicketValidator()
        
        # Test case 1: Missing net weight (should be calculated)
        from backend.models.ticket import TicketDTO
        dto_missing_net = TicketDTO(
            ticket_number="T001",
            reference="REF001",
            gross_weight=10.0,
            tare_weight=2.0,
            net_weight=None,  # Missing
            status="COMPLETE",
            date=date.today()
        )
        
        ticket = mapper.map_dto_to_ticket(dto_missing_net, test_batch.id, date.today())
        assert ticket.net_weight == 8.0  # Should be calculated as 10.0 - 2.0
        
        error = validator.validate_ticket(ticket, date.today())
        assert error is None  # Should be valid
        
        # Test case 2: Weight consistency check within tolerance
        dto_consistent = TicketDTO(
            ticket_number="T002",
            reference="REF002",
            gross_weight=10.0,
            tare_weight=2.0,
            net_weight=8.01,  # Slightly different but within tolerance
            status="COMPLETE",
            date=date.today()
        )
        
        ticket = mapper.map_dto_to_ticket(dto_consistent, test_batch.id, date.today())
        error = validator.validate_ticket(ticket, date.today())
        assert error is None  # Should be valid (within tolerance)
        
        # Test case 3: Weight out of tolerance
        dto_inconsistent = TicketDTO(
            ticket_number="T003",
            reference="REF003",
            gross_weight=10.0,
            tare_weight=2.0,
            net_weight=7.0,  # Too different (should be 8.0)
            status="COMPLETE",
            date=date.today()
        )
        
        ticket = mapper.map_dto_to_ticket(dto_inconsistent, test_batch.id, date.today())
        error = validator.validate_ticket(ticket, date.today())
        assert error is not None  # Should be invalid
        assert "weight calculation" in error.lower()

    def test_void_ticket_validation(self, db_session, test_batch):
        mapper = TicketMapper()
        validator = TicketValidator()
        
        # Test case 1: Valid VOID ticket (net weight = 0)
        from backend.models.ticket import TicketDTO
        dto_void_valid = TicketDTO(
            ticket_number="T001",
            reference="REF001",
            gross_weight=10.0,
            tare_weight=2.0,
            net_weight=0.0,
            status="VOID",
            date=date.today()
        )
        
        ticket = mapper.map_dto_to_ticket(dto_void_valid, test_batch.id, date.today())
        error = validator.validate_ticket(ticket, date.today())
        assert error is None  # Should be valid
        
        # Test case 2: Invalid VOID ticket (net weight != 0)
        dto_void_invalid = TicketDTO(
            ticket_number="T002",
            reference="REF002",
            gross_weight=10.0,
            tare_weight=2.0,
            net_weight=5.0,  # Should be 0 for VOID
            status="VOID",
            date=date.today()
        )
        
        ticket = mapper.map_dto_to_ticket(dto_void_invalid, test_batch.id, date.today())
        error = validator.validate_ticket(ticket, date.today())
        assert error is not None  # Should be invalid
        assert "VOID" in error and "net_weight" in error

    def test_date_validation_range(self, db_session, test_batch):
        mapper = TicketMapper()
        validator = TicketValidator()
        upload_date = date(2024, 1, 15)
        
        # Test case 1: Date within range
        from backend.models.ticket import TicketDTO
        dto_valid_date = TicketDTO(
            ticket_number="T001",
            reference="REF001",
            gross_weight=10.0,
            tare_weight=2.0,
            net_weight=8.0,
            status="COMPLETE",
            date=date(2024, 1, 10)  # 5 days before upload
        )
        
        ticket = mapper.map_dto_to_ticket(dto_valid_date, test_batch.id, upload_date)
        error = validator.validate_ticket(ticket, upload_date)
        assert error is None  # Should be valid
        
        # Test case 2: Date out of range (too early)
        dto_early_date = TicketDTO(
            ticket_number="T002",
            reference="REF002",
            gross_weight=10.0,
            tare_weight=2.0,
            net_weight=8.0,
            status="COMPLETE",
            date=date(2023, 12, 1)  # More than 30 days before
        )
        
        ticket = mapper.map_dto_to_ticket(dto_early_date, test_batch.id, upload_date)
        # Mapper should have corrected the date to upload_date
        assert ticket.date == upload_date
        
        error = validator.validate_ticket(ticket, upload_date)
        assert error is None  # Should be valid after date correction