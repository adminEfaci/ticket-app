from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from ..utils.datetime_utils import utcnow_naive
from uuid import UUID
from sqlmodel import Session, select
from enum import Enum
from ..models.audit_log import AuditLog


class AuditEventType(Enum):
    """Enum for standardized audit event types"""
    # Authentication & Authorization
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    PERMISSION_VIOLATION = "permission_violation"
    
    # User Management
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    
    # Batch & Upload
    UPLOAD_ATTEMPT = "upload_attempt"
    UPLOAD_SUCCESS = "upload_success"
    BATCH_DELETION = "batch_deletion"
    BATCH_DELETION_FAILED = "batch_deletion_failed"
    
    # Ticket Parsing
    TICKET_PARSING_STARTED = "ticket_parsing_started"
    TICKET_PARSING_COMPLETED = "ticket_parsing_completed"
    TICKET_PARSING_FAILED = "ticket_parsing_failed"
    TICKET_VALIDATION_ERRORS = "ticket_validation_errors"
    DUPLICATE_TICKETS_DETECTED = "duplicate_tickets_detected"
    
    # Ticket CRUD
    TICKET_CREATED = "ticket_created"
    TICKET_UPDATED = "ticket_updated"
    TICKET_DELETED = "ticket_deleted"
    
    # Image Extraction
    IMAGE_EXTRACTION_STARTED = "image_extraction_started"
    IMAGE_EXTRACTION_COMPLETED = "image_extraction_completed"
    IMAGE_EXTRACTION_ERROR = "image_extraction_error"
    OCR_CONFIDENCE_WARNING = "ocr_confidence_warning"
    IMAGE_QUALITY_VALIDATION_FAILED = "image_quality_validation_failed"
    TICKET_IMAGE_CREATED = "ticket_image_created"
    TICKET_IMAGE_DELETED = "ticket_image_deleted"
    
    # Phase 5: Matching
    MATCH_STARTED = "match_started"
    MATCH_COMPLETED = "match_completed"
    MATCH_REVIEWED = "match_reviewed"
    MATCH_ACCEPTED = "match_accepted"
    MATCH_REJECTED = "match_rejected"
    MATCH_CONFLICT_DETECTED = "match_conflict_detected"
    MATCH_CONFIDENCE_LOW = "match_confidence_low"
    
    # Phase 6: Client Management
    CLIENT_CREATED = "client_created"
    CLIENT_UPDATED = "client_updated"
    CLIENT_DELETED = "client_deleted"
    CLIENT_ASSIGNED = "client_assigned"
    CLIENT_HIERARCHY_UPDATED = "client_hierarchy_updated"
    
    # Client Rates
    RATE_CREATED = "rate_created"
    RATE_UPDATED = "rate_updated"
    RATE_DELETED = "rate_deleted"
    RATE_APPROVED = "rate_approved"
    RATE_REJECTED = "rate_rejected"
    
    # Client References
    REFERENCE_CREATED = "reference_created"
    REFERENCE_UPDATED = "reference_updated"
    REFERENCE_DELETED = "reference_deleted"
    REFERENCE_PATTERN_MATCHED = "reference_pattern_matched"
    
    # Billing Configuration
    BILLING_CONFIG_UPDATED = "billing_config_updated"
    INVOICE_GENERATED = "invoice_generated"
    
    # Access Control
    ACCESS_GRANTED = "access_granted"
    ACCESS_REVOKED = "access_revoked"
    PERMISSION_CHANGED = "permission_changed"
    
    # System Events
    SYSTEM_ERROR = "system_error"

