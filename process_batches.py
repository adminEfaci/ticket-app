#!/usr/bin/env python3
"""
Script to process the existing batches and create tickets in the database.
This will parse the XLS files and create tickets that can be used for export testing.
"""

import os
import sys
import pandas as pd
from datetime import date, datetime
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent))

# Set up environment
os.environ['DATABASE_URL'] = 'postgresql://postgres:postgres@localhost:5432/ticketapp'

from backend.core.database import get_session, engine
from backend.models.ticket import Ticket
from backend.models.batch import ProcessingBatch
from backend.models.client import Client
from backend.services.xls_parser_service import XlsParserService
from backend.services.ticket_mapper import TicketMapper
from backend.services.ticket_validator import TicketValidator
from sqlmodel import Session, select

def get_or_create_default_client(session: Session) -> Client:
    """Get or create a default client for testing"""
    # Check if any client exists
    stmt = select(Client).where(Client.name == "DEFAULT_CLIENT")
    client = session.exec(stmt).first()
    
    if not client:
        client = Client(
            name="DEFAULT_CLIENT",
            code="DEFAULT",
            active=True
        )
        session.add(client)
        session.commit()
        session.refresh(client)
        print(f"Created default client: {client.id}")
    else:
        print(f"Using existing client: {client.id}")
    
    return client

def process_xls_file(file_path: str, client_id: str, session: Session):
    """Process an XLS file and create tickets"""
    print(f"\nProcessing {file_path}")
    
    # Initialize services
    parser = XlsParserService()
    mapper = TicketMapper()
    validator = TicketValidator()
    
    # Parse the XLS file
    df = parser.parse_xls_file(file_path)
    print(f"Found {len(df)} rows in XLS")
    
    # Extract tickets
    raw_tickets = parser.extract_tickets(df)
    print(f"Extracted {len(raw_tickets)} tickets")
    
    # Map to ticket models
    tickets = []
    for raw_ticket in raw_tickets:
        try:
            # Map to model
            ticket_data = mapper.map_to_ticket_model(raw_ticket)
            
            # Add client ID
            ticket_data['client_id'] = client_id
            
            # Validate
            ticket = Ticket(**ticket_data)
            is_valid, errors = validator.validate_ticket(ticket)
            
            if is_valid:
                tickets.append(ticket)
            else:
                print(f"  Invalid ticket {ticket.ticket_number}: {errors}")
                
        except Exception as e:
            print(f"  Error mapping ticket: {e}")
    
    print(f"Valid tickets: {len(tickets)}")
    
    # Save tickets to database
    saved_count = 0
    for ticket in tickets:
        try:
            # Check if ticket already exists
            existing = session.exec(
                select(Ticket).where(Ticket.ticket_number == ticket.ticket_number)
            ).first()
            
            if not existing:
                session.add(ticket)
                saved_count += 1
            else:
                print(f"  Ticket {ticket.ticket_number} already exists")
                
        except Exception as e:
            print(f"  Error saving ticket {ticket.ticket_number}: {e}")
    
    session.commit()
    print(f"Saved {saved_count} new tickets")
    
    return len(tickets), saved_count

def main():
    """Main processing function"""
    print("Ticket Processing Script")
    print("=" * 60)
    
    # Sample files
    samples_dir = Path(__file__).parent / "samples"
    xls_files = [
        samples_dir / "APRIL_14_2025.xls",
        samples_dir / "APRIL_15_2025.xls"
    ]
    
    # Verify files exist
    for f in xls_files:
        if not f.exists():
            print(f"ERROR: File not found: {f}")
            return 1
    
    # Get database session
    with Session(engine) as session:
        # Get or create default client
        client = get_or_create_default_client(session)
        
        # Process each XLS file
        total_tickets = 0
        total_saved = 0
        
        for xls_file in xls_files:
            extracted, saved = process_xls_file(str(xls_file), str(client.id), session)
            total_tickets += extracted
            total_saved += saved
        
        print("\n" + "=" * 60)
        print(f"Processing complete!")
        print(f"Total tickets extracted: {total_tickets}")
        print(f"Total tickets saved: {total_saved}")
        
        # Verify tickets in database
        ticket_count = session.exec(select(Ticket)).all()
        print(f"Total tickets in database: {len(ticket_count)}")
        
        # Show sample tickets
        print("\nSample tickets:")
        sample_tickets = session.exec(select(Ticket).limit(5)).all()
        for t in sample_tickets:
            print(f"  - {t.ticket_number}: {t.entry_date} - {t.reference} ({t.net_weight} kg)")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())