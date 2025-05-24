import csv
import io
import logging
from datetime import date
from typing import List, Dict

from ..models.export import (
    ClientInvoice, InvoiceLineItem, WeeklyManifest,
    WeeklyGrouping, ClientGrouping
)

logger = logging.getLogger(__name__)


class InvoiceGeneratorService:
    """Service for generating invoice CSV files"""
    
    def generate_merged_csv(
        self, 
        week_groups: Dict[str, WeeklyGrouping]
    ) -> str:
        """
        Generate merged CSV with all REPRINT tickets and billing info
        
        Args:
            week_groups: Dictionary of weekly groupings
            
        Returns:
            CSV content as string
        """
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                'week_start', 'client_id', 'client_name', 'reference',
                'ticket_number', 'entry_date', 'net_weight', 'rate',
                'amount', 'note'
            ]
        )
        writer.writeheader()
        
        for week_key, week_group in sorted(week_groups.items()):
            for client_key, client_group in sorted(week_group.client_groups.items()):
                for reference, ref_group in sorted(client_group.reference_groups.items()):
                    for ticket in ref_group.tickets:
                        writer.writerow({
                            'week_start': week_group.week_start.isoformat(),
                            'client_id': client_group.client_id,
                            'client_name': client_group.client_name,
                            'reference': reference,
                            'ticket_number': ticket['ticket_number'],
                            'entry_date': ticket['entry_date'],
                            'net_weight': f"{ticket['net_weight']:.2f}",
                            'rate': f"{ticket['rate']:.2f}",
                            'amount': f"{ticket['amount']:.2f}",
                            'note': ticket.get('note', '')
                        })
        
        content = output.getvalue()
        logger.info(f"Generated merged CSV with {len(content.splitlines()) - 1} rows")
        return content
    
    def generate_client_invoice(
        self, 
        client_group: ClientGrouping,
        week_start: date,
        week_end: date
    ) -> ClientInvoice:
        """
        Generate invoice for a single client
        
        Args:
            client_group: Client grouping data
            week_start: Start of the week
            week_end: End of the week
            
        Returns:
            ClientInvoice object
        """
        invoice = ClientInvoice(
            client_id=client_group.client_id,
            client_name=client_group.client_name,
            week_start=week_start,
            week_end=week_end,
            line_items=[],
            total_tonnage=0.0,
            total_amount=0.0
        )
        
        # Create line items grouped by reference
        for reference, ref_group in sorted(client_group.reference_groups.items()):
            line_item = InvoiceLineItem(
                reference=reference,
                ticket_count=ref_group.ticket_count,
                total_weight=ref_group.total_tonnage,
                rate=client_group.rate_per_tonne,
                amount=ref_group.subtotal
            )
            invoice.line_items.append(line_item)
        
        # Calculate totals
        invoice.total_tonnage = sum(item.total_weight for item in invoice.line_items)
        invoice.total_amount = sum(item.amount for item in invoice.line_items)
        
        # Validate totals match
        expected_amount = round(invoice.total_tonnage * client_group.rate_per_tonne, 2)
        if abs(invoice.total_amount - expected_amount) > 0.01:
            logger.warning(
                f"Invoice total mismatch for {client_group.client_name}: "
                f"calculated {invoice.total_amount}, expected {expected_amount}"
            )
        
        return invoice
    
    def invoice_to_csv(self, invoice: ClientInvoice) -> str:
        """
        Convert ClientInvoice to CSV format
        
        Args:
            invoice: ClientInvoice object
            
        Returns:
            CSV content as string
        """
        output = io.StringIO()
        
        # Write header info
        output.write("INVOICE\n")
        output.write(f"Client: {invoice.client_name}\n")
        output.write(f"Client ID: {invoice.client_id}\n")
        output.write(f"Period: {invoice.week_start} to {invoice.week_end}\n")
        output.write(f"Invoice Date: {invoice.invoice_date}\n")
        output.write("\n")
        
        # Write line items
        writer = csv.DictWriter(
            output,
            fieldnames=['Reference', 'Tickets', 'Weight (tonnes)', 'Rate', 'Amount']
        )
        writer.writeheader()
        
        for item in invoice.line_items:
            writer.writerow({
                'Reference': item.reference,
                'Tickets': item.ticket_count,
                'Weight (tonnes)': f"{item.total_weight:.2f}",
                'Rate': f"${item.rate:.2f}",
                'Amount': f"${item.amount:.2f}"
            })
        
        # Write totals
        output.write("\n")
        output.write(f"Total Tickets,{sum(item.ticket_count for item in invoice.line_items)}\n")
        output.write(f"Total Weight,{invoice.total_tonnage:.2f} tonnes\n")
        output.write(f"Total Amount,${invoice.total_amount:.2f}\n")
        
        return output.getvalue()
    
    def generate_weekly_manifest(
        self, 
        week_group: WeeklyGrouping
    ) -> WeeklyManifest:
        """
        Generate manifest for a week
        
        Args:
            week_group: Weekly grouping data
            
        Returns:
            WeeklyManifest object
        """
        manifest = WeeklyManifest(
            week_start=week_group.week_start,
            week_end=week_group.week_end,
            client_summaries=[],
            total_clients=len(week_group.client_groups),
            total_tickets=week_group.total_tickets,
            total_tonnage=week_group.total_tonnage,
            total_amount=week_group.total_amount
        )
        
        # Create client summaries
        for client_key, client_group in sorted(week_group.client_groups.items()):
            summary = {
                'client_id': str(client_group.client_id),
                'client_name': client_group.client_name,
                'ticket_count': client_group.total_tickets,
                'total_weight': client_group.total_tonnage,
                'rate': client_group.rate_per_tonne,
                'total_amount': client_group.total_amount,
                'reference_count': len(client_group.reference_groups)
            }
            manifest.client_summaries.append(summary)
        
        return manifest
    
    def manifest_to_csv(self, manifest: WeeklyManifest) -> str:
        """
        Convert WeeklyManifest to CSV format
        
        Args:
            manifest: WeeklyManifest object
            
        Returns:
            CSV content as string
        """
        output = io.StringIO()
        
        # Write header
        output.write("WEEKLY MANIFEST\n")
        output.write(f"Week: {manifest.week_start} to {manifest.week_end}\n")
        output.write(f"Generated: {manifest.generated_at}\n")
        output.write("\n")
        
        # Write summary
        writer = csv.DictWriter(
            output,
            fieldnames=[
                'Client ID', 'Client Name', 'Tickets', 'References',
                'Weight (tonnes)', 'Rate', 'Total Amount'
            ]
        )
        writer.writeheader()
        
        for summary in manifest.client_summaries:
            writer.writerow({
                'Client ID': summary['client_id'],
                'Client Name': summary['client_name'],
                'Tickets': summary['ticket_count'],
                'References': summary['reference_count'],
                'Weight (tonnes)': f"{summary['total_weight']:.2f}",
                'Rate': f"${summary['rate']:.2f}",
                'Total Amount': f"${summary['total_amount']:.2f}"
            })
        
        # Write totals
        output.write("\n")
        output.write(f"Total Clients,{manifest.total_clients}\n")
        output.write(f"Total Tickets,{manifest.total_tickets}\n")
        output.write(f"Total Weight,{manifest.total_tonnage:.2f} tonnes\n")
        output.write(f"Total Amount,${manifest.total_amount:.2f}\n")
        
        return output.getvalue()
    
    def validate_invoice_totals(
        self, 
        invoice: ClientInvoice,
        client_group: ClientGrouping
    ) -> List[str]:
        """
        Validate invoice totals match expected values
        
        Args:
            invoice: Generated invoice
            client_group: Source client grouping
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check tonnage
        if abs(invoice.total_tonnage - client_group.total_tonnage) > 0.01:
            errors.append(
                f"Tonnage mismatch: invoice={invoice.total_tonnage:.2f}, "
                f"expected={client_group.total_tonnage:.2f}"
            )
        
        # Check amount
        if abs(invoice.total_amount - client_group.total_amount) > 0.01:
            errors.append(
                f"Amount mismatch: invoice=${invoice.total_amount:.2f}, "
                f"expected=${client_group.total_amount:.2f}"
            )
        
        # Check line item calculations
        for item in invoice.line_items:
            expected = round(item.total_weight * item.rate, 2)
            if abs(item.amount - expected) > 0.01:
                errors.append(
                    f"Line item calculation error for {item.reference}: "
                    f"amount=${item.amount:.2f}, expected=${expected:.2f}"
                )
        
        return errors