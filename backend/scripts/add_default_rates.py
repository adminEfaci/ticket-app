#!/usr/bin/env python3
"""
Add default rates for existing clients
"""

import sys
from pathlib import Path
from datetime import date, datetime
import asyncio

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlmodel import Session, select
from backend.core.database import engine
from backend.models.client import Client, ClientRate
from backend.models.user import User
from backend.utils.datetime_utils import utcnow_naive

async def add_default_rates():
    """Add default rates for all active clients"""
    
    with Session(engine) as session:
        # Get admin user
        admin_user = session.exec(select(User).where(User.role == "admin")).first()
        if not admin_user:
            print("No admin user found")
            return
            
        # Get all active clients
        clients = session.exec(select(Client).where(Client.active == True)).all()
        print(f"Found {len(clients)} active clients")
        
        rates_added = 0
        
        for client in clients:
            # Check if client already has a rate
            existing_rate = session.exec(
                select(ClientRate).where(
                    ClientRate.client_id == client.id,
                    ClientRate.effective_from <= date.today(),
                    ClientRate.approved_by != None  # Rate is approved if approved_by is set
                ).order_by(ClientRate.effective_from.desc())
            ).first()
            
            if existing_rate:
                print(f"Client {client.name} already has rate: ${existing_rate.rate_per_tonne}/tonne")
                continue
                
            # Add default rate
            rate = ClientRate(
                client_id=client.id,
                rate_per_tonne=25.00,  # Default $25/tonne
                effective_from=date(2025, 1, 1),  # Effective from Jan 1, 2025
                approved_by=admin_user.id,
                approved_at=utcnow_naive()
            )
            
            session.add(rate)
            rates_added += 1
            print(f"Added rate for {client.name}: $25.00/tonne")
        
        session.commit()
        print(f"\nAdded {rates_added} new rates")
        
        # Show all rates
        print("\nCurrent rates:")
        all_rates = session.exec(
            select(ClientRate).where(ClientRate.approved_by != None)
        ).all()
        
        for rate in all_rates:
            client = session.get(Client, rate.client_id)
            if client:
                print(f"  {client.name}: ${rate.rate_per_tonne}/tonne (from {rate.effective_from})")

if __name__ == "__main__":
    asyncio.run(add_default_rates())