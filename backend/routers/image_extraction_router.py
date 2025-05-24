from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import List
from uuid import UUID
import logging

from ..middleware.auth_middleware import authenticated_required, manager_or_admin_required
from ..core.database import get_session
from ..models.ticket_image import (
    TicketImageRead, TicketImageUpdate, ImageExtractionResult
)
from ..models.user import UserRole
from ..services.pdf_extraction_service import PDFExtractionService
from ..services.ocr_service import OCRService
from ..services.image_validator import ImageValidator
from ..services.image_export_service import ImageExportService
from ..services.ticket_image_service import TicketImageService
from ..services.batch_service import BatchService
from ..services.audit_service import AuditService
from ..utils.request_context import get_client_ip

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/batches",
    tags=["Image Extraction"],
    dependencies=[Depends(authenticated_required())]
)


@router.post("/{batch_id}/extract-images", response_model=ImageExtractionResult)
async def extract_images_from_batch(
    batch_id: UUID,
    current_user: dict = Depends(authenticated_required()),
    db=Depends(get_session),
    request: Request = None,
    client_ip: str = Depends(get_client_ip)
):
    """
    Extract ticket images from PDF for a batch
    
    Requires PROCESSOR, MANAGER, or ADMIN role
    """
    try:
        # Initialize services
        batch_service = BatchService(db)
        audit_service = AuditService(db)
        pdf_service = PDFExtractionService()
        ocr_service = OCRService()
        image_validator = ImageValidator()
        image_export_service = ImageExportService()
        ticket_image_service = TicketImageService(db, audit_service)
        
        user_id = current_user.get('id')
        user_role = current_user.get('role')
        
        # Check permissions
        if user_role not in [UserRole.PROCESSOR, UserRole.MANAGER, UserRole.ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for image extraction"
            )
        
        # Check user access to batch
        if not ticket_image_service.check_user_access(current_user, batch_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No access to this batch"
            )
        
        # Get batch information
        batch = batch_service.get_batch_by_id(batch_id)
        if not batch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Batch not found"
            )
        
        # Check if batch has a PDF file
        if not batch.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Batch does not contain a PDF file"
            )
        
        # Get PDF file path
        pdf_path = batch_service.get_batch_file_path(batch_id)
        if not pdf_path or not pdf_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PDF file not found"
            )
        
        # Validate PDF file
        if not pdf_service.validate_pdf_file(pdf_path):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or corrupted PDF file"
            )
        
        # Get PDF info for logging
        pdf_info = pdf_service.get_pdf_info(pdf_path)
        total_pages = pdf_info.get('page_count', 0)
        
        # Log extraction start
        audit_service.log_image_extraction_started(
            user_id=user_id,
            batch_id=batch_id,
            ip_address=client_ip,
            pdf_pages=total_pages
        )
        
        # Initialize extraction result
        extraction_result = ImageExtractionResult(
            pages_processed=0,
            images_extracted=0,
            images_failed=0,
            ocr_low_confidence=0,
            quality_failed=0,
            extraction_errors=[]
        )
        
        # Extract pages as images
        try:
            page_images = pdf_service.extract_pages_as_images(pdf_path)
            extraction_result.pages_processed = len(page_images)
            
            logger.info(f"Extracted {len(page_images)} pages from PDF {batch.filename}")
            
        except Exception as e:
            error_msg = f"Failed to extract pages from PDF: {str(e)}"
            logger.error(error_msg)
            extraction_result.extraction_errors.append(error_msg)
            
            # Log error and return early
            audit_service.log_image_extraction_error(
                batch_id=batch_id,
                page_number=0,
                error_type="pdf_extraction_failed",
                error_message=error_msg
            )
            
            return extraction_result
        
        # Process each page
        created_images = []
        errors = []
        
        for page_number, page_image in page_images:
            try:
                # Detect and crop tickets
                cropped_images = pdf_service.detect_and_crop_tickets(page_image, page_number)
                
                if not cropped_images:
                    error_msg = f"No tickets detected on page {page_number}"
                    errors.append(error_msg)
                    extraction_result.images_failed += 1
                    audit_service.log_image_extraction_error(
                        batch_id=batch_id,
                        page_number=page_number,
                        error_type="no_tickets_detected",
                        error_message=error_msg
                    )
                    continue
                
                # Process each cropped image (usually just one per page)
                for crop_index, cropped_image in enumerate(cropped_images):
                    try:
                        # Enhance image for processing
                        enhanced_image = pdf_service.enhance_image_for_processing(cropped_image)
                        
                        # Validate image quality
                        validation_result = image_validator.validate_image(enhanced_image)
                        
                        if not validation_result['valid']:
                            error_msg = f"Page {page_number} failed quality validation: {validation_result['errors']}"
                            errors.append(error_msg)
                            extraction_result.quality_failed += 1
                            
                            audit_service.log_image_quality_validation_failed(
                                batch_id=batch_id,
                                page_number=page_number,
                                validation_errors=validation_result['errors']
                            )
                            continue
                        
                        # Extract ticket number using OCR
                        ticket_number, ocr_confidence = ocr_service.extract_ticket_number(enhanced_image)
                        
                        # Check OCR confidence
                        if ocr_confidence < 80.0:
                            extraction_result.ocr_low_confidence += 1
                            audit_service.log_ocr_confidence_warning(
                                batch_id=batch_id,
                                page_number=page_number,
                                ticket_number=ticket_number,
                                confidence=ocr_confidence
                            )
                        
                        # Save image to file system
                        save_result = image_export_service.save_ticket_image(
                            enhanced_image, str(batch_id), ticket_number, page_number
                        )
                        
                        if not save_result['success']:
                            error_msg = f"Failed to save image for page {page_number}: {save_result.get('error', 'Unknown error')}"
                            errors.append(error_msg)
                            extraction_result.images_failed += 1
                            continue
                        
                        # Create database record
                        from ..models.ticket_image import TicketImageCreate
                        
                        ticket_image_data = TicketImageCreate(
                            batch_id=batch_id,
                            page_number=page_number,
                            image_path=save_result['image_path'],
                            ticket_number=ticket_number if ticket_number else None,
                            ocr_confidence=ocr_confidence if ocr_confidence > 0 else None,
                            valid=True
                        )
                        
                        ticket_image = ticket_image_service.create_ticket_image(ticket_image_data)
                        created_images.append(ticket_image)
                        extraction_result.images_extracted += 1
                        
                        # Log successful image creation
                        audit_service.log_ticket_image_created(
                            batch_id=batch_id,
                            image_id=ticket_image.id,
                            ticket_number=ticket_number,
                            ocr_confidence=ocr_confidence
                        )
                        
                        logger.info(f"Successfully extracted image from page {page_number}, "
                                   f"ticket: {ticket_number}, confidence: {ocr_confidence:.1f}%")
                        
                    except Exception as e:
                        error_msg = f"Error processing page {page_number}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        extraction_result.images_failed += 1
                        
                        audit_service.log_image_extraction_error(
                            batch_id=batch_id,
                            page_number=page_number,
                            error_type="image_processing_failed",
                            error_message=error_msg
                        )
            
            except Exception as e:
                error_msg = f"Error processing page {page_number}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                extraction_result.images_failed += 1
        
        # Update extraction result with errors
        extraction_result.extraction_errors = errors[:10]  # Limit to first 10 errors
        
        # Update batch with extraction results
        batch_service.update_batch_with_image_extraction_results(batch_id, extraction_result)
        
        # Log completion
        audit_service.log_image_extraction_completed(
            user_id=user_id,
            batch_id=batch_id,
            pages_processed=extraction_result.pages_processed,
            images_extracted=extraction_result.images_extracted,
            images_failed=extraction_result.images_failed
        )
        
        logger.info(f"Image extraction completed for batch {batch_id}: "
                   f"{extraction_result.images_extracted} extracted, "
                   f"{extraction_result.images_failed} failed")
        
        return extraction_result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in image extraction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during image extraction"
        )


