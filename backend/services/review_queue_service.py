from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import timedelta
from ..utils.datetime_utils import utcnow_naive

from sqlmodel import Session, select, and_
from backend.models.match_result import MatchResult, MatchResultRead


class ReviewQueueService:
    """Service for managing the manual review queue for matching results"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def get_queue_items(
        self, 
        batch_id: Optional[UUID] = None,
        assigned_to: Optional[UUID] = None,
        priority_order: bool = True
    ) -> List[MatchResultRead]:
        """
        Get items in the review queue
        
        Args:
            batch_id: Filter by specific batch
            assigned_to: Filter by assigned reviewer
            priority_order: Sort by priority (confidence desc, then created_at asc)
        """
        query = select(MatchResult).where(
            and_(
                not MatchResult.reviewed,
                MatchResult.confidence >= 60.0,
                MatchResult.confidence < 85.0
            )
        )
        
        if batch_id:
            # Need to join with Ticket to filter by batch
            from backend.models.ticket import Ticket
            query = query.join(Ticket, MatchResult.ticket_id == Ticket.id)
            query = query.where(Ticket.batch_id == batch_id)
        
        if assigned_to:
            query = query.where(MatchResult.reviewed_by == assigned_to)
        
        if priority_order:
            # Higher confidence items first, then older items
            query = query.order_by(
                MatchResult.confidence.desc(),
                MatchResult.created_at.asc()
            )
        else:
            query = query.order_by(MatchResult.created_at.desc())
        
        results = self.session.exec(query).all()
        return [MatchResultRead.model_validate(result) for result in results]
    
    def get_queue_statistics(self, batch_id: Optional[UUID] = None) -> Dict[str, Any]:
        """Get statistics about the review queue"""
        query = select(MatchResult).where(
            and_(
                not MatchResult.reviewed,
                MatchResult.confidence >= 60.0,
                MatchResult.confidence < 85.0
            )
        )
        
        if batch_id:
            from backend.models.ticket import Ticket
            query = query.join(Ticket, MatchResult.ticket_id == Ticket.id)
            query = query.where(Ticket.batch_id == batch_id)
        
        results = list(self.session.exec(query).all())
        
        if not results:
            return {
                "total_items": 0,
                "avg_confidence": 0.0,
                "oldest_item_age_hours": 0,
                "confidence_distribution": {
                    "60-65": 0,
                    "65-70": 0,
                    "70-75": 0,
                    "75-80": 0,
                    "80-85": 0
                }
            }
        
        confidences = [r.confidence for r in results]
        avg_confidence = sum(confidences) / len(confidences)
        
        # Calculate age of oldest item
        oldest_item = min(results, key=lambda r: r.created_at)
        oldest_age_hours = (utcnow_naive() - oldest_item.created_at).total_seconds() / 3600
        
        # Confidence distribution
        distribution = {
            "60-65": sum(1 for c in confidences if 60 <= c < 65),
            "65-70": sum(1 for c in confidences if 65 <= c < 70),
            "70-75": sum(1 for c in confidences if 70 <= c < 75),
            "75-80": sum(1 for c in confidences if 75 <= c < 80),
            "80-85": sum(1 for c in confidences if 80 <= c < 85)
        }
        
        return {
            "total_items": len(results),
            "avg_confidence": avg_confidence,
            "oldest_item_age_hours": oldest_age_hours,
            "confidence_distribution": distribution
        }
    
    def assign_reviewer(self, match_id: UUID, reviewer_id: UUID) -> bool:
        """Assign a reviewer to a match result"""
        match_result = self.session.get(MatchResult, match_id)
        if not match_result:
            return False
        
        match_result.reviewed_by = reviewer_id
        match_result.updated_at = utcnow_naive()
        
        self.session.add(match_result)
        self.session.commit()
        
        return True
    
    def get_reviewer_workload(self, reviewer_id: UUID) -> Dict[str, Any]:
        """Get workload statistics for a specific reviewer"""
        # Active assignments (not yet reviewed)
        active_query = select(MatchResult).where(
            and_(
                MatchResult.reviewed_by == reviewer_id,
                not MatchResult.reviewed
            )
        )
        active_assignments = list(self.session.exec(active_query).all())
        
        # Recently completed reviews (last 7 days)
        week_ago = utcnow_naive() - timedelta(days=7)
        completed_query = select(MatchResult).where(
            and_(
                MatchResult.reviewed_by == reviewer_id,
                MatchResult.reviewed,
                MatchResult.reviewed_at >= week_ago
            )
        )
        completed_reviews = list(self.session.exec(completed_query).all())
        
        return {
            "active_assignments": len(active_assignments),
            "completed_this_week": len(completed_reviews),
            "avg_confidence_active": (
                sum(r.confidence for r in active_assignments) / len(active_assignments)
                if active_assignments else 0.0
            ),
            "acceptance_rate_week": (
                sum(1 for r in completed_reviews if r.accepted) / len(completed_reviews)
                if completed_reviews else 0.0
            )
        }
    
    def auto_assign_by_workload(self, eligible_reviewers: List[UUID]) -> Optional[UUID]:
        """
        Automatically assign the next queue item to the reviewer with the lowest workload
        
        Args:
            eligible_reviewers: List of user IDs who can be assigned reviews
            
        Returns:
            UUID of the selected reviewer, or None if no reviewers available
        """
        if not eligible_reviewers:
            return None
        
        # Calculate workload for each reviewer
        workloads = {}
        for reviewer_id in eligible_reviewers:
            workload = self.get_reviewer_workload(reviewer_id)
            workloads[reviewer_id] = workload["active_assignments"]
        
        # Select reviewer with minimum workload
        min_workload_reviewer = min(workloads, key=workloads.get)
        return min_workload_reviewer
    
    def escalate_old_items(self, hours_threshold: int = 24) -> List[UUID]:
        """
        Find items that have been in the queue longer than threshold and escalate them
        
        Returns:
            List of match result IDs that were escalated
        """
        threshold_time = utcnow_naive() - timedelta(hours=hours_threshold)
        
        query = select(MatchResult).where(
            and_(
                not MatchResult.reviewed,
                MatchResult.confidence >= 60.0,
                MatchResult.confidence < 85.0,
                MatchResult.created_at <= threshold_time
            )
        )
        
        old_items = list(self.session.exec(query).all())
        escalated_ids = []
        
        for item in old_items:
            # Flag for escalation
            item.flagged = True
            item.reason = f"Escalated: In queue for {hours_threshold}+ hours"
            item.updated_at = utcnow_naive()
            
            self.session.add(item)
            escalated_ids.append(item.id)
        
        if escalated_ids:
            self.session.commit()
        
        return escalated_ids


def get_review_queue_service(session: Session) -> ReviewQueueService:
    """Dependency injection for ReviewQueueService"""
    return ReviewQueueService(session)