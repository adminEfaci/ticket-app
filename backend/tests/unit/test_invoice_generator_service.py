import pytest
from datetime import date
from uuid import uuid4
from io import StringIO
import csv

from backend.services.invoice_generator_service import InvoiceGeneratorService
from backend.models.export import (
    ClientInvoice, InvoiceLineItem, WeeklyManifest,
    WeeklyGrouping, ClientGrouping, ReferenceGrouping
)


class TestInvoiceGeneratorService:
    
    @pytest.fixture
    def service(self):
        return InvoiceGeneratorService()
    
    @pytest.fixture
    def sample_week_groups(self):
        """Create sample week grouping data"""
        client_id = uuid4()
        
        # Create reference groups
        ref_group_007 = ReferenceGrouping(
            reference="#007",
            tickets=[
                {
                    "ticket_number": "T4121",
                    "entry_date": "2024-04-15",
                    "net_weight": 8.5,
                    "rate": 25.0,
                    "amount": 212.50,
                    "image_path": "tickets/T4121.png",
                    "note": "Test note 1"
                },
                {
                    "ticket_number": "T4122",
                    "entry_date": "2024-04-16",
                    "net_weight": 10.0,
                    "rate": 25.0,
                    "amount": 250.00,
                    "image_path": "tickets/T4122.png",
                    "note": "Test note 2"
                }
            ],
            ticket_count=2,
            total_tonnage=18.5,
            subtotal=462.50
        )
        
        ref_group_mm = ReferenceGrouping(
            reference="MM1001",
            tickets=[
                {
                    "ticket_number": "T4123",
                    "entry_date": "2024-04-17",
                    "net_weight": 5.0,
                    "rate": 25.0,
                    "amount": 125.00,
                    "image_path": "tickets/T4123.png",
                    "note": None
                }
            ],
            ticket_count=1,
            total_tonnage=5.0,
            subtotal=125.00
        )
        
        # Create client grouping
        client_group = ClientGrouping(
            client_id=client_id,
            client_name="Client 007",
            reference_groups={
                "#007": ref_group_007,
                "MM1001": ref_group_mm
            },
            total_tickets=3,
            total_tonnage=23.5,
            total_amount=587.50,
            rate_per_tonne=25.0
        )
        
        # Create weekly grouping
        week_group = WeeklyGrouping(
            week_start=date(2024, 4, 15),
            week_end=date(2024, 4, 20),
            client_groups={str(client_id): client_group},
            total_tickets=3,
            total_tonnage=23.5,
            total_amount=587.50
        )
        
        return {"2024-04-15": week_group}
    
    def test_generate_merged_csv(self, service, sample_week_groups):
        """Test merged CSV generation"""
        csv_content = service.generate_merged_csv(sample_week_groups)
        
        # Parse CSV
        reader = csv.DictReader(StringIO(csv_content))
        rows = list(reader)
        
        assert len(rows) == 3  # 3 tickets total
        
        # Check first row
        row1 = rows[0]
        assert row1['week_start'] == '2024-04-15'
        assert row1['client_name'] == 'Client 007'
        assert row1['reference'] == '#007'
        assert row1['ticket_number'] == 'T4121'
        assert row1['net_weight'] == '8.50'
        assert row1['rate'] == '25.00'
        assert row1['amount'] == '212.50'
        assert row1['note'] == 'Test note 1'
        
        # Check different reference
        row3 = rows[2]
        assert row3['reference'] == 'MM1001'
        assert row3['ticket_number'] == 'T4123'
    
    def test_generate_client_invoice(self, service, sample_week_groups):
        """Test client invoice generation"""
        week_group = sample_week_groups["2024-04-15"]
        client_group = list(week_group.client_groups.values())[0]
        
        invoice = service.generate_client_invoice(
            client_group=client_group,
            week_start=week_group.week_start,
            week_end=week_group.week_end
        )
        
        assert invoice.client_name == "Client 007"
        assert invoice.week_start == date(2024, 4, 15)
        assert invoice.week_end == date(2024, 4, 20)
        assert len(invoice.line_items) == 2  # 2 references
        
        # Check line items
        line1 = invoice.line_items[0]
        assert line1.reference == "#007"
        assert line1.ticket_count == 2
        assert line1.total_weight == 18.5
        assert line1.rate == 25.0
        assert line1.amount == 462.50
        
        line2 = invoice.line_items[1]
        assert line2.reference == "MM1001"
        assert line2.ticket_count == 1
        assert line2.total_weight == 5.0
        assert line2.amount == 125.00
        
        # Check totals
        assert invoice.total_tonnage == 23.5
        assert invoice.total_amount == 587.50
    
    def test_invoice_to_csv(self, service):
        """Test invoice CSV formatting"""
        invoice = ClientInvoice(
            client_id=uuid4(),
            client_name="Test Client",
            week_start=date(2024, 4, 15),
            week_end=date(2024, 4, 20),
            line_items=[
                InvoiceLineItem(
                    reference="#007",
                    ticket_count=5,
                    total_weight=50.0,
                    rate=25.0,
                    amount=1250.0
                ),
                InvoiceLineItem(
                    reference="MM1001",
                    ticket_count=3,
                    total_weight=30.0,
                    rate=25.0,
                    amount=750.0
                )
            ],
            total_tonnage=80.0,
            total_amount=2000.0
        )
        
        csv_content = service.invoice_to_csv(invoice)
        
        # Check header info
        assert "INVOICE" in csv_content
        assert "Client: Test Client" in csv_content
        assert "Period: 2024-04-15 to 2024-04-20" in csv_content
        
        # Check totals
        assert "Total Tickets,8" in csv_content
        assert "Total Weight,80.00 tonnes" in csv_content
        assert "Total Amount,$2000.00" in csv_content
    
    def test_generate_weekly_manifest(self, service, sample_week_groups):
        """Test weekly manifest generation"""
        week_group = sample_week_groups["2024-04-15"]
        
        manifest = service.generate_weekly_manifest(week_group)
        
        assert manifest.week_start == date(2024, 4, 15)
        assert manifest.week_end == date(2024, 4, 20)
        assert manifest.total_clients == 1
        assert manifest.total_tickets == 3
        assert manifest.total_tonnage == 23.5
        assert manifest.total_amount == 587.50
        
        # Check client summary
        assert len(manifest.client_summaries) == 1
        summary = manifest.client_summaries[0]
        assert summary['client_name'] == 'Client 007'
        assert summary['ticket_count'] == 3
        assert summary['total_weight'] == 23.5
        assert summary['rate'] == 25.0
        assert summary['total_amount'] == 587.50
        assert summary['reference_count'] == 2
    
    def test_manifest_to_csv(self, service):
        """Test manifest CSV formatting"""
        manifest = WeeklyManifest(
            week_start=date(2024, 4, 15),
            week_end=date(2024, 4, 20),
            client_summaries=[
                {
                    'client_id': str(uuid4()),
                    'client_name': 'Client A',
                    'ticket_count': 10,
                    'total_weight': 100.0,
                    'rate': 25.0,
                    'total_amount': 2500.0,
                    'reference_count': 3
                },
                {
                    'client_id': str(uuid4()),
                    'client_name': 'Client B',
                    'ticket_count': 5,
                    'total_weight': 50.0,
                    'rate': 30.0,
                    'total_amount': 1500.0,
                    'reference_count': 2
                }
            ],
            total_clients=2,
            total_tickets=15,
            total_tonnage=150.0,
            total_amount=4000.0
        )
        
        csv_content = service.manifest_to_csv(manifest)
        
        # Check header
        assert "WEEKLY MANIFEST" in csv_content
        assert "Week: 2024-04-15 to 2024-04-20" in csv_content
        
        # Check client entries
        assert "Client A" in csv_content
        assert "Client B" in csv_content
        
        # Check totals
        assert "Total Clients,2" in csv_content
        assert "Total Tickets,15" in csv_content
        assert "Total Weight,150.00 tonnes" in csv_content
        assert "Total Amount,$4000.00" in csv_content
    
    def test_validate_invoice_totals_success(self, service):
        """Test invoice validation with correct totals"""
        client_group = ClientGrouping(
            client_id=uuid4(),
            client_name="Test Client",
            reference_groups={},
            total_tickets=10,
            total_tonnage=100.0,
            total_amount=2500.0,
            rate_per_tonne=25.0
        )
        
        invoice = ClientInvoice(
            client_id=client_group.client_id,
            client_name=client_group.client_name,
            week_start=date(2024, 4, 15),
            week_end=date(2024, 4, 20),
            line_items=[
                InvoiceLineItem(
                    reference="#007",
                    ticket_count=10,
                    total_weight=100.0,
                    rate=25.0,
                    amount=2500.0
                )
            ],
            total_tonnage=100.0,
            total_amount=2500.0
        )
        
        errors = service.validate_invoice_totals(invoice, client_group)
        assert len(errors) == 0
    
    def test_validate_invoice_totals_mismatch(self, service):
        """Test invoice validation with mismatched totals"""
        client_group = ClientGrouping(
            client_id=uuid4(),
            client_name="Test Client",
            reference_groups={},
            total_tickets=10,
            total_tonnage=100.0,
            total_amount=2500.0,
            rate_per_tonne=25.0
        )
        
        invoice = ClientInvoice(
            client_id=client_group.client_id,
            client_name=client_group.client_name,
            week_start=date(2024, 4, 15),
            week_end=date(2024, 4, 20),
            line_items=[
                InvoiceLineItem(
                    reference="#007",
                    ticket_count=10,
                    total_weight=100.0,
                    rate=25.0,
                    amount=2600.0  # Wrong amount
                )
            ],
            total_tonnage=99.0,  # Wrong tonnage
            total_amount=2600.0   # Wrong total
        )
        
        errors = service.validate_invoice_totals(invoice, client_group)
        assert len(errors) == 3  # Tonnage, amount, and line item errors
        assert "Tonnage mismatch" in errors[0]
        assert "Amount mismatch" in errors[1]
        assert "Line item calculation error" in errors[2]
    
    def test_rounding_precision(self, service):
        """Test that financial values are properly rounded"""
        # Test InvoiceLineItem rounding
        line_item = InvoiceLineItem(
            reference="#007",
            ticket_count=1,
            total_weight=10.12345,  # Should be rounded
            rate=25.456,
            amount=257.89123  # Should be rounded
        )
        
        assert line_item.total_weight == 10.12
        assert line_item.amount == 257.89
        
        # Test ClientInvoice rounding
        invoice = ClientInvoice(
            client_id=uuid4(),
            client_name="Test",
            week_start=date.today(),
            week_end=date.today(),
            total_tonnage=123.456789,  # Should be rounded
            total_amount=3086.41975   # Should be rounded
        )
        
        assert invoice.total_tonnage == 123.46
        assert invoice.total_amount == 3086.42