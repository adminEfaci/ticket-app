import pytest
import tempfile
import os
import shutil
from pathlib import Path
from datetime import date, datetime
from uuid import UUID, uuid4
from io import BytesIO
from unittest.mock import Mock, patch, AsyncMock
import pandas as pd
import xlwt
from PIL import Image, ImageDraw

from sqlmodel import Session, select, create_engine, SQLModel
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from main import app
from backend.core.database import get_session
from backend.models.user import User, UserRole
from backend.models.client import Client, ClientReference, ClientRate
from backend.models.ticket import Ticket, TicketDTO
from backend.models.batch import ProcessingBatch as Batch, BatchStatus
from backend.models.ticket_image import TicketImage, TicketImageCreate
from backend.models.match_result import MatchResult

from backend.services.auth_service import get_password_hash
from backend.services.client_service import ClientService
from backend.services.xls_parser_service import XLSParserService
from backend.services.ticket_mapper import TicketMapper
from backend.services.ticket_validator import TicketValidator
from backend.services.ticket_service import TicketService
from backend.services.pdf_extraction_service import PDFExtractionService
from backend.services.ocr_service import OCRService
from backend.services.image_validator import ImageValidator
from backend.services.ticket_image_service import TicketImageService
from backend.services.match_service import MatchService
from backend.services.reference_matcher import ReferenceMatcher


@pytest.fixture(scope="function")
def test_session():
    """Create a test database session"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as session:
        yield session


@pytest.fixture(scope="function")
def client(test_session):
    """Create test client with session override"""
    def get_session_override():
        return test_session
    
    app.dependency_overrides[get_session] = get_session_override
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(test_session):
    """Create an admin user for testing"""
    user = User(
        username="admin",
        email="admin@test.com",
        full_name="Admin User",
        hashed_password=get_password_hash("adminpass123"),
        role=UserRole.ADMIN,
        is_active=True
    )
    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)
    return user


@pytest.fixture
def admin_headers(client, admin_user):
    """Get auth headers for admin user"""
    response = client.post(
        "/api/auth/login",
        data={
            "username": "admin",
            "password": "adminpass123"
        }
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def temp_dir():
    """Create temporary directory for file operations"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


