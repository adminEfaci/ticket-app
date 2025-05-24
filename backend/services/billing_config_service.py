from ..utils.datetime_utils import utcnow_naive
from typing import List, Optional, Dict, Any
from uuid import UUID
import re
import json

from sqlmodel import Session, select

from backend.core.database import get_session
from backend.models.client import (
    Client, ClientRead, InvoiceFormat
)
from backend.services.audit_service import AuditService, AuditEventType


class BillingContact:
    """Billing contact information"""
    def __init__(
        self, 
        email: str, 
        name: Optional[str] = None, 
        phone: Optional[str] = None,
        is_primary: bool = True
    ):
        self.email = email
        self.name = name
        self.phone = phone
        self.is_primary = is_primary


class BillingConfiguration:
    """Complete billing configuration for a client"""
    def __init__(
        self, 
        client_id: UUID,
        invoice_format: InvoiceFormat,
        invoice_frequency: str,
        credit_terms_days: int,
        primary_contact: BillingContact,
        additional_contacts: List[BillingContact] = None,
        delivery_method: str = "email",  # email, api, ftp
        special_instructions: Optional[str] = None
    ):
        self.client_id = client_id
        self.invoice_format = invoice_format
        self.invoice_frequency = invoice_frequency
        self.credit_terms_days = credit_terms_days
        self.primary_contact = primary_contact
        self.additional_contacts = additional_contacts or []
        self.delivery_method = delivery_method
        self.special_instructions = special_instructions


