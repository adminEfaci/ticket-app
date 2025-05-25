#!/usr/bin/env python
import sys
sys.path.append('.')

from backend.core.database import engine
from sqlmodel import Session
from backend.models.client import Client, ClientReference, ClientRate
from sqlmodel import select
from backend.models.user import User, UserRole
from backend.utils.datetime_utils import utcnow_naive
from uuid import uuid4

def create_test_data():
    """Create test clients and references"""
    with Session(engine) as session:
        # Get admin user
        admin = session.exec(
            select(User).where(User.email == "admin@example.com")
        ).first()
        
        if not admin:
            print("Admin user not found. Please create admin first.")
            return
        
        # Create test clients
        clients_data = [
            {
                "name": "ABC Construction Ltd",
                "email": "billing@abcconstruction.com",
                "reference_patterns": ["ABC-*", "ABC Construction*"],
                "rate": 25.00
            },
            {
                "name": "XYZ Demolition Inc",
                "email": "accounts@xyzdemolition.com",
                "reference_patterns": ["XYZ-*", "XYZ Demo*"],
                "rate": 30.00
            },
            {
                "name": "Test Company",
                "email": "billing@testcompany.com",
                "reference_patterns": ["TEST-*", "Test Co*"],
                "rate": 28.50
            }
        ]
        
        for client_data in clients_data:
            # Check if client exists
            existing = session.exec(
                select(Client).where(Client.name == client_data["name"])
            ).first()
            
            if existing:
                print(f"Client {client_data['name']} already exists")
                continue
            
            # Create client
            client = Client(
                id=uuid4(),
                name=client_data["name"],
                billing_email=client_data["email"],
                billing_contact_name="Test Contact",
                active=True,
                notes="Test client for demo",
                created_at=utcnow_naive(),
                updated_at=utcnow_naive(),
                created_by=admin.id
            )
            session.add(client)
            session.commit()
            session.refresh(client)
            
            # Create reference patterns
            for pattern in client_data["reference_patterns"]:
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
                rate_per_tonne=client_data["rate"],
                effective_from=utcnow_naive(),
                approved_by=admin.id,
                approved_at=utcnow_naive(),
                created_at=utcnow_naive()
            )
            session.add(rate)
            
            session.commit()
            print(f"Created client: {client_data['name']} with rate ${client_data['rate']}/tonne")
        
        print("\nTest data created successfully!")
        print("You can now upload XLS files with references matching these patterns:")
        print("- ABC-*, ABC Construction*")
        print("- XYZ-*, XYZ Demo*")
        print("- TEST-*, Test Co*")

if __name__ == "__main__":
    create_test_data()