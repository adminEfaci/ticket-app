#!/usr/bin/env python3
"""
Reset test user password
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlmodel import Session, select
from backend.core.database import engine
from backend.models.user import User
from backend.core.auth import get_password_hash

def reset_test_password():
    """Reset test user password to a known value"""
    
    with Session(engine) as session:
        # Find test user
        user = session.exec(select(User).where(User.email == "test@example.com")).first()
        if user:
            # Set password to "testpassword123"
            user.hashed_password = get_password_hash("testpassword123")
            user.failed_login_attempts = 0
            user.locked_until = None
            session.add(user)
            session.commit()
            print(f"Password reset for {user.email}")
        else:
            print("Test user not found")

if __name__ == "__main__":
    reset_test_password()