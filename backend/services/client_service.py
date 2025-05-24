from datetime import date
from ..utils.datetime_utils import utcnow_naive
from typing import List, Optional
from uuid import UUID

from sqlmodel import Session, select, and_, func

from backend.core.database import get_session
from backend.models.client import (
    Client, ClientCreate, ClientRead, ClientUpdate,
    ClientHierarchy, ClientStatistics
)
from backend.models.ticket import Ticket
from backend.services.audit_service import AuditService, AuditEventType


class ClientService:
    """Service for managing clients, references, and rates"""
    
    def __init__(self, session: Session):
        self.session = session
        self.audit_service = AuditService(session)
    
    # ========== CLIENT CRUD OPERATIONS ==========
    
    async def create_client(self, client_data: ClientCreate, user_id: UUID) -> ClientRead:
        """Create a new client"""
        # Validate parent exists if specified
        if client_data.parent_id:
            parent = self.session.get(Client, client_data.parent_id)
            if not parent:
                raise ValueError(f"Parent client {client_data.parent_id} not found")
            if not parent.active:
                raise ValueError("Cannot assign inactive parent client")
        
        # Check for duplicate name
        existing = self.session.exec(
            select(Client).where(
                and_(Client.name == client_data.name, Client.active)
            )
        ).first()
        
        if existing:
            raise ValueError(f"Active client with name '{client_data.name}' already exists")
        
        # Create client
        client = Client(**client_data.model_dump(), created_by=user_id)
        self.session.add(client)
        self.session.commit()
        self.session.refresh(client)
        
        # Log creation
        await self.audit_service.log_event(
            AuditEventType.CLIENT_CREATED,
            user_id=user_id,
            details=f"Created client: {client.name}"
        )
        
        return ClientRead.model_validate(client)
    
    async def get_client(self, client_id: UUID) -> Optional[ClientRead]:
        """Get a client by ID"""
        client = self.session.get(Client, client_id)
        if not client:
            return None
        
        # Add counts for related entities
        client_read = ClientRead.model_validate(client)
        client_read.reference_count = len(client.references)
        client_read.rate_count = len(client.rates)
        client_read.subcontractor_count = len(client.subcontractors)
        
        return client_read
    
    async def get_clients(
        self, 
        active_only: bool = True,
        parent_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[ClientRead]:
        """Get list of clients with filtering"""
        query = select(Client)
        
        conditions = []
        if active_only:
            conditions.append(Client.active)
        
        if parent_id is not None:
            conditions.append(Client.parent_id == parent_id)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        query = query.order_by(Client.name).offset(skip).limit(limit)
        
        clients = self.session.exec(query).all()
        
        # Convert to read models with counts
        result = []
        for client in clients:
            client_read = ClientRead.model_validate(client)
            client_read.reference_count = len(client.references)
            client_read.rate_count = len(client.rates)
            client_read.subcontractor_count = len(client.subcontractors)
            result.append(client_read)
        
        return result
    
    async def update_client(
        self, 
        client_id: UUID, 
        client_data: ClientUpdate, 
        user_id: UUID
    ) -> ClientRead:
        """Update a client"""
        client = self.session.get(Client, client_id)
        if not client:
            raise ValueError(f"Client {client_id} not found")
        
        # Track changes for audit
        changes = {}
        update_data = client_data.model_dump(exclude_unset=True)
        
        # Validate parent if being changed
        if 'parent_id' in update_data and update_data['parent_id']:
            parent = self.session.get(Client, update_data['parent_id'])
            if not parent:
                raise ValueError(f"Parent client {update_data['parent_id']} not found")
            if not parent.active:
                raise ValueError("Cannot assign inactive parent client")
            # Prevent circular references
            if await self._would_create_cycle(client_id, update_data['parent_id']):
                raise ValueError("Cannot create circular client hierarchy")
        
        # Check for duplicate name if being changed
        if 'name' in update_data and update_data['name'] != client.name:
            existing = self.session.exec(
                select(Client).where(
                    and_(
                        Client.name == update_data['name'],
                        Client.active,
                        Client.id != client_id
                    )
                )
            ).first()
            
            if existing:
                raise ValueError(f"Active client with name '{update_data['name']}' already exists")
        
        # Apply updates
        for field, value in update_data.items():
            old_value = getattr(client, field)
            if old_value != value:
                changes[field] = {"from": old_value, "to": value}
                setattr(client, field, value)
        
        if changes:
            client.updated_at = utcnow_naive()
            self.session.add(client)
            self.session.commit()
            self.session.refresh(client)
            
            # Log changes
            await self.audit_service.log_event(
                AuditEventType.CLIENT_UPDATED,
                user_id=user_id,
                details=f"Updated client {client.name}: {changes}"
            )
        
        return ClientRead.model_validate(client)
    
    async def delete_client(self, client_id: UUID, user_id: UUID) -> bool:
        """Delete a client (with business rule validation)"""
        client = self.session.get(Client, client_id)
        if not client:
            raise ValueError(f"Client {client_id} not found")
        
        # Check for linked tickets
        ticket_count = self.session.exec(
            select(func.count(Ticket.id)).where(Ticket.client_id == client_id)
        ).first()
        
        if ticket_count and ticket_count > 0:
            raise ValueError(f"Cannot delete client {client.name}: {ticket_count} tickets are linked")
        
        # Check for subcontractors
        subcontractor_count = self.session.exec(
            select(func.count(Client.id)).where(Client.parent_id == client_id)
        ).first()
        
        if subcontractor_count and subcontractor_count > 0:
            raise ValueError(f"Cannot delete client {client.name}: {subcontractor_count} subcontractors exist")
        
        # Soft delete by marking inactive
        client.active = False
        client.updated_at = utcnow_naive()
        self.session.add(client)
        self.session.commit()
        
        # Log deletion
        await self.audit_service.log_event(
            AuditEventType.CLIENT_DELETED,
            user_id=user_id,
            details=f"Deleted client: {client.name}"
        )
        
        return True
    
    # ========== CLIENT HIERARCHY OPERATIONS ==========
    
    async def get_client_hierarchy(self, root_client_id: Optional[UUID] = None) -> List[ClientHierarchy]:
        """Get client hierarchy tree"""
        if root_client_id:
            # Get specific client and its hierarchy
            root_client = self.session.get(Client, root_client_id)
            if not root_client:
                raise ValueError(f"Client {root_client_id} not found")
            
            return [await self._build_hierarchy_node(root_client, 0)]
        else:
            # Get all root clients (no parent)
            root_clients = self.session.exec(
                select(Client).where(
                    and_(Client.parent_id.is_(None), Client.active)
                ).order_by(Client.name)
            ).all()
            
            hierarchy = []
            for client in root_clients:
                hierarchy.append(await self._build_hierarchy_node(client, 0))
            
            return hierarchy
    
    async def _build_hierarchy_node(self, client: Client, depth: int) -> ClientHierarchy:
        """Build a single hierarchy node with children"""
        client_read = ClientRead.model_validate(client)
        client_read.reference_count = len(client.references)
        client_read.rate_count = len(client.rates)
        client_read.subcontractor_count = len(client.subcontractors)
        
        # Build children
        children = []
        for subcontractor in client.subcontractors:
            if subcontractor.active:
                children.append(await self._build_hierarchy_node(subcontractor, depth + 1))
        
        return ClientHierarchy(
            client=client_read,
            subcontractors=children,
            depth=depth
        )
    
    async def _would_create_cycle(self, client_id: UUID, new_parent_id: UUID) -> bool:
        """Check if setting new parent would create a circular reference"""
        # Walk up the hierarchy from the new parent to see if we encounter the client
        current_id = new_parent_id
        visited = set()
        
        while current_id and current_id not in visited:
            if current_id == client_id:
                return True  # Cycle detected
            
            visited.add(current_id)
            parent = self.session.get(Client, current_id)
            current_id = parent.parent_id if parent else None
        
        return False
    
    # ========== CLIENT STATISTICS ==========
    
    async def get_client_statistics(
        self, 
        client_id: UUID,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> ClientStatistics:
        """Get statistics for a client"""
        client = self.session.get(Client, client_id)
        if not client:
            raise ValueError(f"Client {client_id} not found")
        
        # Build query for tickets
        query = select(
            func.count(Ticket.id).label("total_tickets"),
            func.coalesce(func.sum(Ticket.net_weight), 0).label("total_weight"),
            func.coalesce(func.avg(Ticket.rate_per_tonne), 0).label("avg_rate"),
            func.max(Ticket.created_at).label("last_activity")
        ).where(Ticket.client_id == client_id)
        
        if date_from:
            query = query.where(Ticket.entry_date >= date_from)
        if date_to:
            query = query.where(Ticket.entry_date <= date_to)
        
        result = self.session.exec(query).first()
        
        # Calculate total revenue
        revenue_query = select(
            func.coalesce(func.sum(Ticket.net_weight * Ticket.rate_per_tonne), 0)
        ).where(Ticket.client_id == client_id)
        
        if date_from:
            revenue_query = revenue_query.where(Ticket.entry_date >= date_from)
        if date_to:
            revenue_query = revenue_query.where(Ticket.entry_date <= date_to)
        
        total_revenue = self.session.exec(revenue_query).first() or 0.0
        
        return ClientStatistics(
            client_id=client_id,
            total_tickets=result.total_tickets or 0,
            total_weight=float(result.total_weight or 0),
            total_revenue=float(total_revenue),
            avg_rate=float(result.avg_rate or 0),
            date_range_start=date_from,
            date_range_end=date_to,
            last_activity=result.last_activity
        )
    
    # ========== HELPER METHODS ==========
    
    async def get_client_by_name(self, name: str) -> Optional[ClientRead]:
        """Get client by name"""
        client = self.session.exec(
            select(Client).where(
                and_(Client.name == name, Client.active)
            )
        ).first()
        
        if client:
            return ClientRead.model_validate(client)
        return None
    
    async def search_clients(self, search_term: str, limit: int = 10) -> List[ClientRead]:
        """Search clients by name"""
        clients = self.session.exec(
            select(Client).where(
                and_(
                    Client.active,
                    Client.name.ilike(f"%{search_term}%")
                )
            ).order_by(Client.name).limit(limit)
        ).all()
        
        return [ClientRead.model_validate(client) for client in clients]


def get_client_service(session: Session = None) -> ClientService:
    """Dependency injection for ClientService"""
    if session is None:
        session = next(get_session())
    return ClientService(session)