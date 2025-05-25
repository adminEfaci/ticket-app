#!/usr/bin/env python3
"""Import complete client data from CSV with all fields"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import csv
import re
from sqlmodel import Session, select
from backend.core.database import engine, create_db_and_tables
from backend.models.client import Client, ClientReference, ClientRate
from uuid import uuid4
from datetime import date
from backend.utils.datetime_utils import utcnow_naive


def parse_price(price_str):
    """Extract numeric price from string like '$120.00'"""
    if not price_str:
        return None
    # Remove $ and commas, extract number
    price_str = price_str.replace('$', '').replace(',', '').strip()
    try:
        return float(price_str)
    except:
        return None


def clean_string(s):
    """Clean up string values"""
    if not s:
        return None
    s = str(s).strip()
    return s if s else None


def import_all_client_data():
    """Import all client data from CSV"""
    
    csv_path = "/app/samples/Clients-all.csv"
    
    # Complete client data from your list
    complete_data = [
        {"name": "Cash Sales", "number": "1", "price": 76.00, "contact": "Billing", "email": "toppsenvironmental@gmail.com", "email2": "info@toppsenv.com"},
        {"name": "The Renovator", "number": "2", "price": 120.00, "contact": "Dave Lee", "email": "dave@therenovator.org", "payment": "CCOR"},
        {"name": "Stanley Sanitation", "number": "3", "price": 110.00, "contact": "Nick Stanley", "email": "stanleysanitation@gmail.com", "note": "ON HOLD"},
        {"name": "Thomas Cavanagh Construction Limited", "number": "4", "price": 110.00, "contact": "Anita Lavergne", "email": "ap@thomascavanagh.ca", "email2": "alavergne@thomascavanagh.ca", "payment": "CHEQUE"},
        {"name": "Lachapelle Antiques", "number": "5", "price": 120.00, "contact": "Gilbert Lachapelle", "email": "thelachapelles85@gmail.com"},
        {"name": "Patten Homes", "number": "7", "price": 110.00, "contact": "Cherry", "email": "ap@pattenhomes.com", "email2": "jgerszke@pattenhomes.com", "payment": "CHEQUE"},
        {"name": "P.A. Langevin Transport", "number": "8", "price": 110.00, "contact": "Francie", "email": "francie@palangevintransport.ca"},
        {"name": "Sunrise Roofing", "number": "9", "price": 120.00, "email": "info@sunriseroofing.ca", "email2": "sunriseroofing@sympatico.ca"},
        {"name": "Jim Miles Guide Service", "number": "10", "price": 120.00, "contact": "James Miles", "email": "jimmilesguideservice@gmail.com"},
        {"name": "Keyuk, Jeff", "number": "11", "price": 120.00, "contact": "Jeff Keyuk", "email": "jeffkeyuk@gmail.com"},
        {"name": "Freda, Jack", "number": "12", "price": 120.00, "email": "Jklonstruction@hotmail.com"},
        {"name": "CN Aquatics", "number": "13", "price": 125.00, "contact": "Chris Neirinck", "email": "Cnaquatics@gmail.com"},
        {"name": "Eagle Comm Solutions", "number": "14", "price": 125.00, "contact": "Jamie Lang", "email": "jlang@eaglecommsolutions.com"},
        {"name": "McNeely, Scott", "number": "15", "price": 125.00, "contact": "Scott", "email": "Mcneelycontracting@gmail.com"},
        {"name": "1-800-GOT-JUNK", "number": "16", "price": 120.00, "contact": "Luc Raymond", "email": "luc.raymond@1800gotjunk.com"},
        {"name": "March Road Motorsports 1872025 Ontario Inc", "number": "17", "price": 130.00, "email": "info@funcomesalive.ca"},
        {"name": "Chaysen Trash Bins", "number": "18", "price": 120.00, "contact": "Courtney", "email": "taylorroofing@gmail.com"},
        {"name": "Sparton Inc.", "number": "19", "price": 120.00, "contact": "Neil Sparrow", "email": "spartonlandscaping@gmail.com"},
        {"name": "Mr. Dumpster", "number": "20", "price": 120.00, "contact": "Danny Benson", "email": "info@mrdumpster.ca", "payment": "CCOR"},
        {"name": "12284685 Canada Inc.", "number": "21", "price": 125.00, "contact": "MK Landworks", "email": "info@mklandworks.ca"},
        {"name": "Higher Ground Ottawa", "number": "22", "price": 125.00, "email": "chris@highergroundottawa.com"},
        {"name": "Meunier, Rene", "number": "23", "price": 125.00, "email": "Renemeurier@hotmail.com"},
        {"name": "Gord Scott Construction", "number": "24", "price": 120.00, "contact": "Gord Scott", "email": "gscottawa@gmail.com"},
        # Add more entries as needed...
    ]
    
    # Try to read and parse the CSV file for complete data
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            csv_data = []
            for row in reader:
                try:
                    account_num = clean_string(row.get('Account Number', ''))
                    if account_num and account_num.isdigit():
                        csv_data.append({
                            "name": clean_string(row.get('Account Name', '') or row.get('Name', '')),
                            "number": account_num,
                            "price": parse_price(row.get('Price', '')),
                            "contact": clean_string(row.get('Contact Person', '')),
                            "email": clean_string(row.get('Email', '')),
                            "email2": clean_string(row.get('Email 2', '')),
                            "phone": clean_string(row.get('Phone Number', '')),
                            "phone2": clean_string(row.get('Phone Number 2', '')),
                            "payment": clean_string(row.get('Payment Method', ''))
                        })
                except:
                    continue
            
            if csv_data:
                complete_data = csv_data
                print(f"Successfully parsed {len(csv_data)} entries from CSV")
    except Exception as e:
        print(f"Could not parse CSV, using hardcoded data: {e}")
    
    with Session(engine) as session:
        # Get all existing clients
        all_clients = session.exec(select(Client)).all()
        client_map = {c.name.strip().lower(): c for c in all_clients}
        
        updated_count = 0
        created_rates = 0
        created_refs = 0
        
        for data in complete_data:
            client_name = data['name']
            if not client_name:
                continue
                
            # Find matching client
            client = None
            name_lower = client_name.lower().strip()
            
            # Try exact match
            if name_lower in client_map:
                client = client_map[name_lower]
            else:
                # Try partial matches
                for existing_name, existing_client in client_map.items():
                    if (name_lower in existing_name or existing_name in name_lower or
                        name_lower.replace(' ', '') == existing_name.replace(' ', '') or
                        name_lower.replace(',', '') == existing_name.replace(',', '')):
                        client = existing_client
                        break
            
            if client:
                # Build comprehensive notes
                notes_parts = []
                
                # Always add account number first
                notes_parts.append(f"Account Number: {data['number']}")
                
                # Add payment method if exists
                if data.get('payment'):
                    notes_parts.append(f"Payment Method: {data['payment']}")
                
                # Add second email if exists
                if data.get('email2'):
                    notes_parts.append(f"Secondary Email: {data['email2']}")
                
                # Add second phone if exists  
                if data.get('phone2'):
                    notes_parts.append(f"Secondary Phone: {data['phone2']}")
                
                # Add any existing note
                if data.get('note'):
                    notes_parts.append(data['note'])
                
                # Update client
                client.notes = ". ".join(notes_parts)
                
                # Update contact info if missing
                if data.get('contact') and not client.billing_contact_name:
                    client.billing_contact_name = data['contact']
                
                if data.get('email') and not client.billing_email:
                    client.billing_email = data['email']
                    
                if data.get('phone') and not client.billing_phone:
                    client.billing_phone = data['phone']
                
                # Ensure 10 days credit terms
                client.credit_terms_days = 10
                
                updated_count += 1
                print(f"Updated {client.name} - Account #{data['number']}")
                
                # Create or update rate
                if data.get('price'):
                    existing_rate = session.exec(
                        select(ClientRate).where(
                            ClientRate.client_id == client.id
                        )
                    ).first()
                    
                    if not existing_rate:
                        rate = ClientRate(
                            id=uuid4(),
                            client_id=client.id,
                            rate_per_tonne=data['price'],
                            effective_from=date(2025, 1, 1),
                            created_at=utcnow_naive()
                        )
                        session.add(rate)
                        created_rates += 1
                    elif existing_rate.rate_per_tonne != data['price']:
                        existing_rate.rate_per_tonne = data['price']
                
                # Create reference for account number
                existing_ref = session.exec(
                    select(ClientReference).where(
                        ClientReference.client_id == client.id,
                        ClientReference.pattern == data['number']
                    )
                ).first()
                
                if not existing_ref:
                    reference = ClientReference(
                        id=uuid4(),
                        client_id=client.id,
                        pattern=data['number'],
                        is_regex=False,
                        is_fuzzy=False,
                        priority=10,
                        active=True,
                        description=f"Account number {data['number']}"
                    )
                    session.add(reference)
                    created_refs += 1
            else:
                print(f"WARNING: Could not find client: {client_name}")
        
        session.commit()
        
        print(f"\nSummary:")
        print(f"Updated {updated_count} clients with complete data")
        print(f"Created {created_rates} new rates")
        print(f"Created {created_refs} new references")
        
        # Final verification
        clients_with_numbers = session.exec(
            select(Client).where(Client.notes.contains("Account Number:"))
        ).all()
        
        print(f"\nFinal state: {len(clients_with_numbers)} clients have account numbers")
        
        # Show sample of updated data
        print("\nSample of updated clients:")
        sample_clients = session.exec(
            select(Client).where(Client.notes.contains("Account Number:")).limit(5)
        ).all()
        
        for client in sample_clients:
            print(f"- {client.name}: {client.notes}")


if __name__ == "__main__":
    print("Importing complete client data...")
    create_db_and_tables()
    import_all_client_data()