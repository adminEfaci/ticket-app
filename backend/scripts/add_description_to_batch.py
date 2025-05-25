#!/usr/bin/env python3
"""
Add description field to ProcessingBatch table
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from backend.core.database import engine

def add_description_column():
    """Add description column to processingbatch table if it doesn't exist"""
    with engine.connect() as conn:
        # Check if column exists
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='processingbatch' AND column_name='description'
        """))
        
        if result.fetchone() is None:
            # Add the column
            conn.execute(text("""
                ALTER TABLE processingbatch 
                ADD COLUMN description VARCHAR(255)
            """))
            conn.commit()
            print("Added description column to processingbatch table")
        else:
            print("Description column already exists")

if __name__ == "__main__":
    add_description_column()