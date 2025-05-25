#!/usr/bin/env python3
"""
Extract images from PDFs for existing batches
"""

import sys
from pathlib import Path
from uuid import UUID
import asyncio

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlmodel import Session, select
from backend.core.database import engine
from backend.models.batch import ProcessingBatch
from backend.models.ticket import Ticket
from backend.models.user import User
from backend.services.pdf_extraction_service import PDFExtractionService
from backend.services.ticket_image_matcher import TicketImageMatcher
from backend.services.storage_service import StorageService

async def extract_images_for_batch(batch_id: str):
    """Extract images from PDF for a specific batch"""
    
    with Session(engine) as session:
        # Get batch
        batch = session.get(ProcessingBatch, UUID(batch_id))
        if not batch:
            print(f"Batch {batch_id} not found")
            return
            
        print(f"\nProcessing batch {batch_id} - {batch.xls_filename}")
        
        # Get admin user
        admin_user = session.exec(select(User).where(User.role == "admin")).first()
        if not admin_user:
            print("No admin user found")
            return
            
        # Initialize services
        storage_service = StorageService("/data/batches")
        extraction_service = PDFExtractionService(storage_service)
        matcher_service = TicketImageMatcher(session, storage_service)
        
        # Get PDF path
        pdf_path = storage_service.get_file_path(batch.id, "original.pdf")
        if not Path(pdf_path).exists():
            print(f"PDF file not found: {pdf_path}")
            return
            
        print(f"Extracting images from {pdf_path}")
        
        # Extract images
        result = await extraction_service.extract_images_from_pdf(
            batch_id=batch.id,
            pdf_path=pdf_path,
            user_id=admin_user.id
        )
        
        print(f"Extraction result: {result}")
        
        if result["success"]:
            print(f"Successfully extracted {result['images_extracted']} images")
            
            # Get tickets for this batch
            tickets = session.exec(
                select(Ticket).where(Ticket.batch_id == batch.id)
            ).all()
            
            print(f"Found {len(tickets)} tickets to match")
            
            # Run matching
            match_result = await matcher_service.match_batch_images(
                batch_id=batch.id,
                tickets=tickets,
                user_id=admin_user.id
            )
            
            print(f"Matching result: Success={match_result['success']}, Stats={match_result['statistics']}")
            
        else:
            print(f"Extraction failed: {result.get('error', 'Unknown error')}")

async def main():
    """Extract images for all batches with PDFs"""
    
    batch_ids = [
        "8743c8ef-49af-400e-8668-9d7c596fe222",  # APRIL_14_2025
        "2d818905-3d6d-4f13-83a4-6b601aad5fda"   # APRIL_15_2025
    ]
    
    for batch_id in batch_ids:
        try:
            await extract_images_for_batch(batch_id)
        except Exception as e:
            print(f"Error processing batch {batch_id}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\nImage extraction complete!")

if __name__ == "__main__":
    asyncio.run(main())