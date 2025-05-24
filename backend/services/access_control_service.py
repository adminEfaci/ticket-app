from datetime import datetime
from ..utils.datetime_utils import utcnow_naive
from typing import List, Optional, Dict, Set
from uuid import UUID, uuid4
from enum import Enum

from sqlmodel import SQLModel, Field, Session, select, and_
from backend.core.database import get_session
from backend.models.user import User, UserRole
from backend.models.client import Client
from backend.services.audit_service import AuditService, AuditEventType


class Permission(str, Enum):
    """System permissions"""
    # Client permissions
    CLIENT_READ = "client:read"
    CLIENT_CREATE = "client:create"
    CLIENT_UPDATE = "client:update"
    CLIENT_DELETE = "client:delete"
    
    # Rate permissions
    RATE_READ = "rate:read"
    RATE_CREATE = "rate:create"
    RATE_UPDATE = "rate:update"
    RATE_DELETE = "rate:delete"
    RATE_APPROVE = "rate:approve"
    
    # Reference permissions
    REFERENCE_READ = "reference:read"
    REFERENCE_CREATE = "reference:create"
    REFERENCE_UPDATE = "reference:update"
    REFERENCE_DELETE = "reference:delete"
    
    # Billing permissions
    BILLING_READ = "billing:read"
    BILLING_UPDATE = "billing:update"
    
    # Ticket permissions
    TICKET_READ = "ticket:read"
    TICKET_CREATE = "ticket:create"
    TICKET_UPDATE = "ticket:update"
    TICKET_DELETE = "ticket:delete"
    TICKET_ASSIGN = "ticket:assign"
    
    # User management permissions
    USER_READ = "user:read"
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    
    # System permissions
    SYSTEM_ADMIN = "system:admin"
    AUDIT_READ = "audit:read"


class ClientUserAccess(SQLModel, table=True):
    """Junction table for client-user access control"""
    __tablename__ = "client_user_access"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    client_id: UUID = Field(foreign_key="client.id", index=True)
    permissions: str = Field(description="Comma-separated list of permissions")
    granted_by: UUID = Field(foreign_key="user.id", description="User who granted access")
    created_at: datetime = Field(default_factory=utcnow_naive)
    expires_at: Optional[datetime] = Field(default=None, description="When access expires")
    active: bool = Field(default=True)


