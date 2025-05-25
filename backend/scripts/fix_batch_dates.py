#!/usr/bin/env python3
"""
Fix batch upload dates to match the actual data dates
"""

import sys
from pathlib import Path
from datetime import datetime
from uuid import UUID

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlmodel import Session, select
from backend.core.database import engine
from backend.models.batch import ProcessingBatch

def fix_batch_dates():
    """Update batch dates to match their content"""
    
    batch_dates = {
        "8743c8ef-49af-400e-8668-9d7c596fe222": datetime(2025, 4, 14, 10, 0, 0),  # APRIL_14_2025
        "2d818905-3d6d-4f13-83a4-6b601aad5fda": datetime(2025, 4, 15, 10, 0, 0),  # APRIL_15_2025
        "f2d08c61-c8bf-4831-a7a4-2ffbcefcc61b": datetime(2025, 4, 14, 10, 0, 0),  # APRIL_14_2025
        "06be5733-bfc2-43a2-90b7-51f0cdd66e26": datetime(2025, 4, 15, 10, 0, 0)   # APRIL_15_2025
    }
    
    with Session(engine) as session:
        for batch_id_str, new_date in batch_dates.items():
            batch_id = UUID(batch_id_str)
            batch = session.get(ProcessingBatch, batch_id)
            if batch:
                print(f"Updating batch {batch_id}: {batch.uploaded_at} -> {new_date}")
                batch.uploaded_at = new_date
                session.add(batch)
            else:
                print(f"Batch {batch_id} not found")
        
        session.commit()
        print("Batch dates updated successfully")

if __name__ == "__main__":
    fix_batch_dates()