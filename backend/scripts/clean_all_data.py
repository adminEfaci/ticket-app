#!/usr/bin/env python3
"""
Script to clean all batch and ticket data
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlmodel import Session, select
from backend.core.database import engine
from backend.models.batch import ProcessingBatch
from backend.models.ticket import Ticket
from backend.models.ticket_image import TicketImage
import shutil

def clean_all_data():
    """Clean all batch, ticket, and related data"""
    with Session(engine) as session:
        # First, delete all ticket images
        ticket_images = session.exec(select(TicketImage)).all()
        for img in ticket_images:
            session.delete(img)
        print(f"Deleted {len(ticket_images)} ticket images")
        
        # Then delete all tickets
        tickets = session.exec(select(Ticket)).all()
        for ticket in tickets:
            session.delete(ticket)
        print(f"Deleted {len(tickets)} tickets")
        
        # Finally delete all batches
        batches = session.exec(select(ProcessingBatch)).all()
        for batch in batches:
            session.delete(batch)
        print(f"Deleted {len(batches)} batches")
        
        session.commit()
        
    # Clean up file storage
    upload_path = os.getenv("UPLOAD_PATH", "/data/batches")
    if os.path.exists(upload_path):
        # Remove all batch directories
        for item in os.listdir(upload_path):
            item_path = os.path.join(upload_path, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
                print(f"Removed directory: {item}")
    
    print("\nAll data cleaned successfully!")

if __name__ == "__main__":
    response = input("Are you sure you want to delete ALL batches, tickets, and files? (yes/no): ")
    if response.lower() == "yes":
        clean_all_data()
    else:
        print("Cancelled")