from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import List, Optional, Dict, Any
from uuid import UUID

from backend.middleware.auth_middleware import get_current_user, staff_required
from backend.models.user import User
from backend.models.match_result import (
    MatchResultRead, MatchResultSummary, MatchDecision
)
from backend.services.match_service import MatchService, get_match_service
from backend.core.database import get_session
from sqlmodel import Session


router = APIRouter(prefix="/match", tags=["matching"])


@router.post("/batches/{batch_id}/match")
async def run_batch_matching(
    batch_id: UUID,
    force_rematch: bool = False,
    request: Request = None,
    current_user: dict = Depends(staff_required()),
    match_service: MatchService = Depends(get_match_service)
):
    """
    Run matching engine on all tickets and images in a batch
    
    Requires PROCESSOR, MANAGER, or ADMIN role.
    """
    try:
        result = await match_service.run_batch_matching(
            batch_id=batch_id,
            user_id=current_user['user_id'],
            force_rematch=force_rematch
        )
        
        return {
            "success": result["success"],
            "message": result["message"],
            "batch_id": str(batch_id),
            "statistics": result["statistics"],
            "total_matches": len(result.get("match_results", [])),
            "auto_accepted": result["statistics"].get("auto_accepted", 0),
            "needs_review": result["statistics"].get("needs_review", 0),
            "unmatched": result["statistics"].get("unmatched", 0)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run batch matching: {str(e)}"
        )


@router.get("/batches/{batch_id}/results")
async def get_batch_match_results(
    batch_id: UUID,
    needs_review: Optional[bool] = None,
    current_user: dict = Depends(staff_required()),
    match_service: MatchService = Depends(get_match_service)
) -> List[MatchResultRead]:
    """
    Get all match results for a batch
    
    Args:
        batch_id: The batch ID to get results for
        needs_review: Filter for matches that need review (optional)
    """
    try:
        results = await match_service.get_match_results(
            batch_id=batch_id,
            needs_review=needs_review
        )
        return results
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get match results: {str(e)}"
        )


@router.get("/batches/{batch_id}/summary")
async def get_batch_match_summary(
    batch_id: UUID,
    current_user: dict = Depends(staff_required()),
    match_service: MatchService = Depends(get_match_service)
):
    """Get summary statistics for matches in a batch"""
    try:
        summary = await match_service.get_batch_match_summary(batch_id)
        return summary
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get match summary: {str(e)}"
        )


@router.get("/results")
async def get_match_results(
    batch_id: Optional[UUID] = None,
    ticket_id: Optional[UUID] = None,
    image_id: Optional[UUID] = None,
    needs_review: Optional[bool] = None,
    current_user: dict = Depends(staff_required()),
    match_service: MatchService = Depends(get_match_service)
) -> List[MatchResultRead]:
    """
    Get match results with optional filtering
    
    Args:
        batch_id: Filter by batch ID (optional)
        ticket_id: Filter by ticket ID (optional)
        image_id: Filter by image ID (optional)
        needs_review: Filter for matches that need review (optional)
    """
    try:
        results = await match_service.get_match_results(
            batch_id=batch_id,
            ticket_id=ticket_id,
            image_id=image_id,
            needs_review=needs_review
        )
        return results
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get match results: {str(e)}"
        )


@router.get("/results/{match_id}")
async def get_match_result(
    match_id: UUID,
    current_user: dict = Depends(staff_required()),
    match_service: MatchService = Depends(get_match_service)
) -> MatchResultRead:
    """Get a specific match result by ID"""
    try:
        result = await match_service.get_match_result(match_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Match result {match_id} not found"
            )
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get match result: {str(e)}"
        )


@router.post("/results/{match_id}/accept")
async def accept_match(
    match_id: UUID,
    decision: MatchDecision,
    request: Request = None,
    current_user: dict = Depends(staff_required()),
    match_service: MatchService = Depends(get_match_service)
) -> MatchResultRead:
    """
    Manually accept or reject a match result
    
    Requires PROCESSOR, MANAGER, or ADMIN role.
    """
    try:
        result = await match_service.accept_match(
            match_id=match_id,
            user_id=current_user['user_id'],
            decision=decision
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process match decision: {str(e)}"
        )


@router.post("/results/{match_id}/reject")
async def reject_match(
    match_id: UUID,
    reason: Optional[str] = None,
    request: Request = None,
    current_user: dict = Depends(staff_required()),
    match_service: MatchService = Depends(get_match_service)
) -> MatchResultRead:
    """
    Manually reject a match result
    
    Requires PROCESSOR, MANAGER, or ADMIN role.
    """
    try:
        result = await match_service.reject_match(
            match_id=match_id,
            user_id=current_user['user_id'],
            reason=reason
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject match: {str(e)}"
        )


@router.get("/review-queue")
async def get_review_queue(
    batch_id: Optional[UUID] = None,
    current_user: dict = Depends(staff_required()),
    match_service: MatchService = Depends(get_match_service)
) -> List[MatchResultRead]:
    """
    Get all matches that need manual review
    
    Args:
        batch_id: Filter by batch ID (optional)
    """
    try:
        results = await match_service.get_review_queue(batch_id=batch_id)
        return results
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get review queue: {str(e)}"
        )


# Statistics and monitoring endpoints

@router.get("/statistics")
async def get_matching_statistics(
    batch_id: Optional[UUID] = None,
    current_user: dict = Depends(staff_required()),
    match_service: MatchService = Depends(get_match_service)
):
    """
    Get overall matching statistics
    
    Requires MANAGER or ADMIN role.
    """
    try:
        if batch_id:
            summary = await match_service.get_batch_match_summary(batch_id)
            return {
                "batch_id": str(batch_id),
                "summary": summary.model_dump()
            }
        else:
            # Get statistics across all batches
            all_results = await match_service.get_match_results()
            
            if not all_results:
                return {
                    "total_matches": 0,
                    "auto_accepted": 0,
                    "needs_review": 0,
                    "rejected": 0,
                    "confidence_avg": 0.0
                }
            
            total_matches = len(all_results)
            auto_accepted = sum(1 for r in all_results if r.accepted and r.confidence >= 85.0)
            needs_review = sum(1 for r in all_results if not r.reviewed and 60.0 <= r.confidence < 85.0)
            rejected = sum(1 for r in all_results if r.reviewed and not r.accepted)
            
            confidences = [r.confidence for r in all_results]
            confidence_avg = sum(confidences) / len(confidences) if confidences else 0.0
            
            return {
                "total_matches": total_matches,
                "auto_accepted": auto_accepted,
                "needs_review": needs_review,
                "rejected": rejected,
                "confidence_avg": confidence_avg,
                "confidence_min": min(confidences) if confidences else 0.0,
                "confidence_max": max(confidences) if confidences else 0.0
            }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get matching statistics: {str(e)}"
        )