import pytest
from datetime import date
from uuid import uuid4
from unittest.mock import Mock, MagicMock

from backend.models.ticket import Ticket, TicketCreate, TicketUpdate, TicketErrorLog
from backend.models.batch import ProcessingBatch
from backend.models.user import UserRole
from backend.services.ticket_service import TicketService


@pytest.fixture
def mock_session():
    """Create a mock database session"""
    return MagicMock()


@pytest.fixture
def ticket_service(mock_session):
    """Create a TicketService instance"""
    return TicketService(mock_session)


@pytest.fixture
def test_batch():
    """Create a test batch"""
    return ProcessingBatch(
        id=uuid4(),
        filename="test.xlsx",
        file_type="excel",
        status="pending",
        uploaded_by=uuid4()
    )


@pytest.fixture
def test_ticket():
    """Create a test ticket"""
    return Ticket(
        id=uuid4(),
        batch_id=uuid4(),
        ticket_number="T001",
        reference="REF001",
        status="COMPLETE",
        gross_weight=10.0,
        tare_weight=2.0,
        net_weight=8.0,
        entry_date=date.today()
    )


class TestTicketService:
    """Test ticket service functionality"""
    
    @pytest.mark.asyncio
    async def test_create_ticket_success(self, ticket_service, test_batch, mock_session):
        """Test successful ticket creation"""
        ticket_data = TicketCreate(
            batch_id=test_batch.id,
            ticket_number="T001",
            reference="REF001",
            status="COMPLETE",
            gross_weight=10.0,
            tare_weight=2.0,
            net_weight=8.0,
            entry_date=date.today()
        )
        
        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.refresh = Mock()
        
        ticket_service.create_ticket(ticket_data)
        
        assert mock_session.add.called
        assert mock_session.commit.called
    
    @pytest.mark.asyncio
    async def test_create_tickets_batch(self, ticket_service, test_batch, mock_session):
        """Test batch ticket creation"""
        tickets_data = [
            TicketCreate(
                batch_id=test_batch.id,
                ticket_number=f"T00{i}",
                reference=f"REF00{i}",
                status="COMPLETE",
                gross_weight=10.0,
                tare_weight=2.0,
                net_weight=8.0,
                entry_date=date.today()
            )
            for i in range(1, 4)
        ]
        
        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.refresh = Mock()
        
        result = ticket_service.create_tickets_batch(tickets_data)
        
        assert mock_session.add.call_count == 3
        assert mock_session.commit.called
        assert len(result) == 3
    
    @pytest.mark.asyncio
    async def test_get_ticket_by_id(self, ticket_service, test_ticket, mock_session):
        """Test getting ticket by ID"""
        mock_query = Mock()
        mock_query.first.return_value = test_ticket
        mock_session.exec.return_value = mock_query
        
        user_id = str(uuid4())
        user_role = UserRole.ADMIN
        result = ticket_service.get_ticket_by_id(test_ticket.id, user_id, user_role)
        
        assert result == test_ticket
        assert mock_session.exec.called
    
    @pytest.mark.asyncio
    async def test_get_tickets_by_batch(self, ticket_service, test_batch, mock_session):
        """Test getting tickets by batch ID"""
        tickets = [
            Ticket(
                id=uuid4(),
                batch_id=test_batch.id,
                ticket_number=f"T00{i}",
                reference=f"REF00{i}",
                status="COMPLETE",
                gross_weight=10.0,
                tare_weight=2.0,
                net_weight=8.0,
                entry_date=date.today()
            )
            for i in range(1, 4)
        ]
        
        mock_query = Mock()
        mock_query.all.return_value = tickets
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_session.exec.return_value = mock_query
        
        user_id = str(uuid4())
        user_role = UserRole.ADMIN
        result = ticket_service.get_tickets_by_batch(test_batch.id, user_id, user_role)
        
        assert len(result) == 3
        assert all(t.batch_id == test_batch.id for t in result)
    
    @pytest.mark.asyncio
    async def test_update_ticket(self, ticket_service, test_ticket, mock_session):
        """Test ticket update"""
        update_data = TicketUpdate(
            status="VOID",
            net_weight=0.0  # VOID tickets must have net_weight = 0
        )
        
        # Mock get_ticket_by_id to return the test ticket
        mock_query = Mock()
        mock_query.first.return_value = test_ticket
        mock_session.exec.return_value = mock_query
        mock_session.commit = Mock()
        mock_session.refresh = Mock()
        
        user_id = str(uuid4())
        user_role = UserRole.ADMIN
        ticket_service.update_ticket(test_ticket.id, update_data, user_id, user_role)
        
        assert mock_session.commit.called
        assert test_ticket.status == "VOID"
        assert test_ticket.net_weight == 0.0
    
    @pytest.mark.asyncio
    async def test_delete_ticket(self, ticket_service, test_ticket, mock_session):
        """Test ticket deletion (soft delete)"""
        # Mock get_ticket_by_id to return the test ticket
        mock_query = Mock()
        mock_query.first.return_value = test_ticket
        mock_session.exec.return_value = mock_query
        mock_session.commit = Mock()
        
        user_id = str(uuid4())
        user_role = UserRole.ADMIN
        result = ticket_service.delete_ticket(test_ticket.id, user_id, user_role)
        
        assert result is True
        assert test_ticket.is_billable is False
        assert mock_session.commit.called
    
    @pytest.mark.asyncio
    async def test_get_batch_ticket_stats(self, ticket_service, test_batch, mock_session):
        """Test batch statistics calculation"""
        # Mock the various database queries
        # Total tickets count
        mock_session.exec.side_effect = [
            Mock(first=Mock(return_value=4)),  # total_tickets
            Mock(first=Mock(return_value=3)),  # billable_tickets
            Mock(first=Mock(return_value=2)),  # ORIGINAL status count
            Mock(first=Mock(return_value=0)),  # REPRINT status count
            Mock(first=Mock(return_value=1)),  # VOID status count
            Mock(first=Mock(return_value=(24.0, 8.0, 8.0, 8.0)))  # weight stats
        ]
        
        stats = ticket_service.get_batch_ticket_stats(test_batch.id)
        
        assert stats["total_tickets"] == 4
        assert stats["valid_tickets"] == 4  # All tickets in DB are valid
        assert stats["invalid_tickets"] == 0  # Errors tracked separately
        assert stats["billable_tickets"] == 3
        assert stats["status_breakdown"]["original"] == 2
        assert stats["status_breakdown"]["void"] == 1
        assert stats["weight_stats"]["total_weight"] == 24.0
    
    
    
    @pytest.mark.asyncio
    async def test_save_parsing_errors(self, ticket_service, test_batch, mock_session):
        """Test saving parsing errors"""
        error_logs = [
            TicketErrorLog(
                batch_id=test_batch.id,
                ticket_number="T001",
                row_number=1,
                error_type="validation",
                error_message="Invalid weight"
            ),
            TicketErrorLog(
                batch_id=test_batch.id,
                ticket_number="T002",
                row_number=2,
                error_type="format",
                error_message="Invalid date format"
            )
        ]
        
        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.refresh = Mock()
        
        result = ticket_service.save_parsing_errors(test_batch.id, error_logs)
        
        assert mock_session.add.call_count == 2
        assert mock_session.commit.called
        assert len(result) == 2