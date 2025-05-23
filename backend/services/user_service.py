from typing import List, Optional
from uuid import UUID
from sqlmodel import Session, select
from ..models.user import User, UserCreate, UserUpdate, UserRole
from ..core.auth import get_password_hash, validate_password_strength

class UserService:
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def get_user_by_id(self, user_id: UUID, requester_role: str, requester_id: UUID) -> Optional[User]:
        if requester_role == "client" and str(user_id) != str(requester_id):
            return None
        
        user = self.db.exec(select(User).where(User.id == user_id)).first()
        return user
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        user = self.db.exec(select(User).where(User.email == email)).first()
        return user
    
    def get_users(self, requester_role: str, skip: int = 0, limit: int = 100) -> List[User]:
        if requester_role == "client":
            return []
        
        query = select(User).offset(skip).limit(limit)
        
        if requester_role == "processor":
            query = query.where(User.role == UserRole.CLIENT)
        
        users = self.db.exec(query).all()
        return list(users)
    
    def create_user(self, user_data: UserCreate, creator_role: str) -> Optional[User]:
        if creator_role not in ["admin", "manager"]:
            return None
        
        if creator_role == "manager" and user_data.role.value == "admin":
            return None
        
        if not validate_password_strength(user_data.password):
            return None
        
        existing_user = self.db.exec(select(User).where(User.email == user_data.email)).first()
        if existing_user:
            return None
        
        user = User(
            email=user_data.email,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            role=user_data.role,
            hashed_password=get_password_hash(user_data.password),
            is_active=user_data.is_active
        )
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        return user
    
    def update_user(self, user_id: UUID, user_data: UserUpdate, updater_role: str, updater_id: UUID) -> Optional[User]:
        user = self.db.exec(select(User).where(User.id == user_id)).first()
        if not user:
            return None
        
        if updater_role == "client" and str(user_id) != str(updater_id):
            return None
        
        if updater_role == "client" and user_data.role is not None:
            return None
        
        if updater_role == "processor":
            return None
        
        if updater_role == "manager" and (user.role.value == "admin" or user_data.role.value == "admin"):
            return None
        
        update_data = user_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        return user
    
    def delete_user(self, user_id: UUID, deleter_role: str, deleter_id: UUID) -> bool:
        if deleter_role not in ["admin", "manager"]:
            return False
        
        if str(user_id) == str(deleter_id):
            return False
        
        user = self.db.exec(select(User).where(User.id == user_id)).first()
        if not user:
            return False
        
        if deleter_role == "manager" and user.role.value == "admin":
            return False
        
        self.db.delete(user)
        self.db.commit()
        
        return True
    
    def deactivate_user(self, user_id: UUID, deactivator_role: str, deactivator_id: UUID) -> Optional[User]:
        if deactivator_role not in ["admin", "manager"]:
            return None
        
        if str(user_id) == str(deactivator_id):
            return None
        
        user = self.db.exec(select(User).where(User.id == user_id)).first()
        if not user:
            return None
        
        if deactivator_role == "manager" and user.role.value == "admin":
            return None
        
        user.is_active = False
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        
        return user