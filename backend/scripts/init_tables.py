#!/usr/bin/env python3
"""
Initialize database tables
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlmodel import SQLModel
from backend.core.database import engine

# Import all models to ensure they're registered
from backend.models.user import User
from backend.models.client import Client, ClientReference  
from backend.models.batch import ProcessingBatch
from backend.models.ticket import Ticket
from backend.models.ticket_image import TicketImage
from backend.models.match_result import MatchResult
from backend.models.session import Session as UserSession
from backend.models.audit_log import AuditLog
from backend.models.export import ExportAuditLog

def create_tables():
    """Create all tables"""
    print("Creating tables...")
    SQLModel.metadata.create_all(engine)
    print("Tables created successfully!")

if __name__ == "__main__":
    create_tables()