class BillingConfigService:
    """Service for managing client billing configurations"""
    
    def __init__(self, session: Session = None):
        self.session = session or next(get_session())
        self.audit_service = AuditService(self.session)
    
    async def update_billing_config(
        self,
        client_id: UUID,
        billing_email: Optional[str] = None,
        billing_contact_name: Optional[str] = None,
        billing_phone: Optional[str] = None,
        invoice_format: Optional[InvoiceFormat] = None,
        invoice_frequency: Optional[str] = None,
        credit_terms_days: Optional[int] = None,
        updated_by: Optional[UUID] = None
    ) -> Optional[ClientRead]:
        """
        Update billing configuration for a client
        
        Args:
            client_id: Client ID
            billing_email: Primary billing email
            billing_contact_name: Billing contact name
            billing_phone: Billing contact phone
            invoice_format: Preferred invoice format
            invoice_frequency: Invoice frequency (weekly, monthly)
            credit_terms_days: Payment terms in days
            updated_by: User making the update
        
        Returns:
            Updated client or None if not found
        """
        client = self.session.get(Client, client_id)
        if not client:
            return None
        
        # Store original values for audit
        original_config = {
            "billing_email": client.billing_email,
            "billing_contact_name": client.billing_contact_name,
            "billing_phone": client.billing_phone,
            "invoice_format": client.invoice_format.value,
            "invoice_frequency": client.invoice_frequency,
            "credit_terms_days": client.credit_terms_days
        }
        
        # Apply updates
        updates = {}
        if billing_email is not None:
            self._validate_email(billing_email)
            client.billing_email = billing_email
            updates["billing_email"] = billing_email
        
        if billing_contact_name is not None:
            client.billing_contact_name = billing_contact_name
            updates["billing_contact_name"] = billing_contact_name
        
        if billing_phone is not None:
            if billing_phone:  # Only validate if not empty
                self._validate_phone(billing_phone)
            client.billing_phone = billing_phone
            updates["billing_phone"] = billing_phone
        
        if invoice_format is not None:
            client.invoice_format = invoice_format
            updates["invoice_format"] = invoice_format.value
        
        if invoice_frequency is not None:
            if invoice_frequency not in ["weekly", "monthly", "quarterly"]:
                raise ValueError("Invalid invoice frequency. Must be weekly, monthly, or quarterly")
            client.invoice_frequency = invoice_frequency
            updates["invoice_frequency"] = invoice_frequency
        
        if credit_terms_days is not None:
            if not (1 <= credit_terms_days <= 365):
                raise ValueError("Credit terms must be between 1 and 365 days")
            client.credit_terms_days = credit_terms_days
            updates["credit_terms_days"] = credit_terms_days
        
        if not updates:
            return ClientRead.model_validate(client)
        
        client.updated_at = utcnow_naive()
        self.session.commit()
        self.session.refresh(client)
        
        # Log audit event
        await self.audit_service.log_event(
            event_type=AuditEventType.CLIENT_UPDATED,
            entity_type="Client",
            entity_id=client.id,
            user_id=updated_by,
            details={
                "config_type": "billing",
                "original_config": original_config,
                "updated_fields": updates
            }
        )
        
        return ClientRead.model_validate(client)
    
    async def get_billing_config(self, client_id: UUID) -> Optional[Dict]:
        """
        Get billing configuration for a client
        
        Args:
            client_id: Client ID
        
        Returns:
            Billing configuration dictionary or None if client not found
        """
        client = self.session.get(Client, client_id)
        if not client:
            return None
        
        return {
            "client_id": client.id,
            "client_name": client.name,
            "billing_email": client.billing_email,
            "billing_contact_name": client.billing_contact_name,
            "billing_phone": client.billing_phone,
            "invoice_format": client.invoice_format.value,
            "invoice_frequency": client.invoice_frequency,
            "credit_terms_days": client.credit_terms_days,
            "active": client.active,
            "updated_at": client.updated_at
        }
    
    async def get_clients_by_invoice_format(
        self, 
        invoice_format: InvoiceFormat,
        active_only: bool = True
    ) -> List[ClientRead]:
        """
        Get all clients using a specific invoice format
        
        Args:
            invoice_format: Invoice format to filter by
            active_only: Whether to include only active clients
        
        Returns:
            List of clients using the specified format
        """
        statement = select(Client).where(Client.invoice_format == invoice_format)
        
        if active_only:
            statement = statement.where(Client.active)
        
        results = self.session.exec(statement).all()
        return [ClientRead.model_validate(client) for client in results]
    
    async def get_clients_by_frequency(
        self, 
        frequency: str,
        active_only: bool = True
    ) -> List[ClientRead]:
        """
        Get all clients with a specific invoice frequency
        
        Args:
            frequency: Invoice frequency to filter by
            active_only: Whether to include only active clients
        
        Returns:
            List of clients with the specified frequency
        """
        statement = select(Client).where(Client.invoice_frequency == frequency)
        
        if active_only:
            statement = statement.where(Client.active)
        
        results = self.session.exec(statement).all()
        return [ClientRead.model_validate(client) for client in results]
    
    async def get_overdue_clients(self, days_overdue: int = 30) -> List[Dict]:
        """
        Get clients with overdue payments based on credit terms
        
        Note: This would typically integrate with an accounting system
        For now, it returns clients with longer credit terms as they
        might be more likely to have overdue payments
        
        Args:
            days_overdue: Minimum days overdue to consider
        
        Returns:
            List of potentially overdue clients
        """
        statement = select(Client).where(
            Client.active,
            Client.credit_terms_days >= days_overdue
        ).order_by(Client.credit_terms_days.desc())
        
        results = self.session.exec(statement).all()
        
        return [
            {
                "client_id": client.id,
                "client_name": client.name,
                "billing_email": client.billing_email,
                "credit_terms_days": client.credit_terms_days,
                "invoice_frequency": client.invoice_frequency,
                "last_updated": client.updated_at
            }
            for client in results
        ]
    
    async def validate_billing_config(self, client_id: UUID) -> Dict[str, List[str]]:
        """
        Validate billing configuration for a client
        
        Args:
            client_id: Client ID
        
        Returns:
            Dictionary with validation results
        """
        client = self.session.get(Client, client_id)
        if not client:
            return {"errors": ["Client not found"]}
        
        errors = []
        warnings = []
        
        # Required field validations
        if not client.billing_email:
            errors.append("Billing email is required")
        
        # Business rule validations
        if client.credit_terms_days > 90:
            warnings.append(f"Credit terms of {client.credit_terms_days} days is unusually long")
        
        if client.invoice_frequency not in ["weekly", "monthly", "quarterly"]:
            errors.append(f"Invalid invoice frequency: {client.invoice_frequency}")
        
        # Contact information completeness
        if not client.billing_contact_name:
            warnings.append("Billing contact name is recommended")
        
        if not client.billing_phone:
            warnings.append("Billing contact phone is recommended")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    async def get_billing_summary(self) -> Dict:
        """
        Get summary statistics for billing configurations
        
        Returns:
            Summary of billing configuration statistics
        """
        all_clients = self.session.exec(select(Client).where(Client.active)).all()
        
        if not all_clients:
            return {
                "total_clients": 0,
                "invoice_formats": {},
                "frequencies": {},
                "avg_credit_terms": 0,
                "incomplete_configs": 0
            }
        
        # Count by invoice format
        format_counts = {}
        for format_type in InvoiceFormat:
            format_counts[format_type.value] = len([
                c for c in all_clients if c.invoice_format == format_type
            ])
        
        # Count by frequency
        frequency_counts = {}
        for client in all_clients:
            freq = client.invoice_frequency
            frequency_counts[freq] = frequency_counts.get(freq, 0) + 1
        
        # Calculate average credit terms
        avg_credit_terms = sum(c.credit_terms_days for c in all_clients) / len(all_clients)
        
        # Count incomplete configurations
        incomplete = len([
            c for c in all_clients 
            if not c.billing_email or not c.billing_contact_name
        ])
        
        return {
            "total_clients": len(all_clients),
            "invoice_formats": format_counts,
            "frequencies": frequency_counts,
            "avg_credit_terms": round(avg_credit_terms, 1),
            "incomplete_configs": incomplete,
            "completion_rate": round((len(all_clients) - incomplete) / len(all_clients) * 100, 1)
        }
    
    async def bulk_update_invoice_format(
        self,
        client_ids: List[UUID],
        new_format: InvoiceFormat,
        updated_by: Optional[UUID] = None
    ) -> Dict[str, int]:
        """
        Bulk update invoice format for multiple clients
        
        Args:
            client_ids: List of client IDs to update
            new_format: New invoice format
            updated_by: User making the update
        
        Returns:
            Dictionary with update results
        """
        updated_count = 0
        errors = 0
        
        for client_id in client_ids:
            try:
                result = await self.update_billing_config(
                    client_id=client_id,
                    invoice_format=new_format,
                    updated_by=updated_by
                )
                if result:
                    updated_count += 1
                else:
                    errors += 1
            except Exception:
                errors += 1
        
        # Log bulk update event
        if updated_count > 0:
            await self.audit_service.log_event(
                event_type=AuditEventType.CLIENT_UPDATED,
                entity_type="Client",
                entity_id=None,  # Bulk operation
                user_id=updated_by,
                details={
                    "operation": "bulk_invoice_format_update",
                    "new_format": new_format.value,
                    "client_count": len(client_ids),
                    "updated_count": updated_count,
                    "errors": errors
                }
            )
        
        return {
            "total_requested": len(client_ids),
            "updated": updated_count,
            "errors": errors,
            "success_rate": round(updated_count / len(client_ids) * 100, 1) if client_ids else 0
        }
    
    async def get_billing_configuration(self, client_id: UUID) -> Optional[BillingConfiguration]:
        """Get complete billing configuration for a client as BillingConfiguration object"""
        client = self.session.get(Client, client_id)
        if not client:
            return None
        
        # Create primary contact from client data
        primary_contact = BillingContact(
            email=client.billing_email,
            name=client.billing_contact_name,
            phone=client.billing_phone,
            is_primary=True
        )
        
        # Extract delivery method from notes if stored there
        delivery_method = "email"
        special_instructions = client.notes
        
        if client.notes:
            try:
                notes_data = json.loads(client.notes)
                if "delivery_preferences" in notes_data:
                    delivery_method = notes_data["delivery_preferences"].get("method", "email")
                    special_instructions = notes_data.get("original_notes", "")
            except:
                pass
        
        return BillingConfiguration(
            client_id=client.id,
            invoice_format=client.invoice_format,
            invoice_frequency=client.invoice_frequency,
            credit_terms_days=client.credit_terms_days,
            primary_contact=primary_contact,
            additional_contacts=[],
            delivery_method=delivery_method,
            special_instructions=special_instructions
        )
    
    async def get_delivery_preferences(self, client_id: UUID) -> Dict[str, Any]:
        """Get invoice delivery preferences for a client"""
        config = await self.get_billing_configuration(client_id)
        if not config:
            return {}
        
        return {
            "delivery_method": config.delivery_method,
            "primary_email": config.primary_contact.email,
            "cc_emails": [c.email for c in config.additional_contacts],
            "format": config.invoice_format,
            "frequency": config.invoice_frequency,
            "special_instructions": config.special_instructions
        }
    
    async def set_delivery_method(
        self, 
        client_id: UUID,
        delivery_method: str,
        delivery_config: Optional[Dict[str, Any]] = None,
        updated_by: Optional[UUID] = None
    ) -> bool:
        """Set invoice delivery method and configuration"""
        valid_methods = ["email", "api", "ftp", "manual"]
        if delivery_method not in valid_methods:
            raise ValueError(f"Invalid delivery method. Must be one of: {valid_methods}")
        
        client = self.session.get(Client, client_id)
        if not client:
            raise ValueError(f"Client {client_id} not found")
        
        # Store delivery configuration in notes for now
        delivery_info = {
            "method": delivery_method,
            "config": delivery_config or {},
            "updated_at": utcnow_naive().isoformat()
        }
        
        # Update notes with delivery info
        notes_data = {}
        if client.notes:
            try:
                notes_data = json.loads(client.notes)
            except:
                notes_data = {"original_notes": client.notes}
        
        notes_data["delivery_preferences"] = delivery_info
        client.notes = json.dumps(notes_data)
        client.updated_at = utcnow_naive()
        
        self.session.commit()
        
        # Log audit event
        if updated_by:
            await self.audit_service.log_event(
                event_type=AuditEventType.BILLING_CONFIG_UPDATED,
                entity_type="Client",
                entity_id=client.id,
                user_id=updated_by,
                details={
                    "client_name": client.name,
                    "delivery_method": delivery_method,
                    "delivery_config": delivery_config
                }
            )
        
        return True
    
    async def get_invoice_format_requirements(self, format_type: InvoiceFormat) -> Dict[str, Any]:
        """Get requirements and specifications for each invoice format"""
        requirements = {
            InvoiceFormat.CSV: {
                "file_extension": ".csv",
                "mime_type": "text/csv",
                "required_fields": [
                    "ticket_number", "reference", "entry_date", "entry_time",
                    "truck_rego", "product", "supplier", "gross_weight",
                    "tare_weight", "net_weight", "rate_per_tonne", "total_amount"
                ],
                "encoding": "utf-8",
                "delimiter": ",",
                "includes_header": True
            },
            InvoiceFormat.XLSX: {
                "file_extension": ".xlsx",
                "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "sheet_name": "Invoice Details",
                "includes_summary": True,
                "includes_formatting": True,
                "required_fields": [
                    "ticket_number", "reference", "entry_date", "entry_time",
                    "truck_rego", "product", "supplier", "gross_weight",
                    "tare_weight", "net_weight", "rate_per_tonne", "total_amount"
                ]
            },
            InvoiceFormat.PDF: {
                "file_extension": ".pdf",
                "mime_type": "application/pdf",
                "includes_logo": True,
                "includes_terms": True,
                "includes_summary": True,
                "page_size": "A4",
                "orientation": "portrait"
            },
            InvoiceFormat.ODOO: {
                "format": "api",
                "endpoint": "https://api.odoo.com/v1/invoices",
                "authentication": "api_key",
                "required_fields": [
                    "partner_id", "invoice_line_ids", "date_invoice",
                    "journal_id", "account_id"
                ],
                "requires_setup": True,
                "setup_fields": ["odoo_partner_id", "odoo_api_key", "odoo_database"]
            }
        }
        
        return requirements.get(format_type, {})
    
    def _validate_email(self, email: str) -> bool:
        """Validate email format"""
        pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if not re.match(pattern, email):
            raise ValueError(f"Invalid email format: {email}")
        return True
    
    def _validate_phone(self, phone: str) -> bool:
        """Validate phone number format"""
        # Remove common formatting characters
        cleaned = re.sub(r'[\s\-\(\)\+]', '', phone)
        
        # Check if it's all digits and reasonable length
        if not cleaned.isdigit() or len(cleaned) < 7 or len(cleaned) > 15:
            raise ValueError(f"Invalid phone format: {phone}")
        
        return True


def get_billing_config_service(session: Session = None) -> BillingConfigService:
    """Dependency injection for BillingConfigService"""
    if session is None:
        session = next(get_session())
    return BillingConfigService(session)