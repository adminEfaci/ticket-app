from datetime import timedelta
from ..utils.datetime_utils import utcnow_naive
from typing import Optional
from sqlmodel import Session, select
from ..core.auth import verify_password, get_password_hash, create_access_token, validate_password_strength
from ..models.user import User, UserCreate
from ..models.session import Session as UserSession
import hashlib

class AuthService:
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def authenticate_user(self, email: str, password: str, ip_address: str, user_agent: str) -> Optional[dict]:
        user = self.db.exec(select(User).where(User.email == email)).first()
        
        if not user:
            return None
        
        if user.locked_until and utcnow_naive() < user.locked_until:
            return None
        
        if not user.is_active:
            return None
        
        if not verify_password(password, user.hashed_password):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = utcnow_naive() + timedelta(minutes=30)
            self.db.add(user)
            self.db.commit()
            return None
        
        user.failed_login_attempts = 0
        user.locked_until = None
        self.db.add(user)
        
        token = create_access_token(
            data={"sub": str(user.id), "email": user.email, "role": user.role}
        )
        
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        session = UserSession(
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            token_hash=token_hash
        )
        self.db.add(session)
        self.db.commit()
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "role": user.role.value
            }
        }
    
    def logout_user(self, token: str) -> bool:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        session = self.db.exec(select(UserSession).where(UserSession.token_hash == token_hash)).first()
        
        if session:
            self.db.delete(session)
            self.db.commit()
            return True
        return False
    
    def validate_session(self, token: str) -> Optional[dict]:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        session = self.db.exec(select(UserSession).where(UserSession.token_hash == token_hash)).first()
        
        if not session or session.is_expired():
            if session:
                self.db.delete(session)
                self.db.commit()
            return None
        
        user = self.db.exec(select(User).where(User.id == session.user_id)).first()
        if not user or not user.is_active:
            return None
        
        return {
            "user_id": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "session_id": str(session.id)
        }
    
    def create_user(self, user_data: UserCreate, creator_role: str) -> Optional[User]:
        if creator_role not in ["admin", "manager"] and user_data.role.value in ["admin", "manager", "processor"]:
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
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        user = self.db.exec(select(User).where(User.email == email)).first()
        return user