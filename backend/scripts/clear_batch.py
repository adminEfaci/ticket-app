#!/usr/bin/env python3
"""
Script to clear specific batches from the database
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlmodel import Session, select
from backend.core.database import engine
from backend.models.batch import ProcessingBatch
from datetime import datetime

def clear_batches_by_hash(hash_prefix: str = None):
    """Clear batches by hash prefix or all batches"""
    with Session(engine) as session:
        if hash_prefix:
            statement = select(ProcessingBatch).where(
                ProcessingBatch.file_hash.startswith(hash_prefix)
            )
            batches = session.exec(statement).all()
            print(f"Found {len(batches)} batches with hash prefix '{hash_prefix}'")
        else:
            statement = select(ProcessingBatch)
            batches = session.exec(statement).all()
            print(f"Found {len(batches)} total batches")
        
        if batches:
            for batch in batches:
                print(f"Deleting batch {batch.id}: {batch.xls_filename} + {batch.pdf_filename}")
                print(f"  Hash: {batch.file_hash[:16] if batch.file_hash else 'None'}...")
                print(f"  Created: {batch.uploaded_at}")
                session.delete(batch)
            
            session.commit()
            print(f"\nDeleted {len(batches)} batches")
        else:
            print("No batches found")

def list_batches():
    """List all batches"""
    with Session(engine) as session:
        statement = select(ProcessingBatch).order_by(ProcessingBatch.uploaded_at.desc())
        batches = session.exec(statement).all()
        
        if batches:
            print(f"Found {len(batches)} batches:\n")
            for batch in batches:
                print(f"ID: {batch.id}")
                print(f"  Files: {batch.xls_filename} + {batch.pdf_filename}")
                print(f"  Hash: {batch.file_hash[:16] if batch.file_hash else 'None'}...")
                print(f"  Status: {batch.status}")
                print(f"  Created: {batch.uploaded_at}")
                print()
        else:
            print("No batches found")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Manage processing batches")
    parser.add_argument("--list", action="store_true", help="List all batches")
    parser.add_argument("--clear-hash", help="Clear batches with specific hash prefix")
    parser.add_argument("--clear-all", action="store_true", help="Clear all batches")
    
    args = parser.parse_args()
    
    if args.list:
        list_batches()
    elif args.clear_hash:
        clear_batches_by_hash(args.clear_hash)
    elif args.clear_all:
        response = input("Are you sure you want to delete ALL batches? (yes/no): ")
        if response.lower() == "yes":
            clear_batches_by_hash()
        else:
            print("Cancelled")
    else:
        parser.print_help()