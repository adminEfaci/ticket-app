from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlmodel import Session, select
from ..utils.datetime_utils import utcnow_naive
import logging

from ..models.batch import ProcessingBatch, ProcessingBatchCreate, ProcessingBatchUpdate, BatchStatus
from ..models.user import UserRole
from ..models.ticket import TicketParsingResult
from .storage_service import StorageService

logger = logging.getLogger(__name__)

class BatchService:
    def __init__(self, db: Session, storage_service: Optional[StorageService] = None):
        self.db = db
        self.storage = storage_service or StorageService()
    
    def create_batch(self, batch_data: Dict[str, Any]) -> ProcessingBatch:
        """
        Create a new processing batch record.
        
        Args:
            batch_data: Dictionary containing batch information
            
        Returns:
            Created ProcessingBatch instance
        """
        batch_create = ProcessingBatchCreate(**batch_data)
        batch = ProcessingBatch.model_validate(batch_create)
        
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)
        
        return batch
    
    def get_batch_by_id(self, batch_id: UUID, requester_id: UUID, requester_role: UserRole) -> Optional[ProcessingBatch]:
        """
        Get a batch by ID with access control.
        
        Args:
            batch_id: Batch UUID
            requester_id: ID of user requesting the batch
            requester_role: Role of requesting user
            
        Returns:
            ProcessingBatch if found and accessible, None otherwise
        """
        query = select(ProcessingBatch).where(ProcessingBatch.id == batch_id)
        
        # Apply access control
        if requester_role == UserRole.CLIENT:
            # Clients can only see their own batches or batches assigned to them
            query = query.where(
                (ProcessingBatch.created_by == requester_id) |
                (ProcessingBatch.client_id == requester_id)
            )
        elif requester_role in [UserRole.PROCESSOR, UserRole.MANAGER]:
            # Processors and managers can see all batches
            pass
        elif requester_role == UserRole.ADMIN:
            # Admins can see all batches
            pass
        
        result = self.db.exec(query).first()
        return result
    
    def get_batches(
        self, 
        requester_id: UUID, 
        requester_role: UserRole,
        skip: int = 0,
        limit: int = 100,
        status_filter: Optional[str] = None,
        client_filter: Optional[UUID] = None
    ) -> List[ProcessingBatch]:
        """
        Get batches with access control and filtering.
        
        Args:
            requester_id: ID of user requesting the batches
            requester_role: Role of requesting user
            skip: Number of records to skip
            limit: Maximum number of records to return
            status_filter: Optional status to filter by
            client_filter: Optional client ID to filter by
            
        Returns:
            List of ProcessingBatch instances
        """
        query = select(ProcessingBatch)
        
        # Apply access control
        if requester_role == UserRole.CLIENT:
            # Clients can only see their own batches or batches assigned to them
            query = query.where(
                (ProcessingBatch.created_by == requester_id) |
                (ProcessingBatch.client_id == requester_id)
            )
        elif requester_role in [UserRole.PROCESSOR, UserRole.MANAGER]:
            # Processors and managers can see all batches, but apply client filter if provided
            if client_filter and requester_role == UserRole.PROCESSOR:
                # Processors might have client restrictions in a real system
                pass
        elif requester_role == UserRole.ADMIN:
            # Admins can see all batches
            pass
        
        # Apply filters
        if status_filter:
            query = query.where(ProcessingBatch.status == status_filter)
        
        if client_filter and requester_role != UserRole.CLIENT:
            query = query.where(ProcessingBatch.client_id == client_filter)
        
        # Apply pagination and ordering
        query = query.order_by(ProcessingBatch.uploaded_at.desc()).offset(skip).limit(limit)
        
        result = self.db.exec(query).all()
        return result
    
    def update_batch(self, batch_id: UUID, update_data: ProcessingBatchUpdate) -> Optional[ProcessingBatch]:
        """
        Update a batch record.
        
        Args:
            batch_id: Batch UUID
            update_data: Update data
            
        Returns:
            Updated ProcessingBatch if found, None otherwise
        """
        batch = self.db.get(ProcessingBatch, batch_id)
        if not batch:
            return None
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(batch, field, value)
        
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)
        
        return batch
    
    def mark_batch_as_processed(self, batch_id: UUID) -> Optional[ProcessingBatch]:
        """
        Mark a batch as processed.
        
        Args:
            batch_id: Batch UUID
            
        Returns:
            Updated ProcessingBatch if found, None otherwise
        """
        update_data = ProcessingBatchUpdate(
            status=BatchStatus.READY,
            processed_at=utcnow_naive()
        )
        return self.update_batch(batch_id, update_data)
    
    def mark_batch_as_error(self, batch_id: UUID, error_reason: str) -> Optional[ProcessingBatch]:
        """
        Mark a batch as having an error.
        
        Args:
            batch_id: Batch UUID
            error_reason: Description of the error
            
        Returns:
            Updated ProcessingBatch if found, None otherwise
        """
        update_data = ProcessingBatchUpdate(
            status=BatchStatus.ERROR,
            error_reason=error_reason
        )
        return self.update_batch(batch_id, update_data)
    
    def delete_batch(
        self, 
        batch_id: UUID, 
        requester_id: UUID, 
        requester_role: UserRole
    ) -> bool:
        """
        Delete a batch and its associated files.
        
        Args:
            batch_id: Batch UUID
            requester_id: ID of user requesting deletion
            requester_role: Role of requesting user
            
        Returns:
            True if deletion was successful, False otherwise
        """
        # Get the batch with access control
        batch = self.get_batch_by_id(batch_id, requester_id, requester_role)
        if not batch:
            return False
        
        # Check if user has permission to delete
        if requester_role == UserRole.CLIENT:
            # Clients can only delete their own pending batches
            if batch.created_by != requester_id or batch.status != BatchStatus.PENDING:
                return False
        elif requester_role in [UserRole.PROCESSOR, UserRole.MANAGER]:
            # Processors and managers can delete any pending batch
            if batch.status != BatchStatus.PENDING:
                return False
        elif requester_role == UserRole.ADMIN:
            # Admins can delete any batch
            pass
        
        try:
            # Delete files from storage
            self.storage.delete_batch_directory(batch_id)
            
            # Delete database record
            self.db.delete(batch)
            self.db.commit()
            
            return True
            
        except Exception:
            self.db.rollback()
            return False
    
    def check_duplicate_hash(self, file_hash: str, exclude_batch_id: Optional[UUID] = None) -> bool:
        """
        Check if a file hash already exists in the database.
        
        Args:
            file_hash: SHA256 hash to check
            exclude_batch_id: Optional batch ID to exclude from the check
            
        Returns:
            True if hash exists (duplicate), False otherwise
        """
        query = select(ProcessingBatch).where(ProcessingBatch.file_hash == file_hash)
        
        if exclude_batch_id:
            query = query.where(ProcessingBatch.id != exclude_batch_id)
        
        result = self.db.exec(query).first()
        return result is not None
    
    def get_batch_stats(self) -> Dict[str, Any]:
        """
        Get overall statistics about batches.
        
        Returns:
            Dictionary containing batch statistics
        """
        from sqlmodel import func
        
        total_batches = self.db.exec(select(func.count(ProcessingBatch.id))).first()
        
        pending_batches = self.db.exec(
            select(func.count(ProcessingBatch.id)).where(ProcessingBatch.status == BatchStatus.PENDING)
        ).first()
        
        ready_batches = self.db.exec(
            select(func.count(ProcessingBatch.id)).where(ProcessingBatch.status == BatchStatus.READY)
        ).first()
        
        error_batches = self.db.exec(
            select(func.count(ProcessingBatch.id)).where(ProcessingBatch.status == BatchStatus.ERROR)
        ).first()
        
        return {
            "total_batches": total_batches or 0,
            "pending_batches": pending_batches or 0,
            "ready_batches": ready_batches or 0,
            "error_batches": error_batches or 0,
            "processing_batches": (total_batches or 0) - (pending_batches or 0) - (ready_batches or 0) - (error_batches or 0)
        }
    
    def update_batch_with_parsing_results(self, batch_id: UUID, parsing_result: TicketParsingResult) -> ProcessingBatch:
        """
        Update batch status and stats after ticket parsing
        
        Args:
            batch_id: Processing batch ID
            parsing_result: Results from ticket parsing operation
            
        Returns:
            Updated ProcessingBatch
            
        Raises:
            ValueError: If batch not found
        """
        batch = self.db.exec(select(ProcessingBatch).where(ProcessingBatch.id == batch_id)).first()
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")
        
        # Update batch status based on parsing results
        if parsing_result.tickets_valid > 0:
            batch.status = BatchStatus.READY
        else:
            batch.status = BatchStatus.ERROR
        
        # Update stats
        if not batch.stats:
            batch.stats = {}
        
        batch.stats.update({
            "tickets_parsed": parsing_result.tickets_parsed,
            "tickets_valid": parsing_result.tickets_valid,
            "tickets_invalid": parsing_result.tickets_invalid,
            "duplicates_detected": parsing_result.duplicates_detected,
            "parsing_errors": parsing_result.errors,
            "parsed_at": utcnow_naive().isoformat()
        })
        
        # Update timestamps
        batch.updated_at = utcnow_naive()
        
        self.db.commit()
        self.db.refresh(batch)
        
        logger.info(f"Updated batch {batch_id} with parsing results: {parsing_result.tickets_valid} valid tickets")
        return batch
    
    def update_batch_with_image_extraction_results(self, batch_id: UUID, extraction_result) -> ProcessingBatch:
        """
        Update batch with image extraction results and statistics
        
        Args:
            batch_id: Batch ID to update
            extraction_result: ImageExtractionResult object
            
        Returns:
            Updated ProcessingBatch object
            
        Raises:
            ValueError: If batch not found
        """
        batch = self.db.exec(select(ProcessingBatch).where(ProcessingBatch.id == batch_id)).first()
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")
        
        # Update stats
        if not batch.stats:
            batch.stats = {}
        
        batch.stats.update({
            "pages_processed": extraction_result.pages_processed,
            "images_extracted": extraction_result.images_extracted,
            "images_failed": extraction_result.images_failed,
            "ocr_low_confidence": extraction_result.ocr_low_confidence,
            "quality_failed": extraction_result.quality_failed,
            "extraction_errors": extraction_result.extraction_errors,
            "extracted_at": utcnow_naive().isoformat()
        })
        
        # Update status based on results
        if extraction_result.images_extracted > 0:
            # If we have extracted images, keep status as ready for matching (Phase 5)
            if batch.status not in [BatchStatus.READY]:
                batch.status = BatchStatus.READY
        elif extraction_result.pages_processed > 0:
            # If we processed pages but extracted no images, mark as error
            batch.status = BatchStatus.ERROR
        
        # Update timestamps
        batch.updated_at = utcnow_naive()
        
        self.db.commit()
        self.db.refresh(batch)
        
        logger.info(f"Updated batch {batch_id} with image extraction results: {extraction_result.images_extracted} images extracted")
        return batch
    
    def get_batch_image_extraction_status(self, batch_id: UUID) -> Dict[str, Any]:
        """
        Get image extraction status for a batch
        
        Args:
            batch_id: Batch ID
            
        Returns:
            Dictionary with extraction status information
        """
        batch = self.db.exec(select(ProcessingBatch).where(ProcessingBatch.id == batch_id)).first()
        if not batch:
            return {
                'batch_found': False,
                'error': 'Batch not found'
            }
        
        stats = batch.stats or {}
        
        return {
            'batch_found': True,
            'batch_id': str(batch_id),
            'status': batch.status,
            'pages_processed': stats.get('pages_processed', 0),
            'images_extracted': stats.get('images_extracted', 0),
            'images_failed': stats.get('images_failed', 0),
            'ocr_low_confidence': stats.get('ocr_low_confidence', 0),
            'quality_failed': stats.get('quality_failed', 0),
            'extraction_success_rate': (
                stats.get('images_extracted', 0) / stats.get('pages_processed', 1) * 100.0
                if stats.get('pages_processed', 0) > 0 else 0.0
            ),
            'extracted_at': stats.get('extracted_at'),
            'extraction_errors': stats.get('extraction_errors', [])
        }
    
    def start_batch_parsing(self, batch_id: UUID) -> ProcessingBatch:
        """
        Mark batch as being parsed (set status to VALIDATING)
        
        Args:
            batch_id: Processing batch ID
            
        Returns:
            Updated ProcessingBatch
            
        Raises:
            ValueError: If batch not found or not in PENDING status
        """
        batch = self.db.exec(select(ProcessingBatch).where(ProcessingBatch.id == batch_id)).first()
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")
        
        if batch.status != BatchStatus.PENDING:
            raise ValueError(f"Batch {batch_id} is not in PENDING status (current: {batch.status})")
        
        batch.status = BatchStatus.VALIDATING
        
        # Initialize stats if not present
        if not batch.stats:
            batch.stats = {}
        
        batch.stats["parsing_started_at"] = utcnow_naive().isoformat()
        
        self.db.commit()
        self.db.refresh(batch)
        
        logger.info(f"Started parsing for batch {batch_id}")
        return batch
    
    def mark_batch_parsing_failed(self, batch_id: UUID, error_message: str) -> ProcessingBatch:
        """
        Mark batch parsing as failed
        
        Args:
            batch_id: Processing batch ID
            error_message: Error message describing the failure
            
        Returns:
            Updated ProcessingBatch
            
        Raises:
            ValueError: If batch not found
        """
        batch = self.db.exec(select(ProcessingBatch).where(ProcessingBatch.id == batch_id)).first()
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")
        
        batch.status = BatchStatus.ERROR
        batch.error_reason = error_message
        batch.updated_at = utcnow_naive()
        
        # Update stats
        if not batch.stats:
            batch.stats = {}
        
        batch.stats.update({
            "parsing_failed_at": utcnow_naive().isoformat(),
            "error_message": error_message
        })
        
        self.db.commit()
        self.db.refresh(batch)
        
        logger.error(f"Marked batch {batch_id} as failed: {error_message}")
        return batch
    
    def get_batch_parsing_status(self, batch_id: UUID) -> Dict[str, Any]:
        """
        Get parsing status and progress for a batch
        
        Args:
            batch_id: Processing batch ID
            
        Returns:
            Dictionary with parsing status information
            
        Raises:
            ValueError: If batch not found
        """
        batch = self.db.exec(select(ProcessingBatch).where(ProcessingBatch.id == batch_id)).first()
        if not batch:
            raise ValueError(f"Batch {batch_id} not found")
        
        status_info = {
            "batch_id": str(batch_id),
            "status": batch.status,
            "created_at": batch.uploaded_at.isoformat() if batch.uploaded_at else None,
            "updated_at": batch.updated_at.isoformat() if batch.updated_at else None,
            "error_reason": batch.error_reason
        }
        
        # Add parsing stats if available
        if batch.stats:
            status_info.update({
                "tickets_parsed": batch.stats.get("tickets_parsed", 0),
                "tickets_valid": batch.stats.get("tickets_valid", 0),
                "tickets_invalid": batch.stats.get("tickets_invalid", 0),
                "duplicates_detected": batch.stats.get("duplicates_detected", 0),
                "parsing_started_at": batch.stats.get("parsing_started_at"),
                "parsed_at": batch.stats.get("parsed_at"),
                "parsing_errors": batch.stats.get("parsing_errors", [])
            })
        
        return status_info