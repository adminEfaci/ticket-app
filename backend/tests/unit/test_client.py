import pytest
from datetime import date
from uuid import uuid4

from backend.models.client import (
    Client, ClientCreate, ClientUpdate,
    ClientReference, ClientReferenceCreate,
    ClientRate, ClientRateCreate,
    InvoiceFormat
)


class TestClientModels:
    """Test client model creation and validation"""
    
    def test_create_client(self):
        """Test creating a basic client"""
        client_data = ClientCreate(
            name="Test Company Inc",
            billing_email="billing@testcompany.com",
            invoice_format=InvoiceFormat.CSV,
            credit_terms_days=30
        )
        
        # Test that the model can be created
        client = Client(**client_data.model_dump())
        
        assert client.id is not None
        assert client.name == "Test Company Inc"
        assert client.billing_email == "billing@testcompany.com"
        assert client.invoice_format == InvoiceFormat.CSV
        assert client.active is True  # default value
        assert client.created_at is not None
    
    def test_create_client_with_parent(self):
        """Test creating a client with a parent (subcontractor)"""
        parent_id = uuid4()
        
        # Create subcontractor
        sub_data = ClientCreate(
            name="Subcontractor Inc",
            parent_id=parent_id,
            billing_email="sub@contractor.com"
        )
        
        subcontractor = Client(**sub_data.model_dump())
        
        assert subcontractor.parent_id == parent_id
        
    def test_invoice_format_enum(self):
        """Test invoice format enum values"""
        assert InvoiceFormat.CSV.value == "csv"
        assert InvoiceFormat.XLSX.value == "xlsx"
        assert InvoiceFormat.PDF.value == "pdf"
        assert InvoiceFormat.ODOO.value == "odoo"
    
    def test_client_update_model(self):
        """Test client update model with partial data"""
        update_data = ClientUpdate(
            billing_email="newemail@company.com",
            credit_terms_days=45
        )
        
        # Should only have the fields that were set
        dump = update_data.model_dump(exclude_unset=True)
        assert len(dump) == 2
        assert dump["billing_email"] == "newemail@company.com"
        assert dump["credit_terms_days"] == 45
    
    def test_email_validation(self):
        """Test email validation"""
        # Valid email
        client_data = ClientCreate(
            name="Test Company",
            billing_email="test@example.com"
        )
        client = Client(**client_data.model_dump())
        assert client.billing_email == "test@example.com"
        
        # Invalid email should raise
        with pytest.raises(ValueError, match="Invalid email format"):
            ClientCreate(
                name="Test Company",
                billing_email="invalid-email"
            )


class TestClientReference:
    """Test client reference pattern models"""
    
    def test_create_exact_reference(self):
        """Test creating an exact match reference"""
        client_id = uuid4()
        
        ref_data = ClientReferenceCreate(
            client_id=client_id,
            pattern="REF123",
            is_regex=False,
            is_fuzzy=False,
            priority=10
        )
        
        reference = ClientReference(**ref_data.model_dump())
        
        assert reference.client_id == client_id
        assert reference.pattern == "REF123"
        assert reference.is_regex is False
        assert reference.is_fuzzy is False
        assert reference.priority == 10
        assert reference.active is True  # default
    
    def test_create_regex_reference(self):
        """Test creating a regex reference pattern"""
        client_id = uuid4()
        
        ref_data = ClientReferenceCreate(
            client_id=client_id,
            pattern=r"REF\d{3}",
            is_regex=True,
            priority=20
        )
        
        reference = ClientReference(**ref_data.model_dump())
        
        assert reference.pattern == r"REF\d{3}"
        assert reference.is_regex is True
    
    def test_pattern_validation(self):
        """Test pattern validation"""
        # Empty pattern should fail (Pydantic validation)
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="String should have at least 1 character"):
            ClientReferenceCreate(
                client_id=uuid4(),
                pattern=""
            )
        
        # Invalid regex should fail
        with pytest.raises(ValidationError, match="Invalid regex pattern"):
            ClientReferenceCreate(
                client_id=uuid4(),
                pattern="[invalid",
                is_regex=True
            )


class TestClientRate:
    """Test client rate models"""
    
    def test_create_rate(self):
        """Test creating a client rate"""
        client_id = uuid4()
        
        rate_data = ClientRateCreate(
            client_id=client_id,
            rate_per_tonne=25.50,
            effective_from=date.today()
        )
        
        rate = ClientRate(**rate_data.model_dump())
        
        assert rate.client_id == client_id
        assert rate.rate_per_tonne == 25.50
        assert rate.effective_from == date.today()
        assert rate.effective_to is None  # indefinite
        assert rate.approved_by is None  # not yet approved
    
    def test_rate_validation(self):
        """Test rate validation constraints"""
        # Rate too low
        with pytest.raises(ValueError):
            ClientRateCreate(
                client_id=uuid4(),
                rate_per_tonne=5.00,  # Below $10 minimum
                effective_from=date.today()
            )
        
        # Rate too high
        with pytest.raises(ValueError):
            ClientRateCreate(
                client_id=uuid4(),
                rate_per_tonne=150.00,  # Above $100 maximum
                effective_from=date.today()
            )
    
    def test_effective_date_validation(self):
        """Test effective date validation"""
        # effective_to must be after effective_from
        with pytest.raises(ValueError, match="effective_to must be after effective_from"):
            ClientRateCreate(
                client_id=uuid4(),
                rate_per_tonne=25.00,
                effective_from=date(2024, 1, 1),
                effective_to=date(2023, 12, 31)  # Before effective_from
            )