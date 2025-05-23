from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.params import Query
from sqlmodel import Session
from ..models.user import UserRead, UserCreate, UserUpdate
from ..services.user_service import UserService
from ..services.audit_service import AuditService
from ..middleware.auth_middleware import (
    manager_or_admin_required, 
    staff_required,
    authenticated_required
)
from ..core.database import get_session

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/", response_model=List[UserRead])
async def get_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: dict = Depends(staff_required()),
    db: Session = Depends(get_session)
):
    user_service = UserService(db)
    
    users = user_service.get_users(
        requester_role=current_user["role"],
        skip=skip,
        limit=limit
    )
    
    return [UserRead.model_validate(user) for user in users]

@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: UUID,
    current_user: dict = Depends(authenticated_required()),
    db: Session = Depends(get_session)
):
    user_service = UserService(db)
    
    user = user_service.get_user_by_id(
        user_id=user_id,
        requester_role=current_user["role"],
        requester_id=current_user["user_id"]
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found or access denied"
        )
    
    return UserRead.model_validate(user)

@router.post("/", response_model=UserRead)
async def create_user(
    user_data: UserCreate,
    request: Request,
    current_user: dict = Depends(manager_or_admin_required()),
    db: Session = Depends(get_session)
):
    user_service = UserService(db)
    audit_service = AuditService(db)
    
    client_ip = request.client.host if request.client else "unknown"
    
    try:
        user = user_service.create_user(
            user_data=user_data,
            creator_role=current_user["role"]
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User creation failed. Email may already exist or insufficient permissions."
            )
        
        audit_service.log_user_creation(
            creator_id=current_user["user_id"],
            created_user_id=user.id,
            ip_address=client_ip,
            role=user.role
        )
        
        return UserRead.model_validate(user)
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User creation failed"
        )

@router.put("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    request: Request,
    current_user: dict = Depends(authenticated_required()),
    db: Session = Depends(get_session)
):
    user_service = UserService(db)
    audit_service = AuditService(db)
    
    client_ip = request.client.host if request.client else "unknown"
    
    try:
        user = user_service.update_user(
            user_id=user_id,
            user_data=user_data,
            updater_role=current_user["role"],
            updater_id=current_user["user_id"]
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or insufficient permissions"
            )
        
        changes = user_data.dict(exclude_unset=True)
        audit_service.log_user_update(
            updater_id=current_user["user_id"],
            updated_user_id=user_id,
            ip_address=client_ip,
            changes=changes
        )
        
        return UserRead.model_validate(user)
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User update failed"
        )

@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    request: Request,
    current_user: dict = Depends(manager_or_admin_required()),
    db: Session = Depends(get_session)
):
    user_service = UserService(db)
    audit_service = AuditService(db)
    
    client_ip = request.client.host if request.client else "unknown"
    
    try:
        success = user_service.delete_user(
            user_id=user_id,
            deleter_role=current_user["role"],
            deleter_id=current_user["user_id"]
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or insufficient permissions"
            )
        
        audit_service.log_user_deletion(
            deleter_id=current_user["user_id"],
            deleted_user_id=user_id,
            ip_address=client_ip
        )
        
        return {"message": "User deleted successfully"}
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User deletion failed"
        )

@router.post("/{user_id}/deactivate", response_model=UserRead)
async def deactivate_user(
    user_id: UUID,
    request: Request,
    current_user: dict = Depends(manager_or_admin_required()),
    db: Session = Depends(get_session)
):
    user_service = UserService(db)
    audit_service = AuditService(db)
    
    client_ip = request.client.host if request.client else "unknown"
    
    try:
        user = user_service.deactivate_user(
            user_id=user_id,
            deactivator_role=current_user["role"],
            deactivator_id=current_user["user_id"]
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or insufficient permissions"
            )
        
        audit_service.log_user_update(
            updater_id=current_user["user_id"],
            updated_user_id=user_id,
            ip_address=client_ip,
            changes={"is_active": False, "action": "deactivated"}
        )
        
        return UserRead.model_validate(user)
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User deactivation failed"
        )