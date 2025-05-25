from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File, Form
import logging
from fastapi.params import Query as QueryParam
from sqlmodel import Session

from ..models.batch import ProcessingBatchRead
from ..models.user import UserRole
from backend.models.user import User
from ..services.batch_service import BatchService
from ..services.upload_service import UploadService
from ..services.storage_service import StorageService
from ..services.validation_service import ValidationService
from ..services.audit_service import AuditService
from ..middleware.auth_middleware import authenticated_required
from ..core.database import get_session
import os

# Configure logging
logging.basicConfig(level=logging.INFO)

router = APIRouter(prefix="/upload", tags=["upload"])
logger = logging.getLogger(__name__)

# Initialize services
def get_storage_service() -> StorageService:
    upload_path = os.getenv("UPLOAD_PATH", "/data/batches")
    return StorageService(upload_path)

def get_validation_service() -> ValidationService:
    return ValidationService()

def get_upload_service(
    storage: StorageService = Depends(get_storage_service),
    validation: ValidationService = Depends(get_validation_service)
) -> UploadService:
    return UploadService(storage, validation)

def get_batch_service(
    db: Session = Depends(get_session),
    storage: StorageService = Depends(get_storage_service)
) -> BatchService:
    return BatchService(db, storage)

@router.post("/test")
async def test_upload(
    files: List[UploadFile] = File(...),
    client_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None)
):
    """Test endpoint to debug file uploads"""
    return {
        "files_count": len(files),
        "files": [{"name": f.filename, "size": f.size, "type": f.content_type} for f in files],
        "client_id": client_id,
        "description": description
    }

@router.post("/pairs", response_model=dict)
async def upload_file_pairs(
    files: List[UploadFile] = File(...),
    client_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    request: Request = None,
    current_user: User = Depends(authenticated_required()),
    upload_service: UploadService = Depends(get_upload_service),
    batch_service: BatchService = Depends(get_batch_service),
    audit_service: AuditService = Depends(lambda db=Depends(get_session): AuditService(db)),
    db: Session = Depends(get_session)
):
    """
    Upload multiple XLS+PDF file pairs.
    
    Each pair will create a separate processing batch.
    Maximum 30 pairs per request.
    """
    client_ip = request.client.host if request and request.client else "unknown"
    
    try:
        # Log incoming files for debugging
        logger.info(f"Received {len(files)} files for upload")
        logger.info(f"Client ID: {client_id}, Description: {description}")
        for file in files:
            logger.info(f"File: {file.filename}, Size: {file.size}, Content-Type: {file.content_type}")
        
        # Extract user information
        user_id = current_user.id
        user_role = UserRole(current_user.role.value)
        
        # Determine client_id - use provided client_id if admin/manager, otherwise use user_id for client users
        if user_role == UserRole.CLIENT:
            effective_client_id = user_id
        elif client_id and user_role in [UserRole.ADMIN, UserRole.MANAGER]:
            # Convert string UUID to UUID object
            try:
                effective_client_id = UUID(client_id) if client_id else None
            except ValueError:
                effective_client_id = None
        else:
            effective_client_id = None
        
        # Extract file pairs from upload
        logger.info("Extracting file pairs...")
        file_pairs, pairing_errors = upload_service.extract_file_pairs_from_upload(files)
        logger.info(f"Found {len(file_pairs)} pairs, {len(pairing_errors)} errors")
        
        if not file_pairs and pairing_errors:
            # Log the failed upload attempt
            audit_service.log_upload_attempt(
                user_id=user_id,
                ip_address=client_ip,
                success=False,
                file_count=len(files),
                details={"errors": pairing_errors}
            )
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "No valid file pairs found",
                    "errors": pairing_errors
                }
            )
        
        # Process file pairs
        logger.info(f"Processing {len(file_pairs)} file pairs...")
        successful_batches, failed_batches = await upload_service.process_multiple_pairs(
            file_pairs, user_id, effective_client_id
        )
        logger.info(f"Processing complete: {len(successful_batches)} successful, {len(failed_batches)} failed")
        
        # Create database records for successful batches
        created_batches = []
        for batch_data in successful_batches:
            # Check for duplicate hash
            if batch_service.check_duplicate_hash(batch_data["file_hash"]):
                # Clean up files
                upload_service.storage.delete_batch_directory(batch_data["id"])
                failed_batches.append({
                    "error": f"Duplicate files detected (hash: {batch_data['file_hash'][:16]}...)",
                    "xls_filename": batch_data["xls_filename"],
                    "pdf_filename": batch_data["pdf_filename"]
                })
                continue
            
            try:
                # Add description if provided
                if description:
                    batch_data["description"] = description
                batch = batch_service.create_batch(batch_data)
                created_batches.append(ProcessingBatchRead.model_validate(batch))
                
                # Log successful upload
                audit_service.log_upload_success(
                    user_id=user_id,
                    batch_id=batch.id,
                    ip_address=client_ip,
                    xls_filename=batch.xls_filename,
                    pdf_filename=batch.pdf_filename
                )
                
            except Exception as e:
                # Clean up files on database error
                upload_service.storage.delete_batch_directory(batch_data["id"])
                failed_batches.append({
                    "error": f"Database error: {str(e)}",
                    "xls_filename": batch_data["xls_filename"],
                    "pdf_filename": batch_data["pdf_filename"]
                })
        
        # Log overall upload attempt
        audit_service.log_upload_attempt(
            user_id=user_id,
            ip_address=client_ip,
            success=len(created_batches) > 0,
            file_count=len(files),
            details={
                "successful_batches": len(created_batches),
                "failed_batches": len(failed_batches),
                "pairing_errors": pairing_errors
            }
        )
        
        response_data = {
            "message": f"Upload completed: {len(created_batches)} successful, {len(failed_batches)} failed",
            "successful_batches": created_batches,
            "failed_batches": failed_batches + pairing_errors,
            "summary": {
                "total_files": len(files),
                "successful_pairs": len(created_batches),
                "failed_pairs": len(failed_batches),
                "pairing_errors": len(pairing_errors)
            }
        }
        
        # Return appropriate status code
        if not created_batches:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=response_data
            )
        elif failed_batches or pairing_errors:
            # Partial success
            return response_data
        else:
            # Complete success
            return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        # Log the error
        audit_service.log_upload_attempt(
            user_id=current_user.id,
            ip_address=client_ip,
            success=False,
            file_count=len(files),
            details={"error": str(e)}
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload processing failed: {str(e)}"
        )

