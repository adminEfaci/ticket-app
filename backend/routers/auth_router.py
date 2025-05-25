from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlmodel import Session
from ..models.user import UserLogin, UserCreate, UserRead
from ..services.auth_service import AuthService
from ..services.audit_service import AuditService
from ..middleware.auth_middleware import get_current_user, security, manager_or_admin_required
from ..core.database import get_session
from backend.models.user import User

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.post("/login")
async def login(
    user_credentials: UserLogin,
    request: Request,
    db: Session = Depends(get_session)
):
    auth_service = AuthService(db)
    audit_service = AuditService(db)
    
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    try:
        result = auth_service.authenticate_user(
            email=user_credentials.email,
            password=user_credentials.password,
            ip_address=client_ip,
            user_agent=user_agent
        )
        
        if not result:
            user = auth_service.get_user_by_email(user_credentials.email)
            if user:
                audit_service.log_login_attempt(
                    user_id=user.id,
                    ip_address=client_ip,
                    success=False,
                    details={"reason": "invalid_credentials"}
                )
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials or account locked",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        from uuid import UUID
        audit_service.log_login_attempt(
            user_id=UUID(result["user"]["id"]),
            ip_address=client_ip,
            success=True,
            details={"user_agent": user_agent}
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

@router.post("/logout")
async def logout(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    auth_service = AuthService(db)
    audit_service = AuditService(db)
    
    client_ip = request.client.host if request.client else "unknown"
    
    try:
        success = auth_service.logout_user(credentials.credentials)
        
        if success:
            audit_service.log_logout(
                user_id=current_user.id,
                ip_address=client_ip,
                session_id=current_user["session_id"]
            )
            
            return {"message": "Successfully logged out"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Logout failed"
            )
            
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )

@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    from ..services.user_service import UserService
    
    user_service = UserService(db)
    user = user_service.get_user_by_id(
        user_id=current_user.id,
        requester_role=current_user.role.value,
        requester_id=current_user.id
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserRead.model_validate(user)

@router.post("/register", response_model=UserRead)
async def register_user(
    user_data: UserCreate,
    request: Request,
    current_user: dict = Depends(manager_or_admin_required()),
    db: Session = Depends(get_session)
):
    auth_service = AuthService(db)
    audit_service = AuditService(db)
    
    client_ip = request.client.host if request.client else "unknown"
    
    try:
        user = auth_service.create_user(
            user_data=user_data,
            creator_role=current_user.role.value
        )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User creation failed. Email may already exist or invalid permissions."
            )
        
        audit_service.log_user_creation(
            creator_id=current_user.id,
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
            detail="User registration failed"
        )

@router.post("/validate-token")
async def validate_token(
    current_user: User = Depends(get_current_user)
):
    return {
        "valid": True,
        "user": current_user
    }