@router.get("/{batch_id}/images", response_model=List[TicketImageRead])
async def list_batch_images(
    batch_id: UUID,
    skip: int = 0,
    limit: int = 100,
    valid_only: bool = False,
    current_user: dict = Depends(authenticated_required()),
    db=Depends(get_session)
):
    """
    List ticket images for a batch
    """
    try:
        ticket_image_service = TicketImageService(db)
        
        # Check user access
        if not ticket_image_service.check_user_access(current_user, batch_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No access to this batch"
            )
        
        images = ticket_image_service.get_ticket_images_by_batch_id(
            batch_id, skip=skip, limit=limit, valid_only=valid_only
        )
        
        return images
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing batch images: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list batch images"
        )


@router.get("/{batch_id}/image-statistics")
async def get_batch_image_statistics(
    batch_id: UUID,
    current_user: dict = Depends(authenticated_required()),
    db=Depends(get_session)
):
    """
    Get image statistics for a batch
    """
    try:
        ticket_image_service = TicketImageService(db)
        
        # Check user access
        if not ticket_image_service.check_user_access(current_user, batch_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No access to this batch"
            )
        
        stats = ticket_image_service.get_batch_image_statistics(batch_id)
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting batch image statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get image statistics"
        )


@router.get("/images/{image_id}", response_model=TicketImageRead)
async def get_ticket_image(
    image_id: UUID,
    current_user: dict = Depends(authenticated_required()),
    db=Depends(get_session)
):
    """
    Get ticket image metadata by ID
    """
    try:
        ticket_image_service = TicketImageService(db)
        
        image = ticket_image_service.get_ticket_image_by_id(image_id)
        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket image not found"
            )
        
        # Check user access to the batch
        if not ticket_image_service.check_user_access(current_user, image.batch_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No access to this image"
            )
        
        return image
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting ticket image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get ticket image"
        )


