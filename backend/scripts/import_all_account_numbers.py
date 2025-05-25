#!/usr/bin/env python3
"""Import ALL account numbers from the CSV file comprehensively"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import csv
from sqlmodel import Session, select
from backend.core.database import engine, create_db_and_tables
from backend.models.client import Client, ClientReference
from uuid import uuid4
import re


def clean_name(name):
    """Clean up client name"""
    if not name:
        return None
    # Remove extra spaces and quotes
    name = name.strip().strip('"').strip()
    # Remove multiple spaces
    name = ' '.join(name.split())
    return name


def parse_csv_properly():
    """Parse the CSV file and extract all account numbers"""
    csv_path = "/app/samples/Clients-all.csv"
    
    account_data = {}
    
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        # Read all content
        content = f.read()
        
    # Split into lines
    lines = content.split('\n')
    
    # Skip header
    current_row = []
    in_multiline = False
    
    for i in range(1, len(lines)):
        line = lines[i].strip()
        
        if not line:
            continue
            
        # Count quotes to detect multiline entries
        quote_count = line.count('"')
        
        if not in_multiline and quote_count % 2 == 0:
            # Single line entry
            parts = line.split(',')
            if len(parts) >= 2:
                name = clean_name(parts[0])
                account_num = parts[1].strip()
                if name and account_num and account_num.isdigit():
                    account_data[name] = account_num
        else:
            # Handle multiline or complex entries
            if not in_multiline:
                current_row = [line]
                in_multiline = True
            else:
                current_row.append(line)
                
            # Check if we've completed the multiline
            full_text = ' '.join(current_row)
            if full_text.count('"') % 2 == 0:
                # Parse the complete row
                try:
                    # Use csv reader for complex parsing
                    reader = csv.reader([full_text])
                    for row in reader:
                        if len(row) >= 2:
                            name = clean_name(row[0])
                            account_num = row[1].strip()
                            if name and account_num and account_num.isdigit():
                                account_data[name] = account_num
                except:
                    pass
                    
                in_multiline = False
                current_row = []
    
    return account_data


def update_all_clients():
    """Update all clients with their account numbers"""
    
    # First, let's parse the CSV properly
    account_data = parse_csv_properly()
    
    print(f"Found {len(account_data)} clients with account numbers in CSV")
    
    with Session(engine) as session:
        # Get all clients
        all_clients = session.exec(select(Client)).all()
        print(f"Found {len(all_clients)} clients in database")
        
        updated_count = 0
        created_refs = 0
        
        # Try to match each client
        for client in all_clients:
            client_name = client.name.strip()
            
            # Try exact match first
            account_number = None
            if client_name in account_data:
                account_number = account_data[client_name]
            else:
                # Try partial matches
                for csv_name, csv_account in account_data.items():
                    # Check if names are similar
                    if (client_name.lower() in csv_name.lower() or 
                        csv_name.lower() in client_name.lower() or
                        client_name.replace(' ', '').lower() == csv_name.replace(' ', '').lower()):
                        account_number = csv_account
                        break
            
            if account_number:
                # Update client notes
                if "Account Number:" not in (client.notes or ""):
                    old_notes = client.notes or ""
                    # Remove any existing payment method or other info from notes
                    if "Payment Method:" in old_notes or "Cash on Gate" in old_notes or "ON HOLD" in old_notes:
                        client.notes = f"Account Number: {account_number}. {old_notes}"
                    else:
                        client.notes = f"Account Number: {account_number}" + (f". {old_notes}" if old_notes else "")
                    
                    print(f"Updated {client.name} with Account Number: {account_number}")
                    updated_count += 1
                
                # Create reference if it doesn't exist
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
                    created_refs += 1
            else:
                print(f"WARNING: No account number found for: {client.name}")
        
        session.commit()
        
        print(f"\nUpdated {updated_count} clients with account numbers")
        print(f"Created {created_refs} new references")
        
        # Verify final state
        clients_with_numbers = session.exec(
            select(Client).where(Client.notes.contains("Account Number:"))
        ).all()
        
        print(f"\nFinal state: {len(clients_with_numbers)} clients have account numbers")


if __name__ == "__main__":
    print("Importing ALL account numbers from CSV...")
    create_db_and_tables()
    update_all_clients()