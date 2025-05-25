#!/usr/bin/env python3
"""
Update batch records to include PDF filenames
"""

import sys
from pathlib import Path
from uuid import UUID

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlmodel import Session, select
from backend.core.database import engine
from backend.models.batch import ProcessingBatch

def update_batch_pdfs():
    """Update batch records with PDF filenames"""
    
    batch_pdfs = {
        "8743c8ef-49af-400e-8668-9d7c596fe222": "APRIL_14_2025.pdf",
        "2d818905-3d6d-4f13-83a4-6b601aad5fda": "APRIL_15_2025.pdf"
    }
    
    with Session(engine) as session:
        for batch_id_str, pdf_filename in batch_pdfs.items():
            batch_id = UUID(batch_id_str)
            batch = session.get(ProcessingBatch, batch_id)
            if batch:
                print(f"Updating batch {batch_id}: adding PDF {pdf_filename}")
                batch.pdf_filename = pdf_filename
                session.add(batch)
            else:
                print(f"Batch {batch_id} not found")
        
        session.commit()
        print("Batch PDF filenames updated successfully")

if __name__ == "__main__":
    update_batch_pdfs()