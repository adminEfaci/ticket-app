import pytest
from datetime import date, datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock, MagicMock, AsyncMock, patch

from backend.models.client import Client, ClientRate, ClientRateCreate
from backend.services.rate_service import RateService


@pytest.fixture
def mock_session():
    """Create a mock database session"""
    session = MagicMock()
    return session


@pytest.fixture
def rate_service(mock_session):
    """Create a RateService instance with mocked session"""
    return RateService(mock_session)


@pytest.fixture
def test_client():
    """Create a test client"""
    client = Client(
        id=uuid4(),
        name="Test Client",
        billing_email="test@client.com",
        active=True
    )
    return client


class TestRateService:
    """Test rate service functionality"""
    
    @pytest.mark.asyncio
    async def test_create_rate(self, rate_service, test_client, mock_session):
        """Test creating a new rate"""
        rate_data = ClientRateCreate(
            client_id=test_client.id,
            rate_per_tonne=25.50,
            effective_from=date.today()
        )
        
        # Mock the _get_client method
        with patch.object(rate_service, '_get_client', new_callable=AsyncMock, return_value=test_client):
            # Mock the database operations
            mock_session.add = Mock()
            mock_session.commit = Mock()
            mock_session.refresh = Mock()
            
            # Call the service method
            await rate_service.create_rate(
                rate_data=rate_data,
                approved_by=uuid4() if rate_data else None
            )
            
            # Verify
            assert mock_session.add.called
            assert mock_session.commit.called
    
    @pytest.mark.asyncio
    async def test_create_rate_with_auto_approval(self, rate_service, test_client, mock_session):
        """Test creating a rate with auto-approval"""
        admin_id = uuid4()
        rate_data = ClientRateCreate(
            client_id=test_client.id,
            rate_per_tonne=30.00,
            effective_from=date.today()
        )
        
        with patch.object(rate_service, '_get_client', new_callable=AsyncMock, return_value=test_client):
            mock_session.add = Mock()
            mock_session.commit = Mock()
            mock_session.refresh = Mock()
            
            await rate_service.create_rate(
                rate_data=rate_data,
                approved_by=admin_id,
                auto_approve=True
            )
            
            assert mock_session.add.called
    
    @pytest.mark.asyncio
    async def test_get_effective_rate(self, rate_service, test_client, mock_session):
        """Test getting effective rate for a client"""
        # Create mock rates
        ClientRate(
            id=uuid4(),
            client_id=test_client.id,
            rate_per_tonne=25.00,
            effective_from=date.today() - timedelta(days=30),
            approved_by=uuid4(),
            approved_at=datetime.now()
        )
        
        rate2 = ClientRate(
            id=uuid4(),
            client_id=test_client.id,
            rate_per_tonne=30.00,
            effective_from=date.today() - timedelta(days=10),
            approved_by=uuid4(),
            approved_at=datetime.now()
        )
        
        # Mock the query
        mock_query = Mock()
        mock_query.first.return_value = rate2
        mock_session.exec.return_value = mock_query
        
        result = await rate_service.get_effective_rate(test_client.id)
        
        assert result.id == rate2.id
        assert result.rate_per_tonne == 30.00
    
    @pytest.mark.asyncio
    async def test_approve_rate(self, rate_service, mock_session):
        """Test rate approval"""
        rate_id = uuid4()
        admin_id = uuid4()
        
        # Create mock rate
        mock_rate = ClientRate(
            id=rate_id,
            client_id=uuid4(),
            rate_per_tonne=35.00,
            effective_from=date.today(),
            approved_by=None,
            approved_at=None
        )
        
        # Mock the get method
        mock_session.get.return_value = mock_rate
        mock_session.commit = Mock()
        mock_session.refresh = Mock()
        
        # Mock audit service
        with patch('backend.services.rate_service.AuditService') as mock_audit:
            mock_audit_instance = Mock()
            mock_audit.return_value = mock_audit_instance
            mock_audit_instance.log_event = AsyncMock()
            
            result = await rate_service.approve_rate(rate_id, admin_id)
            
            assert result.approved_by == admin_id
            assert result.approved_at is not None
            assert mock_session.commit.called
    
    @pytest.mark.asyncio
    async def test_validate_rate_range(self, rate_service):
        """Test rate validation"""
        # Valid rate
        assert await rate_service.validate_rate_range(25.00) is True
        assert await rate_service.validate_rate_range(10.00) is True
        assert await rate_service.validate_rate_range(100.00) is True
        
        # Invalid rates
        assert await rate_service.validate_rate_range(5.00) is False
        assert await rate_service.validate_rate_range(150.00) is False
        assert await rate_service.validate_rate_range(-10.00) is False
    
    @pytest.mark.asyncio
    async def test_get_pending_rates(self, rate_service, mock_session):
        """Test getting pending rates"""
        # Create mock pending rates
        pending_rate = ClientRate(
            id=uuid4(),
            client_id=uuid4(),
            rate_per_tonne=40.00,
            effective_from=date.today(),
            approved_by=None
        )
        
        # Mock the query
        mock_query = Mock()
        mock_query.all.return_value = [pending_rate]
        mock_session.exec.return_value = mock_query
        
        result = await rate_service.get_pending_rates()
        
        assert len(result) == 1
        assert result[0].approved_by is None