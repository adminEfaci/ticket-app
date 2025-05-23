from typing import List, Optional
from datetime import datetime, timedelta
from ..utils.datetime_utils import utcnow_naive
from uuid import UUID
from sqlmodel import Session, select
from ..models.session import Session as UserSession
import hashlib

class SessionService:
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def create_session(self, user_id: UUID, ip_address: str, user_agent: str, token: str) -> UserSession:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        session = UserSession(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            token_hash=token_hash
        )
        
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        return session
    
    def get_session_by_token(self, token: str) -> Optional[UserSession]:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        session = self.db.exec(select(UserSession).where(UserSession.token_hash == token_hash)).first()
        
        if session and session.is_expired():
            self.db.delete(session)
            self.db.commit()
            return None
        
        return session
    
    def get_user_sessions(self, user_id: UUID, requester_role: str, requester_id: UUID) -> List[UserSession]:
        if requester_role == "client" and str(user_id) != str(requester_id):
            return []
        
        sessions = self.db.exec(select(UserSession).where(UserSession.user_id == user_id)).all()
        
        active_sessions = []
        expired_sessions = []
        
        for session in sessions:
            if session.is_expired():
                expired_sessions.append(session)
            else:
                active_sessions.append(session)
        
        for expired_session in expired_sessions:
            self.db.delete(expired_session)
        
        if expired_sessions:
            self.db.commit()
        
        return active_sessions
    
    def revoke_session(self, session_id: UUID, requester_role: str, requester_id: UUID) -> bool:
        session = self.db.exec(select(UserSession).where(UserSession.id == session_id)).first()
        if not session:
            return False
        
        if requester_role == "client" and str(session.user_id) != str(requester_id):
            return False
        
        self.db.delete(session)
        self.db.commit()
        
        return True
    
    def revoke_user_sessions(self, user_id: UUID, requester_role: str, requester_id: UUID, exclude_session_id: UUID | None = None) -> int:
        if requester_role == "client" and str(user_id) != str(requester_id):
            return 0
        
        query = select(UserSession).where(UserSession.user_id == user_id)
        if exclude_session_id:
            query = query.where(UserSession.id != exclude_session_id)
        
        sessions = self.db.exec(query).all()
        
        count = len(sessions)
        for session in sessions:
            self.db.delete(session)
        
        if sessions:
            self.db.commit()
        
        return count
    
    def cleanup_expired_sessions(self) -> int:
        expired_sessions = self.db.exec(
            select(UserSession).where(UserSession.expires_at < utcnow_naive())
        ).all()
        
        count = len(expired_sessions)
        for session in expired_sessions:
            self.db.delete(session)
        
        if expired_sessions:
            self.db.commit()
        
        return count
    
    def extend_session(self, session_id: UUID, hours: int = 8) -> Optional[UserSession]:
        session = self.db.exec(select(UserSession).where(UserSession.id == session_id)).first()
        if not session or session.is_expired():
            return None
        
        session.expires_at = utcnow_naive() + timedelta(hours=hours)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        return session