class TestComprehensiveWorkflow:
    """Comprehensive integration test covering the full workflow"""
    
    def test_complete_workflow_with_all_features(self, client, admin_headers, test_session, temp_dir):
        """Test the complete workflow from client setup to final matching"""
        
        # Step 1: Create clients including TOPPS
        print("Step 1: Creating clients...")
        clients_data = [
            {
                "name": "TOPPS",
                "billing_email": "billing@topps.com",
                "invoice_format": "xlsx",
                "credit_terms_days": 30
            },
            {
                "name": "ABC Transport",
                "billing_email": "billing@abc.com",
                "invoice_format": "csv",
                "credit_terms_days": 45
            },
            {
                "name": "XYZ Logistics",
                "billing_email": "billing@xyz.com",
                "invoice_format": "xlsx",
                "credit_terms_days": 30
            }
        ]
        
        created_clients = {}
        for client_data in clients_data:
            response = client.post(
                "/api/clients/",
                json=client_data,
                headers=admin_headers
            )
            assert response.status_code == 201
            created_client = response.json()
            created_clients[created_client["name"]] = created_client
            print(f"Created client: {created_client['name']} with ID: {created_client['id']}")
        
        # Step 2: Set up reference patterns for each client
        print("\nStep 2: Setting up reference patterns...")
        
        # TOPPS gets T-xxx pattern
        topps_ref = {
            "client_id": created_clients["TOPPS"]["id"],
            "pattern": r"T-\d+",
            "is_regex": True,
            "is_fuzzy": False,
            "priority": 10,
            "description": "T-xxx pattern for TOPPS"
        }
        response = client.post(
            f"/api/clients/{created_clients['TOPPS']['id']}/references",
            json=topps_ref,
            headers=admin_headers
        )
        assert response.status_code == 201
        
        # ABC Transport gets #007 pattern (with and without #)
        abc_refs = [
            {
                "client_id": created_clients["ABC Transport"]["id"],
                "pattern": r"#?\d{3}",  # Matches 007 or #007
                "is_regex": True,
                "is_fuzzy": False,
                "priority": 20,
                "description": "Three digit codes with optional #"
            },
            {
                "client_id": created_clients["ABC Transport"]["id"],
                "pattern": "ABC*",
                "is_regex": False,
                "is_fuzzy": False,
                "priority": 30,
                "description": "ABC prefix pattern"
            }
        ]
        for ref in abc_refs:
            response = client.post(
                f"/api/clients/{created_clients['ABC Transport']['id']}/references",
                json=ref,
                headers=admin_headers
            )
            assert response.status_code == 201
        
        # XYZ Logistics gets MM pattern
        xyz_ref = {
            "client_id": created_clients["XYZ Logistics"]["id"],
            "pattern": r"MM\d+",
            "is_regex": True,
            "is_fuzzy": False,
            "priority": 10,
            "description": "MM followed by numbers"
        }
        response = client.post(
            f"/api/clients/{created_clients['XYZ Logistics']['id']}/references",
            json=xyz_ref,
            headers=admin_headers
        )
        assert response.status_code == 201
        
        # Step 3: Set up rates for each client
        print("\nStep 3: Setting up client rates...")
        rates_data = [
            {"client": "TOPPS", "rate": 25.00},
            {"client": "ABC Transport", "rate": 30.00},
            {"client": "XYZ Logistics", "rate": 35.00}
        ]
        
        for rate_data in rates_data:
            rate = {
                "client_id": created_clients[rate_data["client"]]["id"],
                "rate_per_tonne": rate_data["rate"],
                "effective_from": "2024-01-01",
                "notes": f"Standard rate for {rate_data['client']}"
            }
            response = client.post(
                f"/api/clients/{created_clients[rate_data['client']]['id']}/rates",
                json=rate,
                headers=admin_headers,
                params={"auto_approve": True}
            )
            assert response.status_code == 201
            print(f"Set rate ${rate_data['rate']}/tonne for {rate_data['client']}")
        
        # Step 4: Load clients from CSV
        print("\nStep 4: Testing client CSV import...")
        csv_content = """name,billing_email,invoice_format,credit_terms_days,parent_company
"New Transport Co","billing@newtransport.com","csv",30,""
"Sub Contractor 1","billing@sub1.com","xlsx",45,"New Transport Co"
"""
        csv_file = BytesIO(csv_content.encode())
        
        files = {
            "file": ("clients.csv", csv_file, "text/csv")
        }
        
        response = client.post(
            "/api/clients/import",
            files=files,
            headers=admin_headers
        )
        assert response.status_code == 200
        import_result = response.json()
        assert import_result["success"] == True
        assert import_result["imported"] >= 2
        print(f"Imported {import_result['imported']} clients from CSV")
        
        # Step 5: Create and upload XLS file with tickets
        print("\nStep 5: Creating and uploading XLS file with tickets...")
        xls_path = self._create_test_xls_file(temp_dir)
        
        with open(xls_path, 'rb') as f:
            files = {
                "file": ("APRIL 14 2025.xls", f, "application/vnd.ms-excel")
            }
            
            response = client.post(
                "/api/upload/",
                files=files,
                headers=admin_headers
            )
            assert response.status_code == 200
            upload_result = response.json()
            batch_id = upload_result["batch"]["id"]
            print(f"Uploaded XLS file, batch ID: {batch_id}")
        
        # Step 6: Process the batch to parse tickets
        print("\nStep 6: Processing batch to parse tickets...")
        response = client.post(
            f"/api/batch/{batch_id}/process",
            headers=admin_headers
        )
        assert response.status_code == 200
        process_result = response.json()
        print(f"Processed {process_result.get('tickets_parsed', 0)} tickets")
        
        # Verify tickets were created and assigned to clients
        tickets = test_session.exec(
            select(Ticket).where(Ticket.batch_id == UUID(batch_id))
        ).all()
        
        assert len(tickets) > 0
        print(f"Created {len(tickets)} tickets in database")
        
        # Check client assignments
        for ticket in tickets:
            if ticket.reference and "T-" in ticket.reference:
                assert ticket.client_id == UUID(created_clients["TOPPS"]["id"])
                assert ticket.rate_per_tonne == 25.00
            elif ticket.reference and ("007" in ticket.reference or "#007" in ticket.reference):
                assert ticket.client_id == UUID(created_clients["ABC Transport"]["id"])
                assert ticket.rate_per_tonne == 30.00
            elif ticket.reference and "MM" in ticket.reference:
                assert ticket.client_id == UUID(created_clients["XYZ Logistics"]["id"])
                assert ticket.rate_per_tonne == 35.00
            elif ticket.reference == "REPRINT" or ticket.status == "VOID":
                # REPRINT VOID tickets should be filtered out or marked appropriately
                assert ticket.net_weight == 0.0
        
        # Step 7: Upload PDF with ticket images
        print("\nStep 7: Creating and uploading PDF with ticket images...")
        pdf_path = self._create_test_pdf_with_tickets(temp_dir, tickets[:3])  # Use first 3 tickets
        
        with open(pdf_path, 'rb') as f:
            files = {
                "file": ("tickets.pdf", f, "application/pdf")
            }
            
            response = client.post(
                f"/api/batch/{batch_id}/upload-images",
                files=files,
                headers=admin_headers
            )
            assert response.status_code == 200
            image_result = response.json()
            print(f"Extracted {image_result.get('images_extracted', 0)} images from PDF")
        
        # Step 8: Run OCR and matching
        print("\nStep 8: Running OCR and ticket matching...")
        
        # Mock OCR service for consistent results
        with patch('backend.services.ocr_service.OCRService.extract_ticket_number') as mock_ocr:
            # Return ticket numbers that match our created tickets
            mock_ocr.side_effect = [
                (ticket.ticket_number, 95.0) for ticket in tickets[:3]
            ]
            
            response = client.post(
                f"/api/batch/{batch_id}/match",
                headers=admin_headers
            )
            assert response.status_code == 200
            match_result = response.json()
            print(f"Matching completed: {match_result.get('message', 'Success')}")
        
        # Step 9: Verify complete data flow
        print("\nStep 9: Verifying complete data flow...")
        
        # Check ticket images were created
        ticket_images = test_session.exec(
            select(TicketImage).where(TicketImage.batch_id == UUID(batch_id))
        ).all()
        assert len(ticket_images) > 0
        print(f"Created {len(ticket_images)} ticket images")
        
        # Check match results
        match_results = test_session.exec(
            select(MatchResult).where(MatchResult.batch_id == UUID(batch_id))
        ).all()
        assert len(match_results) > 0
        print(f"Created {len(match_results)} match results")
        
        # Verify high confidence matches
        high_confidence_matches = [m for m in match_results if m.confidence >= 90.0]
        print(f"Found {len(high_confidence_matches)} high confidence matches")
        
        # Step 10: Test edge cases
        print("\nStep 10: Testing edge cases...")
        
        # Test #007 vs 007 matching
        response = client.post(
            "/api/clients/test-reference-matching",
            json=["#007", "007", "T-123", "MM1001", "REPRINT"],
            headers=admin_headers
        )
        assert response.status_code == 200
        match_test = response.json()
        
        # Both #007 and 007 should match ABC Transport
        assert match_test["#007"]["best_match"]["client_name"] == "ABC Transport"
        assert match_test["007"]["best_match"]["client_name"] == "ABC Transport"
        
        # T-123 should match TOPPS
        assert match_test["T-123"]["best_match"]["client_name"] == "TOPPS"
        
        # MM1001 should match XYZ Logistics
        assert match_test["MM1001"]["best_match"]["client_name"] == "XYZ Logistics"
        
        print("\nWorkflow test completed successfully!")
        
        # Return summary for assertions
        return {
            "clients_created": len(created_clients),
            "tickets_created": len(tickets),
            "images_extracted": len(ticket_images),
            "matches_found": len(match_results),
            "high_confidence_matches": len(high_confidence_matches)
        }
    
    def _create_test_xls_file(self, temp_dir):
        """Create a test XLS file in APRIL 14 2025 format"""
        xls_path = os.path.join(temp_dir, "APRIL 14 2025.xls")
        
        workbook = xlwt.Workbook()
        sheet = workbook.add_sheet('Tickets')
        
        # Headers matching the expected format
        headers = [
            'Ticket Number', 'Reference', 'Entry Date', 'Entry Time',
            'Truck Rego', 'Product', 'Supplier', 'Gross Weight',
            'Tare Weight', 'Net Weight', 'Status'
        ]
        
        for col, header in enumerate(headers):
            sheet.write(0, col, header)
        
        # Test data with various reference patterns
        test_data = [
            # TOPPS tickets (T-xxx pattern)
            ['TK001', 'T-100', '14/04/2025', '08:30', 'ABC123', 'Sand', 'Quarry A', 
             '25000', '10000', '15000', 'COMPLETE'],
            ['TK002', 'T-101', '14/04/2025', '09:15', 'ABC124', 'Gravel', 'Quarry A',
             '30000', '12000', '18000', 'COMPLETE'],
            
            # ABC Transport tickets (#007 pattern)
            ['TK003', '#007', '14/04/2025', '10:00', 'XYZ456', 'Rock', 'Quarry B',
             '28000', '11000', '17000', 'COMPLETE'],
            ['TK004', '007', '14/04/2025', '10:30', 'XYZ457', 'Sand', 'Quarry B',
             '26000', '10500', '15500', 'COMPLETE'],
            
            # XYZ Logistics tickets (MM pattern)
            ['TK005', 'MM1001', '14/04/2025', '11:00', 'DEF789', 'Gravel', 'Quarry C',
             '32000', '13000', '19000', 'COMPLETE'],
            ['TK006', 'MM1002', '14/04/2025', '11:30', 'DEF790', 'Rock', 'Quarry C',
             '29000', '11500', '17500', 'COMPLETE'],
            
            # REPRINT VOID ticket (should be filtered)
            ['TK007', 'REPRINT', '14/04/2025', '12:00', 'GHI012', 'Sand', 'Quarry A',
             '0', '0', '0', 'VOID'],
            
            # Regular VOID ticket
            ['TK008', 'REF123', '14/04/2025', '12:30', 'GHI013', 'Gravel', 'Quarry B',
             '0', '0', '0', 'VOID'],
            
            # Unmatched reference
            ['TK009', 'NOMATCH', '14/04/2025', '13:00', 'JKL345', 'Rock', 'Quarry D',
             '27000', '10800', '16200', 'COMPLETE'],
            
            # Empty row (should be skipped)
            ['', '', '', '', '', '', '', '', '', '', ''],
            
            # Multi-row ticket (testing aggregation)
            ['TK010', 'T-102', '14/04/2025', '14:00', 'MNO678', 'Sand', 'Quarry A',
             '15000', '6000', '9000', 'PARTIAL'],
            ['TK010', 'T-102', '14/04/2025', '14:30', 'MNO678', 'Sand', 'Quarry A',
             '15000', '6000', '9000', 'COMPLETE']
        ]
        
        for row, data in enumerate(test_data, start=1):
            for col, value in enumerate(data):
                sheet.write(row, col, value)
        
        workbook.save(xls_path)
        return xls_path
    
    def _create_test_pdf_with_tickets(self, temp_dir, tickets):
        """Create a test PDF with ticket images"""
        pdf_path = os.path.join(temp_dir, "tickets.pdf")
        
        # Create ticket images
        images = []
        for ticket in tickets:
            # Create a ticket-like image
            img = Image.new('RGB', (800, 600), color='white')
            draw = ImageDraw.Draw(img)
            
            # Draw ticket border
            draw.rectangle([50, 50, 750, 550], outline='black', width=3)
            
            # Add ticket content
            draw.text((100, 100), "WEIGHBRIDGE TICKET", fill='black')
            draw.text((100, 150), f"Ticket #: {ticket.ticket_number}", fill='black')
            draw.text((100, 200), f"Reference: {ticket.reference or 'N/A'}", fill='black')
            draw.text((100, 250), f"Date: {ticket.entry_date}", fill='black')
            draw.text((100, 300), f"Truck: {ticket.truck_rego or 'N/A'}", fill='black')
            draw.text((100, 350), f"Product: {ticket.product or 'N/A'}", fill='black')
            draw.text((100, 400), f"Net Weight: {ticket.net_weight} kg", fill='black')
            draw.text((100, 450), f"Status: {ticket.status}", fill='black')
            
            images.append(img)
        
        # For testing, we'll save as individual images since we're mocking PDF extraction
        # In real implementation, this would create an actual PDF
        for i, img in enumerate(images):
            img.save(os.path.join(temp_dir, f"ticket_{i}.png"))
        
        # Create a mock PDF file
        with open(pdf_path, 'wb') as f:
            f.write(b'%PDF-1.4 mock content for testing')
        
        return pdf_path
    
    def test_error_handling_and_recovery(self, client, admin_headers, test_session, temp_dir):
        """Test error handling throughout the workflow"""
        
        # Test invalid client CSV
        print("Testing invalid client CSV...")
        invalid_csv = """name,billing_email,invalid_column
"Bad Client",,
"""
        csv_file = BytesIO(invalid_csv.encode())
        
        files = {
            "file": ("invalid_clients.csv", csv_file, "text/csv")
        }
        
        response = client.post(
            "/api/clients/import",
            files=files,
            headers=admin_headers
        )
        assert response.status_code == 400
        
        # Test XLS with validation errors
        print("Testing XLS with validation errors...")
        xls_path = self._create_invalid_xls_file(temp_dir)
        
        with open(xls_path, 'rb') as f:
            files = {
                "file": ("invalid_tickets.xls", f, "application/vnd.ms-excel")
            }
            
            response = client.post(
                "/api/upload/",
                files=files,
                headers=admin_headers
            )
            assert response.status_code == 200
            batch_id = response.json()["batch"]["id"]
        
        # Process should handle errors gracefully
        response = client.post(
            f"/api/batch/{batch_id}/process",
            headers=admin_headers
        )
        assert response.status_code == 200
        result = response.json()
        assert result.get("tickets_invalid", 0) > 0
        
        print("Error handling tests passed!")
    
    def _create_invalid_xls_file(self, temp_dir):
        """Create XLS file with validation errors"""
        xls_path = os.path.join(temp_dir, "invalid_tickets.xls")
        
        workbook = xlwt.Workbook()
        sheet = workbook.add_sheet('Tickets')
        
        # Headers
        headers = [
            'Ticket Number', 'Reference', 'Entry Date', 'Entry Time',
            'Truck Rego', 'Product', 'Supplier', 'Gross Weight',
            'Tare Weight', 'Net Weight', 'Status'
        ]
        
        for col, header in enumerate(headers):
            sheet.write(0, col, header)
        
        # Invalid test data
        test_data = [
            # Missing ticket number
            ['', 'REF001', '14/04/2025', '08:30', 'ABC123', 'Sand', 'Quarry A',
             '25000', '10000', '15000', 'COMPLETE'],
            
            # Weight exceeds 100 tonnes
            ['TK999', 'REF002', '14/04/2025', '09:00', 'XYZ456', 'Rock', 'Quarry B',
             '150000', '30000', '120000', 'COMPLETE'],
            
            # VOID with non-zero weight
            ['TK998', 'REF003', '14/04/2025', '10:00', 'DEF789', 'Gravel', 'Quarry C',
             '20000', '8000', '12000', 'VOID'],
            
            # Invalid date format
            ['TK997', 'REF004', 'INVALID', '11:00', 'GHI012', 'Sand', 'Quarry D',
             '30000', '12000', '18000', 'COMPLETE']
        ]
        
        for row, data in enumerate(test_data, start=1):
            for col, value in enumerate(data):
                sheet.write(row, col, value)
        
        workbook.save(xls_path)
        return xls_path
    
    def test_performance_with_large_dataset(self, client, admin_headers, test_session, temp_dir):
        """Test system performance with larger datasets"""
        
        print("Testing performance with large dataset...")
        
        # Create client for bulk test
        client_data = {
            "name": "Bulk Test Co",
            "billing_email": "bulk@test.com"
        }
        
        response = client.post(
            "/api/clients/",
            json=client_data,
            headers=admin_headers
        )
        assert response.status_code == 201
        bulk_client = response.json()
        
        # Add reference pattern
        ref = {
            "client_id": bulk_client["id"],
            "pattern": "BULK*",
            "is_regex": False,
            "is_fuzzy": False,
            "priority": 10
        }
        
        response = client.post(
            f"/api/clients/{bulk_client['id']}/references",
            json=ref,
            headers=admin_headers
        )
        assert response.status_code == 201
        
        # Create XLS with 100 tickets
        xls_path = self._create_large_xls_file(temp_dir, 100)
        
        start_time = datetime.now()
        
        with open(xls_path, 'rb') as f:
            files = {
                "file": ("large_batch.xls", f, "application/vnd.ms-excel")
            }
            
            response = client.post(
                "/api/upload/",
                files=files,
                headers=admin_headers
            )
            assert response.status_code == 200
            batch_id = response.json()["batch"]["id"]
        
        # Process the large batch
        response = client.post(
            f"/api/batch/{batch_id}/process",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        print(f"Processed 100 tickets in {processing_time:.2f} seconds")
        assert processing_time < 30  # Should complete within 30 seconds
        
        # Verify all tickets were processed
        tickets = test_session.exec(
            select(Ticket).where(Ticket.batch_id == UUID(batch_id))
        ).all()
        assert len(tickets) == 100
    
    def _create_large_xls_file(self, temp_dir, num_tickets):
        """Create XLS file with specified number of tickets"""
        xls_path = os.path.join(temp_dir, "large_batch.xls")
        
        workbook = xlwt.Workbook()
        sheet = workbook.add_sheet('Tickets')
        
        # Headers
        headers = [
            'Ticket Number', 'Reference', 'Entry Date', 'Entry Time',
            'Truck Rego', 'Product', 'Supplier', 'Gross Weight',
            'Tare Weight', 'Net Weight', 'Status'
        ]
        
        for col, header in enumerate(headers):
            sheet.write(0, col, header)
        
        # Generate test data
        for i in range(num_tickets):
            row_data = [
                f'BULK{i:04d}',  # Ticket number
                f'BULK-REF-{i}',  # Reference
                '14/04/2025',     # Date
                f'{8 + i//60:02d}:{i%60:02d}',  # Time
                f'TRUCK{i:03d}',  # Truck rego
                ['Sand', 'Gravel', 'Rock'][i % 3],  # Product
                f'Quarry {chr(65 + i % 4)}',  # Supplier
                str(20000 + i * 100),  # Gross weight
                str(8000 + i * 50),    # Tare weight
                str(12000 + i * 50),   # Net weight
                'COMPLETE'             # Status
            ]
            
            for col, value in enumerate(row_data):
                sheet.write(i + 1, col, value)
        
        workbook.save(xls_path)
        return xls_path