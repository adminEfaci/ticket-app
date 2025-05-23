import pytest
import json
import zipfile
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4
from io import BytesIO

from fastapi.testclient import TestClient
from sqlmodel import Session

from main import app
from backend.core.database import get_session
from backend.models.user import User, UserRole
from backend.models.client import Client, ClientRate
from backend.models.ticket import Ticket
from backend.models.batch import ProcessingBatch
from backend.models.export import ExportAuditLog


class TestExportFlow:
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    @pytest.fixture
    def test_db(self):
        """Create test database session"""
        from backend.core.database import engine
        from sqlmodel import SQLModel
        
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            yield session
    
    @pytest.fixture
    def admin_user(self, test_db):
        """Create admin user"""
        user = User(
            username="admin",
            email="admin@test.com",
            role=UserRole.ADMIN,
            is_active=True
        )
        user.set_password("adminpass")
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)
        return user
    
    @pytest.fixture
    def auth_headers(self, client, admin_user):
        """Get auth headers for admin user"""
        response = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "adminpass"}
        )
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    @pytest.fixture
    def test_clients(self, test_db):
        """Create test clients with rates"""
        # Client 007
        client_007 = Client(
            name="Client 007",
            code="007",
            is_active=True
        )
        test_db.add(client_007)
        
        # Rate for Client 007
        rate_007 = ClientRate(
            client_id=client_007.id,
            rate_per_tonne=25.0,
            effective_from=date(2024, 1, 1),
            is_active=True,
            approved_by=uuid4(),
            approved_at=datetime.utcnow()
        )
        test_db.add(rate_007)
        
        # Client 004
        client_004 = Client(
            name="Client 004",
            code="004",
            is_active=True
        )
        test_db.add(client_004)
        
        # Rate for Client 004
        rate_004 = ClientRate(
            client_id=client_004.id,
            rate_per_tonne=30.0,
            effective_from=date(2024, 1, 1),
            is_active=True,
            approved_by=uuid4(),
            approved_at=datetime.utcnow()
        )
        test_db.add(rate_004)
        
        test_db.commit()
        test_db.refresh(client_007)
        test_db.refresh(client_004)
        
        return {"007": client_007, "004": client_004}
    
    @pytest.fixture
    def test_batch(self, test_db):
        """Create test batch"""
        batch = ProcessingBatch(
            status="completed",
            file_hash="test_hash",
            uploaded_at=datetime.utcnow()
        )
        test_db.add(batch)
        test_db.commit()
        test_db.refresh(batch)
        return batch
    
    @pytest.fixture
    def test_tickets(self, test_db, test_batch, test_clients):
        """Create test tickets for export"""
        tickets = []
        
        # Week 1 tickets (April 15-20, 2024)
        # Client 007 - Reference #007
        for i in range(3):
            ticket = Ticket(
                batch_id=test_batch.id,
                ticket_number=f"T412{i}",
                reference="#007",
                note=f"Note {i}",
                status="REPRINT",
                is_billable=True,
                net_weight=8.5 + i,
                entry_date=date(2024, 4, 15 + i),
                client_id=test_clients["007"].id,
                image_path=f"tickets/T412{i}.png",
                image_extracted=True
            )
            test_db.add(ticket)
            tickets.append(ticket)
        
        # Client 007 - Reference MM1001
        ticket = Ticket(
            batch_id=test_batch.id,
            ticket_number="T4123",
            reference="MM1001",
            status="REPRINT",
            is_billable=True,
            net_weight=12.0,
            entry_date=date(2024, 4, 16),
            client_id=test_clients["007"].id,
            image_path="tickets/T4123.png",
            image_extracted=True
        )
        test_db.add(ticket)
        tickets.append(ticket)
        
        # Client 004 - Reference #004
        for i in range(2):
            ticket = Ticket(
                batch_id=test_batch.id,
                ticket_number=f"T413{i}",
                reference="#004",
                status="REPRINT",
                is_billable=True,
                net_weight=10.0 + i * 2,
                entry_date=date(2024, 4, 17 + i),
                client_id=test_clients["004"].id,
                image_path=f"tickets/T413{i}.png",
                image_extracted=True
            )
            test_db.add(ticket)
            tickets.append(ticket)
        
        # Week 2 tickets (April 22-27, 2024)
        ticket = Ticket(
            batch_id=test_batch.id,
            ticket_number="T4140",
            reference="#007",
            status="REPRINT",
            is_billable=True,
            net_weight=15.0,
            entry_date=date(2024, 4, 22),
            client_id=test_clients["007"].id,
            image_path="tickets/T4140.png",
            image_extracted=True
        )
        test_db.add(ticket)
        tickets.append(ticket)
        
        # Add some non-REPRINT tickets that should be excluded
        void_ticket = Ticket(
            batch_id=test_batch.id,
            ticket_number="T9999",
            reference="#007",
            status="VOID",
            is_billable=False,
            net_weight=0.0,
            entry_date=date(2024, 4, 15),
            client_id=test_clients["007"].id
        )
        test_db.add(void_ticket)
        
        test_db.commit()
        return tickets
    
    def test_export_validation_endpoint(self, client, auth_headers, test_tickets):
        """Test export validation endpoint"""
        response = client.post(
            "/api/export/validate",
            headers=auth_headers,
            json={
                "start_date": "2024-04-15",
                "end_date": "2024-04-30",
                "export_type": "weekly",
                "include_images": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["validation"]["is_valid"] is True
        assert data["validation"]["total_tickets"] == 7  # Excluding VOID
        assert data["validation"]["matched_images"] == 7
        assert data["validation"]["match_percentage"] == 100.0
        assert data["can_export"] is True
        assert data["ticket_count"] == 7
    
    def test_export_validation_missing_images(self, client, auth_headers, test_db, test_tickets):
        """Test validation with missing images"""
        # Remove image from one ticket
        ticket = test_tickets[0]
        ticket.image_path = None
        ticket.image_extracted = False
        test_db.commit()
        
        response = client.post(
            "/api/export/validate",
            headers=auth_headers,
            json={
                "start_date": "2024-04-15",
                "end_date": "2024-04-30",
                "export_type": "weekly",
                "include_images": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["validation"]["is_valid"] is False
        assert data["validation"]["matched_images"] == 6
        assert data["validation"]["missing_images"] == 1
        assert data["can_export"] is False
        assert data["require_force"] is True
    
    def test_create_export_bundle(self, client, auth_headers, test_tickets):
        """Test creating export bundle"""
        response = client.post(
            "/api/export/invoices-bundle",
            headers=auth_headers,
            json={
                "start_date": "2024-04-15",
                "end_date": "2024-04-30",
                "export_type": "weekly",
                "include_images": False  # Skip images for test
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["export_id"] is not None
        assert data["file_path"] is not None
        assert data["file_size"] > 0
        assert data["validation"]["total_tickets"] == 7
        assert data["audit_log_id"] is not None
    
    def test_export_weekly_bundle_download(self, client, auth_headers, test_tickets):
        """Test downloading weekly export bundle"""
        response = client.get(
            "/api/export/invoices-bundle/2024-04-15",
            headers=auth_headers,
            params={"include_images": False}
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        
        # Verify ZIP structure
        zip_data = BytesIO(response.content)
        with zipfile.ZipFile(zip_data, 'r') as zf:
            namelist = zf.namelist()
            
            # Check for merged.csv
            assert "merged.csv" in namelist
            
            # Check for week directories
            assert any("week_2024-04-15" in name for name in namelist)
            assert any("week_2024-04-22" in name for name in namelist)
            
            # Check for manifest files
            assert "week_2024-04-15/manifest.csv" in namelist
            assert "week_2024-04-22/manifest.csv" in namelist
            
            # Check for client directories
            assert any("client_Client_007" in name for name in namelist)
            assert any("client_Client_004" in name for name in namelist)
            
            # Check for invoice files
            assert any("invoice.csv" in name for name in namelist)
            
            # Read and verify merged.csv content
            with zf.open("merged.csv") as f:
                content = f.read().decode('utf-8')
                assert "T4120" in content  # First ticket
                assert "Client 007" in content
                assert "#007" in content
                assert "25.00" in content  # Rate
    
    def test_export_with_forced_validation(self, client, auth_headers, test_db, test_tickets):
        """Test export with forced validation override"""
        # Create duplicate ticket
        duplicate = Ticket(
            batch_id=test_tickets[0].batch_id,
            ticket_number="T4120",  # Duplicate number
            reference="#007",
            status="REPRINT",
            is_billable=True,
            net_weight=5.0,
            entry_date=date(2024, 4, 15),
            client_id=test_tickets[0].client_id,
            image_path="tickets/T4120_dup.png",
            image_extracted=True
        )
        test_db.add(duplicate)
        test_db.commit()
        
        # Try export without force - should fail
        response = client.post(
            "/api/export/invoices-bundle",
            headers=auth_headers,
            json={
                "start_date": "2024-04-15",
                "end_date": "2024-04-30",
                "export_type": "weekly",
                "include_images": False,
                "force_export": False
            }
        )
        
        assert response.status_code == 400
        
        # Try with force - should succeed
        response = client.post(
            "/api/export/invoices-bundle",
            headers=auth_headers,
            json={
                "start_date": "2024-04-15",
                "end_date": "2024-04-30",
                "export_type": "weekly",
                "include_images": False,
                "force_export": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["validation"]["duplicate_tickets"]) > 0
    
    def test_export_financial_accuracy(self, client, auth_headers, test_tickets):
        """Test financial calculations in export"""
        response = client.get(
            "/api/export/invoices-bundle/2024-04-15",
            headers=auth_headers,
            params={"include_images": False}
        )
        
        assert response.status_code == 200
        
        # Parse ZIP and check calculations
        zip_data = BytesIO(response.content)
        with zipfile.ZipFile(zip_data, 'r') as zf:
            # Read week 1 manifest
            with zf.open("week_2024-04-15/manifest.csv") as f:
                manifest_content = f.read().decode('utf-8')
                
                # Client 007: 4 tickets, total weight = 8.5 + 9.5 + 10.5 + 12.0 = 40.0
                # Amount = 40.0 * 25.0 = 1000.00
                assert "Client 007" in manifest_content
                assert "40.00" in manifest_content  # Total weight
                assert "1000.00" in manifest_content  # Total amount
                
                # Client 004: 2 tickets, total weight = 10.0 + 12.0 = 22.0
                # Amount = 22.0 * 30.0 = 660.00
                assert "Client 004" in manifest_content
                assert "22.00" in manifest_content
                assert "660.00" in manifest_content
            
            # Read Client 007 invoice
            invoice_path = None
            for name in zf.namelist():
                if "Client_007" in name and "invoice.csv" in name and "week_2024-04-15" in name:
                    invoice_path = name
                    break
            
            assert invoice_path is not None
            
            with zf.open(invoice_path) as f:
                invoice_content = f.read().decode('utf-8')
                
                # Check reference grouping
                assert "#007" in invoice_content
                assert "MM1001" in invoice_content
                
                # Check totals
                assert "Total Amount,$1000.00" in invoice_content
    
    def test_export_audit_logging(self, client, auth_headers, test_db, test_tickets):
        """Test that export operations are logged"""
        response = client.post(
            "/api/export/invoices-bundle",
            headers=auth_headers,
            json={
                "start_date": "2024-04-15",
                "end_date": "2024-04-30",
                "export_type": "weekly",
                "include_images": False
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Check audit log was created
        audit_log = test_db.get(ExportAuditLog, data["audit_log_id"])
        assert audit_log is not None
        assert audit_log.status == "success"
        assert audit_log.total_tickets == 7
        assert audit_log.total_clients == 2
        assert audit_log.total_amount > 0
        assert audit_log.validation_passed is True
        assert audit_log.file_path is not None
        
        # Check metadata
        metadata = json.loads(audit_log.export_metadata)
        assert metadata["export_type"] == "weekly"
        assert metadata["validation_summary"]["total_tickets"] == 7
    
    def test_download_previous_export(self, client, auth_headers, test_tickets):
        """Test downloading a previously generated export"""
        # First create an export
        response = client.post(
            "/api/export/invoices-bundle",
            headers=auth_headers,
            json={
                "start_date": "2024-04-15",
                "export_type": "weekly",
                "include_images": False
            }
        )
        
        export_id = response.json()["export_id"]
        
        # Download using export ID
        response = client.get(
            f"/api/export/download/{export_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
    
    def test_export_permissions(self, client, test_db):
        """Test that only authorized users can export"""
        # Create viewer user
        viewer = User(
            username="viewer",
            email="viewer@test.com",
            role=UserRole.VIEWER,
            is_active=True
        )
        viewer.set_password("viewerpass")
        test_db.add(viewer)
        test_db.commit()
        
        # Get viewer token
        response = client.post(
            "/api/auth/login",
            json={"username": "viewer", "password": "viewerpass"}
        )
        viewer_token = response.json()["access_token"]
        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
        
        # Try to create export as viewer - should fail
        response = client.post(
            "/api/export/invoices-bundle",
            headers=viewer_headers,
            json={
                "start_date": "2024-04-15",
                "export_type": "weekly"
            }
        )
        
        assert response.status_code == 403