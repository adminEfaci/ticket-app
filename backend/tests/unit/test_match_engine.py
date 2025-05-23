import pytest
from datetime import datetime, date
from uuid import uuid4
from unittest.mock import Mock, MagicMock

from backend.services.match_engine import (
    TicketMatchEngine, MatchScore, MatchCandidate
)
from backend.models.ticket import TicketRead
from backend.models.ticket_image import TicketImageRead


class TestMatchScore:
    """Test suite for MatchScore class"""
    
    def test_match_score_initialization(self):
        """Test MatchScore initialization"""
        score = MatchScore()
        assert score.total_score == 0.0
        assert score.confidence == 0.0
        assert score.breakdown == {}
        assert score.reasons == []
        assert score.max_possible_score == 100.0
    
    def test_add_score(self):
        """Test adding scores to MatchScore"""
        score = MatchScore()
        score.add_score("test_rule", 10.0, 20.0, "Test detail")
        
        assert score.total_score == 10.0
        assert score.breakdown["test_rule"]["points"] == 10.0
        assert score.breakdown["test_rule"]["max_points"] == 20.0
        assert score.breakdown["test_rule"]["details"] == "Test detail"
        assert "test_rule: Test detail" in score.reasons
    
    def test_add_multiple_scores(self):
        """Test adding multiple scores"""
        score = MatchScore()
        score.add_score("rule1", 10.0, 20.0, "Detail 1")
        score.add_score("rule2", 15.0, 30.0, "Detail 2")
        
        assert score.total_score == 25.0
        assert len(score.breakdown) == 2
        assert len(score.reasons) == 2
    
    def test_calculate_confidence(self):
        """Test confidence calculation"""
        score = MatchScore()
        score.max_possible_score = 100.0
        score.add_score("rule", 80.0, 100.0)
        
        confidence = score.calculate_confidence()
        assert confidence == 80.0
        assert score.confidence == 80.0
    
    def test_calculate_confidence_over_100(self):
        """Test confidence calculation caps at 100%"""
        score = MatchScore()
        score.max_possible_score = 100.0
        score.add_score("rule", 120.0, 100.0)  # Over max
        
        confidence = score.calculate_confidence()
        assert confidence == 100.0
    
    def test_to_dict(self):
        """Test converting MatchScore to dictionary"""
        score = MatchScore()
        score.add_score("test_rule", 10.0, 20.0, "Test detail")
        score.calculate_confidence()
        
        result = score.to_dict()
        
        assert "total_score" in result
        assert "confidence" in result
        assert "breakdown" in result
        assert "reasons" in result
        assert result["breakdown"]["test_rule"]["points"] == 10.0


