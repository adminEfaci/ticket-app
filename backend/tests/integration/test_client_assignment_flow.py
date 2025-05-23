import pytest
from datetime import date, datetime
from uuid import UUID
from io import BytesIO
import pandas as pd

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from main import app
from backend.core.database import get_session, create_db_and_tables
from backend.models.user import User, UserRole
from backend.models.client import Client, ClientReference, ClientRate, InvoiceFormat
from backend.models.ticket import Ticket
from backend.models.batch import Batch
from backend.services.auth_service import get_password_hash


@pytest.fixture(scope="function")
def test_session():
    """Create a test database session"""
    from sqlmodel import create_engine, SQLModel
    from sqlalchemy.pool import StaticPool
    
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
def client_user(test_session):
    """Create a client user for testing"""
    # First create the client
    client_obj = Client(
        name="Test Transport Co",
        billing_email="billing@transport.com",
        invoice_format=InvoiceFormat.CSV,
        credit_terms_days=30
    )
    test_session.add(client_obj)
    test_session.commit()
    
    # Then create user linked to client
    user = User(
        username="clientuser",
        email="user@transport.com",
        full_name="Client User",
        hashed_password=get_password_hash("clientpass123"),
        role=UserRole.CLIENT,
        client_id=client_obj.id,
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
def client_headers(client, client_user):
    """Get auth headers for client user"""
    response = client.post(
        "/api/auth/login",
        data={
            "username": "clientuser",
            "password": "clientpass123"
        }
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestClientAssignmentFlow:
    """Test the complete client assignment and rate application flow"""
    
    def test_admin_creates_client_tree(self, client, admin_headers, test_session):
        """Test creating a parent client with subcontractors"""
        # Create parent client
        parent_data = {
            "name": "Big Transport Corp",
            "billing_email": "billing@bigtransport.com",
            "billing_contact_name": "John Doe",
            "billing_phone": "+1234567890",
            "invoice_format": "xlsx",
            "invoice_frequency": "monthly",
            "credit_terms_days": 45
        }
        
        response = client.post(
            "/api/clients/",
            json=parent_data,
            headers=admin_headers
        )
        assert response.status_code == 201
        parent = response.json()
        assert parent["name"] == "Big Transport Corp"
        
        # Create subcontractor
        sub_data = {
            "name": "Small Trucking Ltd",
            "parent_id": parent["id"],
            "billing_email": "billing@smalltrucking.com",
            "invoice_format": "csv",
            "credit_terms_days": 30
        }
        
        response = client.post(
            "/api/clients/",
            json=sub_data,
            headers=admin_headers
        )
        assert response.status_code == 201
        subcontractor = response.json()
        assert subcontractor["parent_id"] == parent["id"]
        
        # Verify hierarchy
        response = client.get(
            "/api/clients/hierarchy",
            headers=admin_headers
        )
        assert response.status_code == 200
        hierarchy = response.json()
        assert len(hierarchy) >= 1
        
        # Find our parent in hierarchy
        parent_node = next(h for h in hierarchy if h["client"]["id"] == parent["id"])
        assert len(parent_node["subcontractors"]) == 1
        assert parent_node["subcontractors"][0]["client"]["id"] == subcontractor["id"]
    
    def test_client_reference_pattern_setup(self, client, admin_headers, test_session):
        """Test setting up various reference patterns for a client"""
        # Create client
        client_data = {
            "name": "Pattern Test Co",
            "billing_email": "pattern@test.com"
        }
        
        response = client.post(
            "/api/clients/",
            json=client_data,
            headers=admin_headers
        )
        assert response.status_code == 201
        test_client = response.json()
        client_id = test_client["id"]
        
        # Add exact match reference
        ref1 = {
            "client_id": client_id,
            "pattern": "ABC123",
            "is_regex": False,
            "is_fuzzy": False,
            "priority": 10,
            "description": "Exact ticket reference"
        }
        
        response = client.post(
            f"/api/clients/{client_id}/references",
            json=ref1,
            headers=admin_headers
        )
        assert response.status_code == 201
        
        # Add prefix pattern
        ref2 = {
            "client_id": client_id,
            "pattern": "PT*",
            "is_regex": False,
            "is_fuzzy": False,
            "priority": 20,
            "description": "All tickets starting with PT"
        }
        
        response = client.post(
            f"/api/clients/{client_id}/references",
            json=ref2,
            headers=admin_headers
        )
        assert response.status_code == 201
        
        # Add regex pattern
        ref3 = {
            "client_id": client_id,
            "pattern": r"JOB#\d{4}",
            "is_regex": True,
            "is_fuzzy": False,
            "priority": 30,
            "description": "Job number pattern"
        }
        
        response = client.post(
            f"/api/clients/{client_id}/references",
            json=ref3,
            headers=admin_headers
        )
        assert response.status_code == 201
        
        # Add fuzzy pattern
        ref4 = {
            "client_id": client_id,
            "pattern": "PATTERNTEST",
            "is_regex": False,
            "is_fuzzy": True,
            "priority": 40,
            "description": "Fuzzy match for variations"
        }
        
        response = client.post(
            f"/api/clients/{client_id}/references",
            json=ref4,
            headers=admin_headers
        )
        assert response.status_code == 201
        
        # Verify all references
        response = client.get(
            f"/api/clients/{client_id}/references",
            headers=admin_headers
        )
        assert response.status_code == 200
        references = response.json()
        assert len(references) == 4
    
    def test_rate_history_management(self, client, admin_headers, test_session):
        """Test creating and managing rate history"""
        # Create client
        client_data = {
            "name": "Rate Test Co",
            "billing_email": "rate@test.com"
        }
        
        response = client.post(
            "/api/clients/",
            json=client_data,
            headers=admin_headers
        )
        assert response.status_code == 201
        test_client = response.json()
        client_id = test_client["id"]
        
        # Add historical rate
        rate1 = {
            "client_id": client_id,
            "rate_per_tonne": 20.00,
            "effective_from": "2023-01-01",
            "effective_to": "2023-12-31",
            "notes": "2023 rate"
        }
        
        response = client.post(
            f"/api/clients/{client_id}/rates",
            json=rate1,
            headers=admin_headers,
            params={"auto_approve": True}
        )
        assert response.status_code == 201
        
        # Add current rate
        rate2 = {
            "client_id": client_id,
            "rate_per_tonne": 25.00,
            "effective_from": "2024-01-01",
            "notes": "2024 rate - increased"
        }
        
        response = client.post(
            f"/api/clients/{client_id}/rates",
            json=rate2,
            headers=admin_headers,
            params={"auto_approve": True}
        )
        assert response.status_code == 201
        
        # Get rate history
        response = client.get(
            f"/api/clients/{client_id}/rates",
            headers=admin_headers,
            params={"include_expired": True}
        )
        assert response.status_code == 200
        rates = response.json()
        assert len(rates) == 2
        
        # Check effective rate for different dates
        response = client.get(
            f"/api/clients/{client_id}/rates/effective",
            headers=admin_headers,
            params={"effective_date": "2023-06-15"}
        )
        assert response.status_code == 200
        effective_rate = response.json()
        assert effective_rate["rate_per_tonne"] == 20.00
        
        response = client.get(
            f"/api/clients/{client_id}/rates/effective",
            headers=admin_headers,
            params={"effective_date": "2024-06-15"}
        )
        assert response.status_code == 200
        effective_rate = response.json()
        assert effective_rate["rate_per_tonne"] == 25.00
    
    def test_upload_tickets_with_auto_client_assignment(self, client, admin_headers, test_session):
        """Test uploading tickets and having them automatically assigned to clients"""
        # First, set up clients with references and rates
        # Client 1: ABC Transport
        client1_data = {
            "name": "ABC Transport",
            "billing_email": "abc@transport.com"
        }
        
        response = client.post(
            "/api/clients/",
            json=client1_data,
            headers=admin_headers
        )
        assert response.status_code == 201
        client1 = response.json()
        
        # Add reference pattern for Client 1
        ref1 = {
            "client_id": client1["id"],
            "pattern": "ABC*",
            "is_regex": False,
            "is_fuzzy": False,
            "priority": 10
        }
        
        response = client.post(
            f"/api/clients/{client1['id']}/references",
            json=ref1,
            headers=admin_headers
        )
        assert response.status_code == 201
        
        # Add rate for Client 1
        rate1 = {
            "client_id": client1["id"],
            "rate_per_tonne": 30.00,
            "effective_from": "2024-01-01"
        }
        
        response = client.post(
            f"/api/clients/{client1['id']}/rates",
            json=rate1,
            headers=admin_headers,
            params={"auto_approve": True}
        )
        assert response.status_code == 201
        
        # Client 2: XYZ Logistics
        client2_data = {
            "name": "XYZ Logistics",
            "billing_email": "xyz@logistics.com"
        }
        
        response = client.post(
            "/api/clients/",
            json=client2_data,
            headers=admin_headers
        )
        assert response.status_code == 201
        client2 = response.json()
        
        # Add regex pattern for Client 2
        ref2 = {
            "client_id": client2["id"],
            "pattern": r"JOB#\d+",
            "is_regex": True,
            "is_fuzzy": False,
            "priority": 20
        }
        
        response = client.post(
            f"/api/clients/{client2['id']}/references",
            json=ref2,
            headers=admin_headers
        )
        assert response.status_code == 201
        
        # Add rate for Client 2
        rate2 = {
            "client_id": client2["id"],
            "rate_per_tonne": 35.00,
            "effective_from": "2024-01-01"
        }
        
        response = client.post(
            f"/api/clients/{client2['id']}/rates",
            json=rate2,
            headers=admin_headers,
            params={"auto_approve": True}
        )
        assert response.status_code == 201
        
        # Create test data with various references
        tickets_data = [
            {
                "Ticket Number": "T001",
                "Reference": "ABC123",  # Should match Client 1
                "Entry Date": "15/03/2024",
                "Entry Time": "08:30",
                "Truck Rego": "ABC123",
                "Product": "Sand",
                "Supplier": "Quarry A",
                "Gross Weight": "25000",
                "Tare Weight": "10000",
                "Net Weight": "15000"
            },
            {
                "Ticket Number": "T002",
                "Reference": "JOB#5678",  # Should match Client 2
                "Entry Date": "15/03/2024",
                "Entry Time": "09:15",
                "Truck Rego": "XYZ456",
                "Product": "Gravel",
                "Supplier": "Quarry B",
                "Gross Weight": "30000",
                "Tare Weight": "12000",
                "Net Weight": "18000"
            },
            {
                "Ticket Number": "T003",
                "Reference": "NOMATCH",  # Should not match any client
                "Entry Date": "15/03/2024",
                "Entry Time": "10:00",
                "Truck Rego": "DEF789",
                "Product": "Rock",
                "Supplier": "Quarry C",
                "Gross Weight": "28000",
                "Tare Weight": "11000",
                "Net Weight": "17000"
            }
        ]
        
        # Create Excel file
        df = pd.DataFrame(tickets_data)
        excel_buffer = BytesIO()
        df.to_excel(excel_buffer, index=False)
        excel_buffer.seek(0)
        
        # Upload file
        files = {
            "file": ("test_tickets.xlsx", excel_buffer, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        }
        
        response = client.post(
            "/api/upload/",
            files=files,
            headers=admin_headers
        )
        assert response.status_code == 200
        upload_result = response.json()
        batch_id = upload_result["batch"]["id"]
        
        # Process the batch
        response = client.post(
            f"/api/batch/{batch_id}/process",
            headers=admin_headers
        )
        assert response.status_code == 200
        
        # Check ticket assignments
        tickets = test_session.exec(
            select(Ticket).where(Ticket.batch_id == UUID(batch_id))
        ).all()
        
        assert len(tickets) == 3
        
        # Verify ticket 1 assigned to Client 1 with correct rate
        ticket1 = next(t for t in tickets if t.ticket_number == "T001")
        assert ticket1.client_id == UUID(client1["id"])
        assert ticket1.rate_per_tonne == 30.00
        
        # Verify ticket 2 assigned to Client 2 with correct rate
        ticket2 = next(t for t in tickets if t.ticket_number == "T002")
        assert ticket2.client_id == UUID(client2["id"])
        assert ticket2.rate_per_tonne == 35.00
        
        # Verify ticket 3 has no client assignment
        ticket3 = next(t for t in tickets if t.ticket_number == "T003")
        assert ticket3.client_id is None
        assert ticket3.rate_per_tonne is None
    
    def test_client_access_control(self, client, admin_headers, client_headers, client_user, test_session):
        """Test that clients can only see their own data"""
        # Get the client ID from the client user
        client_id = str(client_user.client_id)
        
        # Client user should be able to see their own client
        response = client.get(
            f"/api/clients/{client_id}",
            headers=client_headers
        )
        assert response.status_code == 200
        
        # Client user should not be able to see other clients
        # Create another client as admin
        other_client_data = {
            "name": "Other Company",
            "billing_email": "other@company.com"
        }
        
        response = client.post(
            "/api/clients/",
            json=other_client_data,
            headers=admin_headers
        )
        assert response.status_code == 201
        other_client_id = response.json()["id"]
        
        # Try to access other client as client user
        response = client.get(
            f"/api/clients/{other_client_id}",
            headers=client_headers
        )
        assert response.status_code == 403
        
        # Client user should only see their own rates
        response = client.get(
            f"/api/clients/{client_id}/rates",
            headers=client_headers
        )
        assert response.status_code == 200
        
        # Client user cannot access other client's rates
        response = client.get(
            f"/api/clients/{other_client_id}/rates",
            headers=client_headers
        )
        assert response.status_code == 403
        
        # Client user cannot create/update/delete clients
        response = client.post(
            "/api/clients/",
            json={"name": "New Client", "billing_email": "new@client.com"},
            headers=client_headers
        )
        assert response.status_code == 403
    
    def test_reference_conflict_detection(self, client, admin_headers, test_session):
        """Test that duplicate reference patterns are detected"""
        # Create first client
        client1_data = {
            "name": "Client One",
            "billing_email": "one@client.com"
        }
        
        response = client.post(
            "/api/clients/",
            json=client1_data,
            headers=admin_headers
        )
        assert response.status_code == 201
        client1 = response.json()
        
        # Add reference pattern
        ref1 = {
            "client_id": client1["id"],
            "pattern": "REF123",
            "is_regex": False,
            "is_fuzzy": False,
            "priority": 10
        }
        
        response = client.post(
            f"/api/clients/{client1['id']}/references",
            json=ref1,
            headers=admin_headers
        )
        assert response.status_code == 201
        
        # Create second client
        client2_data = {
            "name": "Client Two",
            "billing_email": "two@client.com"
        }
        
        response = client.post(
            "/api/clients/",
            json=client2_data,
            headers=admin_headers
        )
        assert response.status_code == 201
        client2 = response.json()
        
        # Try to add same reference pattern - should fail
        ref2 = {
            "client_id": client2["id"],
            "pattern": "REF123",
            "is_regex": False,
            "is_fuzzy": False,
            "priority": 20
        }
        
        response = client.post(
            f"/api/clients/{client2['id']}/references",
            json=ref2,
            headers=admin_headers
        )
        assert response.status_code == 409
        assert "conflict" in response.json()["detail"]["message"].lower()
    
    def test_billing_configuration_management(self, client, admin_headers, test_session):
        """Test billing configuration features"""
        # Create client
        client_data = {
            "name": "Billing Test Co",
            "billing_email": "billing@test.com",
            "invoice_format": "csv"
        }
        
        response = client.post(
            "/api/clients/",
            json=client_data,
            headers=admin_headers
        )
        assert response.status_code == 201
        test_client = response.json()
        client_id = test_client["id"]
        
        # Update billing configuration
        update_data = {
            "billing_email": "newbilling@test.com",
            "billing_contact_name": "Jane Smith",
            "billing_phone": "+1987654321",
            "invoice_format": "xlsx",
            "invoice_frequency": "weekly",
            "credit_terms_days": 60
        }
        
        response = client.put(
            f"/api/clients/{client_id}",
            json=update_data,
            headers=admin_headers
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated["billing_email"] == "newbilling@test.com"
        assert updated["invoice_format"] == "xlsx"
        assert updated["credit_terms_days"] == 60
    
    def test_rate_validation_rules(self, client, admin_headers, test_session):
        """Test rate validation rules ($10-$100)"""
        # Create client
        client_data = {
            "name": "Rate Validation Co",
            "billing_email": "validation@test.com"
        }
        
        response = client.post(
            "/api/clients/",
            json=client_data,
            headers=admin_headers
        )
        assert response.status_code == 201
        test_client = response.json()
        client_id = test_client["id"]
        
        # Try to add rate below minimum ($10)
        low_rate = {
            "client_id": client_id,
            "rate_per_tonne": 5.00,
            "effective_from": "2024-01-01"
        }
        
        response = client.post(
            f"/api/clients/{client_id}/rates",
            json=low_rate,
            headers=admin_headers
        )
        assert response.status_code == 400
        
        # Try to add rate above maximum ($100)
        high_rate = {
            "client_id": client_id,
            "rate_per_tonne": 150.00,
            "effective_from": "2024-01-01"
        }
        
        response = client.post(
            f"/api/clients/{client_id}/rates",
            json=high_rate,
            headers=admin_headers
        )
        assert response.status_code == 400
        
        # Valid rate should succeed
        valid_rate = {
            "client_id": client_id,
            "rate_per_tonne": 50.00,
            "effective_from": "2024-01-01"
        }
        
        response = client.post(
            f"/api/clients/{client_id}/rates",
            json=valid_rate,
            headers=admin_headers
        )
        assert response.status_code == 201
    
    def test_reference_matching_api(self, client, admin_headers, test_session):
        """Test the reference matching test API"""
        # Set up test data with various patterns
        # Create client with multiple reference types
        client_data = {
            "name": "Match Test Co",
            "billing_email": "match@test.com"
        }
        
        response = client.post(
            "/api/clients/",
            json=client_data,
            headers=admin_headers
        )
        assert response.status_code == 201
        test_client = response.json()
        client_id = test_client["id"]
        
        # Add various reference patterns
        patterns = [
            {"pattern": "EXACT123", "is_regex": False, "is_fuzzy": False},
            {"pattern": "PREFIX*", "is_regex": False, "is_fuzzy": False},
            {"pattern": r"CODE-\d{3}", "is_regex": True, "is_fuzzy": False},
            {"pattern": "FUZZYREF", "is_regex": False, "is_fuzzy": True}
        ]
        
        for i, pattern in enumerate(patterns):
            ref = {
                "client_id": client_id,
                **pattern,
                "priority": (i + 1) * 10
            }
            response = client.post(
                f"/api/clients/{client_id}/references",
                json=ref,
                headers=admin_headers
            )
            assert response.status_code == 201
        
        # Test reference matching
        test_refs = [
            "EXACT123",      # Should match exact
            "PREFIX456",     # Should match prefix
            "CODE-789",      # Should match regex
            "FUZZYRF",       # Should match fuzzy (typo)
            "NOMATCH"        # Should not match
        ]
        
        response = client.post(
            "/api/clients/test-reference-matching",
            json=test_refs,
            headers=admin_headers
        )
        assert response.status_code == 200
        results = response.json()
        
        # Verify matches
        assert results["EXACT123"]["best_match"]["client_name"] == "Match Test Co"
        assert results["EXACT123"]["best_match"]["match_type"] == "exact"
        
        assert results["PREFIX456"]["best_match"]["client_name"] == "Match Test Co"
        assert results["PREFIX456"]["best_match"]["match_type"] == "prefix"
        
        assert results["CODE-789"]["best_match"]["client_name"] == "Match Test Co"
        assert results["CODE-789"]["best_match"]["match_type"] == "regex"
        
        assert results["FUZZYRF"]["best_match"]["client_name"] == "Match Test Co"
        assert results["FUZZYRF"]["best_match"]["match_type"] == "fuzzy"
        
        assert results["NOMATCH"]["best_match"]["client_id"] is None