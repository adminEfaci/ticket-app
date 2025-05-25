#!/usr/bin/env python3
"""Create client references based on account numbers in notes"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlmodel import Session, select
from backend.core.database import engine, create_db_and_tables
from backend.models.client import Client, ClientReference
from uuid import uuid4
import re


def create_client_references():
    """Create references for all clients based on their account numbers"""
    with Session(engine) as session:
        # Get all clients
        clients = session.exec(select(Client)).all()
        
        created_count = 0
        
        for client in clients:
            # Extract account number from notes
            if client.notes:
                account_match = re.search(r'Account Number:\s*(\d+)', client.notes, re.IGNORECASE)
                if account_match:
                    account_number = account_match.group(1)
                    
                    # Check if reference already exists
                    existing = session.exec(
                        select(ClientReference).where(
                            ClientReference.client_id == client.id,
                            ClientReference.pattern == account_number
                        )
                    ).first()
                    
                    if not existing:
                        # Create reference
                        reference = ClientReference(
                            id=uuid4(),
                            client_id=client.id,
                            pattern=account_number,
                            is_regex=False,
                            is_fuzzy=False,
                            priority=10,  # High priority for exact account number match
                            active=True,
                            description=f"Account number {account_number}"
                        )
                        session.add(reference)
                        created_count += 1
                        print(f"Created reference for {client.name}: {account_number}")
        
        session.commit()
        print(f"\nCreated {created_count} client references")
        
        # Show summary
        total_refs = session.exec(select(ClientReference)).all()
        print(f"Total references in database: {len(total_refs)}")


if __name__ == "__main__":
    print("Creating client references from account numbers...")
    create_db_and_tables()
    create_client_references()