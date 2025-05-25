#!/usr/bin/env python3
"""Create admin user with predefined credentials"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlmodel import Session, select
from backend.core.database import engine, create_db_and_tables
from backend.models.user import User, UserRole
from backend.core.auth import get_password_hash


def create_admin_user():
    """Create admin user with default credentials"""
    with Session(engine) as session:
        # Check if admin already exists
        stmt = select(User).where(User.email == "admin@example.com")
        existing_user = session.exec(stmt).first()
        
        if existing_user:
            print("Admin user already exists")
            # Update password in case it's different
            existing_user.hashed_password = get_password_hash("admin123")
            existing_user.is_active = True
            session.add(existing_user)
            session.commit()
            print("Admin password updated")
            return True
        
        # Create new admin user
        admin_user = User(
            email="admin@example.com",
            username="admin",
            hashed_password=get_password_hash("admin123"),
            first_name="Admin",
            last_name="User",
            role=UserRole.ADMIN,
            is_active=True
        )
        
        session.add(admin_user)
        session.commit()
        
        print(f"Admin user created successfully!")
        print(f"Email: admin@example.com")
        print(f"Password: admin123")
        return True


if __name__ == "__main__":
    print("Initializing database...")
    create_db_and_tables()
    
    if create_admin_user():
        print("\nAdmin user is ready!")
    else:
        print("\nFailed to create admin user")
        sys.exit(1)