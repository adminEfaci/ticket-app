#!/usr/bin/env python
import sys
sys.path.append('.')

from backend.core.database import engine
from sqlmodel import Session
from backend.models.user import User, UserRole
from backend.services.auth_service import get_password_hash
from backend.utils.datetime_utils import utcnow_naive

def create_test_admin():
    """Create a test admin user"""
    with Session(engine) as session:
        # Check if admin exists
        existing = session.query(User).filter(User.email == "admin@example.com").first()
        if existing:
            print("Admin user already exists")
            return
        
        # Create admin user
        admin = User(
            email="admin@example.com",
            first_name="Admin",
            last_name="User",
            hashed_password=get_password_hash("admin123456"),
            role=UserRole.ADMIN,
            is_active=True,
            created_at=utcnow_naive(),
            updated_at=utcnow_naive()
        )
        
        session.add(admin)
        session.commit()
        
        print("Admin user created successfully!")
        print("Email: admin@example.com")
        print("Password: admin123456")
        print("\nYou can now login at: http://localhost:3000/login")

if __name__ == "__main__":
    create_test_admin()