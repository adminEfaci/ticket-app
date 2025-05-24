#!/usr/bin/env python3
"""
Script to create an admin user for the Ticket Management System
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from getpass import getpass
from sqlmodel import Session
from backend.core.database import engine
from backend.models.user import User, UserRole
from backend.services.user_service import UserService


def create_admin_user():
    """Create an admin user interactively"""
    print("=== Create Admin User ===")
    
    # Get user input
    username = input("Enter admin username: ").strip()
    if not username:
        print("Error: Username cannot be empty")
        return False
    
    email = input("Enter admin email: ").strip()
    if not email or '@' not in email:
        print("Error: Invalid email address")
        return False
    
    password = getpass("Enter admin password: ")
    if len(password) < 8:
        print("Error: Password must be at least 8 characters long")
        return False
    
    confirm_password = getpass("Confirm password: ")
    if password != confirm_password:
        print("Error: Passwords do not match")
        return False
    
    # Create user
    try:
        with Session(engine) as session:
            user_service = UserService(session)
            
            # Check if user already exists
            existing = user_service.get_user_by_username(username)
            if existing:
                print(f"Error: User '{username}' already exists")
                return False
            
            # Create admin user
            admin = User(
                username=username,
                email=email,
                role=UserRole.ADMIN,
                is_active=True
            )
            admin.set_password(password)
            
            session.add(admin)
            session.commit()
            
            print(f"\n✅ Admin user '{username}' created successfully!")
            print(f"   Email: {email}")
            print("   Role: ADMIN")
            print("   Active: Yes")
            print("\nYou can now login with these credentials.")
            return True
            
    except Exception as e:
        print(f"Error creating admin user: {e}")
        return False


if __name__ == "__main__":
    # Initialize database tables
    from backend.core.database import create_db_and_tables
    print("Initializing database...")
    create_db_and_tables()
    
    # Create admin user
    success = create_admin_user()
    sys.exit(0 if success else 1)