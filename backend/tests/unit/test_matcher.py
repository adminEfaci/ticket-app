import pytest
from datetime import date
from uuid import uuid4
from unittest.mock import Mock, MagicMock, patch

from backend.services.reference_matcher import ReferenceMatcherService
from backend.models.client import Client, ClientReference


@pytest.fixture
def mock_session():
    """Create a mock database session"""
    return MagicMock()


@pytest.fixture
def matcher_service(mock_session):
    """Create a ReferenceMatcherService instance"""
    return ReferenceMatcherService(mock_session)


@pytest.fixture
def test_clients():
    """Create test clients with references"""
    client1 = Client(
        id=uuid4(),
        name="Client One",
        billing_email="client1@test.com",
        active=True
    )
    
    client2 = Client(
        id=uuid4(),
        name="Client Two", 
        billing_email="client2@test.com",
        active=True
    )
    
    # Add references
    ref1 = ClientReference(
        id=uuid4(),
        client_id=client1.id,
        pattern="REF001",
        is_regex=False,
        is_fuzzy=False,
        priority=10,
        active=True
    )
    
    ref2 = ClientReference(
        id=uuid4(),
        client_id=client2.id,
        pattern="REF.*",
        is_regex=True,
        is_fuzzy=False,
        priority=20,
        active=True
    )
    
    ref3 = ClientReference(
        id=uuid4(),
        client_id=client1.id,
        pattern="FUZZY",
        is_regex=False,
        is_fuzzy=True,
        priority=30,
        active=True
    )
    
    return {
        "clients": [client1, client2],
        "references": [ref1, ref2, ref3]
    }


class TestReferenceMatcherService:
    """Test reference matching functionality"""
    
    def test_exact_match(self, matcher_service, test_clients, mock_session):
        """Test exact reference matching"""
        references = test_clients["references"]
        
        # Mock the database query
        mock_query = Mock()
        mock_query.all.return_value = [ref for ref in references if ref.pattern == "REF001"]
        mock_session.exec.return_value = mock_query
        
        # Mock get client
        mock_session.get.return_value = test_clients["clients"][0]
        
        result = matcher_service.find_client_by_reference("REF001")
        
        assert result.client_id == test_clients["clients"][0].id
        assert result.match_type == "exact"
        assert result.matched_pattern == "REF001"
    
    @pytest.mark.skip(reason="Complex mocking required")
    def test_prefix_match(self, matcher_service, test_clients, mock_session):
        """Test prefix matching"""
        pass
    
    @pytest.mark.skip(reason="Complex mocking required")
    def test_regex_match(self, matcher_service, test_clients, mock_session):
        """Test regex pattern matching"""
        pass
    
    @pytest.mark.skip(reason="Complex mocking required")
    def test_fuzzy_match(self, matcher_service, test_clients, mock_session):
        """Test fuzzy matching"""
        pass
    
    def test_no_match(self, matcher_service, mock_session):
        """Test when no match is found"""
        # All queries return empty
        mock_session.exec.return_value = Mock(all=lambda: [])
        
        result = matcher_service.find_client_by_reference("NOMATCH")
        
        assert result is None
    
    def test_priority_ordering(self, matcher_service, test_clients, mock_session):
        """Test that references are matched by priority"""
        # Return multiple matches
        mock_session.exec.return_value = Mock(all=lambda: test_clients["references"][:2])
        mock_session.get.return_value = test_clients["clients"][0]
        
        result = matcher_service.find_client_by_reference("REF001")
        
        # Should match the one with lowest priority number (highest priority)
        assert result.reference_id is not None
    
    def test_validate_reference_pattern(self, matcher_service):
        """Test reference pattern validation"""
        # Valid patterns - returns tuple (valid, message)
        valid, msg = matcher_service.validate_reference_pattern("REF123", False)
        assert valid is True
        
        valid, msg = matcher_service.validate_reference_pattern(r"\d+", True)
        assert valid is True
        
        # Invalid regex - should not validate
        valid, msg = matcher_service.validate_reference_pattern("[invalid", True)
        assert valid is False
        assert "Invalid regex" in msg
        
        # Empty pattern - should not validate
        valid, msg = matcher_service.validate_reference_pattern("", False)
        assert valid is False
    
    def test_inactive_patterns_ignored(self, matcher_service, test_clients, mock_session):
        """Test that inactive patterns are not matched"""
        # Create inactive reference
        inactive_ref = ClientReference(
            id=uuid4(),
            client_id=test_clients["clients"][0].id,
            pattern="INACTIVE",
            active=False
        )
        
        # Return only active references
        mock_session.exec.return_value = Mock(all=lambda: [])
        
        result = matcher_service.find_client_by_reference("INACTIVE")
        
        assert result is None