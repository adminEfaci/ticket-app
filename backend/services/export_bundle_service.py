import os
import shutil
import zipfile
import json
import logging
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Any
from uuid import UUID

from sqlmodel import Session

from ..models.export import (
    ExportRequest, ExportResult, ExportValidation,
    ExportAuditLog, WeeklyGrouping
)
from ..services.weekly_export_service import WeeklyExportService
from ..services.invoice_generator_service import InvoiceGeneratorService
from ..services.storage_service import StorageService
from ..services.audit_service import AuditService

logger = logging.getLogger(__name__)


class ExportBundleService:
    """Service for creating export bundles (ZIP files)"""
    
    def __init__(self, db: Session):
        self.db = db
        self.weekly_export_service = WeeklyExportService(db)
        self.invoice_generator = InvoiceGeneratorService()
        self.storage_service = StorageService()
        self.audit_service = AuditService(db)
        
        # Create export directory
        self.export_base_path = Path("exports")
        self.export_base_path.mkdir(exist_ok=True)
    
    async def create_export_bundle(
        self,
        export_request: ExportRequest,
        user_id: UUID
    ) -> ExportResult:
        """
        Create complete export bundle
        
        Args:
            export_request: Export request parameters
            user_id: User performing the export
            
        Returns:
            ExportResult with status and file info
        """
        try:
            # 1. Get tickets for export
            tickets = self.weekly_export_service.get_tickets_for_export(
                start_date=export_request.start_date,
                end_date=export_request.end_date,
                client_ids=export_request.client_ids
            )
            
            # 2. Validate export data
            validation = self.weekly_export_service.validate_export_data(
                tickets=tickets,
                require_images=export_request.include_images
            )
            
            # Check if we should proceed
            if validation.has_critical_errors and not export_request.force_export:
                error_msg = f"Export validation failed: {', '.join(validation.validation_errors)}"
                logger.error(error_msg)
                
                # Log failed export
                await self.weekly_export_service.log_export_operation(
                    user_id=user_id,
                    export_request=export_request,
                    validation=validation,
                    week_groups={},
                    success=False,
                    error_message=error_msg
                )
                
                # Create audit log entry
                audit_log = self._create_audit_log(
                    export_request=export_request,
                    user_id=user_id,
                    validation=validation,
                    status="failed",
                    error_message=error_msg
                )
                
                return ExportResult(
                    success=False,
                    export_id=audit_log.id,
                    validation=validation,
                    error_message=error_msg,
                    audit_log_id=audit_log.id
                )
            
            # 3. Group tickets by week/client/reference
            week_groups = self.weekly_export_service.group_tickets_by_week(tickets)
            
            if not week_groups:
                error_msg = "No data to export after grouping"
                return ExportResult(
                    success=False,
                    export_id=UUID('00000000-0000-0000-0000-000000000000'),
                    validation=validation,
                    error_message=error_msg,
                    audit_log_id=UUID('00000000-0000-0000-0000-000000000000')
                )
            
            # 4. Create export bundle
            export_path = await self._create_zip_bundle(
                week_groups=week_groups,
                export_request=export_request,
                validation=validation
            )
            
            # 5. Log successful export
            await self.weekly_export_service.log_export_operation(
                user_id=user_id,
                export_request=export_request,
                validation=validation,
                week_groups=week_groups,
                success=True
            )
            
            # 6. Create audit log entry
            audit_log = self._create_audit_log(
                export_request=export_request,
                user_id=user_id,
                validation=validation,
                status="success" if not validation.has_critical_errors else "partial",
                file_path=str(export_path),
                week_groups=week_groups
            )
            
            # Get file size
            file_size = export_path.stat().st_size if export_path.exists() else 0
            
            return ExportResult(
                success=True,
                export_id=audit_log.id,
                file_path=str(export_path),
                file_size=file_size,
                validation=validation,
                audit_log_id=audit_log.id
            )
            
        except Exception as e:
            logger.exception("Export bundle creation failed")
            error_msg = f"Export failed: {str(e)}"
            
            # Create minimal audit log
            audit_log = self._create_audit_log(
                export_request=export_request,
                user_id=user_id,
                validation=ExportValidation(
                    is_valid=False,
                    total_tickets=0,
                    matched_images=0,
                    missing_images=0,
                    match_percentage=0.0,
                    validation_errors=[error_msg]
                ),
                status="failed",
                error_message=error_msg
            )
            
            return ExportResult(
                success=False,
                export_id=audit_log.id,
                validation=validation if 'validation' in locals() else ExportValidation(
                    is_valid=False,
                    total_tickets=0,
                    matched_images=0,
                    missing_images=0,
                    match_percentage=0.0
                ),
                error_message=error_msg,
                audit_log_id=audit_log.id
            )
    
    async def _create_zip_bundle(
        self,
        week_groups: Dict[str, WeeklyGrouping],
        export_request: ExportRequest,
        validation: ExportValidation
    ) -> Path:
        """
        Create the ZIP file with proper structure
        
        Returns:
            Path to created ZIP file
        """
        # Create temporary directory for building the export
        timestamp = date.today().strftime("%Y%m%d")
        temp_dir = self.export_base_path / f"temp_{timestamp}_{os.getpid()}"
        temp_dir.mkdir(exist_ok=True)
        
        try:
            # Generate merged CSV
            merged_csv = self.invoice_generator.generate_merged_csv(week_groups)
            merged_path = temp_dir / "merged.csv"
            merged_path.write_text(merged_csv)
            
            # Process each week
            for week_key, week_group in week_groups.items():
                week_dir_name = f"week_{week_group.week_start.isoformat()}"
                week_dir = temp_dir / week_dir_name
                week_dir.mkdir(exist_ok=True)
                
                # Generate manifest for the week
                manifest = self.invoice_generator.generate_weekly_manifest(week_group)
                manifest_csv = self.invoice_generator.manifest_to_csv(manifest)
                manifest_path = week_dir / "manifest.csv"
                manifest_path.write_text(manifest_csv)
                
                # Process each client in the week
                for client_key, client_group in week_group.client_groups.items():
                    # Use client name for directory, sanitized
                    client_dir_name = f"client_{self._sanitize_filename(client_group.client_name)}"
                    client_dir = week_dir / client_dir_name
                    client_dir.mkdir(exist_ok=True)
                    
                    # Generate invoice
                    invoice = self.invoice_generator.generate_client_invoice(
                        client_group=client_group,
                        week_start=week_group.week_start,
                        week_end=week_group.week_end
                    )
                    
                    # Validate invoice totals
                    invoice_errors = self.invoice_generator.validate_invoice_totals(
                        invoice=invoice,
                        client_group=client_group
                    )
                    if invoice_errors:
                        logger.warning(
                            f"Invoice validation errors for {client_group.client_name}: "
                            f"{invoice_errors}"
                        )
                    
                    # Write invoice CSV
                    invoice_csv = self.invoice_generator.invoice_to_csv(invoice)
                    invoice_path = client_dir / "invoice.csv"
                    invoice_path.write_text(invoice_csv)
                    
                    # Copy ticket images if requested
                    if export_request.include_images:
                        tickets_dir = client_dir / "tickets"
                        tickets_dir.mkdir(exist_ok=True)
                        
                        for reference, ref_group in client_group.reference_groups.items():
                            # Create reference folder
                            ref_dir_name = self._sanitize_filename(reference)
                            ref_dir = tickets_dir / ref_dir_name
                            ref_dir.mkdir(exist_ok=True)
                            
                            # Copy images for tickets in this reference
                            for ticket_data in ref_group.tickets:
                                if ticket_data.get('image_path'):
                                    await self._copy_ticket_image(
                                        image_path=ticket_data['image_path'],
                                        ticket_number=ticket_data['ticket_number'],
                                        destination_dir=ref_dir
                                    )
            
            # Create audit.json if there were validation issues
            if validation.validation_errors or validation.has_critical_errors:
                audit_data = {
                    "export_date": date.today().isoformat(),
                    "validation": {
                        "is_valid": validation.is_valid,
                        "total_tickets": validation.total_tickets,
                        "matched_images": validation.matched_images,
                        "missing_images": validation.missing_images,
                        "match_percentage": validation.match_percentage,
                        "duplicate_tickets": validation.duplicate_tickets,
                        "validation_errors": validation.validation_errors
                    },
                    "forced_export": export_request.force_export
                }
                audit_path = temp_dir / "audit.json"
                audit_path.write_text(json.dumps(audit_data, indent=2))
            
            # Create ZIP file
            zip_filename = f"invoices_export_{timestamp}.zip"
            zip_path = self.export_base_path / zip_filename
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in temp_dir.rglob('*'):
                    if file_path.is_file():
                        arcname = str(file_path.relative_to(temp_dir))
                        zipf.write(file_path, arcname)
            
            logger.info(f"Created export bundle: {zip_path}")
            return zip_path
            
        finally:
            # Clean up temp directory
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize filename for filesystem compatibility"""
        # Remove or replace problematic characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')
        # Limit length
        return name[:50]
    
    async def _copy_ticket_image(
        self,
        image_path: str,
        ticket_number: str,
        destination_dir: Path
    ):
        """Copy ticket image to export directory with proper naming"""
        try:
            # Read image from storage
            image_data = await self.storage_service.read_file(image_path)
            if image_data:
                # Save with ticket number as filename
                dest_path = destination_dir / f"{ticket_number}.png"
                dest_path.write_bytes(image_data)
            else:
                logger.warning(f"Could not read image for ticket {ticket_number} from {image_path}")
        except Exception as e:
            logger.error(f"Error copying image for ticket {ticket_number}: {e}")
    
    def _create_audit_log(
        self,
        export_request: ExportRequest,
        user_id: UUID,
        validation: ExportValidation,
        status: str,
        file_path: Optional[str] = None,
        error_message: Optional[str] = None,
        week_groups: Optional[Dict[str, WeeklyGrouping]] = None
    ) -> ExportAuditLog:
        """Create audit log entry for export operation"""
        
        # Calculate totals if we have week groups
        total_tickets = 0
        total_clients = 0
        total_amount = 0.0
        
        if week_groups:
            total_tickets = sum(wg.total_tickets for wg in week_groups.values())
            total_clients = sum(len(wg.client_groups) for wg in week_groups.values())
            total_amount = sum(wg.total_amount for wg in week_groups.values())
        
        # Create metadata
        metadata = {
            "export_type": export_request.export_type,
            "include_images": export_request.include_images,
            "force_export": export_request.force_export,
            "client_ids": [str(cid) for cid in export_request.client_ids] if export_request.client_ids else None,
            "validation_summary": {
                "total_tickets": validation.total_tickets,
                "matched_images": validation.matched_images,
                "match_percentage": validation.match_percentage,
                "error_count": len(validation.validation_errors)
            }
        }
        
        audit_log = ExportAuditLog(
            export_type=export_request.export_type,
            start_date=export_request.start_date,
            end_date=export_request.end_date or export_request.start_date,
            user_id=user_id,
            status=status,
            total_tickets=total_tickets,
            total_clients=total_clients,
            total_amount=round(total_amount, 2),
            validation_passed=validation.is_valid,
            validation_errors=json.dumps(validation.validation_errors) if validation.validation_errors else None,
            export_metadata=json.dumps(metadata),
            file_path=file_path
        )
        
        self.db.add(audit_log)
        self.db.commit()
        self.db.refresh(audit_log)
        
        return audit_log
    
    def get_export_file_path(self, export_id: UUID) -> Optional[Path]:
        """Get file path for a previous export"""
        audit_log = self.db.get(ExportAuditLog, export_id)
        if audit_log and audit_log.file_path:
            path = Path(audit_log.file_path)
            if path.exists():
                return path
        return None