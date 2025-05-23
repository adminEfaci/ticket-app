from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional
from ..services.auth_service import AuthService
from ..services.audit_service import AuditService
from ..core.database import get_session
from sqlmodel import Session
import functools

security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_session)
) -> dict:
    
    token = credentials.credentials
    
    auth_service = AuthService(db)
    user_data = auth_service.validate_session(token)
    
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_data

def require_roles(allowed_roles: List[str]):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user') or args[0] if args else None
            
            if not current_user or current_user.get('role') not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def audit_action(action: str, entity: Optional[str] = None):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request = None
            current_user = None
            db = None
            
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                elif isinstance(arg, dict) and 'user_id' in arg:
                    current_user = arg
                elif isinstance(arg, Session):
                    db = arg
            
            for key, value in kwargs.items():
                if isinstance(value, Request):
                    request = value
                elif isinstance(value, dict) and 'user_id' in value:
                    current_user = value
                elif isinstance(value, Session):
                    db = value
            
            if current_user and db and request:
                audit_service = AuditService(db)
                client_ip = request.client.host if request.client else "unknown"
                
                try:
                    result = await func(*args, **kwargs)
                    
                    entity_id = None
                    if hasattr(result, 'id'):
                        entity_id = result.id
                    elif isinstance(result, dict) and 'id' in result:
                        entity_id = result['id']
                    
                    await audit_service.log_action(
                        user_id=current_user['user_id'],
                        action=action,
                        ip_address=client_ip,
                        entity=entity,
                        entity_id=entity_id
                    )
                    
                    return result
                    
                except HTTPException as e:
                    if e.status_code == status.HTTP_403_FORBIDDEN:
                        await audit_service.log_permission_violation(
                            user_id=current_user['user_id'],
                            ip_address=client_ip,
                            attempted_action=action,
                            target_entity=entity
                        )
                    raise
                except Exception as e:
                    await audit_service.log_action(
                        user_id=current_user['user_id'],
                        action=f"{action}_failed",
                        ip_address=client_ip,
                        entity=entity,
                        details={"error": str(e)}
                    )
                    raise
            else:
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator

class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles
    
    def __call__(self, current_user: dict = Depends(get_current_user)):
        if current_user['role'] not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user

def admin_required():
    return RoleChecker(["admin"])

def manager_or_admin_required():
    return RoleChecker(["admin", "manager"])

def staff_required():
    return RoleChecker(["admin", "manager", "processor"])

def authenticated_required():
    return RoleChecker(["admin", "manager", "processor", "client"])