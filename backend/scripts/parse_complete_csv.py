#!/usr/bin/env python3
"""Parse the complete CSV and update ALL clients with ALL data"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pandas as pd
from sqlmodel import Session, select
from backend.core.database import engine, create_db_and_tables
from backend.models.client import Client, ClientReference, ClientRate
from uuid import uuid4
from datetime import date
from backend.utils.datetime_utils import utcnow_naive


def import_from_csv():
    """Import all client data using pandas for better CSV handling"""
    
    csv_path = "/app/samples/Clients-all.csv"
    
    # Read CSV with pandas for better handling
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    
    # Clean column names
    df.columns = df.columns.str.strip()
    
    print(f"Found {len(df)} rows in CSV")
    print(f"Columns: {df.columns.tolist()}")
    
    with Session(engine) as session:
        # Get all existing clients
        all_clients = session.exec(select(Client)).all()
        print(f"Found {len(all_clients)} clients in database")
        
        # Create lookup maps
        client_by_name = {}
        for client in all_clients:
            # Multiple keys for matching
            name_clean = client.name.strip().lower()
            client_by_name[name_clean] = client
            # Also try without commas
            client_by_name[name_clean.replace(',', '')] = client
            # And without spaces
            client_by_name[name_clean.replace(' ', '')] = client
        
        updated_count = 0
        not_found = []
        
        for idx, row in df.iterrows():
            account_name = str(row.get('Account Name', '')).strip()
            account_number = str(row.get('Account Number', '')).strip()
            
            if not account_name or not account_number:
                continue
                
            # Skip non-numeric account numbers
            if not account_number.isdigit():
                continue
            
            # Find matching client
            client = None
            name_lower = account_name.lower().strip()
            
            # Try various matching strategies
            if name_lower in client_by_name:
                client = client_by_name[name_lower]
            elif name_lower.replace(',', '') in client_by_name:
                client = client_by_name[name_lower.replace(',', '')]
            elif name_lower.replace(' ', '') in client_by_name:
                client = client_by_name[name_lower.replace(' ', '')]
            else:
                # Try partial matches
                for key, c in client_by_name.items():
                    if name_lower in key or key in name_lower:
                        client = c
                        break
            
            if client:
                # Build comprehensive notes
                notes_parts = []
                notes_parts.append(f"Account Number: {account_number}")
                
                # Payment method
                payment = str(row.get('Payment Method', '')).strip()
                if payment and payment not in ['nan', '']:
                    notes_parts.append(f"Payment Method: {payment}")
                
                # Secondary email
                email2 = str(row.get('Email 2', '')).strip()
                if email2 and email2 not in ['nan', '']:
                    notes_parts.append(f"Secondary Email: {email2}")
                
                # Phone numbers
                phone2 = str(row.get('Phone Number 2', '')).strip()
                if phone2 and phone2 not in ['nan', '']:
                    notes_parts.append(f"Secondary Phone: {phone2}")
                    
                phone3 = str(row.get('Phone Number 3', '')).strip()
                if phone3 and phone3 not in ['nan', '']:
                    notes_parts.append(f"Third Phone: {phone3}")
                
                # Other notes
                note1 = str(row.get('NOTE1', '')).strip()
                if note1 and note1 not in ['nan', '']:
                    notes_parts.append(note1)
                    
                note2 = str(row.get('NOTE', '')).strip()
                if note2 and note2 not in ['nan', '']:
                    notes_parts.append(note2)
                
                # Update client
                client.notes = ". ".join(notes_parts)
                
                # Update primary contact info if provided and missing
                contact = str(row.get('Contact Person', '')).strip()
                if contact and contact not in ['nan', ''] and not client.billing_contact_name:
                    client.billing_contact_name = contact
                
                email = str(row.get('Email', '')).strip()
                if email and email not in ['nan', ''] and not client.billing_email:
                    client.billing_email = email
                    
                phone = str(row.get('Phone Number', '')).strip()
                if phone and phone not in ['nan', ''] and not client.billing_phone:
                    client.billing_phone = phone
                
                # Set credit terms to 10 days
                client.credit_terms_days = 10
                
                # Handle price/rate
                price_str = str(row.get('Price', '')).strip()
                if price_str and price_str not in ['nan', '']:
                    price_str = price_str.replace('$', '').replace(',', '')
                    try:
                        price = float(price_str)
                        
                        # Check if rate exists
                        existing_rate = session.exec(
                            select(ClientRate).where(ClientRate.client_id == client.id)
                        ).first()
                        
                        if not existing_rate:
                            rate = ClientRate(
                                id=uuid4(),
                                client_id=client.id,
                                rate_per_tonne=price,
                                effective_from=date(2025, 1, 1),
                                created_at=utcnow_naive()
                            )
                            session.add(rate)
                        else:
                            existing_rate.rate_per_tonne = price
                    except:
                        pass
                
                # Create reference for account number
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
                
                updated_count += 1
                print(f"✓ Updated {client.name} - Account #{account_number}")
            else:
                not_found.append(f"{account_name} (#{account_number})")
        
        session.commit()
        
        print(f"\n=== SUMMARY ===")
        print(f"Successfully updated: {updated_count} clients")
        print(f"Not found in database: {len(not_found)} entries")
        
        if not_found:
            print("\nClients not found in database:")
            for nf in not_found[:10]:  # Show first 10
                print(f"  - {nf}")
            if len(not_found) > 10:
                print(f"  ... and {len(not_found) - 10} more")
        
        # Final verification
        clients_with_numbers = session.exec(
            select(Client).where(Client.notes.contains("Account Number:"))
        ).all()
        
        print(f"\nFinal state: {len(clients_with_numbers)}/{len(all_clients)} clients have account numbers")
        
        # Count by number range
        ranges = {"1-50": 0, "51-100": 0, "101-200": 0, "201-300": 0, "301+": 0}
        for client in clients_with_numbers:
            import re
            match = re.search(r'Account Number: (\d+)', client.notes)
            if match:
                num = int(match.group(1))
                if num <= 50:
                    ranges["1-50"] += 1
                elif num <= 100:
                    ranges["51-100"] += 1
                elif num <= 200:
                    ranges["101-200"] += 1
                elif num <= 300:
                    ranges["201-300"] += 1
                else:
                    ranges["301+"] += 1
        
        print("\nAccount number distribution:")
        for range_name, count in ranges.items():
            print(f"  {range_name}: {count} clients")


if __name__ == "__main__":
    print("Parsing complete CSV file...")
    create_db_and_tables()
    import_from_csv()