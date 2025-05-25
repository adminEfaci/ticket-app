#!/usr/bin/env python3
"""Fix missing account numbers and update credit terms"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlmodel import Session, select
from backend.core.database import engine, create_db_and_tables
from backend.models.client import Client, ClientReference
from uuid import uuid4


def fix_clients():
    """Fix missing account numbers and credit terms"""
    
    # Mapping of client names to their account numbers from CSV
    account_mappings = {
        "Cash Sales": "001",
        "The Renovator": "002", 
        "Stanley Sanitation": "003",
        "Thomas Cavanagh Construction Limited": "004",
        "Lachapelle Antiques": "005",
        "Patten Homes": "007",
        "Jim Miles Guide Service": "010"
    }
    
    with Session(engine) as session:
        # First, update all clients to have 10 days credit terms
        all_clients = session.exec(select(Client)).all()
        updated_count = 0
        
        for client in all_clients:
            if client.credit_terms_days != 10:
                client.credit_terms_days = 10
                updated_count += 1
        
        print(f"Updated {updated_count} clients to 10 days credit terms")
        
        # Now fix missing account numbers
        fixed_count = 0
        
        for client_name, account_number in account_mappings.items():
            # Find the client
            client = session.exec(
                select(Client).where(Client.name.contains(client_name))
            ).first()
            
            if client:
                # Update notes to include account number if not already there
                if "Account Number:" not in (client.notes or ""):
                    if client.notes:
                        client.notes = f"Account Number: {account_number}. {client.notes}"
                    else:
                        client.notes = f"Account Number: {account_number}"
                    
                    print(f"Updated {client.name} with Account Number: {account_number}")
                    fixed_count += 1
                    
                    # Also create reference if it doesn't exist
                    existing_ref = session.exec(
                        select(ClientReference).where(
                            ClientReference.client_id == client.id,
                            ClientReference.pattern == account_number
                        )
                    ).first()
                    
                    if not existing_ref:
                        reference = ClientReference(
                            id=uuid4(),
                            client_id=client.id,
                            pattern=account_number,
                            is_regex=False,
                            is_fuzzy=False,
                            priority=10,
                            active=True,
                            description=f"Account number {account_number}"
                        )
                        session.add(reference)
                        print(f"  Created reference for account number {account_number}")
        
        session.commit()
        print(f"\nFixed {fixed_count} clients with missing account numbers")
        print(f"All clients now have 10 days credit terms")


if __name__ == "__main__":
    print("Fixing missing account numbers and credit terms...")
    create_db_and_tables()
    fix_clients()