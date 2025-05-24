import pytest
from datetime import date
from uuid import uuid4
from unittest.mock import Mock, AsyncMock

from backend.services.weekly_export_service import WeeklyExportService
from backend.models.ticket import Ticket
from backend.models.client import Client
from backend.models.export import ExportRequest, ExportValidation


class TestWeeklyExportService:
    
    @pytest.fixture
    def mock_db(self):
        return Mock()
    
    @pytest.fixture
    def service(self, mock_db):
        return WeeklyExportService(mock_db)
    
    @pytest.fixture
    def sample_ticket(self):
        return Ticket(
            id=uuid4(),
            batch_id=uuid4(),
            ticket_number="T4121",
            reference="#007",
            note="Test note",
            status="REPRINT",
            is_billable=True,
            net_weight=8.5,
            entry_date=date(2024, 4, 15),  # Monday
            client_id=uuid4(),
            image_path="tickets/T4121.png",
            image_extracted=True
        )
    
    @pytest.fixture
    def sample_client(self):
        return Client(
            id=uuid4(),
            name="Client 007",
            code="007",
            is_active=True
        )
    
    def test_get_week_range_monday(self, service):
        """Test week range calculation for Monday"""
        test_date = date(2024, 4, 15)  # Monday
        start, end = service.get_week_range(test_date)
        
        assert start == date(2024, 4, 15)  # Monday
        assert end == date(2024, 4, 20)    # Saturday
        assert start.weekday() == 0  # Monday
        assert end.weekday() == 5    # Saturday
    
    def test_get_week_range_wednesday(self, service):
        """Test week range calculation for mid-week"""
        test_date = date(2024, 4, 17)  # Wednesday
        start, end = service.get_week_range(test_date)
        
        assert start == date(2024, 4, 15)  # Monday
        assert end == date(2024, 4, 20)    # Saturday
    
    def test_get_week_range_sunday(self, service):
        """Test week range calculation for Sunday"""
        test_date = date(2024, 4, 21)  # Sunday
        start, end = service.get_week_range(test_date)
        
        # Sunday belongs to the previous week in our system
        assert start == date(2024, 4, 15)  # Monday
        assert end == date(2024, 4, 20)    # Saturday
    
    def test_validate_export_data_success(self, service, sample_ticket):
        """Test successful validation"""
        tickets = [sample_ticket]
        
        validation = service.validate_export_data(tickets, require_images=True)
        
        assert validation.is_valid is True
        assert validation.total_tickets == 1
        assert validation.matched_images == 1
        assert validation.missing_images == 0
        assert validation.match_percentage == 100.0
        assert len(validation.validation_errors) == 0
    
    def test_validate_export_data_missing_image(self, service, sample_ticket):
        """Test validation with missing image"""
        sample_ticket.image_path = None
        sample_ticket.image_extracted = False
        tickets = [sample_ticket]
        
        validation = service.validate_export_data(tickets, require_images=True)
        
        assert validation.is_valid is False
        assert validation.matched_images == 0
        assert validation.missing_images == 1
        assert validation.match_percentage == 0.0
        assert "missing image" in validation.validation_errors[0]
    
    def test_validate_export_data_duplicate_tickets(self, service, sample_ticket):
        """Test validation with duplicate ticket numbers"""
        ticket1 = sample_ticket
        ticket2 = Ticket(
            id=uuid4(),
            batch_id=sample_ticket.batch_id,
            ticket_number="T4121",  # Duplicate
            reference="#007",
            status="REPRINT",
            is_billable=True,
            net_weight=5.0,
            entry_date=date(2024, 4, 15),
            client_id=sample_ticket.client_id,
            image_path="tickets/T4121_2.png",
            image_extracted=True
        )
        
        tickets = [ticket1, ticket2]
        validation = service.validate_export_data(tickets, require_images=True)
        
        assert validation.is_valid is False
        assert "T4121" in validation.duplicate_tickets
        assert "duplicate ticket numbers" in validation.validation_errors[0]
    
    def test_validate_export_data_missing_entry_date(self, service, sample_ticket):
        """Test validation with missing entry date"""
        sample_ticket.entry_date = None
        tickets = [sample_ticket]
        
        validation = service.validate_export_data(tickets, require_images=True)
        
        assert validation.is_valid is False
        assert "missing entry_date" in validation.validation_errors[0]
    
    def test_validate_export_data_missing_client(self, service, sample_ticket):
        """Test validation with unassigned client"""
        sample_ticket.client_id = None
        tickets = [sample_ticket]
        
        validation = service.validate_export_data(tickets, require_images=True)
        
        assert validation.is_valid is False
        assert "not assigned to client" in validation.validation_errors[0]
    
    def test_validate_export_data_invalid_weight(self, service, sample_ticket):
        """Test validation with invalid weight"""
        sample_ticket.net_weight = 0
        tickets = [sample_ticket]
        
        validation = service.validate_export_data(tickets, require_images=True)
        
        assert validation.is_valid is False
        assert "invalid weight" in validation.validation_errors[0]
    
    def test_group_tickets_by_week(self, service, sample_ticket, sample_client, mock_db):
        """Test grouping tickets by week/client/reference"""
        # Setup mocks
        mock_db.get.return_value = sample_client
        
        mock_rate = Mock()
        mock_rate.rate_per_tonne = 25.0
        service.rate_service.get_rate_for_ticket = Mock(return_value=mock_rate)
        
        tickets = [sample_ticket]
        
        # Group tickets
        week_groups = service.group_tickets_by_week(tickets)
        
        # Verify structure
        assert len(week_groups) == 1
        week_key = "2024-04-15"
        assert week_key in week_groups
        
        week_group = week_groups[week_key]
        assert week_group.week_start == date(2024, 4, 15)
        assert week_group.week_end == date(2024, 4, 20)
        assert week_group.total_tickets == 1
        assert week_group.total_tonnage == 8.5
        assert week_group.total_amount == 212.50  # 8.5 * 25
        
        # Check client group
        assert len(week_group.client_groups) == 1
        client_group = list(week_group.client_groups.values())[0]
        assert client_group.client_name == "Client 007"
        assert client_group.rate_per_tonne == 25.0
        assert client_group.total_tickets == 1
        assert client_group.total_tonnage == 8.5
        assert client_group.total_amount == 212.50
        
        # Check reference group
        assert len(client_group.reference_groups) == 1
        assert "#007" in client_group.reference_groups
        ref_group = client_group.reference_groups["#007"]
        assert ref_group.ticket_count == 1
        assert ref_group.total_tonnage == 8.5
        assert ref_group.subtotal == 212.50
        
        # Check ticket data
        assert len(ref_group.tickets) == 1
        ticket_data = ref_group.tickets[0]
        assert ticket_data["ticket_number"] == "T4121"
        assert ticket_data["net_weight"] == 8.5
        assert ticket_data["rate"] == 25.0
        assert ticket_data["amount"] == 212.50
    
    def test_group_tickets_multiple_weeks(self, service, sample_client, mock_db):
        """Test grouping tickets across multiple weeks"""
        mock_db.get.return_value = sample_client
        
        mock_rate = Mock()
        mock_rate.rate_per_tonne = 25.0
        service.rate_service.get_rate_for_ticket = Mock(return_value=mock_rate)
        
        # Create tickets in different weeks
        ticket1 = Ticket(
            id=uuid4(),
            batch_id=uuid4(),
            ticket_number="T4121",
            reference="#007",
            status="REPRINT",
            is_billable=True,
            net_weight=8.5,
            entry_date=date(2024, 4, 15),  # Week 1
            client_id=sample_client.id,
            image_path="tickets/T4121.png",
            image_extracted=True
        )
        
        ticket2 = Ticket(
            id=uuid4(),
            batch_id=uuid4(),
            ticket_number="T4122",
            reference="#007",
            status="REPRINT",
            is_billable=True,
            net_weight=10.0,
            entry_date=date(2024, 4, 22),  # Week 2
            client_id=sample_client.id,
            image_path="tickets/T4122.png",
            image_extracted=True
        )
        
        tickets = [ticket1, ticket2]
        week_groups = service.group_tickets_by_week(tickets)
        
        # Should have 2 weeks
        assert len(week_groups) == 2
        assert "2024-04-15" in week_groups
        assert "2024-04-22" in week_groups
        
        # Check week 1
        week1 = week_groups["2024-04-15"]
        assert week1.total_tickets == 1
        assert week1.total_tonnage == 8.5
        
        # Check week 2
        week2 = week_groups["2024-04-22"]
        assert week2.total_tickets == 1
        assert week2.total_tonnage == 10.0
    
    def test_group_tickets_multiple_references(self, service, sample_client, mock_db):
        """Test grouping tickets with different references"""
        mock_db.get.return_value = sample_client
        
        mock_rate = Mock()
        mock_rate.rate_per_tonne = 25.0
        service.rate_service.get_rate_for_ticket = Mock(return_value=mock_rate)
        
        # Create tickets with different references
        ticket1 = Ticket(
            id=uuid4(),
            batch_id=uuid4(),
            ticket_number="T4121",
            reference="#007",
            status="REPRINT",
            is_billable=True,
            net_weight=8.5,
            entry_date=date(2024, 4, 15),
            client_id=sample_client.id,
            image_path="tickets/T4121.png",
            image_extracted=True
        )
        
        ticket2 = Ticket(
            id=uuid4(),
            batch_id=uuid4(),
            ticket_number="T4122",
            reference="MM1001",
            status="REPRINT",
            is_billable=True,
            net_weight=10.0,
            entry_date=date(2024, 4, 15),
            client_id=sample_client.id,
            image_path="tickets/T4122.png",
            image_extracted=True
        )
        
        tickets = [ticket1, ticket2]
        week_groups = service.group_tickets_by_week(tickets)
        
        # Should have 1 week
        assert len(week_groups) == 1
        week_group = week_groups["2024-04-15"]
        
        # Should have 1 client with 2 references
        assert len(week_group.client_groups) == 1
        client_group = list(week_group.client_groups.values())[0]
        assert len(client_group.reference_groups) == 2
        assert "#007" in client_group.reference_groups
        assert "MM1001" in client_group.reference_groups
        
        # Check totals
        assert client_group.total_tickets == 2
        assert client_group.total_tonnage == 18.5
        assert client_group.total_amount == 462.50  # 18.5 * 25
    
    def test_group_tickets_no_reference(self, service, sample_ticket, sample_client, mock_db):
        """Test grouping tickets without reference"""
        mock_db.get.return_value = sample_client
        
        mock_rate = Mock()
        mock_rate.rate_per_tonne = 25.0
        service.rate_service.get_rate_for_ticket = Mock(return_value=mock_rate)
        
        sample_ticket.reference = None
        tickets = [sample_ticket]
        
        week_groups = service.group_tickets_by_week(tickets)
        
        # Should use "NO_REF" as reference
        client_group = list(week_groups["2024-04-15"].client_groups.values())[0]
        assert "NO_REF" in client_group.reference_groups
    
    def test_group_tickets_no_rate(self, service, sample_ticket, sample_client, mock_db):
        """Test grouping when no rate is found"""
        mock_db.get.return_value = sample_client
        service.rate_service.get_rate_for_ticket = Mock(return_value=None)
        
        tickets = [sample_ticket]
        week_groups = service.group_tickets_by_week(tickets)
        
        # Should skip ticket without rate
        assert len(week_groups) == 0
    
    @pytest.mark.asyncio
    async def test_log_export_operation(self, service, mock_db):
        """Test logging export operation"""
        service.audit_service.log_event = AsyncMock()
        
        user_id = uuid4()
        export_request = ExportRequest(
            start_date=date(2024, 4, 15),
            export_type="weekly",
            include_images=True,
            force_export=False
        )
        
        validation = ExportValidation(
            is_valid=True,
            total_tickets=10,
            matched_images=10,
            missing_images=0,
            match_percentage=100.0
        )
        
        week_groups = {
            "2024-04-15": Mock(
                total_tickets=10,
                total_tonnage=85.0,
                total_amount=2125.0,
                client_groups={"client1": Mock()}
            )
        }
        
        await service.log_export_operation(
            user_id=user_id,
            export_request=export_request,
            validation=validation,
            week_groups=week_groups,
            success=True
        )
        
        # Verify audit log was called
        assert service.audit_service.log_event.called
        call_args = service.audit_service.log_event.call_args
        assert call_args[1]["event_type"].value == "upload_success"
        assert call_args[1]["user_id"] == user_id
        
        # Check metadata in details
        details = eval(call_args[1]["details"])
        metadata = details["metadata"]
        assert metadata["export_type"] == "weekly"
        assert metadata["validation"]["total_tickets"] == 10
        assert metadata["validation"]["match_percentage"] == 100.0
        assert metadata["summary"]["total_amount"] == 2125.0