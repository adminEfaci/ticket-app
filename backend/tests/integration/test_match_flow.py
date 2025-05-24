import pytest
from datetime import datetime, date
from uuid import uuid4
from unittest.mock import Mock, AsyncMock

from backend.services.match_service import MatchService
from backend.services.match_engine import TicketMatchEngine
from backend.models.match_result import MatchResult, MatchDecision


class TestMatchFlowIntegration:
    """Integration tests for the complete matching flow"""
    
    @pytest.fixture
    def mock_session(self):
        """Mock database session"""
        session = Mock()
        session.exec.return_value.all.return_value = []
        session.get.return_value = None
        session.commit.return_value = None
        session.rollback.return_value = None
        return session
    
    @pytest.fixture
    def match_service(self, mock_session):
        """Create MatchService with mocked dependencies"""
        return MatchService(mock_session)
    
    @pytest.fixture
    def sample_tickets(self):
        """Create sample ticket data"""
        tickets = []
        
        # Perfect match ticket
        ticket1 = Mock()
        ticket1.id = uuid4()
        ticket1.ticket_number = "ABC123"
        ticket1.entry_date = date(2023, 1, 15)
        ticket1.net_weight = 10.5
        ticket1.batch_id = uuid4()
        tickets.append(ticket1)
        
        # Fuzzy match ticket
        ticket2 = Mock()
        ticket2.id = uuid4()
        ticket2.ticket_number = "XYZ789"
        ticket2.entry_date = date(2023, 1, 16)
        ticket2.net_weight = 15.0
        ticket2.batch_id = uuid4()
        tickets.append(ticket2)
        
        # No match ticket
        ticket3 = Mock()
        ticket3.id = uuid4()
        ticket3.ticket_number = "NOMATCH"
        ticket3.entry_date = date(2023, 1, 17)
        ticket3.net_weight = 20.0
        ticket3.batch_id = uuid4()
        tickets.append(ticket3)
        
        return tickets
    
    @pytest.fixture
    def sample_images(self):
        """Create sample image data"""
        images = []
        
        # Perfect match image
        image1 = Mock()
        image1.id = uuid4()
        image1.ticket_number = "ABC123"
        image1.created_at = datetime(2023, 1, 15, 10, 30)
        image1.batch_id = uuid4()
        images.append(image1)
        
        # Fuzzy match image (OCR error)
        image2 = Mock()
        image2.id = uuid4()
        image2.ticket_number = "XYZ78O"  # O instead of 9
        image2.created_at = datetime(2023, 1, 16, 11, 30)
        image2.batch_id = uuid4()
        images.append(image2)
        
        return images
    
    async def test_complete_match_flow_success(self, match_service, sample_tickets, sample_images, mock_session):
        """Test complete successful matching flow"""
        batch_id = uuid4()
        user_id = uuid4()
        
        # Mock the database queries
        match_service._get_batch_tickets = AsyncMock(return_value=sample_tickets)
        match_service._get_batch_images = AsyncMock(return_value=sample_images)
        match_service._create_match_result = AsyncMock()
        match_service._link_ticket_to_image = AsyncMock()
        
        # Mock audit service
        match_service.audit_service.log_event = AsyncMock()
        
        # Create mock match results for the return
        mock_match_results = []
        for i, ticket in enumerate(sample_tickets[:2]):  # Only first 2 will have matches
            mock_result = Mock()
            mock_result.id = uuid4()
            mock_result.ticket_id = ticket.id
            mock_result.confidence = 90.0 if i == 0 else 75.0
            mock_match_results.append(mock_result)
        
        match_service._create_match_result.side_effect = mock_match_results
        
        # Execute the matching flow
        result = await match_service.run_batch_matching(
            batch_id=batch_id,
            user_id=user_id,
            force_rematch=False
        )
        
        # Verify the result structure
        assert result["success"] is True
        assert "statistics" in result
        assert "message" in result
        
        # Verify audit logging was called
        assert match_service.audit_service.log_event.call_count >= 2  # Start and completion
    
    def test_match_flow_with_no_tickets(self, match_service, sample_images, mock_session):
        """Test match flow when no tickets are found"""
        batch_id = uuid4()
        user_id = uuid4()
        
        # Mock empty ticket list
        match_service._get_batch_tickets = AsyncMock(return_value=[])
        match_service._get_batch_images = AsyncMock(return_value=sample_images)
        
        result = match_service.run_batch_matching(
            batch_id=batch_id,
            user_id=user_id,
            force_rematch=False
        )
        
        assert result["success"] is False
        assert "No tickets found" in result["message"]
    
    def test_match_flow_with_no_images(self, match_service, sample_tickets, mock_session):
        """Test match flow when no images are found"""
        batch_id = uuid4()
        user_id = uuid4()
        
        # Mock empty image list
        match_service._get_batch_tickets = AsyncMock(return_value=sample_tickets)
        match_service._get_batch_images = AsyncMock(return_value=[])
        
        result = match_service.run_batch_matching(
            batch_id=batch_id,
            user_id=user_id,
            force_rematch=False
        )
        
        assert result["success"] is False
        assert "No images found" in result["message"]
    
    def test_match_review_workflow(self, match_service, mock_session):
        """Test the complete manual review workflow"""
        match_id = uuid4()
        user_id = uuid4()
        
        # Create mock match result
        mock_match = Mock(spec=MatchResult)
        mock_match.id = match_id
        mock_match.ticket_id = uuid4()
        mock_match.image_id = uuid4()
        mock_match.confidence = 75.0
        mock_match.accepted = False
        mock_match.reviewed = False
        
        mock_session.get.return_value = mock_match
        match_service._link_ticket_to_image = AsyncMock()
        match_service.audit_service.log_event = AsyncMock()
        
        # Test accepting a match
        decision = MatchDecision(accepted=True, reason="Manual verification confirmed")
        
        match_service.accept_match(
            match_id=match_id,
            user_id=user_id,
            decision=decision
        )
        
        # Verify the match was accepted and linked
        assert mock_match.accepted is True
        assert mock_match.reviewed is True
        assert mock_match.reviewed_by == user_id
        assert mock_match.reason == "Manual verification confirmed"
        
        # Verify ticket was linked to image
        match_service._link_ticket_to_image.assert_called_once_with(
            mock_match.ticket_id, mock_match.image_id
        )
    
    def test_conflict_resolution_flow(self, match_service, mock_session):
        """Test conflict resolution in matching flow"""
        # Create two tickets that both match the same image well
        ticket1 = Mock()
        ticket1.id = uuid4()
        ticket1.ticket_number = "ABC123"
        ticket1.entry_date = date(2023, 1, 15)
        ticket1.net_weight = 10.5
        
        ticket2 = Mock()
        ticket2.id = uuid4()
        ticket2.ticket_number = "ABC123"  # Same ticket number
        ticket2.entry_date = date(2023, 1, 16)  # Different date
        ticket2.net_weight = 10.5
        
        # Create one image that both tickets match
        image = Mock()
        image.id = uuid4()
        image.ticket_number = "ABC123"
        image.created_at = datetime(2023, 1, 15, 10, 30)
        
        # Test the matching engine's conflict resolution
        engine = TicketMatchEngine()
        
        # Find initial matches
        batch_matches = engine.find_matches_for_batch([ticket1, ticket2], [image])
        
        # Both tickets should have matches for the image
        assert len(batch_matches[ticket1.id]) > 0
        assert len(batch_matches[ticket2.id]) > 0
        
        # Resolve conflicts
        resolved_matches = engine.resolve_conflicts(batch_matches)
        
        # After conflict resolution, matches should still exist but be handled differently
        assert len(resolved_matches[ticket1.id]) > 0
        assert len(resolved_matches[ticket2.id]) > 0
        
        # One should have higher confidence than the other after resolution
        match1 = resolved_matches[ticket1.id][0]
        match2 = resolved_matches[ticket2.id][0]
        
        # At least one should be modified by conflict resolution
        assert match1.confidence != match2.confidence or \
               "conflict" in str(match1.score.reasons) or \
               "conflict" in str(match2.score.reasons)
    
    def test_batch_statistics_calculation(self, match_service, mock_session):
        """Test batch statistics calculation"""
        batch_id = uuid4()
        
        # Mock match results with different confidence levels
        mock_results = []
        
        # High confidence (auto-accepted)
        result1 = Mock()
        result1.confidence = 95.0
        result1.accepted = True
        result1.reviewed = True
        mock_results.append(result1)
        
        # Medium confidence (needs review)
        result2 = Mock()
        result2.confidence = 75.0
        result2.accepted = False
        result2.reviewed = False
        mock_results.append(result2)
        
        # Low confidence (rejected)
        result3 = Mock()
        result3.confidence = 45.0
        result3.accepted = False
        result3.reviewed = True
        mock_results.append(result3)
        
        # Mock get_match_results to return our test data
        match_service.get_match_results = AsyncMock(return_value=mock_results)
        
        summary = match_service.get_batch_match_summary(batch_id)
        
        # Verify statistics are calculated correctly
        assert summary.total_matches == 3
        assert summary.auto_accepted == 1
        assert summary.needs_review == 1
        assert summary.rejected == 1
        assert summary.confidence_avg == (95.0 + 75.0 + 45.0) / 3
        assert summary.confidence_min == 45.0
        assert summary.confidence_max == 95.0
    
    def test_error_handling_in_match_flow(self, match_service, sample_tickets, sample_images, mock_session):
        """Test error handling during match flow"""
        batch_id = uuid4()
        user_id = uuid4()
        
        # Mock the database queries to succeed initially
        match_service._get_batch_tickets = AsyncMock(return_value=sample_tickets)
        match_service._get_batch_images = AsyncMock(return_value=sample_images)
        
        # Mock an error during match result creation
        match_service._create_match_result = AsyncMock(side_effect=Exception("Database error"))
        match_service.audit_service.log_event = AsyncMock()
        
        # The method should handle the error and rollback
        with pytest.raises(Exception):
            match_service.run_batch_matching(
                batch_id=batch_id,
                user_id=user_id,
                force_rematch=False
            )
        
        # Verify rollback was called
        mock_session.rollback.assert_called_once()
        
        # Verify error was logged
        match_service.audit_service.log_event.assert_called()
    
    def test_review_queue_functionality(self, match_service, mock_session):
        """Test review queue filtering and management"""
        batch_id = uuid4()
        
        # Create mock match results with different states
        all_results = []
        
        # Auto-accepted (should not be in queue)
        result1 = Mock()
        result1.confidence = 90.0
        result1.reviewed = True
        result1.accepted = True
        all_results.append(result1)
        
        # Needs review (should be in queue)
        result2 = Mock()
        result2.confidence = 75.0
        result2.reviewed = False
        result2.accepted = False
        all_results.append(result2)
        
        # Already reviewed (should not be in queue)
        result3 = Mock()
        result3.confidence = 70.0
        result3.reviewed = True
        result3.accepted = False
        all_results.append(result3)
        
        # Low confidence (should not be in queue)
        result4 = Mock()
        result4.confidence = 50.0
        result4.reviewed = False
        result4.accepted = False
        all_results.append(result4)
        
        # Mock the database query to filter correctly
        def mock_get_match_results(**kwargs):
            if kwargs.get('needs_review'):
                # Return only items that need review (60-84% confidence, not reviewed)
                return [r for r in all_results 
                       if 60.0 <= r.confidence < 85.0 and not r.reviewed]
            return all_results
        
        match_service.get_match_results = AsyncMock(side_effect=mock_get_match_results)
        
        # Get review queue
        queue_items = match_service.get_review_queue(batch_id=batch_id)
        
        # Should only contain result2
        assert len(queue_items) == 1
        assert queue_items[0].confidence == 75.0