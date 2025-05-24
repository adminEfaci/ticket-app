from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File
from fastapi.params import Query as QueryParam
from sqlmodel import Session

from ..models.batch import ProcessingBatchRead
from ..models.user import UserRole
from ..services.batch_service import BatchService
from ..services.upload_service import UploadService
from ..services.storage_service import StorageService
from ..services.validation_service import ValidationService
from ..services.audit_service import AuditService
from ..middleware.auth_middleware import authenticated_required
from ..core.database import get_session
import os

router = APIRouter(prefix="/upload", tags=["upload"])

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

@router.post("/pairs")
async def upload_file_pairs(
    request: Request,
    files: List[UploadFile] = File(...),
    current_user: dict = Depends(authenticated_required()),
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
    client_ip = request.client.host if request.client else "unknown"
    
    try:
        # Extract user information
        user_id = current_user["user_id"]
        user_role = UserRole(current_user["role"])
        
        # Determine client_id for client users
        client_id = user_id if user_role == UserRole.CLIENT else None
        
        # Extract file pairs from upload
        file_pairs, pairing_errors = upload_service.extract_file_pairs_from_upload(files)
        
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
        successful_batches, failed_batches = await upload_service.process_multiple_pairs(
            file_pairs, user_id, client_id
        )
        
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
            user_id=current_user["user_id"],
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
    current_user: dict = Depends(authenticated_required()),
    batch_service: BatchService = Depends(get_batch_service)
):
    """
    Get list of processing batches for the current user.
    
    Access control:
    - Clients: Only see their own batches
    - Processors/Managers: See all batches, can filter by client
    - Admins: See all batches, can filter by client
    """
    user_id = current_user["user_id"]
    user_role = UserRole(current_user["role"])
    
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
    current_user: dict = Depends(authenticated_required()),
    batch_service: BatchService = Depends(get_batch_service)
):
    """
    Get a specific processing batch by ID.
    
    Access control applied based on user role.
    """
    user_id = current_user["user_id"]
    user_role = UserRole(current_user["role"])
    
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
    current_user: dict = Depends(authenticated_required()),
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
    user_id = current_user["user_id"]
    user_role = UserRole(current_user["role"])
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
    current_user: dict = Depends(authenticated_required()),
    batch_service: BatchService = Depends(get_batch_service)
):
    """
    Get upload and batch statistics.
    
    Available to all authenticated users.
    """
    # Only admins and managers get full stats
    user_role = UserRole(current_user["role"])
    
    if user_role in [UserRole.ADMIN, UserRole.MANAGER]:
        return batch_service.get_batch_stats()
    else:
        # Limited stats for other users
        user_id = current_user["user_id"]
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