@router.get("/batches", response_model=List[ProcessingBatchRead])
async def get_batches(
    skip: int = QueryParam(0, ge=0),
    limit: int = QueryParam(100, ge=1, le=1000),
    status: Optional[str] = QueryParam(None),
    client_id: Optional[UUID] = QueryParam(None),
    current_user: User = Depends(authenticated_required()),
    batch_service: BatchService = Depends(get_batch_service)
):
    """
    Get list of processing batches for the current user.
    
    Access control:
    - Clients: Only see their own batches
    - Processors/Managers: See all batches, can filter by client
    - Admins: See all batches, can filter by client
    """
    user_id = current_user.id
    user_role = UserRole(current_user.role.value)
    
    batches = batch_service.get_batches(
        requester_id=user_id,
        requester_role=user_role,
        skip=skip,
        limit=limit,
        status_filter=status,
        client_filter=client_id
    )
    
    return [ProcessingBatchRead.model_validate(batch) for batch in batches]

@router.get("/batches/{batch_id}", response_model=ProcessingBatchRead)
async def get_batch(
    batch_id: UUID,
    current_user: User = Depends(authenticated_required()),
    batch_service: BatchService = Depends(get_batch_service)
):
    """
    Get a specific processing batch by ID.
    
    Access control applied based on user role.
    """
    user_id = current_user.id
    user_role = UserRole(current_user.role.value)
    
    batch = batch_service.get_batch_by_id(batch_id, user_id, user_role)
    
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found or access denied"
        )
    
    return ProcessingBatchRead.model_validate(batch)

@router.delete("/batches/{batch_id}")
async def delete_batch(
    batch_id: UUID,
    request: Request,
    current_user: User = Depends(authenticated_required()),
    batch_service: BatchService = Depends(get_batch_service),
    audit_service: AuditService = Depends(lambda db=Depends(get_session): AuditService(db))
):
    """
    Delete a processing batch and its associated files.
    
    Access control:
    - Clients: Can only delete their own pending batches
    - Processors/Managers: Can delete any pending batch
    - Admins: Can delete any batch
    """
    user_id = current_user.id
    user_role = UserRole(current_user.role.value)
    client_ip = request.client.host if request.client else "unknown"
    
    # Get batch for audit logging
    batch = batch_service.get_batch_by_id(batch_id, user_id, user_role)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found or access denied"
        )
    
    success = batch_service.delete_batch(batch_id, user_id, user_role)
    
    if success:
        # Log successful deletion
        audit_service.log_batch_deletion(
            user_id=user_id,
            batch_id=batch_id,
            ip_address=client_ip,
            batch_status=batch.status
        )
        
        return {"message": "Batch deleted successfully"}
    else:
        # Log failed deletion attempt
        audit_service.log_batch_deletion_failed(
            user_id=user_id,
            batch_id=batch_id,
            ip_address=client_ip,
            reason="Permission denied or batch not in deletable state"
        )
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete batch. Check permissions and batch status."
        )

@router.get("/stats")
async def get_upload_stats(
    current_user: User = Depends(authenticated_required()),
    batch_service: BatchService = Depends(get_batch_service)
):
    """
    Get upload and batch statistics.
    
    Available to all authenticated users.
    """
    # Only admins and managers get full stats
    user_role = UserRole(current_user.role.value)
    
    if user_role in [UserRole.ADMIN, UserRole.MANAGER]:
        return batch_service.get_batch_stats()
    else:
        # Limited stats for other users
        user_id = current_user.id
        user_batches = batch_service.get_batches(
            requester_id=user_id,
            requester_role=user_role,
            skip=0,
            limit=1000  # Get all user batches for counting
        )
        
        user_stats = {
            "total_batches": len(user_batches),
            "pending_batches": len([b for b in user_batches if b.status == "pending"]),
            "ready_batches": len([b for b in user_batches if b.status == "ready"]),
            "error_batches": len([b for b in user_batches if b.status == "error"])
        }
        
        return user_stats

@router.get("/batches/{batch_id}/files")
async def get_batch_files(
    batch_id: UUID,
    current_user: User = Depends(authenticated_required()),
    batch_service: BatchService = Depends(get_batch_service),
    storage_service: StorageService = Depends(get_storage_service)
):
    """Get information about files in a batch"""
    user_role = UserRole(current_user.role.value)
    
    # Get batch with access control
    batch = batch_service.get_batch_by_id(batch_id, current_user.id, user_role)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found or access denied"
        )
    
    # Get file information
    files_info = storage_service.get_batch_files_info(batch_id)
    
    return {
        "batch_id": batch_id,
        "files": files_info,
        "xls_filename": batch.xls_filename,
        "pdf_filename": batch.pdf_filename
    }