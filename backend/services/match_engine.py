import json
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any
from uuid import UUID

from backend.models.ticket import TicketRead
from backend.models.ticket_image import TicketImageRead
from backend.utils.fuzzy_utils import FuzzyMatchUtils


class MatchScore:
    """Represents a match score with detailed breakdown"""
    
    def __init__(self):
        self.total_score: float = 0.0
        self.confidence: float = 0.0
        self.breakdown: Dict[str, Any] = {}
        self.reasons: List[str] = []
        self.max_possible_score: float = 100.0
    
    def add_score(self, rule_name: str, points: float, max_points: float, details: str = ""):
        """Add points for a specific matching rule"""
        self.breakdown[rule_name] = {
            "points": points,
            "max_points": max_points,
            "details": details
        }
        self.total_score += points
        if details:
            self.reasons.append(f"{rule_name}: {details}")
    
    def calculate_confidence(self) -> float:
        """Calculate final confidence percentage"""
        if self.max_possible_score == 0:
            return 0.0
        self.confidence = min(100.0, (self.total_score / self.max_possible_score) * 100.0)
        return self.confidence
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage"""
        return {
            "total_score": self.total_score,
            "confidence": self.confidence,
            "max_possible_score": self.max_possible_score,
            "breakdown": self.breakdown,
            "reasons": self.reasons
        }


class MatchCandidate:
    """Represents a potential match between ticket and image"""
    
    def __init__(self, ticket: TicketRead, image: TicketImageRead, score: MatchScore):
        self.ticket = ticket
        self.image = image
        self.score = score
        self.confidence = score.confidence
        
    def should_auto_accept(self) -> bool:
        """Check if match confidence is high enough for auto-acceptance"""
        return self.confidence >= 85.0
    
    def needs_review(self) -> bool:
        """Check if match needs manual review"""
        return 60.0 <= self.confidence < 85.0
    
    def should_reject(self) -> bool:
        """Check if match should be rejected"""
        return self.confidence < 60.0


class TicketMatchEngine:
    """Core matching engine for ticket-to-image matching with multi-factor scoring"""
    
    def __init__(self):
        # Scoring weights for different matching rules
        self.scoring_rules = {
            "ticket_number_exact": 90.0,
            "date_within_range": 5.0,
            "reference_match": 3.0,
            "weight_within_tolerance": 2.0
        }
        self.max_score = sum(self.scoring_rules.values())
    
    def find_matches_for_ticket(
        self, 
        ticket: TicketRead, 
        candidate_images: List[TicketImageRead]
    ) -> List[MatchCandidate]:
        """
        Find potential matches for a single ticket among candidate images
        
        Args:
            ticket: The ticket to match
            candidate_images: List of images to consider
            
        Returns:
            List of match candidates sorted by confidence (highest first)
        """
        candidates = []
        
        for image in candidate_images:
            score = self._calculate_match_score(ticket, image)
            score.calculate_confidence()
            
            candidate = MatchCandidate(ticket, image, score)
            candidates.append(candidate)
        
        # Sort by confidence (highest first)
        candidates.sort(key=lambda c: c.confidence, reverse=True)
        
        return candidates
    
    def find_matches_for_batch(
        self, 
        tickets: List[TicketRead], 
        images: List[TicketImageRead]
    ) -> Dict[UUID, List[MatchCandidate]]:
        """
        Find matches for all tickets in a batch
        
        Args:
            tickets: List of tickets to match
            images: List of images to match against
            
        Returns:
            Dictionary mapping ticket_id to list of match candidates
        """
        batch_matches = {}
        
        for ticket in tickets:
            matches = self.find_matches_for_ticket(ticket, images)
            # Only include meaningful matches (confidence >= 20%)
            meaningful_matches = [m for m in matches if m.confidence >= 20.0]
            batch_matches[ticket.id] = meaningful_matches
        
        return batch_matches
    
    def _calculate_match_score(self, ticket: TicketRead, image: TicketImageRead) -> MatchScore:
        """Calculate detailed match score between ticket and image"""
        score = MatchScore()
        score.max_possible_score = self.max_score
        
        # Rule 1: Ticket Number Match (90 points)
        self._score_ticket_number_match(ticket, image, score)
        
        # Rule 2: Date Match (5 points)
        self._score_date_match(ticket, image, score)
        
        # Rule 3: Reference Match (3 points)
        self._score_reference_match(ticket, image, score)
        
        # Rule 4: Weight Match (2 points)
        self._score_weight_match(ticket, image, score)
        
        return score
    
    def _score_ticket_number_match(self, ticket: TicketRead, image: TicketImageRead, score: MatchScore):
        """Score ticket number matching with fuzzy logic"""
        max_points = self.scoring_rules["ticket_number_exact"]
        
        if not ticket.ticket_number or not image.ticket_number:
            score.add_score("ticket_number", 0.0, max_points, "Missing ticket number")
            return
        
        # Use fuzzy matching for OCR error tolerance
        is_match, similarity = FuzzyMatchUtils.fuzzy_ticket_match(
            ticket.ticket_number, 
            image.ticket_number,
            threshold=0.8
        )
        
        if similarity >= 0.95:
            # Near-perfect match
            points = max_points
            details = f"Exact match: {ticket.ticket_number} = {image.ticket_number}"
        elif similarity >= 0.8:
            # Good match with minor OCR errors
            points = max_points * 0.9
            details = f"Fuzzy match ({similarity:.2f}): {ticket.ticket_number} ≈ {image.ticket_number}"
        elif similarity >= 0.6:
            # Partial match
            points = max_points * 0.5
            details = f"Partial match ({similarity:.2f}): {ticket.ticket_number} ~ {image.ticket_number}"
        else:
            # Poor match
            points = max_points * similarity * 0.3
            details = f"Poor match ({similarity:.2f}): {ticket.ticket_number} ≠ {image.ticket_number}"
        
        score.add_score("ticket_number", points, max_points, details)
    
    def _score_date_match(self, ticket: TicketRead, image: TicketImageRead, score: MatchScore):
        """Score date matching with tolerance"""
        max_points = self.scoring_rules["date_within_range"]
        
        if not ticket.entry_date:
            score.add_score("date_match", 0.0, max_points, "Missing ticket entry date")
            return
        
        # For images, we might use the PDF page extraction date or batch date
        # For now, we'll use the image creation date as a proxy
        image_date = image.created_at.date() if image.created_at else None
        
        if not image_date:
            score.add_score("date_match", 0.0, max_points, "Missing image date")
            return
        
        is_within_tolerance, similarity = FuzzyMatchUtils.date_within_tolerance(
            ticket.entry_date,
            image_date,
            tolerance_days=1
        )
        
        if is_within_tolerance:
            points = max_points * similarity
            details = f"Date within tolerance: {ticket.entry_date} ≈ {image_date}"
        else:
            points = max_points * similarity * 0.3
            details = f"Date outside tolerance: {ticket.entry_date} vs {image_date}"
        
        score.add_score("date_match", points, max_points, details)
    
    def _score_reference_match(self, ticket: TicketRead, image: TicketImageRead, score: MatchScore):
        """Score reference field matching"""
        max_points = self.scoring_rules["reference_match"]
        
        # For images, reference might be extracted from OCR or filename
        # For now, we'll compare with any available reference field
        ticket_ref = getattr(ticket, 'reference', None) or getattr(ticket, 'customer_reference', '')
        image_ref = getattr(image, 'reference', '') or ""
        
        if not ticket_ref and not image_ref:
            score.add_score("reference_match", 0.0, max_points, "No reference data to compare")
            return
        
        if not ticket_ref or not image_ref:
            score.add_score("reference_match", 0.0, max_points, "Missing reference in one record")
            return
        
        is_match, similarity = FuzzyMatchUtils.fuzzy_reference_match(
            ticket_ref,
            image_ref,
            threshold=0.7
        )
        
        points = max_points * similarity
        
        if similarity >= 0.9:
            details = f"Strong reference match: {ticket_ref} ≈ {image_ref}"
        elif similarity >= 0.7:
            details = f"Good reference match: {ticket_ref} ~ {image_ref}"
        else:
            details = f"Weak reference match: {ticket_ref} ≠ {image_ref}"
        
        score.add_score("reference_match", points, max_points, details)
    
    def _score_weight_match(self, ticket: TicketRead, image: TicketImageRead, score: MatchScore):
        """Score weight matching with tolerance"""
        max_points = self.scoring_rules["weight_within_tolerance"]
        
        if not ticket.net_weight:
            score.add_score("weight_match", 0.0, max_points, "Missing ticket weight")
            return
        
        # For images, weight might be extracted from OCR
        # For now, we'll assume it's not available and give partial credit
        image_weight = getattr(image, 'extracted_weight', None)
        
        if image_weight is None:
            # Give partial credit for having weight data in ticket
            score.add_score("weight_match", max_points * 0.5, max_points, "Weight only available in ticket")
            return
        
        is_within_tolerance, similarity = FuzzyMatchUtils.weight_within_tolerance(
            ticket.net_weight,
            image_weight,
            tolerance=0.5
        )
        
        points = max_points * similarity
        
        if is_within_tolerance:
            details = f"Weight within tolerance: {ticket.net_weight}t ≈ {image_weight}t"
        else:
            details = f"Weight outside tolerance: {ticket.net_weight}t vs {image_weight}t"
        
        score.add_score("weight_match", points, max_points, details)
    
    def resolve_conflicts(self, batch_matches: Dict[UUID, List[MatchCandidate]]) -> Dict[UUID, List[MatchCandidate]]:
        """
        Resolve conflicts where multiple tickets match the same image
        
        Args:
            batch_matches: Dictionary of ticket_id -> match candidates
            
        Returns:
            Resolved matches with conflicts flagged
        """
        # Track which images are claimed by which tickets
        image_claims: Dict[UUID, List[Tuple[UUID, float]]] = {}
        
        # Collect all image claims
        for ticket_id, candidates in batch_matches.items():
            for candidate in candidates:
                if candidate.should_auto_accept() or candidate.needs_review():
                    image_id = candidate.image.id
                    if image_id not in image_claims:
                        image_claims[image_id] = []
                    image_claims[image_id].append((ticket_id, candidate.confidence))
        
        # Resolve conflicts
        resolved_matches = {}
        
        for ticket_id, candidates in batch_matches.items():
            resolved_candidates = []
            
            for candidate in candidates:
                image_id = candidate.image.id
                claims = image_claims.get(image_id, [])
                
                if len(claims) <= 1:
                    # No conflict
                    resolved_candidates.append(candidate)
                else:
                    # Conflict detected - find the best claimant
                    claims.sort(key=lambda x: x[1], reverse=True)
                    best_ticket_id, best_confidence = claims[0]
                    
                    if ticket_id == best_ticket_id:
                        # This ticket wins the conflict
                        candidate.score.reasons.append("Won conflict resolution")
                        resolved_candidates.append(candidate)
                    else:
                        # This ticket loses - reduce confidence and flag for review
                        candidate.confidence = max(candidate.confidence * 0.5, 40.0)
                        candidate.score.confidence = candidate.confidence
                        candidate.score.reasons.append("Lost conflict resolution - needs manual review")
                        resolved_candidates.append(candidate)
            
            resolved_matches[ticket_id] = resolved_candidates
        
        return resolved_matches
    
    def get_batch_statistics(self, batch_matches: Dict[UUID, List[MatchCandidate]]) -> Dict[str, Any]:
        """Calculate statistics for batch matching results"""
        stats = {
            "total_tickets": len(batch_matches),
            "auto_accepted": 0,
            "needs_review": 0,
            "unmatched": 0,
            "conflicts": 0,
            "average_confidence": 0.0,
            "match_distribution": {
                "excellent": 0,  # >= 95%
                "good": 0,       # 85-94%
                "fair": 0,       # 60-84%
                "poor": 0        # < 60%
            }
        }
        
        total_confidence = 0.0
        ticket_count = 0
        
        for ticket_id, candidates in batch_matches.items():
            ticket_count += 1
            
            if not candidates:
                stats["unmatched"] += 1
                continue
            
            # Use the best candidate for statistics
            best_candidate = candidates[0]
            confidence = best_candidate.confidence
            total_confidence += confidence
            
            # Categorize match quality
            if confidence >= 95.0:
                stats["match_distribution"]["excellent"] += 1
                stats["auto_accepted"] += 1
            elif confidence >= 85.0:
                stats["match_distribution"]["good"] += 1
                stats["auto_accepted"] += 1
            elif confidence >= 60.0:
                stats["match_distribution"]["fair"] += 1
                stats["needs_review"] += 1
            else:
                stats["match_distribution"]["poor"] += 1
                stats["unmatched"] += 1
            
            # Check for conflicts
            if len(candidates) > 1 and candidates[1].confidence >= 60.0:
                stats["conflicts"] += 1
        
        if ticket_count > 0:
            stats["average_confidence"] = total_confidence / ticket_count
        
        return stats