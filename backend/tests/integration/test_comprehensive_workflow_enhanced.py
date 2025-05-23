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
from backend.services.multi_row_xls_parser import MultiRowXLSParser
from backend.services.ticket_mapper import TicketMapper
from backend.services.ticket_validator import TicketValidator
from backend.services.ticket_service import TicketService
from backend.services.pdf_extraction_service import PDFExtractionService
from backend.services.ocr_service import OCRService
from backend.services.image_validator import ImageValidator
from backend.services.ticket_image_service import TicketImageService
from backend.services.match_service import MatchService
from backend.services.reference_matcher import ReferenceMatcher
from backend.services.client_loader_service import ClientLoaderService
from backend.services.ticket_image_matcher import TicketImageMatcher


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


class TestEnhancedComprehensiveWorkflow:
    """Enhanced integration test covering all new services and features"""
    
    async def test_complete_workflow_with_new_services(self, client, admin_headers, test_session, temp_dir):
        """Test the complete workflow including new services"""
        
        # Step 1: Load clients from CSV with account numbers
        print("Step 1: Loading clients from CSV with account numbers...")
        csv_content = """account_number,name,billing_email,address,city,state,zip,phone,contact_name
007,ABC Transport,billing@abc.com,123 Main St,Sydney,NSW,2000,0400123456,John Doe
141,DEF Logistics,billing@def.com,456 Queen St,Melbourne,VIC,3000,0400234567,Jane Smith
1001,XYZ Carriers,billing@xyz.com,789 King St,Brisbane,QLD,4000,0400345678,Bob Johnson
2001,TOPPS,billing@topps.com,321 Park Ave,Perth,WA,6000,0400456789,Alice Brown
"""
        csv_file = BytesIO(csv_content.encode())
        
        files = {
            "file": ("Clients-all.csv", csv_file, "text/csv")
        }
        
        response = client.post(
            "/api/clients/import/csv",
            files=files,
            headers=admin_headers,
            params={"create_topps": True}
        )
        assert response.status_code == 201
        import_result = response.json()
        assert import_result["imported"] == 4
        assert import_result["skipped"] == 0
        print(f"Imported {import_result['imported']} clients with account numbers")
        
        # Verify reference patterns were created
        abc_client = test_session.exec(
            select(Client).where(Client.name == "ABC Transport")
        ).first()
        assert abc_client is not None
        
        # Check ABC Transport has both 007 and #007 patterns
        abc_refs = test_session.exec(
            select(ClientReference).where(ClientReference.client_id == abc_client.id)
        ).all()
        patterns = [ref.pattern for ref in abc_refs]
        assert "007" in patterns  # Exact match
        assert "#007" in patterns  # With hash
        
        # Check XYZ Carriers has MM1001 pattern
        xyz_client = test_session.exec(
            select(Client).where(Client.name == "XYZ Carriers")
        ).first()
        xyz_refs = test_session.exec(
            select(ClientReference).where(ClientReference.client_id == xyz_client.id)
        ).all()
        patterns = [ref.pattern for ref in xyz_refs]
        assert "MM1001" in patterns
        
        # Step 2: Create and process multi-row XLS file
        print("\nStep 2: Creating multi-row XLS file in APRIL 14 2025 format...")
        xls_path = self._create_multi_row_xls_file(temp_dir)
        
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
            print(f"Uploaded multi-row XLS file, batch ID: {batch_id}")
        
        # Step 3: Process with MultiRowXLSParser
        print("\nStep 3: Processing multi-row XLS with specialized parser...")
        response = client.post(
            f"/api/batch/{batch_id}/process",
            headers=admin_headers,
            params={"use_multi_row_parser": True}
        )
        assert response.status_code == 200
        process_result = response.json()
        print(f"Processed {process_result.get('tickets_parsed', 0)} tickets from multi-row format")
        
        # Verify tickets were created and reference/note parsing worked
        tickets = test_session.exec(
            select(Ticket).where(Ticket.batch_id == UUID(batch_id))
        ).all()
        
        # Check reference parsing and note extraction
        for ticket in tickets:
            if ticket.ticket_number == "0001":
                assert ticket.reference == "007"  # Should strip #
                assert ticket.note == "SAND EX SEVEN HILLS"
                assert ticket.client_id == abc_client.id
            elif ticket.ticket_number == "0002":
                assert ticket.reference == "MM1001"
                assert ticket.note == "GRAVEL FROM QUARRY"
                assert ticket.client_id == xyz_client.id
            elif ticket.ticket_number == "0003":
                assert ticket.reference == "T-202"
                assert ticket.client and "TOPPS" in ticket.client.name
        
        # Verify REPRINT VOID tickets are filtered
        void_tickets = [t for t in tickets if t.reference == "REPRINT" and t.status == "VOID"]
        assert all(t.net_weight == 0 for t in void_tickets)
        
        # Step 4: Create PDF with multiple tickets per page
        print("\nStep 4: Creating PDF with multiple tickets per page...")
        pdf_path = self._create_multi_ticket_pdf(temp_dir, tickets[:6])
        
        with open(pdf_path, 'rb') as f:
            files = {
                "file": ("APRIL 14 2025.pdf", f, "application/pdf")
            }
            
            # Mock the PDF extraction to simulate multiple tickets per page
            with patch('backend.services.pdf_extraction_service.PDFExtractionService.extract_images_from_pdf') as mock_extract:
                # Simulate 3 pages with 2 tickets each
                mock_images = []
                for i in range(3):
                    page_image = self._create_page_with_two_tickets(
                        tickets[i*2], 
                        tickets[i*2+1] if i*2+1 < len(tickets) else None
                    )
                    mock_images.append(page_image)
                
                mock_extract.return_value = mock_images
                
                response = client.post(
                    f"/api/batch/{batch_id}/upload-images",
                    files=files,
                    headers=admin_headers
                )
                assert response.status_code == 200
                image_result = response.json()
                print(f"Extracted {image_result.get('images_extracted', 0)} images from PDF")
        
        # Step 5: Test TicketImageMatcher service
        print("\nStep 5: Testing ticket-image matching with OCR...")
        
        # Get ticket images
        ticket_images = test_session.exec(
            select(TicketImage).where(TicketImage.batch_id == UUID(batch_id))
        ).all()
        
        # Mock OCR results
        with patch('backend.services.ocr_service.OCRService.extract_ticket_number') as mock_ocr:
            # Return matching ticket numbers
            mock_ocr.side_effect = [
                ("0001", 95.0),
                ("0002", 92.0),
                ("0003", 90.0),
                ("0004", 88.0),
                ("0005", 93.0),
                ("0006", 91.0)
            ]
            
            # Run matching
            matcher = TicketImageMatcher(test_session)
            matches = await matcher.match_tickets_with_images(
                batch_id=UUID(batch_id),
                confidence_threshold=85.0
            )
            
            assert len(matches) > 0
            print(f"Found {len(matches)} ticket-image matches")
            
            # Verify high confidence matches
            high_confidence = [m for m in matches if m['confidence'] >= 90.0]
            assert len(high_confidence) >= 4
        
        # Step 6: Test reference matching edge cases
        print("\nStep 6: Testing reference matching edge cases...")
        
        # Test #007 vs 007 matching
        ref_matcher = ReferenceMatcher(test_session)
        
        # Both should match ABC Transport
        match1 = ref_matcher.match_reference("#007")
        match2 = ref_matcher.match_reference("007")
        assert match1.client_id == abc_client.id
        assert match2.client_id == abc_client.id
        assert match1.confidence >= 90.0
        assert match2.confidence >= 90.0
        
        # T-xxx should match TOPPS
        match3 = ref_matcher.match_reference("T-123")
        assert match3.client and "TOPPS" in match3.client.name
        
        # MM pattern should match XYZ Carriers
        match4 = ref_matcher.match_reference("MM1001")
        assert match4.client_id == xyz_client.id
        
        # Step 7: Export clients to CSV
        print("\nStep 7: Testing client CSV export...")
        response = client.get(
            "/api/clients/export/csv",
            headers=admin_headers
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        
        # Parse exported CSV
        csv_data = response.content.decode('utf-8')
        lines = csv_data.strip().split('\n')
        assert len(lines) >= 5  # Header + 4 clients
        
        # Step 8: Generate comprehensive report
        print("\nStep 8: Generating comprehensive batch report...")
        response = client.get(
            f"/api/batch/{batch_id}/report",
            headers=admin_headers
        )
        assert response.status_code == 200
        report = response.json()
        
        print(f"\nBatch Report Summary:")
        print(f"- Total tickets: {report.get('total_tickets', 0)}")
        print(f"- Valid tickets: {report.get('valid_tickets', 0)}")
        print(f"- Void tickets: {report.get('void_tickets', 0)}")
        print(f"- Tickets with clients: {report.get('tickets_with_clients', 0)}")
        print(f"- Tickets with images: {report.get('tickets_with_images', 0)}")
        print(f"- Total tonnage: {report.get('total_tonnage', 0):.2f}")
        
        # Verify complete workflow success
        assert report.get('total_tickets', 0) > 0
        assert report.get('tickets_with_clients', 0) > 0
        assert report.get('tickets_with_images', 0) > 0
        
        print("\nEnhanced workflow test completed successfully!")
        
        return {
            "clients_imported": import_result["imported"],
            "tickets_created": len(tickets),
            "images_extracted": len(ticket_images),
            "matches_found": len(matches),
            "report": report
        }
    
    def _create_multi_row_xls_file(self, temp_dir):
        """Create XLS file in APRIL 14 2025 multi-row format"""
        xls_path = os.path.join(temp_dir, "APRIL 14 2025.xls")
        
        workbook = xlwt.Workbook()
        sheet = workbook.add_sheet('Sheet1')
        
        # Write multi-row ticket data
        row = 0
        
        # Ticket 1: #007 with note
        sheet.write(row, 0, 'TICKET #')
        sheet.write(row, 1, '0001')
        row += 1
        sheet.write(row, 0, 'In:')
        sheet.write(row, 1, '14/04/2025 08:30:45')
        sheet.write(row, 2, 'Out:')
        sheet.write(row, 3, '14/04/2025 08:45:30')
        row += 1
        sheet.write(row, 0, 'Vehicle:')
        sheet.write(row, 1, 'ABC-123')
        sheet.write(row, 2, 'Material:')
        sheet.write(row, 3, 'Sand')
        row += 1
        sheet.write(row, 0, 'Reference:')
        sheet.write(row, 1, '#007 SAND EX SEVEN HILLS')
        row += 1
        sheet.write(row, 0, 'Gross:')
        sheet.write(row, 1, '25000')
        sheet.write(row, 2, 'Tare:')
        sheet.write(row, 3, '10000')
        sheet.write(row, 4, 'Net:')
        sheet.write(row, 5, '15000')
        row += 2  # Empty row
        
        # Ticket 2: MM1001 with note
        sheet.write(row, 0, 'TICKET #')
        sheet.write(row, 1, '0002')
        row += 1
        sheet.write(row, 0, 'In:')
        sheet.write(row, 1, '14/04/2025 09:15:20')
        sheet.write(row, 2, 'Out:')
        sheet.write(row, 3, '14/04/2025 09:30:10')
        row += 1
        sheet.write(row, 0, 'Vehicle:')
        sheet.write(row, 1, 'XYZ-456')
        sheet.write(row, 2, 'Material:')
        sheet.write(row, 3, 'Gravel')
        row += 1
        sheet.write(row, 0, 'Reference:')
        sheet.write(row, 1, 'MM1001 GRAVEL FROM QUARRY')
        row += 1
        sheet.write(row, 0, 'Gross:')
        sheet.write(row, 1, '30000')
        sheet.write(row, 2, 'Tare:')
        sheet.write(row, 3, '12000')
        sheet.write(row, 4, 'Net:')
        sheet.write(row, 5, '18000')
        row += 2
        
        # Ticket 3: T-202 (TOPPS)
        sheet.write(row, 0, 'TICKET #')
        sheet.write(row, 1, '0003')
        row += 1
        sheet.write(row, 0, 'In:')
        sheet.write(row, 1, '14/04/2025 10:00:00')
        sheet.write(row, 2, 'Out:')
        sheet.write(row, 3, '14/04/2025 10:15:00')
        row += 1
        sheet.write(row, 0, 'Vehicle:')
        sheet.write(row, 1, 'DEF-789')
        sheet.write(row, 2, 'Material:')
        sheet.write(row, 3, 'Rock')
        row += 1
        sheet.write(row, 0, 'Reference:')
        sheet.write(row, 1, 'T-202')
        row += 1
        sheet.write(row, 0, 'Gross:')
        sheet.write(row, 1, '28000')
        sheet.write(row, 2, 'Tare:')
        sheet.write(row, 3, '11000')
        sheet.write(row, 4, 'Net:')
        sheet.write(row, 5, '17000')
        row += 2
        
        # Ticket 4: REPRINT VOID (should be filtered)
        sheet.write(row, 0, 'TICKET #')
        sheet.write(row, 1, '0004')
        row += 1
        sheet.write(row, 0, 'In:')
        sheet.write(row, 1, '14/04/2025 10:30:00')
        sheet.write(row, 2, 'Out:')
        sheet.write(row, 3, '14/04/2025 10:30:00')
        row += 1
        sheet.write(row, 0, 'Vehicle:')
        sheet.write(row, 1, 'GHI-012')
        sheet.write(row, 2, 'Material:')
        sheet.write(row, 3, 'Sand')
        row += 1
        sheet.write(row, 0, 'Reference:')
        sheet.write(row, 1, 'REPRINT')
        row += 1
        sheet.write(row, 0, 'Gross:')
        sheet.write(row, 1, '0')
        sheet.write(row, 2, 'Tare:')
        sheet.write(row, 3, '0')
        sheet.write(row, 4, 'Net:')
        sheet.write(row, 5, '0')
        sheet.write(row, 6, 'VOID')
        row += 2
        
        # Ticket 5: Regular 007 (without #)
        sheet.write(row, 0, 'TICKET #')
        sheet.write(row, 1, '0005')
        row += 1
        sheet.write(row, 0, 'In:')
        sheet.write(row, 1, '14/04/2025 11:00:00')
        sheet.write(row, 2, 'Out:')
        sheet.write(row, 3, '14/04/2025 11:15:00')
        row += 1
        sheet.write(row, 0, 'Vehicle:')
        sheet.write(row, 1, 'JKL-345')
        sheet.write(row, 2, 'Material:')
        sheet.write(row, 3, 'Sand')
        row += 1
        sheet.write(row, 0, 'Reference:')
        sheet.write(row, 1, '007')
        row += 1
        sheet.write(row, 0, 'Gross:')
        sheet.write(row, 1, '26000')
        sheet.write(row, 2, 'Tare:')
        sheet.write(row, 3, '10500')
        sheet.write(row, 4, 'Net:')
        sheet.write(row, 5, '15500')
        row += 2
        
        # Ticket 6: #141 (another hash pattern)
        sheet.write(row, 0, 'TICKET #')
        sheet.write(row, 1, '0006')
        row += 1
        sheet.write(row, 0, 'In:')
        sheet.write(row, 1, '14/04/2025 11:30:00')
        sheet.write(row, 2, 'Out:')
        sheet.write(row, 3, '14/04/2025 11:45:00')
        row += 1
        sheet.write(row, 0, 'Vehicle:')
        sheet.write(row, 1, 'MNO-678')
        sheet.write(row, 2, 'Material:')
        sheet.write(row, 3, 'Gravel')
        row += 1
        sheet.write(row, 0, 'Reference:')
        sheet.write(row, 1, '#141')
        row += 1
        sheet.write(row, 0, 'Gross:')
        sheet.write(row, 1, '32000')
        sheet.write(row, 2, 'Tare:')
        sheet.write(row, 3, '13000')
        sheet.write(row, 4, 'Net:')
        sheet.write(row, 5, '19000')
        
        workbook.save(xls_path)
        return xls_path
    
    def _create_multi_ticket_pdf(self, temp_dir, tickets):
        """Create PDF with multiple tickets per page"""
        pdf_path = os.path.join(temp_dir, "APRIL 14 2025.pdf")
        
        # Mock PDF for testing
        with open(pdf_path, 'wb') as f:
            f.write(b'%PDF-1.4 mock multi-ticket PDF')
        
        return pdf_path
    
    def _create_page_with_two_tickets(self, ticket1, ticket2):
        """Create image with two tickets on one page"""
        img = Image.new('RGB', (800, 1200), color='white')
        draw = ImageDraw.Draw(img)
        
        # Top ticket
        if ticket1:
            draw.rectangle([50, 50, 750, 550], outline='black', width=2)
            draw.text((100, 100), "WEIGHBRIDGE TICKET", fill='black')
            draw.text((100, 150), f"Ticket #: {ticket1.ticket_number}", fill='black')
            draw.text((100, 200), f"Reference: {ticket1.reference or 'N/A'}", fill='black')
            draw.text((100, 250), f"Vehicle: {ticket1.vehicle or 'N/A'}", fill='black')
            draw.text((100, 300), f"Material: {ticket1.material or 'N/A'}", fill='black')
            draw.text((100, 350), f"Net: {ticket1.net_weight} kg", fill='black')
        
        # Dividing line
        draw.line([(50, 600), (750, 600)], fill='gray', width=3)
        
        # Bottom ticket
        if ticket2:
            draw.rectangle([50, 650, 750, 1150], outline='black', width=2)
            draw.text((100, 700), "WEIGHBRIDGE TICKET", fill='black')
            draw.text((100, 750), f"Ticket #: {ticket2.ticket_number}", fill='black')
            draw.text((100, 800), f"Reference: {ticket2.reference or 'N/A'}", fill='black')
            draw.text((100, 850), f"Vehicle: {ticket2.vehicle or 'N/A'}", fill='black')
            draw.text((100, 900), f"Material: {ticket2.material or 'N/A'}", fill='black')
            draw.text((100, 950), f"Net: {ticket2.net_weight} kg", fill='black')
        
        return img
    
    def test_multi_row_parser_edge_cases(self, test_session, temp_dir):
        """Test MultiRowXLSParser with edge cases"""
        print("Testing MultiRowXLSParser edge cases...")
        
        parser = MultiRowXLSParser()
        
        # Test with empty file
        empty_xls = self._create_empty_xls(temp_dir)
        with open(empty_xls, 'rb') as f:
            tickets = parser.parse(f.read(), "empty.xls")
            assert len(tickets) == 0
        
        # Test with malformed data
        malformed_xls = self._create_malformed_xls(temp_dir)
        with open(malformed_xls, 'rb') as f:
            tickets = parser.parse(f.read(), "malformed.xls")
            # Should handle gracefully and skip invalid tickets
            assert all(t.ticket_number for t in tickets)
        
        print("Edge case tests passed!")
    
    def _create_empty_xls(self, temp_dir):
        """Create empty XLS file"""
        xls_path = os.path.join(temp_dir, "empty.xls")
        workbook = xlwt.Workbook()
        sheet = workbook.add_sheet('Sheet1')
        workbook.save(xls_path)
        return xls_path
    
    def _create_malformed_xls(self, temp_dir):
        """Create XLS with malformed data"""
        xls_path = os.path.join(temp_dir, "malformed.xls")
        workbook = xlwt.Workbook()
        sheet = workbook.add_sheet('Sheet1')
        
        # Missing ticket number
        sheet.write(0, 0, 'TICKET #')
        sheet.write(0, 1, '')  # Empty ticket number
        
        # Invalid format
        sheet.write(5, 0, 'Random text')
        sheet.write(6, 1, 'More random data')
        
        workbook.save(xls_path)
        return xls_path
    
    async def test_client_loader_service_directly(self, test_session, temp_dir):
        """Test ClientLoaderService directly"""
        print("Testing ClientLoaderService...")
        
        loader = ClientLoaderService(test_session)
        
        # Create CSV content
        csv_content = """account_number,name,billing_email,address,city,state,zip,phone,contact_name
007,Test Client 1,test1@example.com,123 Test St,Sydney,NSW,2000,0400111111,Test User
#007,Duplicate Test,dup@example.com,456 Dup St,Sydney,NSW,2000,0400222222,Dup User
MM1001,MM Client,mm@example.com,789 MM St,Brisbane,QLD,4000,0400333333,MM User
"""
        
        result = await loader.load_clients_from_csv(
            csv_content=csv_content,
            create_topps=True
        )
        
        assert result["imported"] == 3
        assert result["skipped"] == 0
        
        # Verify TOPPS client was created
        topps = test_session.exec(
            select(Client).where(Client.name == "TOPPS")
        ).first()
        assert topps is not None
        
        # Verify reference patterns
        test_client = test_session.exec(
            select(Client).where(Client.name == "Test Client 1")
        ).first()
        refs = test_session.exec(
            select(ClientReference).where(ClientReference.client_id == test_client.id)
        ).all()
        patterns = [ref.pattern for ref in refs]
        assert "007" in patterns
        assert "#007" in patterns
        
        print("ClientLoaderService test passed!")
    
    async def test_ticket_image_matcher_directly(self, test_session, temp_dir):
        """Test TicketImageMatcher service directly"""
        print("Testing TicketImageMatcher...")
        
        # Create test data
        batch = Batch(
            id=uuid4(),
            user_id=uuid4(),
            filename="test.xls",
            file_type="xls",
            status=BatchStatus.PROCESSING
        )
        test_session.add(batch)
        
        # Create tickets
        tickets = []
        for i in range(3):
            ticket = Ticket(
                id=uuid4(),
                batch_id=batch.id,
                ticket_number=f"TEST{i:03d}",
                entry_date=date.today(),
                net_weight=1000.0 * (i + 1)
            )
            tickets.append(ticket)
            test_session.add(ticket)
        
        # Create ticket images
        for i in range(3):
            image = TicketImage(
                id=uuid4(),
                batch_id=batch.id,
                filename=f"image_{i}.png",
                page_number=i,
                image_data=b"fake_image_data"
            )
            test_session.add(image)
        
        test_session.commit()
        
        # Test matching
        matcher = TicketImageMatcher(test_session)
        
        with patch('backend.services.ocr_service.OCRService.extract_ticket_number') as mock_ocr:
            mock_ocr.side_effect = [
                ("TEST000", 95.0),
                ("TEST001", 92.0),
                ("TEST002", 90.0)
            ]
            
            matches = await matcher.match_tickets_with_images(
                batch_id=batch.id,
                confidence_threshold=85.0
            )
            
            assert len(matches) == 3
            assert all(m['confidence'] >= 85.0 for m in matches)
        
        print("TicketImageMatcher test passed!")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])