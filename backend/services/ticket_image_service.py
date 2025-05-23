from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlmodel import Session
import logging

from ..models.ticket_image import (
    TicketImage, TicketImageCreate, TicketImageRead, TicketImageUpdate,
    ImageExtractionResult, ImageErrorLog
)
from ..models.user import UserRole

logger = logging.getLogger(__name__)


class TicketImageService:
    """
    Service for managing ticket image database operations
    """
    
    def __init__(self, db: Session, audit_service=None):
        self.db = db
        self.audit_service = audit_service
    
    def create_ticket_image(self, ticket_image_data: TicketImageCreate) -> TicketImage:
        """
        Create a new ticket image record
        
        Args:
            ticket_image_data: TicketImageCreate object
            
        Returns:
            Created TicketImage object
            
        Raises:
            Exception: If database operation fails
        """
        try:
            ticket_image = TicketImage(**ticket_image_data.model_dump())
            
            self.db.add(ticket_image)
            self.db.commit()
            self.db.refresh(ticket_image)
            
            logger.info(f"Created ticket image record: {ticket_image.id}")
            return ticket_image
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating ticket image: {e}")
            raise
    
    def create_ticket_images_batch(self, ticket_images_data: List[TicketImageCreate]) -> List[TicketImage]:
        """
        Create multiple ticket image records in a single transaction
        
        Args:
            ticket_images_data: List of TicketImageCreate objects
            
        Returns:
            List of created TicketImage objects
        """
        if not ticket_images_data:
            return []
        
        try:
            ticket_images = [TicketImage(**data.model_dump()) for data in ticket_images_data]
            
            self.db.add_all(ticket_images)
            self.db.commit()
            
            for ticket_image in ticket_images:
                self.db.refresh(ticket_image)
            
            logger.info(f"Created {len(ticket_images)} ticket image records")
            return ticket_images
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating batch ticket images: {e}")
            raise
    
    def get_ticket_image_by_id(self, image_id: UUID) -> Optional[TicketImage]:
        """
        Get a ticket image by ID
        
        Args:
            image_id: TicketImage ID
            
        Returns:
            TicketImage object or None if not found
        """
        try:
            return self.db.query(TicketImage).filter(TicketImage.id == image_id).first()
        except Exception as e:
            logger.error(f"Error getting ticket image {image_id}: {e}")
            return None
    
    def get_ticket_images_by_batch_id(self, batch_id: UUID, skip: int = 0, 
                                    limit: int = 100, valid_only: bool = False) -> List[TicketImage]:
        """
        Get ticket images for a specific batch
        
        Args:
            batch_id: Batch ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            valid_only: If True, return only valid images
            
        Returns:
            List of TicketImage objects
        """
        try:
            query = self.db.query(TicketImage).filter(TicketImage.batch_id == batch_id)
            
            if valid_only:
                query = query.filter(TicketImage.valid == True)
            
            return query.order_by(TicketImage.page_number).offset(skip).limit(limit).all()
            
        except Exception as e:
            logger.error(f"Error getting ticket images for batch {batch_id}: {e}")
            return []
    
    def update_ticket_image(self, image_id: UUID, update_data: TicketImageUpdate) -> Optional[TicketImage]:
        """
        Update a ticket image record
        
        Args:
            image_id: TicketImage ID
            update_data: TicketImageUpdate object
            
        Returns:
            Updated TicketImage object or None if not found
        """
        try:
            ticket_image = self.db.query(TicketImage).filter(TicketImage.id == image_id).first()
            
            if not ticket_image:
                return None
            
            # Update fields that are not None
            update_dict = update_data.model_dump(exclude_unset=True)
            for field, value in update_dict.items():
                setattr(ticket_image, field, value)
            
            self.db.commit()
            self.db.refresh(ticket_image)
            
            logger.info(f"Updated ticket image: {image_id}")
            return ticket_image
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating ticket image {image_id}: {e}")
            return None
    
    def delete_ticket_image(self, image_id: UUID) -> bool:
        """
        Delete a ticket image record
        
        Args:
            image_id: TicketImage ID
            
        Returns:
            True if deleted successfully
        """
        try:
            ticket_image = self.db.query(TicketImage).filter(TicketImage.id == image_id).first()
            
            if not ticket_image:
                return False
            
            self.db.delete(ticket_image)
            self.db.commit()
            
            logger.info(f"Deleted ticket image: {image_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting ticket image {image_id}: {e}")
            return False
    
    def get_batch_image_statistics(self, batch_id: UUID) -> Dict[str, Any]:
        """
        Get statistics for ticket images in a batch
        
        Args:
            batch_id: Batch ID
            
        Returns:
            Dictionary with image statistics
        """
        try:
            # Get all images for the batch
            all_images = self.db.query(TicketImage).filter(TicketImage.batch_id == batch_id).all()
            
            # Calculate statistics
            total_images = len(all_images)
            valid_images = sum(1 for img in all_images if img.valid)
            invalid_images = total_images - valid_images
            
            # OCR statistics
            images_with_ocr = [img for img in all_images if img.ocr_confidence is not None]
            high_confidence_ocr = sum(1 for img in images_with_ocr if img.ocr_confidence >= 0.8)
            
            # Average OCR confidence
            if images_with_ocr:
                avg_ocr_confidence = sum(img.ocr_confidence for img in images_with_ocr) / len(images_with_ocr)
            else:
                avg_ocr_confidence = 0.0
            
            # Detected ticket numbers
            detected_ticket_numbers = [img.ticket_number for img in all_images 
                                     if img.ticket_number and img.ticket_number.strip()]
            
            stats = {
                'total_images': total_images,
                'valid_images': valid_images,
                'invalid_images': invalid_images,
                'images_with_ocr': len(images_with_ocr),
                'high_confidence_ocr': high_confidence_ocr,
                'avg_ocr_confidence': avg_ocr_confidence,
                'detected_tickets': len(detected_ticket_numbers),
                'unique_ticket_numbers': len(set(detected_ticket_numbers)),
                'success_rate': (valid_images / total_images * 100.0) if total_images > 0 else 0.0
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting batch image statistics {batch_id}: {e}")
            return {
                'total_images': 0,
                'valid_images': 0,
                'invalid_images': 0,
                'images_with_ocr': 0,
                'high_confidence_ocr': 0,
                'avg_ocr_confidence': 0.0,
                'detected_tickets': 0,
                'unique_ticket_numbers': 0,
                'success_rate': 0.0,
                'error': str(e)
            }
    
    def mark_image_as_invalid(self, image_id: UUID, error_reason: str) -> bool:
        """
        Mark a ticket image as invalid with error reason
        
        Args:
            image_id: TicketImage ID
            error_reason: Reason for marking as invalid
            
        Returns:
            True if successfully updated
        """
        try:
            ticket_image = self.db.query(TicketImage).filter(TicketImage.id == image_id).first()
            
            if not ticket_image:
                return False
            
            ticket_image.valid = False
            ticket_image.error_reason = error_reason
            
            self.db.commit()
            
            logger.info(f"Marked image {image_id} as invalid: {error_reason}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error marking image as invalid {image_id}: {e}")
            return False
    
    def check_user_access(self, user: dict, batch_id: UUID) -> bool:
        """
        Check if user has access to ticket images for a batch
        
        Args:
            user: User dictionary with id and role
            batch_id: Batch ID
            
        Returns:
            True if user has access
        """
        try:
            user_role = user.get('role')
            
            # Admins have access to all batches
            if user_role == UserRole.ADMIN:
                return True
            
            # Managers have access to all batches
            if user_role == UserRole.MANAGER:
                return True
            
            # Processors can only access their own batches
            if user_role == UserRole.PROCESSOR:
                from ..models.batch import ProcessingBatch
                batch = self.db.query(ProcessingBatch).filter(
                    ProcessingBatch.id == batch_id
                ).first()
                
                if batch and batch.user_id == user.get('id'):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking user access: {e}")
            return False
    
    def save_extraction_errors(self, batch_id: UUID, errors: List[ImageErrorLog]) -> List[ImageErrorLog]:
        """
        Save image extraction error logs
        
        Args:
            batch_id: Batch ID
            errors: List of ImageErrorLog objects
            
        Returns:
            List of saved error records
        """
        if not errors:
            return []
        
        try:
            # Note: ImageErrorLog is not a table model in current implementation
            # This would need to be implemented if we want to persist errors
            # For now, just log them
            for error in errors:
                logger.error(f"Batch {batch_id} page {error.page_number}: "
                           f"{error.error_type} - {error.error_message}")
            
            return errors
            
        except Exception as e:
            logger.error(f"Error saving extraction errors: {e}")
            return []
    
    def process_extraction_results(self, batch_id: UUID, extraction_results: ImageExtractionResult,
                                 created_images: List[TicketImage], 
                                 errors: List[ImageErrorLog]) -> ImageExtractionResult:
        """
        Process and finalize image extraction results
        
        Args:
            batch_id: Batch ID
            extraction_results: Initial extraction results
            created_images: Successfully created TicketImage records
            errors: List of extraction errors
            
        Returns:
            Updated ImageExtractionResult
        """
        try:
            # Update extraction results with actual database counts
            extraction_results.images_extracted = len(created_images)
            extraction_results.images_failed = len(errors)
            
            # Count high/low confidence OCR results
            high_confidence = sum(1 for img in created_images 
                                if img.ocr_confidence and img.ocr_confidence >= 0.8)
            extraction_results.ocr_low_confidence = len(created_images) - high_confidence
            
            # Save error logs
            self.save_extraction_errors(batch_id, errors)
            
            # Log extraction results
            if self.audit_service:
                self.audit_service.log_image_extraction_completed(
                    batch_id=batch_id,
                    pages_processed=extraction_results.pages_processed,
                    images_extracted=extraction_results.images_extracted,
                    images_failed=extraction_results.images_failed
                )
            
            logger.info(f"Processed extraction results for batch {batch_id}: "
                       f"{extraction_results.images_extracted} extracted, "
                       f"{extraction_results.images_failed} failed")
            
            return extraction_results
            
        except Exception as e:
            logger.error(f"Error processing extraction results: {e}")
            return extraction_results
    
    def get_images_by_ticket_number(self, ticket_number: str, batch_id: Optional[UUID] = None) -> List[TicketImage]:
        """
        Find ticket images by ticket number
        
        Args:
            ticket_number: Ticket number to search for
            batch_id: Optional batch ID to limit search
            
        Returns:
            List of matching TicketImage objects
        """
        try:
            query = self.db.query(TicketImage).filter(TicketImage.ticket_number == ticket_number)
            
            if batch_id:
                query = query.filter(TicketImage.batch_id == batch_id)
            
            return query.all()
            
        except Exception as e:
            logger.error(f"Error searching images by ticket number {ticket_number}: {e}")
            return []
    
    def bulk_update_image_status(self, image_ids: List[UUID], valid: bool, 
                               error_reason: Optional[str] = None) -> int:
        """
        Bulk update validity status for multiple images
        
        Args:
            image_ids: List of TicketImage IDs
            valid: New validity status
            error_reason: Error reason if marking as invalid
            
        Returns:
            Number of images updated
        """
        try:
            update_data = {'valid': valid}
            if error_reason:
                update_data['error_reason'] = error_reason
            
            updated_count = self.db.query(TicketImage).filter(
                TicketImage.id.in_(image_ids)
            ).update(update_data, synchronize_session=False)
            
            self.db.commit()
            
            logger.info(f"Bulk updated {updated_count} ticket images")
            return updated_count
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error in bulk update: {e}")
            return 0