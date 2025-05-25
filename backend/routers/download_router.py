from uuid import UUID
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlmodel import Session

from backend.core.database import get_session
from backend.middleware.auth_middleware import get_current_user
from backend.models.user import User, UserRole
from backend.models.batch import ProcessingBatch
from backend.services.storage_service import StorageService

router = APIRouter(prefix="/download", tags=["download"])

def get_storage_service() -> StorageService:
    """Get storage service instance"""
    upload_path = "/data/batches"
    return StorageService(upload_path)

@router.get("/batch/{batch_id}/xls")
async def download_batch_xls(
    batch_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    storage: StorageService = Depends(get_storage_service)
):
    """
    Download original XLS file for a batch
    
    Access control based on user role and ownership
    """
    # Get batch
    batch = db.get(ProcessingBatch, batch_id)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    
    # Check access
    user_role = current_user.role
    if user_role == UserRole.CLIENT:
        # Clients can only access their own batches
        if batch.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
    
    # Get file path
    xls_path = storage.get_file_path(batch_id, "original.xls")
    if not xls_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="XLS file not found"
        )
    
    return FileResponse(
        path=str(xls_path),
        media_type="application/vnd.ms-excel",
        filename=batch.xls_filename or f"batch_{batch_id}.xls"
    )

@router.get("/batch/{batch_id}/pdf")
async def download_batch_pdf(
    batch_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    storage: StorageService = Depends(get_storage_service)
):
    """
    Download original PDF file for a batch
    
    Access control based on user role and ownership
    """
    # Get batch
    batch = db.get(ProcessingBatch, batch_id)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    
    # Check access
    user_role = current_user.role
    if user_role == UserRole.CLIENT:
        # Clients can only access their own batches
        if batch.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
    
    # Get file path
    pdf_path = storage.get_file_path(batch_id, "original.pdf")
    if not pdf_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF file not found"
        )
    
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=batch.pdf_filename or f"batch_{batch_id}.pdf"
    )

@router.get("/batch/{batch_id}/image/{image_filename}")
async def download_ticket_image(
    batch_id: UUID,
    image_filename: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session),
    storage: StorageService = Depends(get_storage_service)
):
    """
    Download a specific ticket image
    
    Access control based on user role and ownership
    """
    # Get batch
    batch = db.get(ProcessingBatch, batch_id)
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
    
    # Check access
    user_role = current_user.role
    if user_role == UserRole.CLIENT:
        # Clients can only access their own batches
        if batch.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
    
    # Get file path
    images_dir = Path(storage.get_batch_directory(batch_id)) / "images"
    image_path = images_dir / image_filename
    
    if not image_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image file not found"
        )
    
    # Determine media type
    if image_filename.lower().endswith('.png'):
        media_type = "image/png"
    elif image_filename.lower().endswith('.jpg') or image_filename.lower().endswith('.jpeg'):
        media_type = "image/jpeg"
    else:
        media_type = "application/octet-stream"
    
    return FileResponse(
        path=str(image_path),
        media_type=media_type,
        filename=image_filename
    )