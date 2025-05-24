import json
from ..utils.datetime_utils import utcnow_naive
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlmodel import Session, select, and_
from fastapi import Depends

from backend.core.database import get_session
from backend.models.match_result import (
    MatchResult, MatchResultCreate, MatchResultRead, MatchResultSummary, MatchDecision
)
from backend.models.ticket import Ticket
from backend.models.ticket_image import TicketImage
from backend.services.match_engine import MatchCandidate, TicketMatchEngine
from backend.services.audit_service import AuditService, AuditEventType


class MatchService:
    """Service for managing ticket-to-image matching operations"""
    
    def __init__(self, session: Session):
        self.session = session
        self.match_engine = TicketMatchEngine()
        self.audit_service = AuditService(session)
    
    async def run_batch_matching(
        self, 
        batch_id: UUID, 
        user_id: UUID,
        force_rematch: bool = False
    ) -> Dict[str, Any]:
        """
        Run matching engine on all tickets and images in a batch
        
        Args:
            batch_id: The batch to process
            user_id: ID of user running the match
            force_rematch: Whether to re-match already matched tickets
            
        Returns:
            Dictionary with match results and statistics
        """
        # Get all tickets and images for the batch
        tickets = await self._get_batch_tickets(batch_id, include_matched=force_rematch)
        images = await self._get_batch_images(batch_id)
        
        if not tickets:
            return {
                "success": False,
                "message": "No tickets found for matching",
                "statistics": {}
            }
        
        if not images:
            return {
                "success": False,
                "message": "No images found for matching",
                "statistics": {}
            }
        
        # Log the start of matching process
        await self.audit_service.log_event(
            AuditEventType.MATCH_STARTED,
            user_id=user_id,
            batch_id=batch_id,
            details=f"Starting match process for {len(tickets)} tickets and {len(images)} images"
        )
        
        try:
            # Run the matching engine
            batch_matches = self.match_engine.find_matches_for_batch(tickets, images)
            
            # Resolve conflicts
            resolved_matches = self.match_engine.resolve_conflicts(batch_matches)
            
            # Persist match results
            match_results = []
            for ticket_id, candidates in resolved_matches.items():
                if candidates:
                    # Take the best candidate
                    best_candidate = candidates[0]
                    match_result = await self._create_match_result(
                        best_candidate, 
                        user_id,
                        batch_id
                    )
                    match_results.append(match_result)
                    
                    # Update ticket with image_id if auto-accepted
                    if best_candidate.should_auto_accept():
                        await self._link_ticket_to_image(ticket_id, best_candidate.image.id)
            
            # Calculate statistics
            statistics = self.match_engine.get_batch_statistics(resolved_matches)
            statistics["matches_created"] = len(match_results)
            
            # Log completion
            await self.audit_service.log_event(
                AuditEventType.MATCH_COMPLETED,
                user_id=user_id,
                batch_id=batch_id,
                details=f"Match completed: {statistics['auto_accepted']} auto-accepted, {statistics['needs_review']} need review"
            )
            
            self.session.commit()
            
            return {
                "success": True,
                "message": f"Matching completed for batch {batch_id}",
                "statistics": statistics,
                "match_results": [self._match_result_to_dict(mr) for mr in match_results]
            }
            
        except Exception as e:
            self.session.rollback()
            await self.audit_service.log_event(
                AuditEventType.SYSTEM_ERROR,
                user_id=user_id,
                batch_id=batch_id,
                details=f"Match process failed: {str(e)}"
            )
            raise
    
    async def get_match_results(
        self, 
        batch_id: Optional[UUID] = None,
        ticket_id: Optional[UUID] = None,
        image_id: Optional[UUID] = None,
        needs_review: Optional[bool] = None
    ) -> List[MatchResultRead]:
        """Get match results with optional filtering"""
        
        query = select(MatchResult)
        
        conditions = []
        if batch_id:
            # Join with tickets to filter by batch
            query = query.join(Ticket, MatchResult.ticket_id == Ticket.id)
            conditions.append(Ticket.batch_id == batch_id)
        
        if ticket_id:
            conditions.append(MatchResult.ticket_id == ticket_id)
        
        if image_id:
            conditions.append(MatchResult.image_id == image_id)
        
        if needs_review is not None:
            if needs_review:
                conditions.append(and_(
                    MatchResult.confidence >= 60.0,
                    MatchResult.confidence < 85.0,
                    not MatchResult.reviewed
                ))
            else:
                conditions.append(MatchResult.reviewed)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        results = self.session.exec(query).all()
        return [MatchResultRead.model_validate(result) for result in results]
    
    async def get_match_result(self, match_id: UUID) -> Optional[MatchResultRead]:
        """Get a specific match result by ID"""
        result = self.session.get(MatchResult, match_id)
        if result:
            return MatchResultRead.model_validate(result)
        return None
    
    async def accept_match(
        self, 
        match_id: UUID, 
        user_id: UUID,
        decision: MatchDecision
    ) -> MatchResultRead:
        """Manually accept a match result"""
        
        match_result = self.session.get(MatchResult, match_id)
        if not match_result:
            raise ValueError(f"Match result {match_id} not found")
        
        # Update match result
        match_result.accepted = decision.accepted
        match_result.reviewed = True
        match_result.reviewed_by = user_id
        match_result.reviewed_at = utcnow_naive()
        match_result.updated_at = utcnow_naive()
        
        if decision.reason:
            match_result.reason = decision.reason
        
        # If accepted, link ticket to image
        if decision.accepted:
            await self._link_ticket_to_image(match_result.ticket_id, match_result.image_id)
            
        # Log the decision
        await self.audit_service.log_event(
            AuditEventType.MATCH_REVIEWED,
            user_id=user_id,
            batch_id=None,  # Will be populated if needed
            details=f"Match {'accepted' if decision.accepted else 'rejected'}: {match_result.ticket_id} -> {match_result.image_id}"
        )
        
        self.session.add(match_result)
        self.session.commit()
        
        return MatchResultRead.model_validate(match_result)
    
    async def reject_match(
        self, 
        match_id: UUID, 
        user_id: UUID,
        reason: Optional[str] = None
    ) -> MatchResultRead:
        """Manually reject a match result"""
        decision = MatchDecision(accepted=False, reason=reason)
        return await self.accept_match(match_id, user_id, decision)
    
    async def get_batch_match_summary(self, batch_id: UUID) -> MatchResultSummary:
        """Get summary statistics for matches in a batch"""
        
        # Get all match results for the batch
        match_results = await self.get_match_results(batch_id=batch_id)
        
        if not match_results:
            return MatchResultSummary(
                total_matches=0,
                auto_accepted=0,
                needs_review=0,
                rejected=0,
                confidence_avg=0.0,
                confidence_min=0.0,
                confidence_max=0.0
            )
        
        total_matches = len(match_results)
        auto_accepted = sum(1 for mr in match_results if mr.accepted and mr.confidence >= 85.0)
        needs_review = sum(1 for mr in match_results if not mr.reviewed and 60.0 <= mr.confidence < 85.0)
        rejected = sum(1 for mr in match_results if mr.reviewed and not mr.accepted)
        
        confidences = [mr.confidence for mr in match_results]
        confidence_avg = sum(confidences) / len(confidences) if confidences else 0.0
        confidence_min = min(confidences) if confidences else 0.0
        confidence_max = max(confidences) if confidences else 0.0
        
        return MatchResultSummary(
            total_matches=total_matches,
            auto_accepted=auto_accepted,
            needs_review=needs_review,
            rejected=rejected,
            confidence_avg=confidence_avg,
            confidence_min=confidence_min,
            confidence_max=confidence_max
        )
    
    async def get_review_queue(self, batch_id: Optional[UUID] = None) -> List[MatchResultRead]:
        """Get all matches that need manual review"""
        return await self.get_match_results(batch_id=batch_id, needs_review=True)
    
    async def _get_batch_tickets(self, batch_id: UUID, include_matched: bool = False) -> List:
        """Get tickets for a batch, optionally including already matched ones"""
        query = select(Ticket).where(Ticket.batch_id == batch_id)
        
        if not include_matched:
            query = query.where(Ticket.image_id.is_(None))
        
        return list(self.session.exec(query).all())
    
    async def _get_batch_images(self, batch_id: UUID) -> List:
        """Get images for a batch"""
        query = select(TicketImage).where(TicketImage.batch_id == batch_id)
        return list(self.session.exec(query).all())
    
    async def _create_match_result(
        self, 
        candidate: MatchCandidate, 
        user_id: UUID,
        batch_id: UUID
    ) -> MatchResult:
        """Create a new match result from a match candidate"""
        
        match_data = MatchResultCreate(
            ticket_id=candidate.ticket.id,
            image_id=candidate.image.id,
            confidence=candidate.confidence,
            accepted=candidate.should_auto_accept(),
            reviewed=candidate.should_auto_accept(),  # Auto-accepted matches are considered reviewed
            flagged=candidate.needs_review(),
            reason="; ".join(candidate.score.reasons) if candidate.score.reasons else None,
            score_breakdown=json.dumps(candidate.score.to_dict()),
            match_method="automatic"
        )
        
        match_result = MatchResult(**match_data.model_dump())
        
        if candidate.should_auto_accept():
            match_result.reviewed_by = user_id
            match_result.reviewed_at = utcnow_naive()
        
        self.session.add(match_result)
        return match_result
    
    async def _link_ticket_to_image(self, ticket_id: UUID, image_id: UUID):
        """Update ticket to link it with an image"""
        ticket = self.session.get(Ticket, ticket_id)
        if ticket:
            ticket.image_id = image_id
            self.session.add(ticket)
    
    def _match_result_to_dict(self, match_result: MatchResult) -> Dict[str, Any]:
        """Convert match result to dictionary for API response"""
        return {
            "id": str(match_result.id),
            "ticket_id": str(match_result.ticket_id),
            "image_id": str(match_result.image_id),
            "confidence": match_result.confidence,
            "accepted": match_result.accepted,
            "reviewed": match_result.reviewed,
            "flagged": match_result.flagged,
            "reason": match_result.reason,
            "score_breakdown": json.loads(match_result.score_breakdown) if match_result.score_breakdown else None,
            "match_method": match_result.match_method,
            "created_at": match_result.created_at.isoformat() if match_result.created_at else None,
            "reviewed_at": match_result.reviewed_at.isoformat() if match_result.reviewed_at else None
        }


def get_match_service(session: Session = Depends(get_session)) -> MatchService:
    """Dependency injection for MatchService"""
    return MatchService(session)