import logging
from datetime import date
from pathlib import Path
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlmodel import Session

from ..core.database import get_session
from ..middleware.auth_middleware import get_current_user
from ..models.user import User, UserRole
from ..models.export import ExportRequest, ExportResult
from ..services.export_bundle_service import ExportBundleService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/export", tags=["export"])


@router.post("/invoices-bundle", response_model=ExportResult)
async def create_export_bundle(
    export_request: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Create export bundle (ZIP file) with invoices and images
    
    Requires ADMIN or MANAGER role.
    """
    # Check permissions
    if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
        raise HTTPException(
            status_code=403,
            detail="Only administrators and managers can create exports"
        )
    
    export_service = ExportBundleService(db)
    
    try:
        result = await export_service.create_export_bundle(
            export_request=export_request,
            user_id=current_user.id
        )
        
        if not result.success:
            raise HTTPException(
                status_code=400,
                detail=result.error_message or "Export failed"
            )
        
        return result
        
    except Exception as e:
        logger.exception("Export creation failed")
        raise HTTPException(
            status_code=500,
            detail=f"Export failed: {str(e)}"
        )


@router.get("/invoices-bundle/{date_str}")
async def export_weekly_bundle(
    date_str: str,
    force: bool = False,
    include_images: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Create and download weekly export bundle
    
    Args:
        date_str: Date in YYYY-MM-DD format (any date in the week)
        force: Force export even if validation fails
        include_images: Include ticket images in export
    """
    # Check permissions
    if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
        raise HTTPException(
            status_code=403,
            detail="Only administrators and managers can create exports"
        )
    
    try:
        # Parse date
        target_date = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use YYYY-MM-DD"
        )
    
    # Create export request
    export_request = ExportRequest(
        start_date=target_date,
        export_type="weekly",
        include_images=include_images,
        force_export=force
    )
    
    export_service = ExportBundleService(db)
    
    # Create export
    result = await export_service.create_export_bundle(
        export_request=export_request,
        user_id=current_user.id
    )
    
    if not result.success:
        raise HTTPException(
            status_code=400,
            detail=result.error_message or "Export failed"
        )
    
    # Return file
    if result.file_path:
        file_path = Path(result.file_path)
        if file_path.exists():
            return FileResponse(
                path=str(file_path),
                media_type='application/zip',
                filename=file_path.name
            )
    
    raise HTTPException(
        status_code=404,
        detail="Export file not found"
    )


@router.get("/download/{export_id}")
async def download_export(
    export_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Download a previously generated export
    """
    # Check permissions
    if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER, UserRole.VIEWER]:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to download exports"
        )
    
    export_service = ExportBundleService(db)
    
    # Get file path
    file_path = export_service.get_export_file_path(export_id)
    
    if not file_path:
        raise HTTPException(
            status_code=404,
            detail="Export not found or file no longer exists"
        )
    
    return FileResponse(
        path=str(file_path),
        media_type='application/zip',
        filename=file_path.name
    )


@router.post("/validate")
async def validate_export_data(
    export_request: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """
    Validate export data without creating the export
    
    Returns validation results including any errors or warnings.
    """
    # Check permissions
    if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER]:
        raise HTTPException(
            status_code=403,
            detail="Only administrators and managers can validate exports"
        )
    
    export_service = ExportBundleService(db)
    
    # Get tickets
    tickets = export_service.weekly_export_service.get_tickets_for_export(
        start_date=export_request.start_date,
        end_date=export_request.end_date,
        client_ids=export_request.client_ids
    )
    
    # Validate
    validation = export_service.weekly_export_service.validate_export_data(
        tickets=tickets,
        require_images=export_request.include_images
    )
    
    return {
        "validation": validation,
        "can_export": not validation.has_critical_errors,
        "ticket_count": len(tickets),
        "require_force": validation.has_critical_errors and len(tickets) > 0
    }