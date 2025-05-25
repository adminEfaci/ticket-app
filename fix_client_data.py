import re
from sqlmodel import Session, select
from backend.core.database import engine
from backend.models.client import Client

def clean_string(s):
    if not s:
        return s
    # Remove control characters
    s = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s)
    # Fix common email issues
    if '@' in s:
        # Remove apostrophes from emails
        s = s.replace("'", '')
        # Replace & with 'and'
        s = s.replace('&', 'and')
    return s

with Session(engine) as session:
    clients = session.exec(select(Client)).all()
    fixed_count = 0
    
    for client in clients:
        changed = False
        
        # Clean all string fields
        if client.billing_email:
            new_email = clean_string(client.billing_email)
            if new_email != client.billing_email:
                print(f'Fixing email for {client.name}: {client.billing_email} -> {new_email}')
                client.billing_email = new_email
                changed = True
                
        if client.name:
            new_name = clean_string(client.name)
            if new_name != client.name:
                print(f'Fixing name: {repr(client.name)} -> {repr(new_name)}')
                client.name = new_name
                changed = True
                
        if client.billing_contact_name:
            new_contact = clean_string(client.billing_contact_name)
            if new_contact != client.billing_contact_name:
                print(f'Fixing contact for {client.name}: {repr(client.billing_contact_name)} -> {repr(new_contact)}')
                client.billing_contact_name = new_contact
                changed = True
                
        if client.notes:
            new_notes = clean_string(client.notes)
            if new_notes != client.notes:
                print(f'Fixing notes for {client.name}')
                client.notes = new_notes
                changed = True
                
        if changed:
            session.add(client)
            fixed_count += 1
    
    session.commit()
    print(f'\nFixed {fixed_count} clients with data issues')
    
    # Now test that all clients can be serialized
    print("\nTesting serialization...")
    try:
        all_clients = session.exec(select(Client)).all()
        print(f"Total clients in database: {len(all_clients)}")
    except Exception as e:
        print(f"Error: {e}")