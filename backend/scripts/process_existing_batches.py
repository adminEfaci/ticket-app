#!/usr/bin/env python3
"""
Script to process existing batches and create tickets.
This runs inside the Docker container with proper database access.
"""

import asyncio
import sys
import os
from pathlib import Path
from uuid import UUID
from datetime import datetime

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlmodel import Session, select
from backend.core.database import engine
from backend.models.batch import ProcessingBatch, BatchStatus
from backend.models.ticket import Ticket
from backend.models.client import Client
from backend.services.xls_parser_service import XlsParserService
from backend.services.ticket_mapper import TicketMapper
from backend.services.ticket_validator import TicketValidator
from backend.services.ticket_service import TicketService
from backend.services.storage_service import StorageService

def get_default_client(session: Session) -> Client:
    """Get the first active client or create a default one"""
    # Try to get any active client
    stmt = select(Client).where(Client.active == True).limit(1)
    client = session.exec(stmt).first()
    
    if not client:
        # Create a default client
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
        print(f"Using client: {client.name} ({client.id})")
    
    return client

def process_batch(batch_id: str, session: Session):
    """Process a single batch"""
    print(f"\nProcessing batch {batch_id}")
    
    # Get batch
    batch = session.get(ProcessingBatch, UUID(batch_id))
    if not batch:
        print(f"Batch {batch_id} not found")
        return
    
    print(f"Batch status: {batch.status}")
    print(f"XLS file: {batch.xls_filename}")
    
    # Initialize services
    storage_service = StorageService("/data/batches")
    parser = XlsParserService()
    mapper = TicketMapper()
    validator = TicketValidator()
    ticket_service = TicketService(session)
    
    # Find XLS file
    batch_dir = Path("/data/batches") / str(batch_id)
    
    # Check if directory exists
    if not batch_dir.exists():
        print(f"Batch directory {batch_dir} does not exist")
        # Try to find by file hash
        print(f"Looking for batch with hash: {batch.file_hash}")
        return
    
    # Look for original.xls first, then any .xls file
    xls_path = batch_dir / "original.xls"
    if not xls_path.exists():
        xls_files = list(batch_dir.glob("*.xls"))
        if not xls_files:
            print(f"No XLS file found in {batch_dir}")
            return
        xls_path = xls_files[0]
    print(f"Processing file: {xls_path}")
    
    # Get client
    client = get_default_client(session)
    
    try:
        # Parse XLS
        df = parser.parse_xls_file(str(xls_path))
        print(f"Parsed {len(df)} rows from XLS")
        
        # Extract tickets
        raw_tickets = parser.extract_tickets(df)
        print(f"Extracted {len(raw_tickets)} raw tickets")
        
        # Process tickets
        valid_count = 0
        invalid_count = 0
        duplicate_count = 0
        
        for raw_ticket in raw_tickets:
            try:
                # Map to ticket model
                ticket_data = mapper.map_to_ticket_model(raw_ticket)
                
                # Set client and batch
                ticket_data['client_id'] = client.id
                ticket_data['batch_id'] = batch.id
                
                # Create ticket instance
                ticket = Ticket(**ticket_data)
                
                # Validate
                is_valid, errors = validator.validate_ticket(ticket)
                
                if not is_valid:
                    print(f"  Invalid ticket {ticket.ticket_number}: {errors}")
                    invalid_count += 1
                    continue
                
                # Check for duplicates
                existing = session.exec(
                    select(Ticket).where(Ticket.ticket_number == ticket.ticket_number)
                ).first()
                
                if existing:
                    print(f"  Duplicate ticket {ticket.ticket_number}")
                    duplicate_count += 1
                    continue
                
                # Save ticket
                session.add(ticket)
                valid_count += 1
                
            except Exception as e:
                print(f"  Error processing ticket: {e}")
                invalid_count += 1
        
        # Commit all tickets
        session.commit()
        
        # Update batch status
        batch.status = BatchStatus.READY
        batch.processed_at = datetime.utcnow()
        batch.stats = {
            "parsing": {
                "total_rows": len(df),
                "total_tickets": len(raw_tickets),
                "valid_tickets": valid_count,
                "invalid_tickets": invalid_count,
                "duplicate_tickets": duplicate_count
            }
        }
        session.add(batch)
        session.commit()
        
        print(f"\nBatch processing complete:")
        print(f"  Valid tickets: {valid_count}")
        print(f"  Invalid tickets: {invalid_count}")
        print(f"  Duplicate tickets: {duplicate_count}")
        
    except Exception as e:
        print(f"Error processing batch: {e}")
        import traceback
        traceback.print_exc()
        
        # Update batch status to error
        batch.status = BatchStatus.ERROR
        batch.error_reason = str(e)
        session.add(batch)
        session.commit()

def main():
    """Main processing function"""
    print("Batch Processing Script")
    print("=" * 60)
    
    with Session(engine) as session:
        # Get all pending batches
        stmt = select(ProcessingBatch).where(
            ProcessingBatch.status == BatchStatus.PENDING
        )
        batches = session.exec(stmt).all()
        
        print(f"Found {len(batches)} pending batches")
        
        if not batches:
            # Try to find any batches
            all_batches = session.exec(select(ProcessingBatch)).all()
            print(f"Total batches in database: {len(all_batches)}")
            
            if all_batches:
                print("\nExisting batches:")
                for b in all_batches[:5]:
                    print(f"  - {b.id}: {b.xls_filename} (status: {b.status})")
                
                # Try to process all batches regardless of status
                print("\nProcessing all batches...")
                for b in all_batches:
                    if b.status == BatchStatus.PENDING:
                        process_batch(str(b.id), session)
        
        # Process each batch
        for batch in batches:
            process_batch(str(batch.id), session)
        
        # Show final ticket count
        total_tickets = len(session.exec(select(Ticket)).all())
        print(f"\nTotal tickets in database: {total_tickets}")
        
        if total_tickets > 0:
            # Show sample tickets
            print("\nSample tickets:")
            tickets = session.exec(select(Ticket).limit(5)).all()
            for t in tickets:
                print(f"  - {t.ticket_number}: {t.entry_date} - {t.reference} ({t.net_weight} kg)")

if __name__ == "__main__":
    main()