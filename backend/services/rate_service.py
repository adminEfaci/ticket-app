from datetime import date, timedelta
from ..utils.datetime_utils import utcnow_naive
from typing import List, Optional, Dict
from uuid import UUID

from sqlmodel import Session, select, and_
from backend.core.database import get_session
from backend.models.client import (
    ClientRate, ClientRateCreate, ClientRateRead, ClientRateUpdate,
    Client
)
from backend.services.audit_service import AuditService, AuditEventType


class RateService:
    """Service for managing client rates with historical tracking"""
    
    def __init__(self, session: Session = None):
        self.session = session or next(get_session())
        self.audit_service = AuditService(self.session)
    
    async def create_rate(
        self, 
        rate_data: ClientRateCreate, 
        approved_by: Optional[UUID] = None,
        auto_approve: bool = False
    ) -> ClientRateRead:
        """
        Create a new rate for a client
        
        Args:
            rate_data: Rate creation data
            approved_by: Admin user who approved this rate
            auto_approve: Whether to auto-approve (admin only)
        
        Returns:
            Created rate
            
        Raises:
            ValueError: If validation fails or overlapping rates exist
        """
        # Validate client exists
        await self._get_client(rate_data.client_id)
        
        # Check for overlapping rates
        await self._validate_no_overlapping_rates(
            rate_data.client_id,
            rate_data.effective_from,
            rate_data.effective_to
        )
        
        # Create rate
        rate = ClientRate(**rate_data.model_dump())
        
        if auto_approve and approved_by:
            rate.approved_by = approved_by
            rate.approved_at = utcnow_naive()
        
        self.session.add(rate)
        self.session.commit()
        self.session.refresh(rate)
        
        # Log audit event
        await self.audit_service.log_event(
            event_type=AuditEventType.RATE_CREATED,
            user_id=approved_by,
            details=str({
                "entity_type": "ClientRate",
                "entity_id": str(rate.id),
                "client_id": str(rate_data.client_id),
                "rate_per_tonne": rate_data.rate_per_tonne,
                "effective_from": rate_data.effective_from.isoformat(),
                "effective_to": rate_data.effective_to.isoformat() if rate_data.effective_to else None,
                "auto_approved": auto_approve
            })
        )
        
        return ClientRateRead.model_validate(rate)
    
    async def get_rate(self, rate_id: UUID) -> Optional[ClientRateRead]:
        """Get a specific rate by ID"""
        statement = select(ClientRate).where(ClientRate.id == rate_id)
        result = self.session.exec(statement).first()
        return ClientRateRead.model_validate(result) if result else None
    
    async def get_client_rates(
        self, 
        client_id: UUID,
        include_expired: bool = False,
        limit: Optional[int] = None
    ) -> List[ClientRateRead]:
        """
        Get all rates for a client
        
        Args:
            client_id: Client ID
            include_expired: Whether to include expired rates
            limit: Maximum number of rates to return
        
        Returns:
            List of rates ordered by effective_from DESC
        """
        statement = select(ClientRate).where(ClientRate.client_id == client_id)
        
        if not include_expired:
            today = date.today()
            statement = statement.where(
                and_(
                    ClientRate.effective_from <= today,
                    ClientRate.effective_to.is_(None) | (ClientRate.effective_to >= today)
                )
            )
        
        statement = statement.order_by(ClientRate.effective_from.desc())
        
        if limit:
            statement = statement.limit(limit)
        
        results = self.session.exec(statement).all()
        return [ClientRateRead.model_validate(rate) for rate in results]
    
    async def get_effective_rate(
        self, 
        client_id: UUID, 
        effective_date: Optional[date] = None
    ) -> Optional[ClientRateRead]:
        """
        Get the effective rate for a client on a specific date
        
        Args:
            client_id: Client ID
            effective_date: Date to check (defaults to today)
        
        Returns:
            Effective rate or None if no rate found
        """
        if not effective_date:
            effective_date = date.today()
        
        statement = select(ClientRate).where(
            and_(
                ClientRate.client_id == client_id,
                ClientRate.effective_from <= effective_date,
                ClientRate.approved_by.is_not(None),  # Only approved rates
                ClientRate.effective_to.is_(None) | (ClientRate.effective_to >= effective_date)
            )
        ).order_by(ClientRate.effective_from.desc())
        
        result = self.session.exec(statement).first()
        return ClientRateRead.model_validate(result) if result else None
    
    async def update_rate(
        self, 
        rate_id: UUID, 
        rate_data: ClientRateUpdate,
        updated_by: Optional[UUID] = None
    ) -> Optional[ClientRateRead]:
        """
        Update an existing rate
        
        Args:
            rate_id: Rate ID to update
            rate_data: Update data
            updated_by: User making the update
        
        Returns:
            Updated rate or None if not found
            
        Raises:
            ValueError: If validation fails
        """
        rate = self.session.get(ClientRate, rate_id)
        if not rate:
            return None
        
        # Prevent updating approved rates
        if rate.approved_by:
            raise ValueError("Cannot update approved rates")
        
        # Store original values for audit
        original_values = {
            "rate_per_tonne": rate.rate_per_tonne,
            "effective_from": rate.effective_from.isoformat(),
            "effective_to": rate.effective_to.isoformat() if rate.effective_to else None,
            "notes": rate.notes
        }
        
        # Apply updates
        update_data = rate_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(rate, field, value)
        
        # Validate no overlapping rates if dates changed
        if 'effective_from' in update_data or 'effective_to' in update_data:
            await self._validate_no_overlapping_rates(
                rate.client_id,
                rate.effective_from,
                rate.effective_to,
                exclude_rate_id=rate_id
            )
        
        self.session.commit()
        self.session.refresh(rate)
        
        # Log audit event
        await self.audit_service.log_event(
            event_type=AuditEventType.RATE_UPDATED,
            user_id=updated_by,
            details=str({
                "entity_type": "ClientRate",
                "entity_id": str(rate.id),
                "client_id": str(rate.client_id),
                "original_values": original_values,
                "updated_fields": update_data
            })
        )
        
        return ClientRateRead.model_validate(rate)
    
    async def approve_rate(
        self, 
        rate_id: UUID, 
        approved_by: UUID
    ) -> Optional[ClientRateRead]:
        """
        Approve a pending rate
        
        Args:
            rate_id: Rate ID to approve
            approved_by: Admin user approving the rate
        
        Returns:
            Approved rate or None if not found
            
        Raises:
            ValueError: If rate is already approved
        """
        rate = self.session.get(ClientRate, rate_id)
        if not rate:
            return None
        
        if rate.approved_by:
            raise ValueError("Rate is already approved")
        
        rate.approved_by = approved_by
        rate.approved_at = utcnow_naive()
        
        self.session.commit()
        self.session.refresh(rate)
        
        # Log audit event
        await self.audit_service.log_event(
            event_type=AuditEventType.RATE_APPROVED,
            user_id=approved_by,
            details=str({
                "entity_type": "ClientRate",
                "entity_id": str(rate.id),
                "client_id": str(rate.client_id),
                "rate_per_tonne": rate.rate_per_tonne,
                "effective_from": rate.effective_from.isoformat()
            })
        )
        
        return ClientRateRead.model_validate(rate)
    
    async def delete_rate(
        self, 
        rate_id: UUID,
        deleted_by: Optional[UUID] = None
    ) -> bool:
        """
        Delete a rate (only if not approved or used)
        
        Args:
            rate_id: Rate ID to delete
            deleted_by: User deleting the rate
        
        Returns:
            True if deleted, False if not found
            
        Raises:
            ValueError: If rate cannot be deleted
        """
        rate = self.session.get(ClientRate, rate_id)
        if not rate:
            return False
        
        # Prevent deleting approved rates
        if rate.approved_by:
            raise ValueError("Cannot delete approved rates")
        
        # TODO: Check if rate is used in any tickets
        # This would require checking the ticket system
        
        # Store details for audit
        rate_details = {
            "client_id": str(rate.client_id),
            "rate_per_tonne": rate.rate_per_tonne,
            "effective_from": rate.effective_from.isoformat(),
            "effective_to": rate.effective_to.isoformat() if rate.effective_to else None
        }
        
        self.session.delete(rate)
        self.session.commit()
        
        # Log audit event
        await self.audit_service.log_event(
            event_type=AuditEventType.RATE_DELETED,
            user_id=deleted_by,
            details=str({
                "entity_type": "ClientRate",
                "entity_id": str(rate_id),
                **rate_details
            })
        )
        
        return True
    
    async def get_rate_history(
        self, 
        client_id: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[ClientRateRead]:
        """
        Get rate history for a client within a date range
        
        Args:
            client_id: Client ID
            start_date: Start date for history (optional)
            end_date: End date for history (optional)
        
        Returns:
            List of rates ordered by effective_from ASC
        """
        statement = select(ClientRate).where(ClientRate.client_id == client_id)
        
        if start_date:
            statement = statement.where(
                ClientRate.effective_to.is_(None) | (ClientRate.effective_to >= start_date)
            )
        
        if end_date:
            statement = statement.where(ClientRate.effective_from <= end_date)
        
        statement = statement.order_by(ClientRate.effective_from.asc())
        
        results = self.session.exec(statement).all()
        return [ClientRateRead.model_validate(rate) for rate in results]
    
    async def get_pending_rates(
        self,
        limit: Optional[int] = None
    ) -> List[ClientRateRead]:
        """
        Get all pending (unapproved) rates
        
        Args:
            limit: Maximum number of rates to return
        
        Returns:
            List of pending rates ordered by created_at ASC
        """
        statement = select(ClientRate).where(
            ClientRate.approved_by.is_(None)
        ).order_by(ClientRate.created_at.asc())
        
        if limit:
            statement = statement.limit(limit)
        
        results = self.session.exec(statement).all()
        return [ClientRateRead.model_validate(rate) for rate in results]
    
    async def validate_rate_range(self, rate_per_tonne: float) -> bool:
        """
        Validate that rate is within allowed range ($10-$100)
        
        Args:
            rate_per_tonne: Rate to validate
        
        Returns:
            True if valid, False otherwise
        """
        return 10.0 <= rate_per_tonne <= 100.0
    
    async def get_rate_conflicts(
        self, 
        client_id: UUID,
        effective_from: date,
        effective_to: Optional[date] = None,
        exclude_rate_id: Optional[UUID] = None
    ) -> List[ClientRateRead]:
        """
        Find rates that would conflict with the given date range
        
        Args:
            client_id: Client ID
            effective_from: Start date
            effective_to: End date (optional)
            exclude_rate_id: Rate ID to exclude from check
        
        Returns:
            List of conflicting rates
        """
        statement = select(ClientRate).where(ClientRate.client_id == client_id)
        
        if exclude_rate_id:
            statement = statement.where(ClientRate.id != exclude_rate_id)
        
        # Check for overlapping date ranges
        if effective_to:
            # New range has end date - check for any overlap
            statement = statement.where(
                and_(
                    ClientRate.effective_from <= effective_to,
                    ClientRate.effective_to.is_(None) | (ClientRate.effective_to >= effective_from)
                )
            )
        else:
            # New range is open-ended - check for any rate that starts before
            # this one ends or has no end date
            statement = statement.where(
                ClientRate.effective_to.is_(None) | (ClientRate.effective_to >= effective_from)
            )
        
        results = self.session.exec(statement).all()
        return [ClientRateRead.model_validate(rate) for rate in results]
    
    async def _get_client(self, client_id: UUID) -> Client:
        """Get client and validate it exists"""
        client = self.session.get(Client, client_id)
        if not client:
            raise ValueError(f"Client {client_id} not found")
        if not client.active:
            raise ValueError(f"Client {client_id} is not active")
        return client
    
    async def _validate_no_overlapping_rates(
        self,
        client_id: UUID,
        effective_from: date,
        effective_to: Optional[date] = None,
        exclude_rate_id: Optional[UUID] = None
    ):
        """
        Validate that no overlapping rates exist for the given date range
        
        Raises:
            ValueError: If overlapping rates found
        """
        conflicts = await self.get_rate_conflicts(
            client_id, effective_from, effective_to, exclude_rate_id
        )
        
        if conflicts:
            conflict_ranges = []
            for conflict in conflicts:
                start = conflict.effective_from.isoformat()
                end = conflict.effective_to.isoformat() if conflict.effective_to else "ongoing"
                conflict_ranges.append(f"{start} to {end}")
            
            raise ValueError(
                f"Rate conflicts with existing rates: {', '.join(conflict_ranges)}"
            )


class RateAnalytics:
    """Analytics service for rate data"""
    
    def __init__(self, session: Session = None):
        self.session = session or next(get_session())
    
    async def get_rate_statistics(
        self, 
        client_id: Optional[UUID] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict:
        """
        Get rate statistics for analysis
        
        Args:
            client_id: Specific client (optional)
            start_date: Start date for analysis
            end_date: End date for analysis
        
        Returns:
            Dictionary with rate statistics
        """
        statement = select(ClientRate).where(ClientRate.approved_by.is_not(None))
        
        if client_id:
            statement = statement.where(ClientRate.client_id == client_id)
        
        if start_date:
            statement = statement.where(ClientRate.effective_from >= start_date)
        
        if end_date:
            statement = statement.where(ClientRate.effective_from <= end_date)
        
        rates = self.session.exec(statement).all()
        
        if not rates:
            return {
                "count": 0,
                "avg_rate": 0,
                "min_rate": 0,
                "max_rate": 0,
                "rate_changes": 0
            }
        
        rate_values = [rate.rate_per_tonne for rate in rates]
        
        return {
            "count": len(rates),
            "avg_rate": sum(rate_values) / len(rate_values),
            "min_rate": min(rate_values),
            "max_rate": max(rate_values),
            "rate_changes": len(rates),
            "date_range": {
                "start": min(rate.effective_from for rate in rates).isoformat(),
                "end": max(rate.effective_from for rate in rates).isoformat()
            }
        }
    
    async def get_rate_trends(
        self, 
        client_id: UUID,
        months: int = 12
    ) -> List[Dict]:
        """
        Get rate trends for a client over time
        
        Args:
            client_id: Client ID
            months: Number of months to analyze
        
        Returns:
            List of monthly rate data
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=months * 30)
        
        rates = await self.get_rate_history(client_id, start_date, end_date)
        
        # Group by month and calculate average rates
        monthly_data = {}
        
        for rate in rates:
            month_key = rate.effective_from.strftime("%Y-%m")
            if month_key not in monthly_data:
                monthly_data[month_key] = []
            monthly_data[month_key].append(rate.rate_per_tonne)
        
        # Calculate monthly averages
        trends = []
        for month, rate_list in sorted(monthly_data.items()):
            trends.append({
                "month": month,
                "avg_rate": sum(rate_list) / len(rate_list),
                "rate_changes": len(rate_list),
                "min_rate": min(rate_list),
                "max_rate": max(rate_list)
            })
        
        return trends