#!/usr/bin/env python
import sys
sys.path.append('.')

import csv
from backend.core.database import engine
from sqlmodel import Session, select
from backend.models.client import Client, ClientReference, ClientRate
from backend.models.user import User
from backend.utils.datetime_utils import utcnow_naive
from uuid import uuid4
import re

def clean_price(price_str):
    """Extract numeric value from price string"""
    if not price_str:
        return 76.0  # Default rate
    # Remove $ and extract number
    clean = re.findall(r'[\d.]+', price_str)
    if clean:
        return float(clean[0])
    return 76.0

def import_clients_from_csv():
    """Import clients from CSV file"""
    with Session(engine) as session:
        # Get admin user
        admin = session.exec(
            select(User).where(User.email == "admin@example.com")
        ).first()
        
        if not admin:
            print("Admin user not found. Please create admin first.")
            return
        
        # Read CSV file
        with open('samples/Clients-all.csv', 'r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            
            count = 0
            for row in reader:
                # Skip empty rows
                if not row.get('Account Name') or not row['Account Name'].strip():
                    continue
                
                client_name = row['Account Name'].strip()
                
                # Check if client already exists
                existing = session.exec(
                    select(Client).where(Client.name == client_name)
                ).first()
                
                if existing:
                    print(f"Client {client_name} already exists, skipping...")
                    continue
                
                # Extract data
                account_number = row.get('Account Number', '').strip()
                price = clean_price(row.get('Price', '$76.00'))
                contact_person = row.get('Contact Person', '').strip() or "Billing Department"
                email = row.get('Email', '').strip()
                email2 = row.get('Email 2', '').strip()
                phone = row.get('Phone Number', '').strip()
                notes = []
                
                if row.get('NOTE1'):
                    notes.append(row['NOTE1'])
                if row.get('NOTE'):
                    notes.append(row['NOTE'])
                if row.get('INFO'):
                    notes.append(row['INFO'])
                if row.get('Payment Method'):
                    notes.append(f"Payment Method: {row['Payment Method']}")
                
                # Use first available email
                billing_email = email or email2 or f"billing@{client_name.lower().replace(' ', '')}.com"
                
                # Create client
                client = Client(
                    id=uuid4(),
                    name=client_name,
                    billing_email=billing_email,
                    billing_contact_name=contact_person,
                    billing_phone=phone,
                    active=True,
                    notes="; ".join(notes) if notes else f"Account Number: {account_number}",
                    created_at=utcnow_naive(),
                    updated_at=utcnow_naive(),
                    created_by=admin.id
                )
                session.add(client)
                session.commit()
                session.refresh(client)
                
                # Create reference patterns based on client name
                patterns = []
                
                # Add exact match pattern
                patterns.append(client_name)
                
                # Add variations without trailing spaces or special chars
                clean_name = client_name.rstrip(' ')
                if clean_name != client_name:
                    patterns.append(clean_name)
                
                # Add pattern for initials or short forms
                words = clean_name.split()
                if len(words) > 1:
                    # First word pattern
                    patterns.append(f"{words[0]}*")
                    # Initials pattern
                    initials = ''.join(w[0] for w in words if w)
                    if len(initials) > 1:
                        patterns.append(f"{initials}*")
                
                # Add account number as pattern if available
                if account_number:
                    patterns.append(f"*{account_number}*")
                
                # Create unique reference patterns
                unique_patterns = list(set(patterns))
                for pattern in unique_patterns:
                    ref = ClientReference(
                        id=uuid4(),
                        client_id=client.id,
                        pattern=pattern,
                        active=True,
                        created_at=utcnow_naive(),
                        created_by=admin.id
                    )
                    session.add(ref)
                
                # Create rate
                rate = ClientRate(
                    id=uuid4(),
                    client_id=client.id,
                    rate_per_tonne=price,
                    effective_from=utcnow_naive(),
                    approved_by=admin.id,
                    approved_at=utcnow_naive(),
                    created_at=utcnow_naive()
                )
                session.add(rate)
                
                session.commit()
                count += 1
                print(f"Created client: {client_name} with rate ${price}/tonne")
                print(f"  Reference patterns: {', '.join(unique_patterns)}")
        
        print(f"\nSuccessfully imported {count} clients from CSV!")
        print("\nYou can now:")
        print("1. Login at http://localhost:3000/login")
        print("2. Upload XLS files at http://localhost:3000/upload")
        print("3. Manage clients at http://localhost:3000/admin/clients")

if __name__ == "__main__":
    import_clients_from_csv()