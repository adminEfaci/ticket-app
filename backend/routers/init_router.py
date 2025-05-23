from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from ..models.user import User, UserRole
from ..services.auth_service import get_password_hash
from ..core.database import get_session

router = APIRouter(prefix="/init", tags=["initialization"])

@router.post("/admin")
async def create_initial_admin(db: Session = Depends(get_session)):
    """Create initial admin user if no users exist"""
    
    # Check if any users exist
    statement = select(User)
    existing_users = db.exec(statement).first()
    
    if existing_users:
        raise HTTPException(
            status_code=400,
            detail="Users already exist. Cannot create initial admin."
        )
    
    # Create admin user
    admin_user = User(
        username="admin",
        email="admin@example.com",
        full_name="Admin User",
        hashed_password=get_password_hash("admin123"),
        role=UserRole.ADMIN,
        is_active=True
    )
    
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    
    return {
        "message": "Admin user created successfully",
        "user": {
            "email": admin_user.email,
            "username": admin_user.username,
            "role": admin_user.role.value
        }
    }