class TestMatchCandidate:
    """Test suite for MatchCandidate class"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.ticket = Mock(spec=TicketRead)
        self.ticket.id = uuid4()
        
        self.image = Mock(spec=TicketImageRead)
        self.image.id = uuid4()
        
        self.score = MatchScore()
    
    def test_match_candidate_initialization(self):
        """Test MatchCandidate initialization"""
        self.score.confidence = 90.0
        candidate = MatchCandidate(self.ticket, self.image, self.score)
        
        assert candidate.ticket == self.ticket
        assert candidate.image == self.image
        assert candidate.score == self.score
        assert candidate.confidence == 90.0
    
    def test_should_auto_accept_high_confidence(self):
        """Test auto-accept for high confidence matches"""
        self.score.confidence = 90.0
        candidate = MatchCandidate(self.ticket, self.image, self.score)
        
        assert candidate.should_auto_accept() is True
        assert candidate.needs_review() is False
        assert candidate.should_reject() is False
    
    def test_needs_review_medium_confidence(self):
        """Test review queue for medium confidence matches"""
        self.score.confidence = 75.0
        candidate = MatchCandidate(self.ticket, self.image, self.score)
        
        assert candidate.should_auto_accept() is False
        assert candidate.needs_review() is True
        assert candidate.should_reject() is False
    
    def test_should_reject_low_confidence(self):
        """Test rejection for low confidence matches"""
        self.score.confidence = 45.0
        candidate = MatchCandidate(self.ticket, self.image, self.score)
        
        assert candidate.should_auto_accept() is False
        assert candidate.needs_review() is False
        assert candidate.should_reject() is True
    
    def test_boundary_conditions(self):
        """Test boundary conditions for confidence thresholds"""
        # Exactly 85% - should auto-accept
        self.score.confidence = 85.0
        candidate = MatchCandidate(self.ticket, self.image, self.score)
        assert candidate.should_auto_accept() is True
        
        # Just below 85% - needs review
        self.score.confidence = 84.9
        candidate = MatchCandidate(self.ticket, self.image, self.score)
        assert candidate.needs_review() is True
        
        # Exactly 60% - needs review
        self.score.confidence = 60.0
        candidate = MatchCandidate(self.ticket, self.image, self.score)
        assert candidate.needs_review() is True
        
        # Just below 60% - should reject
        self.score.confidence = 59.9
        candidate = MatchCandidate(self.ticket, self.image, self.score)
        assert candidate.should_reject() is True


class TestTicketMatchEngine:
    """Test suite for TicketMatchEngine class"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.engine = TicketMatchEngine()
        
        # Create mock ticket
        self.ticket = Mock(spec=TicketRead)
        self.ticket.id = uuid4()
        self.ticket.ticket_number = "ABC123"
        self.ticket.entry_date = date(2023, 1, 15)
        self.ticket.net_weight = 10.5
        
        # Create mock image
        self.image = Mock(spec=TicketImageRead)
        self.image.id = uuid4()
        self.image.ticket_number = "ABC123"
        self.image.created_at = datetime(2023, 1, 15, 10, 30)
    
    def test_engine_initialization(self):
        """Test TicketMatchEngine initialization"""
        assert "ticket_number_exact" in self.engine.scoring_rules
        assert "date_within_range" in self.engine.scoring_rules
        assert "reference_match" in self.engine.scoring_rules
        assert "weight_within_tolerance" in self.engine.scoring_rules
        
        assert self.engine.max_score == sum(self.engine.scoring_rules.values())
    
    def test_perfect_match_scoring(self):
        """Test scoring for perfect ticket match"""
        candidates = self.engine.find_matches_for_ticket(self.ticket, [self.image])
        
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.confidence >= 85.0  # Should be high confidence
    
    def test_ticket_number_mismatch_scoring(self):
        """Test scoring when ticket numbers don't match"""
        self.image.ticket_number = "XYZ789"
        
        candidates = self.engine.find_matches_for_ticket(self.ticket, [self.image])
        
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.confidence < 60.0  # Should be low confidence
    
    def test_date_mismatch_scoring(self):
        """Test scoring when dates are far apart"""
        self.image.created_at = datetime(2023, 2, 15, 10, 30)  # One month later
        
        candidates = self.engine.find_matches_for_ticket(self.ticket, [self.image])
        
        assert len(candidates) == 1
        candidate = candidates[0]
        # Should still be high due to ticket number match, but slightly lower
        assert candidate.confidence >= 85.0
    
    def test_missing_ticket_number_scoring(self):
        """Test scoring when ticket number is missing"""
        self.ticket.ticket_number = None
        
        candidates = self.engine.find_matches_for_ticket(self.ticket, [self.image])
        
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.confidence < 60.0  # Should be very low without ticket number
    
    def test_fuzzy_ticket_number_matching(self):
        """Test fuzzy matching for ticket numbers with OCR errors"""
        self.image.ticket_number = "ABC12O"  # O instead of 3
        
        candidates = self.engine.find_matches_for_ticket(self.ticket, [self.image])
        
        assert len(candidates) == 1
        candidate = candidates[0]
        assert candidate.confidence >= 75.0  # Should still be good with fuzzy match
    
    def test_multiple_candidates_sorting(self):
        """Test that candidates are sorted by confidence"""
        # Create multiple images with different similarities
        image1 = Mock(spec=TicketImageRead)
        image1.id = uuid4()
        image1.ticket_number = "ABC123"  # Perfect match
        image1.created_at = datetime(2023, 1, 15, 10, 30)
        
        image2 = Mock(spec=TicketImageRead)
        image2.id = uuid4()
        image2.ticket_number = "ABC124"  # Close match
        image2.created_at = datetime(2023, 1, 15, 10, 30)
        
        image3 = Mock(spec=TicketImageRead)
        image3.id = uuid4()
        image3.ticket_number = "XYZ789"  # Poor match
        image3.created_at = datetime(2023, 1, 15, 10, 30)
        
        candidates = self.engine.find_matches_for_ticket(
            self.ticket, [image3, image1, image2]  # Intentionally unsorted
        )
        
        assert len(candidates) == 3
        # Should be sorted by confidence (highest first)
        assert candidates[0].confidence >= candidates[1].confidence
        assert candidates[1].confidence >= candidates[2].confidence
        
        # Perfect match should be first
        assert candidates[0].image.ticket_number == "ABC123"
    
    def test_batch_matching(self):
        """Test matching for multiple tickets and images"""
        # Create second ticket and image
        ticket2 = Mock(spec=TicketRead)
        ticket2.id = uuid4()
        ticket2.ticket_number = "XYZ789"
        ticket2.entry_date = date(2023, 1, 16)
        ticket2.net_weight = 15.0
        
        image2 = Mock(spec=TicketImageRead)
        image2.id = uuid4()
        image2.ticket_number = "XYZ789"
        image2.created_at = datetime(2023, 1, 16, 10, 30)
        
        batch_matches = self.engine.find_matches_for_batch(
            [self.ticket, ticket2], [self.image, image2]
        )
        
        assert len(batch_matches) == 2
        assert self.ticket.id in batch_matches
        assert ticket2.id in batch_matches
        
        # Each ticket should have matches for both images
        assert len(batch_matches[self.ticket.id]) >= 1
        assert len(batch_matches[ticket2.id]) >= 1
    
    def test_conflict_resolution_single_winner(self):
        """Test conflict resolution when multiple tickets match same image"""
        # Create second ticket that also matches the same image
        ticket2 = Mock(spec=TicketRead)
        ticket2.id = uuid4()
        ticket2.ticket_number = "ABC123"  # Same ticket number
        ticket2.entry_date = date(2023, 1, 16)  # Different date (lower score)
        ticket2.net_weight = 10.5
        
        # Initial matching
        batch_matches = self.engine.find_matches_for_batch(
            [self.ticket, ticket2], [self.image]
        )
        
        # Resolve conflicts
        resolved_matches = self.engine.resolve_conflicts(batch_matches)
        
        assert len(resolved_matches) == 2
        
        # One should win, one should lose
        ticket1_matches = resolved_matches[self.ticket.id]
        ticket2_matches = resolved_matches[ticket2.id]
        
        # Both should have a match result, but with different handling
        assert len(ticket1_matches) >= 1
        assert len(ticket2_matches) >= 1
    
    def test_batch_statistics(self):
        """Test calculation of batch statistics"""
        # Create tickets with different match qualities
        ticket_good = Mock(spec=TicketRead)
        ticket_good.id = uuid4()
        ticket_good.ticket_number = "ABC123"
        ticket_good.entry_date = date(2023, 1, 15)
        ticket_good.net_weight = 10.5
        
        ticket_poor = Mock(spec=TicketRead)
        ticket_poor.id = uuid4()
        ticket_poor.ticket_number = "NOMATCH"
        ticket_poor.entry_date = date(2023, 1, 15)
        ticket_poor.net_weight = 10.5
        
        batch_matches = self.engine.find_matches_for_batch(
            [ticket_good, ticket_poor], [self.image]
        )
        
        stats = self.engine.get_batch_statistics(batch_matches)
        
        assert "total_tickets" in stats
        assert "auto_accepted" in stats
        assert "needs_review" in stats
        assert "unmatched" in stats
        assert "average_confidence" in stats
        assert "match_distribution" in stats
        
        assert stats["total_tickets"] == 2
        assert isinstance(stats["average_confidence"], float)
    
    def test_empty_batch_statistics(self):
        """Test statistics calculation for empty batch"""
        stats = self.engine.get_batch_statistics({})
        
        assert stats["total_tickets"] == 0
        assert stats["auto_accepted"] == 0
        assert stats["needs_review"] == 0
        assert stats["unmatched"] == 0
        assert stats["average_confidence"] == 0.0
    
    def test_score_breakdown_details(self):
        """Test that score breakdown contains detailed information"""
        candidates = self.engine.find_matches_for_ticket(self.ticket, [self.image])
        
        candidate = candidates[0]
        breakdown = candidate.score.breakdown
        
        # Should have entries for each scoring rule
        assert "ticket_number" in breakdown
        assert "date_match" in breakdown
        assert "reference_match" in breakdown
        assert "weight_match" in breakdown
        
        # Each breakdown should have points, max_points, and details
        for rule, details in breakdown.items():
            assert "points" in details
            assert "max_points" in details
            assert "details" in details
    
    def test_meaningful_matches_filtering(self):
        """Test that only meaningful matches (>=20% confidence) are included"""
        # Create an image with completely different ticket number
        bad_image = Mock(spec=TicketImageRead)
        bad_image.id = uuid4()
        bad_image.ticket_number = "ZZZZZZZ"
        bad_image.created_at = datetime(2023, 1, 15, 10, 30)
        
        batch_matches = self.engine.find_matches_for_batch(
            [self.ticket], [bad_image]
        )
        
        # Should filter out very poor matches
        ticket_matches = batch_matches[self.ticket.id]
        for match in ticket_matches:
            assert match.confidence >= 20.0
    
    def test_date_tolerance_edge_cases(self):
        """Test date matching edge cases"""
        # Test with None dates
        self.ticket.entry_date = None
        candidates = self.engine.find_matches_for_ticket(self.ticket, [self.image])
        
        candidate = candidates[0]
        # Should still match on ticket number but lose date points
        assert candidate.confidence > 0
        
        # Test with image having None created_at
        self.ticket.entry_date = date(2023, 1, 15)
        self.image.created_at = None
        candidates = self.engine.find_matches_for_ticket(self.ticket, [self.image])
        
        candidate = candidates[0]
        assert candidate.confidence > 0
    
    def test_weight_tolerance_edge_cases(self):
        """Test weight matching edge cases"""
        # Test with None weights
        self.ticket.net_weight = None
        candidates = self.engine.find_matches_for_ticket(self.ticket, [self.image])
        
        candidate = candidates[0]
        # Should still match on ticket number
        assert candidate.confidence > 0