#!/usr/bin/env python3
"""
Process the April 2025 data files directly
"""

import sys
from pathlib import Path
from uuid import UUID

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlmodel import Session, select
from backend.core.database import engine
from backend.models.batch import ProcessingBatch, BatchStatus
from backend.models.ticket import Ticket, TicketCreate
from backend.models.client import Client
from backend.models.user import User, UserRole
from backend.services.xls_parser_service import XlsParserService
from backend.services.ticket_mapper import TicketMapper
from backend.services.ticket_validator import TicketValidator
from backend.utils.datetime_utils import utcnow_naive

def process_april_files():
    """Process the April XLS files directly"""
    
    # Known file locations with batch IDs
    april_files = [
        ("/data/batches/8743c8ef-49af-400e-8668-9d7c596fe222/original.xls", "APRIL_14_2025", "8743c8ef-49af-400e-8668-9d7c596fe222"),
        ("/data/batches/2d818905-3d6d-4f13-83a4-6b601aad5fda/original.xls", "APRIL_15_2025", "2d818905-3d6d-4f13-83a4-6b601aad5fda")
    ]
    
    parser = XlsParserService()
    mapper = TicketMapper()
    validator = TicketValidator()
    
    with Session(engine) as session:
        # Get or create admin user
        admin_user = session.exec(select(User).where(User.role == UserRole.ADMIN)).first()
        if not admin_user:
            print("No admin user found, creating one...")
            admin_user = User(
                email="admin@example.com",
                first_name="System",
                last_name="Admin",
                role=UserRole.ADMIN,
                hashed_password="dummy"  # Will be updated later
            )
            session.add(admin_user)
            session.commit()
            session.refresh(admin_user)
        
        print(f"Using admin user: {admin_user.email} ({admin_user.id})")
        
        # Get or create default client
        client = session.exec(select(Client).where(Client.active == True)).first()
        if not client:
            client = Client(name="DEFAULT_CLIENT", code="DEFAULT", active=True)
            session.add(client)
            session.commit()
            session.refresh(client)
        
        print(f"Using client: {client.name} ({client.id})")
        
        total_created = 0
        
        for xls_path, file_desc, batch_id_str in april_files:
            print(f"\nProcessing {file_desc}...")
            
            try:
                # Get the batch
                batch_id = UUID(batch_id_str)
                batch = session.get(ProcessingBatch, batch_id)
                if not batch:
                    print(f"  Batch {batch_id} not found, creating...")
                    batch = ProcessingBatch(
                        id=batch_id,
                        created_by=admin_user.id,
                        xls_filename=f"{file_desc}.xls",
                        pdf_filename="",  # No PDF for manual imports
                        status=BatchStatus.PENDING,
                        uploaded_at=utcnow_naive()
                    )
                    session.add(batch)
                    session.commit()
                    session.refresh(batch)
                
                # Parse XLS - returns (tickets, errors)
                tickets, errors = parser.parse_xls_file(xls_path)
                print(f"  Parsed file, found {len(tickets)} tickets")
                
                if errors:
                    print(f"  Parsing errors: {len(errors)}")
                
                # Process each ticket
                created = 0
                for ticket_dto in tickets:
                    try:
                        # Map to model using correct method
                        ticket_create = mapper.map_dto_to_ticket(
                            ticket_dto, 
                            batch.id, 
                            batch.uploaded_at.date()
                        )
                        ticket_create.client_id = client.id
                        
                        # Create ticket from TicketCreate object
                        ticket = Ticket(**ticket_create.model_dump())
                        
                        # Validate
                        error = validator.validate_ticket(ticket_create, batch.uploaded_at.date())
                        if error:
                            print(f"    Validation error for {ticket_dto.ticket_number}: {error}")
                            continue
                        
                        # Check duplicate
                        existing = session.exec(
                            select(Ticket).where(Ticket.ticket_number == ticket.ticket_number)
                        ).first()
                        
                        if not existing:
                            session.add(ticket)
                            created += 1
                        else:
                            print(f"    Duplicate: {ticket.ticket_number}")
                            
                    except Exception as e:
                        print(f"    Error with ticket {ticket_dto.ticket_number}: {e}")
                
                session.commit()
                print(f"  Created {created} tickets")
                total_created += created
                
                # Update batch status
                batch.status = BatchStatus.READY
                batch.processed_at = utcnow_naive()
                # Add stats
                batch.stats = {
                    "total_tickets": len(tickets),
                    "processed_tickets": created,
                    "errors": len(errors) if errors else 0
                }
                session.add(batch)
                session.commit()
                
            except Exception as e:
                print(f"  Error: {e}")
        
        
        # Show results
        total_tickets = len(session.exec(select(Ticket)).all())
        print(f"\nTotal tickets in database: {total_tickets}")
        
        if total_tickets > 0:
            print("\nSample tickets:")
            tickets = session.exec(select(Ticket).limit(5)).all()
            for t in tickets:
                print(f"  - {t.ticket_number}: {t.entry_date} - {t.reference} ({t.net_weight} kg)")

if __name__ == "__main__":
    process_april_files()