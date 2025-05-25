import re
import unicodedata
from sqlmodel import Session, select, update
from backend.core.database import engine
from backend.models.client import Client

def deep_clean_string(s):
    if not s:
        return s
    
    # First, normalize unicode
    s = unicodedata.normalize('NFKD', s)
    
    # Remove all control characters and non-printable characters
    # Keep only printable ASCII and common unicode
    cleaned = ''.join(char for char in s if ord(char) >= 32 and ord(char) < 127 or ord(char) > 160)
    
    # Remove any remaining problematic characters
    cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)
    
    # Trim whitespace
    cleaned = cleaned.strip()
    
    # For emails, do additional cleaning
    if '@' in cleaned:
        # Remove quotes and apostrophes
        cleaned = cleaned.replace("'", '').replace('"', '')
        # Replace & with 'and'
        cleaned = cleaned.replace('&', 'and')
        # Replace commas with dots
        cleaned = cleaned.replace(',', '.')
        # Remove spaces
        cleaned = cleaned.replace(' ', '')
        # Convert to lowercase
        cleaned = cleaned.lower()
    
    return cleaned

print("Starting deep clean of client data...")

with Session(engine) as session:
    clients = session.exec(select(Client)).all()
    total_fixed = 0
    
    for client in clients:
        updates = {}
        
        # Check each field
        fields_to_clean = {
            'name': client.name,
            'billing_email': client.billing_email,
            'billing_contact_name': client.billing_contact_name,
            'billing_phone': client.billing_phone,
            'notes': client.notes
        }
        
        for field_name, field_value in fields_to_clean.items():
            if field_value:
                cleaned = deep_clean_string(field_value)
                if cleaned != field_value:
                    print(f"Cleaning {field_name} for {client.name}:")
                    print(f"  OLD: {repr(field_value)}")
                    print(f"  NEW: {repr(cleaned)}")
                    setattr(client, field_name, cleaned)
                    updates[field_name] = cleaned
        
        if updates:
            session.add(client)
            total_fixed += 1
    
    session.commit()
    print(f"\nFixed {total_fixed} clients")
    
    # Verify all clients can be loaded
    print("\nVerifying all clients can be loaded...")
    try:
        all_clients = session.exec(select(Client)).all()
        print(f"✓ Successfully loaded all {len(all_clients)} clients")
        
        # Try to access each client's data
        for i, client in enumerate(all_clients):
            try:
                # Access all fields to ensure they're readable
                _ = (client.id, client.name, client.billing_email, 
                     client.billing_contact_name, client.billing_phone,
                     client.active, client.notes)
            except Exception as e:
                print(f"✗ Error with client {i}: {e}")
                print(f"  Name: {repr(client.name)}")
                print(f"  Email: {repr(client.billing_email)}")
                
    except Exception as e:
        print(f"✗ Error loading clients: {e}")