class AccessControlService:
    """Service for managing access control and permissions"""
    
    # Role-based default permissions
    ROLE_PERMISSIONS = {
        UserRole.ADMIN: [
            Permission.SYSTEM_ADMIN,
            Permission.CLIENT_READ, Permission.CLIENT_CREATE, Permission.CLIENT_UPDATE, Permission.CLIENT_DELETE,
            Permission.RATE_READ, Permission.RATE_CREATE, Permission.RATE_UPDATE, Permission.RATE_DELETE, Permission.RATE_APPROVE,
            Permission.REFERENCE_READ, Permission.REFERENCE_CREATE, Permission.REFERENCE_UPDATE, Permission.REFERENCE_DELETE,
            Permission.BILLING_READ, Permission.BILLING_UPDATE,
            Permission.TICKET_READ, Permission.TICKET_CREATE, Permission.TICKET_UPDATE, Permission.TICKET_DELETE, Permission.TICKET_ASSIGN,
            Permission.USER_READ, Permission.USER_CREATE, Permission.USER_UPDATE, Permission.USER_DELETE,
            Permission.AUDIT_READ
        ],
        UserRole.MANAGER: [
            Permission.CLIENT_READ, Permission.CLIENT_CREATE, Permission.CLIENT_UPDATE,
            Permission.RATE_READ, Permission.RATE_CREATE, Permission.RATE_UPDATE, Permission.RATE_APPROVE,
            Permission.REFERENCE_READ, Permission.REFERENCE_CREATE, Permission.REFERENCE_UPDATE,
            Permission.BILLING_READ, Permission.BILLING_UPDATE,
            Permission.TICKET_READ, Permission.TICKET_CREATE, Permission.TICKET_UPDATE, Permission.TICKET_ASSIGN,
            Permission.USER_READ, Permission.USER_CREATE, Permission.USER_UPDATE,
            Permission.AUDIT_READ
        ],
        UserRole.PROCESSOR: [
            Permission.CLIENT_READ,
            Permission.RATE_READ,
            Permission.REFERENCE_READ,
            Permission.BILLING_READ,
            Permission.TICKET_READ, Permission.TICKET_CREATE, Permission.TICKET_UPDATE
        ],
        UserRole.CLIENT: [
            Permission.CLIENT_READ,  # Limited to own client
            Permission.RATE_READ,    # Limited to own client
            Permission.BILLING_READ, # Limited to own client
            Permission.TICKET_READ,  # Limited to own client tickets
        ]
    }
    
    def __init__(self, session: Session = None):
        self.session = session or next(get_session())
        self.audit_service = AuditService(self.session)
    
    async def check_permission(
        self, 
        user_id: UUID, 
        permission: Permission,
        client_id: Optional[UUID] = None
    ) -> bool:
        """
        Check if a user has a specific permission
        
        Args:
            user_id: User ID
            permission: Permission to check
            client_id: Optional client ID for scoped permissions
        
        Returns:
            True if user has permission, False otherwise
        """
        user = self.session.get(User, user_id)
        if not user or not user.is_active:
            return False
        
        # Get role-based permissions
        role_permissions = self.ROLE_PERMISSIONS.get(user.role, [])
        
        # Check if user has global permission
        if permission in role_permissions:
            # For client users, only allow access to their assigned clients
            if user.role == UserRole.CLIENT and client_id:
                return await self._user_has_client_access(user_id, client_id)
            return True
        
        # Check client-scoped permissions
        if client_id:
            client_permissions = await self._get_user_client_permissions(user_id, client_id)
            return permission in client_permissions
        
        return False
    
    async def grant_client_access(
        self,
        user_id: UUID,
        client_id: UUID,
        permissions: List[Permission],
        granted_by: UUID,
        expires_at: Optional[datetime] = None
    ) -> bool:
        """
        Grant specific permissions to a user for a client
        
        Args:
            user_id: User to grant access to
            client_id: Client to grant access for
            permissions: List of permissions to grant
            granted_by: User granting the access
            expires_at: When access expires (optional)
        
        Returns:
            True if access granted successfully
        """
        # Validate users and client exist
        user = self.session.get(User, user_id)
        client = self.session.get(Client, client_id)
        grantor = self.session.get(User, granted_by)
        
        if not all([user, client, grantor]):
            return False
        
        # Check if grantor has permission to grant these permissions
        for perm in permissions:
            if not await self.check_permission(granted_by, perm, client_id):
                return False
        
        # Remove existing access for this user-client pair
        existing = self.session.exec(
            select(ClientUserAccess).where(
                and_(
                    ClientUserAccess.user_id == user_id,
                    ClientUserAccess.client_id == client_id,
                    ClientUserAccess.active
                )
            )
        ).first()
        
        if existing:
            existing.active = False
            self.session.add(existing)
        
        # Create new access record
        access = ClientUserAccess(
            user_id=user_id,
            client_id=client_id,
            permissions=",".join([p.value for p in permissions]),
            granted_by=granted_by,
            expires_at=expires_at
        )
        
        self.session.add(access)
        self.session.commit()
        
        # Log audit event
        await self.audit_service.log_event(
            event_type=AuditEventType.CLIENT_UPDATED,
            entity_type="ClientUserAccess",
            entity_id=access.id,
            user_id=granted_by,
            details={
                "action": "grant_access",
                "target_user_id": str(user_id),
                "client_id": str(client_id),
                "permissions": [p.value for p in permissions],
                "expires_at": expires_at.isoformat() if expires_at else None
            }
        )
        
        return True
    
    async def revoke_client_access(
        self,
        user_id: UUID,
        client_id: UUID,
        revoked_by: UUID
    ) -> bool:
        """
        Revoke all access for a user to a client
        
        Args:
            user_id: User to revoke access from
            client_id: Client to revoke access for
            revoked_by: User revoking the access
        
        Returns:
            True if access revoked successfully
        """
        # Check if revoker has permission
        if not await self.check_permission(revoked_by, Permission.CLIENT_UPDATE, client_id):
            return False
        
        # Find and deactivate access
        access = self.session.exec(
            select(ClientUserAccess).where(
                and_(
                    ClientUserAccess.user_id == user_id,
                    ClientUserAccess.client_id == client_id,
                    ClientUserAccess.active
                )
            )
        ).first()
        
        if not access:
            return False
        
        access.active = False
        self.session.add(access)
        self.session.commit()
        
        # Log audit event
        await self.audit_service.log_event(
            event_type=AuditEventType.CLIENT_UPDATED,
            entity_type="ClientUserAccess",
            entity_id=access.id,
            user_id=revoked_by,
            details={
                "action": "revoke_access",
                "target_user_id": str(user_id),
                "client_id": str(client_id)
            }
        )
        
        return True
    
    async def get_user_permissions(
        self, 
        user_id: UUID,
        client_id: Optional[UUID] = None
    ) -> List[Permission]:
        """
        Get all permissions for a user (global + client-specific)
        
        Args:
            user_id: User ID
            client_id: Optional client ID for scoped permissions
        
        Returns:
            List of permissions
        """
        user = self.session.get(User, user_id)
        if not user or not user.is_active:
            return []
        
        # Start with role-based permissions
        permissions = set(self.ROLE_PERMISSIONS.get(user.role, []))
        
        # Add client-specific permissions
        if client_id:
            client_permissions = await self._get_user_client_permissions(user_id, client_id)
            permissions.update(client_permissions)
        
        return list(permissions)
    
    async def get_user_clients(self, user_id: UUID) -> List[Dict]:
        """
        Get all clients a user has access to
        
        Args:
            user_id: User ID
        
        Returns:
            List of client access information
        """
        user = self.session.get(User, user_id)
        if not user or not user.is_active:
            return []
        
        # For admin/manager roles, return all active clients
        if user.role in [UserRole.ADMIN, UserRole.MANAGER]:
            clients = self.session.exec(
                select(Client).where(Client.active)
            ).all()
            
            return [
                {
                    "client_id": client.id,
                    "client_name": client.name,
                    "access_type": "role_based",
                    "permissions": [p.value for p in self.ROLE_PERMISSIONS[user.role]]
                }
                for client in clients
            ]
        
        # For other roles, return explicitly granted access
        statement = select(ClientUserAccess, Client).join(
            Client, ClientUserAccess.client_id == Client.id
        ).where(
            and_(
                ClientUserAccess.user_id == user_id,
                ClientUserAccess.active,
                Client.active,
                ClientUserAccess.expires_at.is_(None) | (ClientUserAccess.expires_at > utcnow_naive())
            )
        )
        
        results = self.session.exec(statement).all()
        
        client_access = []
        for access, client in results:
            client_access.append({
                "client_id": client.id,
                "client_name": client.name,
                "access_type": "explicit",
                "permissions": access.permissions.split(",") if access.permissions else [],
                "granted_by": access.granted_by,
                "expires_at": access.expires_at.isoformat() if access.expires_at else None
            })
        
        return client_access
    
    async def get_client_users(self, client_id: UUID) -> List[Dict]:
        """
        Get all users with access to a client
        
        Args:
            client_id: Client ID
        
        Returns:
            List of user access information
        """
        # Get explicitly granted access
        statement = select(ClientUserAccess, User).join(
            User, ClientUserAccess.user_id == User.id
        ).where(
            and_(
                ClientUserAccess.client_id == client_id,
                ClientUserAccess.active,
                User.is_active,
                ClientUserAccess.expires_at.is_(None) | (ClientUserAccess.expires_at > utcnow_naive())
            )
        )
        
        explicit_access = self.session.exec(statement).all()
        
        # Get role-based access (admin/manager)
        role_users = self.session.exec(
            select(User).where(
                and_(
                    User.role.in_([UserRole.ADMIN, UserRole.MANAGER]),
                    User.is_active
                )
            )
        ).all()
        
        user_access = []
        
        # Add explicit access
        for access, user in explicit_access:
            user_access.append({
                "user_id": user.id,
                "email": user.email,
                "name": f"{user.first_name} {user.last_name}",
                "role": user.role.value,
                "access_type": "explicit",
                "permissions": access.permissions.split(",") if access.permissions else [],
                "granted_by": access.granted_by,
                "expires_at": access.expires_at.isoformat() if access.expires_at else None
            })
        
        # Add role-based access
        for user in role_users:
            # Skip if already in explicit access
            if any(ua["user_id"] == user.id for ua in user_access):
                continue
            
            user_access.append({
                "user_id": user.id,
                "email": user.email,
                "name": f"{user.first_name} {user.last_name}",
                "role": user.role.value,
                "access_type": "role_based",
                "permissions": [p.value for p in self.ROLE_PERMISSIONS[user.role]],
                "granted_by": None,
                "expires_at": None
            })
        
        return user_access
    
    async def cleanup_expired_access(self) -> int:
        """
        Clean up expired access records
        
        Returns:
            Number of records cleaned up
        """
        now = utcnow_naive()
        
        expired_access = self.session.exec(
            select(ClientUserAccess).where(
                and_(
                    ClientUserAccess.active,
                    ClientUserAccess.expires_at < now
                )
            )
        ).all()
        
        count = 0
        for access in expired_access:
            access.active = False
            self.session.add(access)
            count += 1
        
        if count > 0:
            self.session.commit()
            
            # Log cleanup event
            await self.audit_service.log_event(
                event_type=AuditEventType.CLIENT_UPDATED,
                entity_type="ClientUserAccess",
                entity_id=None,
                user_id=None,
                details={
                    "action": "cleanup_expired_access",
                    "expired_records": count
                }
            )
        
        return count
    
    async def _get_user_client_permissions(
        self, 
        user_id: UUID, 
        client_id: UUID
    ) -> Set[Permission]:
        """Get client-specific permissions for a user"""
        access = self.session.exec(
            select(ClientUserAccess).where(
                and_(
                    ClientUserAccess.user_id == user_id,
                    ClientUserAccess.client_id == client_id,
                    ClientUserAccess.active,
                    ClientUserAccess.expires_at.is_(None) | (ClientUserAccess.expires_at > utcnow_naive())
                )
            )
        ).first()
        
        if not access or not access.permissions:
            return set()
        
        return {Permission(perm) for perm in access.permissions.split(",") if perm}
    
    async def _user_has_client_access(self, user_id: UUID, client_id: UUID) -> bool:
        """Check if a client user has access to a specific client"""
        access = self.session.exec(
            select(ClientUserAccess).where(
                and_(
                    ClientUserAccess.user_id == user_id,
                    ClientUserAccess.client_id == client_id,
                    ClientUserAccess.active,
                    ClientUserAccess.expires_at.is_(None) | (ClientUserAccess.expires_at > utcnow_naive())
                )
            )
        ).first()
        
        return access is not None