class AuditService:
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def log_action(
        self,
        user_id: UUID,
        action: str,
        ip_address: str,
        entity: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> AuditLog:
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            ip_address=ip_address,
            details=details
        )
        
        self.db.add(audit_log)
        self.db.commit()
        self.db.refresh(audit_log)
        
        return audit_log
    
    def log_login_attempt(self, user_id: UUID, ip_address: str, success: bool, details: Optional[Dict[str, Any]] = None) -> AuditLog:
        action = "login_success" if success else "login_failed"
        return self.log_action(
            user_id=user_id,
            action=action,
            ip_address=ip_address,
            entity="session",
            details=details
        )
    
    def log_logout(self, user_id: UUID, ip_address: str, session_id: UUID) -> AuditLog:
        return self.log_action(
            user_id=user_id,
            action="logout",
            ip_address=ip_address,
            entity="session",
            entity_id=session_id
        )
    
    def log_user_creation(self, creator_id: UUID, created_user_id: UUID, ip_address: str, role: str) -> AuditLog:
        return self.log_action(
            user_id=creator_id,
            action="user_created",
            ip_address=ip_address,
            entity="user",
            entity_id=created_user_id,
            details={"created_user_role": role}
        )
    
    def log_user_update(self, updater_id: UUID, updated_user_id: UUID, ip_address: str, changes: Dict[str, Any]) -> AuditLog:
        return self.log_action(
            user_id=updater_id,
            action="user_updated",
            ip_address=ip_address,
            entity="user",
            entity_id=updated_user_id,
            details={"changes": changes}
        )
    
    def log_user_deletion(self, deleter_id: UUID, deleted_user_id: UUID, ip_address: str) -> AuditLog:
        return self.log_action(
            user_id=deleter_id,
            action="user_deleted",
            ip_address=ip_address,
            entity="user",
            entity_id=deleted_user_id
        )
    
    def log_permission_violation(self, user_id: UUID, ip_address: str, attempted_action: str, target_entity: Optional[str] = None) -> AuditLog:
        return self.log_action(
            user_id=user_id,
            action="permission_violation",
            ip_address=ip_address,
            entity=target_entity,
            details={"attempted_action": attempted_action}
        )
    
    # Upload and Batch Related Audit Methods
    def log_upload_attempt(self, user_id: UUID, ip_address: str, success: bool, file_count: int, details: Optional[Dict[str, Any]] = None) -> AuditLog:
        return self.log_action(
            user_id=user_id,
            action="upload_attempt",
            ip_address=ip_address,
            entity="upload",
            details={
                "success": success,
                "file_count": file_count,
                **(details or {})
            }
        )
    
    def log_upload_success(self, user_id: UUID, batch_id: UUID, ip_address: str, xls_filename: str, pdf_filename: str) -> AuditLog:
        return self.log_action(
            user_id=user_id,
            action="upload_success",
            ip_address=ip_address,
            entity="batch",
            entity_id=batch_id,
            details={
                "xls_filename": xls_filename,
                "pdf_filename": pdf_filename
            }
        )
    
    def log_batch_deletion(self, user_id: UUID, batch_id: UUID, ip_address: str, batch_status: str) -> AuditLog:
        return self.log_action(
            user_id=user_id,
            action="batch_deletion",
            ip_address=ip_address,
            entity="batch",
            entity_id=batch_id,
            details={"batch_status": batch_status}
        )
    
    def log_batch_deletion_failed(self, user_id: UUID, batch_id: UUID, ip_address: str, reason: str) -> AuditLog:
        return self.log_action(
            user_id=user_id,
            action="batch_deletion_failed",
            ip_address=ip_address,
            entity="batch",
            entity_id=batch_id,
            details={"reason": reason}
        )
    
    def get_audit_logs(
        self,
        requester_role: str,
        user_id: Optional[UUID] = None,
        action: Optional[str] = None,
        entity: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[AuditLog]:
        if requester_role not in ["admin", "manager"]:
            return []
        
        query = select(AuditLog)
        
        if user_id:
            query = query.where(AuditLog.user_id == user_id)
        
        if action:
            query = query.where(AuditLog.action == action)
        
        if entity:
            query = query.where(AuditLog.entity == entity)
        
        if start_date:
            query = query.where(AuditLog.timestamp >= start_date)
        
        if end_date:
            query = query.where(AuditLog.timestamp <= end_date)
        
        query = query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit)
        
        logs = self.db.exec(query).all()
        return list(logs)
    
    def get_user_activity(self, user_id: UUID, requester_role: str, requester_id: UUID, days: int = 30) -> List[AuditLog]:
        if requester_role == "client" and str(user_id) != str(requester_id):
            return []
        
        start_date = utcnow_naive() - timedelta(days=days)
        
        query = select(AuditLog).where(
            AuditLog.user_id == user_id,
            AuditLog.timestamp >= start_date
        ).order_by(AuditLog.timestamp.desc())
        
        logs = self.db.exec(query).all()
        return list(logs)
    
    def get_security_events(self, requester_role: str, days: int = 7) -> List[AuditLog]:
        if requester_role not in ["admin", "manager"]:
            return []
        
        start_date = utcnow_naive() - timedelta(days=days)
        
        security_actions = [
            "login_failed",
            "permission_violation",
            "user_created",
            "user_deleted",
            "user_updated"
        ]
        
        query = select(AuditLog).where(
            AuditLog.action.in_(security_actions),
            AuditLog.timestamp >= start_date
        ).order_by(AuditLog.timestamp.desc())
        
        logs = self.db.exec(query).all()
        return list(logs)
    
    # Ticket parsing related audit methods
    def log_ticket_parsing_started(
        self, 
        user_id: UUID, 
        batch_id: UUID, 
        ip_address: str, 
        xls_filename: str
    ) -> AuditLog:
        """Log when ticket parsing is started for a batch"""
        return self.log_action(
            user_id=user_id,
            action="ticket_parsing_started",
            ip_address=ip_address,
            entity="batch",
            entity_id=batch_id,
            details={
                "xls_filename": xls_filename,
                "parsing_initiated_at": utcnow_naive().isoformat()
            }
        )
    
    def log_ticket_parsing_completed(
        self, 
        user_id: UUID, 
        batch_id: UUID, 
        ip_address: str, 
        tickets_parsed: int,
        tickets_valid: int,
        tickets_invalid: int,
        duplicates_detected: int
    ) -> AuditLog:
        """Log successful completion of ticket parsing"""
        return self.log_action(
            user_id=user_id,
            action="ticket_parsing_completed",
            ip_address=ip_address,
            entity="batch",
            entity_id=batch_id,
            details={
                "tickets_parsed": tickets_parsed,
                "tickets_valid": tickets_valid,
                "tickets_invalid": tickets_invalid,
                "duplicates_detected": duplicates_detected,
                "success_rate": (tickets_valid / tickets_parsed * 100) if tickets_parsed > 0 else 0,
                "parsing_completed_at": utcnow_naive().isoformat()
            }
        )
    
    def log_ticket_parsing_failed(
        self, 
        user_id: UUID, 
        batch_id: UUID, 
        ip_address: str, 
        error_message: str,
        xls_filename: Optional[str] = None
    ) -> AuditLog:
        """Log failed ticket parsing attempt"""
        return self.log_action(
            user_id=user_id,
            action="ticket_parsing_failed",
            ip_address=ip_address,
            entity="batch",
            entity_id=batch_id,
            details={
                "error_message": error_message,
                "xls_filename": xls_filename,
                "parsing_failed_at": utcnow_naive().isoformat()
            }
        )
    
    def log_ticket_validation_errors(
        self, 
        user_id: UUID, 
        batch_id: UUID, 
        ip_address: str, 
        validation_errors: List[Dict[str, Any]]
    ) -> AuditLog:
        """Log ticket validation errors for audit trail"""
        return self.log_action(
            user_id=user_id,
            action="ticket_validation_errors",
            ip_address=ip_address,
            entity="batch",
            entity_id=batch_id,
            details={
                "validation_errors": validation_errors,
                "error_count": len(validation_errors),
                "logged_at": utcnow_naive().isoformat()
            }
        )
    
    def log_duplicate_tickets_detected(
        self, 
        user_id: UUID, 
        batch_id: UUID, 
        ip_address: str, 
        duplicate_tickets: List[str]
    ) -> AuditLog:
        """Log detection of duplicate ticket numbers"""
        return self.log_action(
            user_id=user_id,
            action="duplicate_tickets_detected",
            ip_address=ip_address,
            entity="batch",
            entity_id=batch_id,
            details={
                "duplicate_ticket_numbers": duplicate_tickets,
                "duplicate_count": len(duplicate_tickets),
                "detected_at": utcnow_naive().isoformat()
            }
        )
    
    def log_ticket_created(
        self, 
        user_id: UUID, 
        ticket_id: UUID, 
        batch_id: UUID, 
        ip_address: str, 
        ticket_number: str
    ) -> AuditLog:
        """Log successful ticket creation"""
        return self.log_action(
            user_id=user_id,
            action="ticket_created",
            ip_address=ip_address,
            entity="ticket",
            entity_id=ticket_id,
            details={
                "ticket_number": ticket_number,
                "batch_id": str(batch_id),
                "created_at": utcnow_naive().isoformat()
            }
        )
    
    def log_ticket_updated(
        self, 
        user_id: UUID, 
        ticket_id: UUID, 
        ip_address: str, 
        ticket_number: str,
        changes: Dict[str, Any]
    ) -> AuditLog:
        """Log ticket update"""
        return self.log_action(
            user_id=user_id,
            action="ticket_updated",
            ip_address=ip_address,
            entity="ticket",
            entity_id=ticket_id,
            details={
                "ticket_number": ticket_number,
                "changes": changes,
                "updated_at": utcnow_naive().isoformat()
            }
        )
    
    def log_ticket_deleted(
        self, 
        user_id: UUID, 
        ticket_id: UUID, 
        ip_address: str, 
        ticket_number: str,
        reason: str
    ) -> AuditLog:
        """Log ticket deletion (soft delete)"""
        return self.log_action(
            user_id=user_id,
            action="ticket_deleted",
            ip_address=ip_address,
            entity="ticket",
            entity_id=ticket_id,
            details={
                "ticket_number": ticket_number,
                "deletion_reason": reason,
                "deleted_at": utcnow_naive().isoformat()
            }
        )
    
    def get_parsing_audit_logs(self, batch_id: UUID, requester_role: str) -> List[AuditLog]:
        """Get all parsing-related audit logs for a specific batch"""
        if requester_role not in ["admin", "manager", "processor"]:
            return []
        
        parsing_actions = [
            "ticket_parsing_started",
            "ticket_parsing_completed",
            "ticket_parsing_failed",
            "ticket_validation_errors",
            "duplicate_tickets_detected"
        ]
        
        query = select(AuditLog).where(
            AuditLog.entity_id == batch_id,
            AuditLog.action.in_(parsing_actions)
        ).order_by(AuditLog.timestamp.asc())
        
        logs = self.db.exec(query).all()
        return list(logs)
    
    def get_ticket_audit_logs(self, ticket_id: UUID, requester_role: str) -> List[AuditLog]:
        """Get all audit logs for a specific ticket"""
        if requester_role not in ["admin", "manager", "processor"]:
            return []
        
        ticket_actions = [
            "ticket_created",
            "ticket_updated", 
            "ticket_deleted"
        ]
        
        query = select(AuditLog).where(
            AuditLog.entity_id == ticket_id,
            AuditLog.action.in_(ticket_actions)
        ).order_by(AuditLog.timestamp.asc())
        
        logs = self.db.exec(query).all()
        return list(logs)
    
    # Phase 4: Image Extraction Audit Methods
    
    def log_image_extraction_started(self, user_id: UUID, batch_id: UUID, ip_address: str, pdf_pages: int):
        """Log the start of image extraction process"""
        return self.log_action(
            user_id=user_id,
            action="image_extraction_started",
            entity="batch",
            entity_id=batch_id,
            ip_address=ip_address,
            details={
                "pdf_pages": pdf_pages
            }
        )
    
    def log_image_extraction_completed(self, user_id: Optional[UUID], batch_id: UUID, 
                                     pages_processed: int, images_extracted: int, images_failed: int):
        """Log the completion of image extraction process"""
        return self.log_action(
            user_id=user_id,
            action="image_extraction_completed",
            entity="batch",
            entity_id=batch_id,
            details={
                "pages_processed": pages_processed,
                "images_extracted": images_extracted,
                "images_failed": images_failed,
                "success_rate": (images_extracted / pages_processed * 100.0) if pages_processed > 0 else 0.0
            }
        )
    
    def log_image_extraction_error(self, batch_id: UUID, page_number: int, error_type: str, error_message: str):
        """Log an image extraction error"""
        return self.log_action(
            user_id=None,
            action="image_extraction_error",
            entity="batch",
            entity_id=batch_id,
            details={
                "page_number": page_number,
                "error_type": error_type,
                "error_message": error_message
            }
        )
    
    def log_ocr_confidence_warning(self, batch_id: UUID, page_number: int, 
                                 ticket_number: Optional[str], confidence: float):
        """Log OCR confidence warning"""
        return self.log_action(
            user_id=None,
            action="ocr_confidence_warning",
            entity="batch",
            entity_id=batch_id,
            details={
                "page_number": page_number,
                "ticket_number": ticket_number,
                "ocr_confidence": confidence,
                "threshold": 80.0
            }
        )
    
    def log_image_quality_validation_failed(self, batch_id: UUID, page_number: int, validation_errors: list):
        """Log image quality validation failure"""
        return self.log_action(
            user_id=None,
            action="image_quality_validation_failed",
            entity="batch",
            entity_id=batch_id,
            details={
                "page_number": page_number,
                "validation_errors": validation_errors
            }
        )
    
    def log_ticket_image_created(self, batch_id: UUID, image_id: UUID, 
                               ticket_number: Optional[str], ocr_confidence: Optional[float]):
        """Log successful ticket image creation"""
        return self.log_action(
            user_id=None,
            action="ticket_image_created",
            entity="ticket_image",
            entity_id=image_id,
            details={
                "batch_id": str(batch_id),
                "ticket_number": ticket_number,
                "ocr_confidence": ocr_confidence
            }
        )
    
    def log_ticket_image_deleted(self, user_id: UUID, image_id: UUID, reason: str):
        """Log ticket image deletion"""
        return self.log_action(
            user_id=user_id,
            action="ticket_image_deleted",
            entity="ticket_image",
            entity_id=image_id,
            details={
                "deletion_reason": reason
            }
        )
    
    # Phase 5: Matching Audit Methods
    
    async def log_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[UUID] = None,
        batch_id: Optional[UUID] = None,
        ticket_id: Optional[UUID] = None,
        image_id: Optional[UUID] = None,
        match_id: Optional[UUID] = None,
        ip_address: str = "system",
        details: Optional[str] = None
    ) -> AuditLog:
        """Modern event logging method using standardized event types"""
        
        # Determine entity and entity_id based on context
        entity = None
        entity_id = None
        
        if match_id:
            entity = "match_result"
            entity_id = match_id
        elif ticket_id:
            entity = "ticket"
            entity_id = ticket_id
        elif image_id:
            entity = "ticket_image"
            entity_id = image_id
        elif batch_id:
            entity = "batch"
            entity_id = batch_id
        
        return self.log_action(
            user_id=user_id,
            action=event_type.value,
            ip_address=ip_address,
            entity=entity,
            entity_id=entity_id,
            details={"details": details} if details else None
        )
    
    def log_match_started(
        self, 
        user_id: UUID, 
        batch_id: UUID, 
        ip_address: str,
        tickets_count: int,
        images_count: int
    ) -> AuditLog:
        """Log the start of matching process"""
        return self.log_action(
            user_id=user_id,
            action="match_started",
            ip_address=ip_address,
            entity="batch",
            entity_id=batch_id,
            details={
                "tickets_count": tickets_count,
                "images_count": images_count,
                "started_at": utcnow_naive().isoformat()
            }
        )
    
    def log_match_completed(
        self, 
        user_id: UUID, 
        batch_id: UUID, 
        ip_address: str,
        auto_accepted: int,
        needs_review: int,
        unmatched: int,
        conflicts: int,
        average_confidence: float
    ) -> AuditLog:
        """Log completion of matching process"""
        return self.log_action(
            user_id=user_id,
            action="match_completed",
            ip_address=ip_address,
            entity="batch",
            entity_id=batch_id,
            details={
                "auto_accepted": auto_accepted,
                "needs_review": needs_review,
                "unmatched": unmatched,
                "conflicts": conflicts,
                "average_confidence": average_confidence,
                "completed_at": utcnow_naive().isoformat()
            }
        )
    
    def log_match_reviewed(
        self, 
        user_id: UUID, 
        match_id: UUID, 
        ip_address: str,
        ticket_id: UUID,
        image_id: UUID,
        accepted: bool,
        confidence: float,
        reason: Optional[str] = None
    ) -> AuditLog:
        """Log manual review of a match"""
        return self.log_action(
            user_id=user_id,
            action="match_reviewed",
            ip_address=ip_address,
            entity="match_result",
            entity_id=match_id,
            details={
                "ticket_id": str(ticket_id),
                "image_id": str(image_id),
                "accepted": accepted,
                "confidence": confidence,
                "reason": reason,
                "reviewed_at": utcnow_naive().isoformat()
            }
        )
    
    def log_match_conflict_detected(
        self, 
        batch_id: UUID, 
        ip_address: str,
        image_id: UUID,
        conflicting_tickets: List[UUID],
        confidences: List[float]
    ) -> AuditLog:
        """Log detection of matching conflicts"""
        return self.log_action(
            user_id=None,
            action="match_conflict_detected",
            ip_address=ip_address,
            entity="batch",
            entity_id=batch_id,
            details={
                "image_id": str(image_id),
                "conflicting_tickets": [str(tid) for tid in conflicting_tickets],
                "confidences": confidences,
                "detected_at": utcnow_naive().isoformat()
            }
        )
    
    def log_match_low_confidence(
        self, 
        batch_id: UUID, 
        ip_address: str,
        ticket_id: UUID,
        image_id: UUID,
        confidence: float,
        threshold: float
    ) -> AuditLog:
        """Log low confidence match requiring review"""
        return self.log_action(
            user_id=None,
            action="match_confidence_low",
            ip_address=ip_address,
            entity="batch",
            entity_id=batch_id,
            details={
                "ticket_id": str(ticket_id),
                "image_id": str(image_id),
                "confidence": confidence,
                "threshold": threshold,
                "flagged_at": utcnow_naive().isoformat()
            }
        )
    
    def get_matching_audit_logs(self, batch_id: UUID, requester_role: str) -> List[AuditLog]:
        """Get all matching-related audit logs for a specific batch"""
        if requester_role not in ["admin", "manager", "processor"]:
            return []
        
        matching_actions = [
            "match_started",
            "match_completed",
            "match_reviewed",
            "match_accepted",
            "match_rejected",
            "match_conflict_detected",
            "match_confidence_low"
        ]
        
        query = select(AuditLog).where(
            AuditLog.entity_id == batch_id,
            AuditLog.action.in_(matching_actions)
        ).order_by(AuditLog.timestamp.asc())
        
        logs = self.db.exec(query).all()
        return list(logs)
    
    def get_match_audit_logs(self, match_id: UUID, requester_role: str) -> List[AuditLog]:
        """Get all audit logs for a specific match result"""
        if requester_role not in ["admin", "manager", "processor"]:
            return []
        
        match_actions = [
            "match_reviewed",
            "match_accepted",
            "match_rejected"
        ]
        
        query = select(AuditLog).where(
            AuditLog.entity_id == match_id,
            AuditLog.action.in_(match_actions)
        ).order_by(AuditLog.timestamp.asc())
        
        logs = self.db.exec(query).all()
        return list(logs)
    
    # Phase 6: Client Management Audit Methods
    
    def log_client_created(
        self,
        user_id: UUID,
        client_id: UUID,
        ip_address: str,
        client_name: str,
        parent_id: Optional[UUID] = None
    ) -> AuditLog:
        """Log client creation"""
        return self.log_action(
            user_id=user_id,
            action="client_created",
            ip_address=ip_address,
            entity="client",
            entity_id=client_id,
            details={
                "client_name": client_name,
                "parent_id": str(parent_id) if parent_id else None,
                "created_at": utcnow_naive().isoformat()
            }
        )
    
    def log_client_updated(
        self,
        user_id: UUID,
        client_id: UUID,
        ip_address: str,
        client_name: str,
        changes: Dict[str, Any]
    ) -> AuditLog:
        """Log client update"""
        return self.log_action(
            user_id=user_id,
            action="client_updated",
            ip_address=ip_address,
            entity="client",
            entity_id=client_id,
            details={
                "client_name": client_name,
                "changes": changes,
                "updated_at": utcnow_naive().isoformat()
            }
        )
    
    def log_client_deleted(
        self,
        user_id: UUID,
        client_id: UUID,
        ip_address: str,
        client_name: str,
        deletion_type: str = "soft"
    ) -> AuditLog:
        """Log client deletion"""
        return self.log_action(
            user_id=user_id,
            action="client_deleted",
            ip_address=ip_address,
            entity="client",
            entity_id=client_id,
            details={
                "client_name": client_name,
                "deletion_type": deletion_type,
                "deleted_at": utcnow_naive().isoformat()
            }
        )
    
    def log_client_assigned(
        self,
        user_id: Optional[UUID],
        client_id: UUID,
        ticket_id: UUID,
        ip_address: str,
        assignment_method: str,
        confidence: Optional[float] = None,
        matched_pattern: Optional[str] = None
    ) -> AuditLog:
        """Log automatic client assignment to ticket"""
        return self.log_action(
            user_id=user_id,
            action="client_assigned",
            ip_address=ip_address,
            entity="ticket",
            entity_id=ticket_id,
            details={
                "client_id": str(client_id),
                "assignment_method": assignment_method,
                "confidence": confidence,
                "matched_pattern": matched_pattern,
                "assigned_at": utcnow_naive().isoformat()
            }
        )
    
    def log_rate_created(
        self,
        user_id: UUID,
        rate_id: UUID,
        client_id: UUID,
        ip_address: str,
        rate_per_tonne: float,
        effective_from: str,
        auto_approved: bool = False
    ) -> AuditLog:
        """Log rate creation"""
        return self.log_action(
            user_id=user_id,
            action="rate_created",
            ip_address=ip_address,
            entity="rate",
            entity_id=rate_id,
            details={
                "client_id": str(client_id),
                "rate_per_tonne": rate_per_tonne,
                "effective_from": effective_from,
                "auto_approved": auto_approved,
                "created_at": utcnow_naive().isoformat()
            }
        )
    
    def log_rate_approved(
        self,
        user_id: UUID,
        rate_id: UUID,
        client_id: UUID,
        ip_address: str,
        rate_per_tonne: float
    ) -> AuditLog:
        """Log rate approval"""
        return self.log_action(
            user_id=user_id,
            action="rate_approved",
            ip_address=ip_address,
            entity="rate",
            entity_id=rate_id,
            details={
                "client_id": str(client_id),
                "rate_per_tonne": rate_per_tonne,
                "approved_at": utcnow_naive().isoformat()
            }
        )
    
    def log_reference_created(
        self,
        user_id: UUID,
        reference_id: UUID,
        client_id: UUID,
        ip_address: str,
        pattern: str,
        pattern_type: str
    ) -> AuditLog:
        """Log reference pattern creation"""
        return self.log_action(
            user_id=user_id,
            action="reference_created",
            ip_address=ip_address,
            entity="reference",
            entity_id=reference_id,
            details={
                "client_id": str(client_id),
                "pattern": pattern,
                "pattern_type": pattern_type,
                "created_at": utcnow_naive().isoformat()
            }
        )
    
    def log_reference_pattern_matched(
        self,
        client_id: UUID,
        reference_id: UUID,
        ticket_reference: str,
        pattern: str,
        match_type: str,
        confidence: float,
        ip_address: str = "system"
    ) -> AuditLog:
        """Log successful reference pattern match"""
        return self.log_action(
            user_id=None,
            action="reference_pattern_matched",
            ip_address=ip_address,
            entity="reference",
            entity_id=reference_id,
            details={
                "client_id": str(client_id),
                "ticket_reference": ticket_reference,
                "pattern": pattern,
                "match_type": match_type,
                "confidence": confidence,
                "matched_at": utcnow_naive().isoformat()
            }
        )
    
    def log_access_granted(
        self,
        grantor_id: UUID,
        user_id: UUID,
        client_id: UUID,
        ip_address: str,
        permissions: List[str],
        expires_at: Optional[str] = None
    ) -> AuditLog:
        """Log access grant to client"""
        return self.log_action(
            user_id=grantor_id,
            action="access_granted",
            ip_address=ip_address,
            entity="client_access",
            details={
                "target_user_id": str(user_id),
                "client_id": str(client_id),
                "permissions": permissions,
                "expires_at": expires_at,
                "granted_at": utcnow_naive().isoformat()
            }
        )
    
    def log_access_revoked(
        self,
        revoker_id: UUID,
        user_id: UUID,
        client_id: UUID,
        ip_address: str
    ) -> AuditLog:
        """Log access revocation from client"""
        return self.log_action(
            user_id=revoker_id,
            action="access_revoked",
            ip_address=ip_address,
            entity="client_access",
            details={
                "target_user_id": str(user_id),
                "client_id": str(client_id),
                "revoked_at": utcnow_naive().isoformat()
            }
        )
    
    def get_client_audit_logs(self, client_id: UUID, requester_role: str) -> List[AuditLog]:
        """Get all audit logs for a specific client"""
        if requester_role not in ["admin", "manager"]:
            return []
        
        client_actions = [
            "client_created",
            "client_updated",
            "client_deleted",
            "client_assigned",
            "rate_created",
            "rate_updated",
            "rate_approved",
            "reference_created",
            "reference_updated",
            "reference_pattern_matched",
            "access_granted",
            "access_revoked"
        ]
        
        query = select(AuditLog).where(
            AuditLog.entity_id == client_id,
            AuditLog.action.in_(client_actions)
        ).order_by(AuditLog.timestamp.desc())
        
        logs = self.db.exec(query).all()
        return list(logs)
    
    def get_rate_audit_logs(self, rate_id: UUID, requester_role: str) -> List[AuditLog]:
        """Get all audit logs for a specific rate"""
        if requester_role not in ["admin", "manager"]:
            return []
        
        rate_actions = [
            "rate_created",
            "rate_updated",
            "rate_deleted",
            "rate_approved",
            "rate_rejected"
        ]
        
        query = select(AuditLog).where(
            AuditLog.entity_id == rate_id,
            AuditLog.action.in_(rate_actions)
        ).order_by(AuditLog.timestamp.asc())
        
        logs = self.db.exec(query).all()
        return list(logs)