@router.put("/images/{image_id}", response_model=TicketImageRead)
async def update_ticket_image(
    image_id: UUID,
    update_data: TicketImageUpdate,
    current_user: dict = Depends(authenticated_required()),
    db=Depends(get_session)
):
    """
    Update ticket image metadata
    
    Requires MANAGER or ADMIN role
    """
    try:
        user_role = current_user.get('role')
        
        if user_role not in [UserRole.MANAGER, UserRole.ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to update ticket images"
            )
        
        ticket_image_service = TicketImageService(db)
        
        # Get existing image
        existing_image = ticket_image_service.get_ticket_image_by_id(image_id)
        if not existing_image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket image not found"
            )
        
        # Check user access
        if not ticket_image_service.check_user_access(current_user, existing_image.batch_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No access to this image"
            )
        
        # Update the image
        updated_image = ticket_image_service.update_ticket_image(image_id, update_data)
        if not updated_image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Failed to update ticket image"
            )
        
        return updated_image
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating ticket image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update ticket image"
        )


@router.delete("/images/{image_id}")
async def delete_ticket_image(
    image_id: UUID,
    current_user: dict = Depends(manager_or_admin_required()),
    db=Depends(get_session)
):
    """
    Delete a ticket image
    
    Requires MANAGER or ADMIN role
    """
    try:
        ticket_image_service = TicketImageService(db)
        audit_service = AuditService(db)
        image_export_service = ImageExportService()
        
        user_id = current_user.get('id')
        
        # Get existing image
        existing_image = ticket_image_service.get_ticket_image_by_id(image_id)
        if not existing_image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ticket image not found"
            )
        
        # Check user access
        if not ticket_image_service.check_user_access(current_user, existing_image.batch_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No access to this image"
            )
        
        # Delete image file
        image_export_service.delete_image(str(existing_image.batch_id), existing_image.image_path)
        
        # Delete database record
        success = ticket_image_service.delete_ticket_image(image_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Failed to delete ticket image"
            )
        
        # Log deletion
        audit_service.log_ticket_image_deleted(
            user_id=user_id,
            image_id=image_id,
            reason="Manual deletion by user"
        )
        
        return {"message": "Ticket image deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting ticket image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete ticket image"
        )