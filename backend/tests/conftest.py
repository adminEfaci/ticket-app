"""Shared test fixtures and configuration"""
import pytest
import os
from typing import Generator
from sqlmodel import Session, SQLModel, create_engine
from fastapi.testclient import TestClient

# Set test database URL
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", 
    "postgresql://ticketapp:password@localhost:5432/ticketapp_test"
)


@pytest.fixture(scope="session")
def engine():
    """Create test database engine"""
    # Always use PostgreSQL for tests
    engine = create_engine(TEST_DATABASE_URL)
    
    # Import all models to ensure they're registered
    from backend.models import rebuild_models
    rebuild_models()
    
    # Create all tables
    SQLModel.metadata.create_all(engine)
    
    yield engine
    
    # Drop all tables after tests
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def session(engine) -> Generator[Session, None, None]:
    """Create a new database session for each test"""
    with Session(engine) as session:
        yield session
        session.rollback()


@pytest.fixture(scope="function")
def client(session: Session) -> Generator[TestClient, None, None]:
    """Create a test client with database session override"""
    from main import app
    from backend.core.database import get_session
    
    def get_session_override():
        return session
    
    app.dependency_overrides[get_session] = get_session_override
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(session: Session):
    """Create an admin user for testing"""
    from backend.models.user import User, UserRole
    from backend.services.auth_service import get_password_hash
    
    user = User(
        username="admin",
        email="admin@test.com",
        full_name="Admin User",
        hashed_password=get_password_hash("adminpass123"),
        role=UserRole.ADMIN,
        is_active=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def admin_headers(client: TestClient, admin_user):
    """Get auth headers for admin user"""
    response = client.post(
        "/api/auth/login",
        data={
            "username": "admin",
            "password": "adminpass123"
        }
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}