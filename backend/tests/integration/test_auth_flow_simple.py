import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from backend.core.database import get_session
from backend.models.user import User, UserRole
from backend.core.auth import get_password_hash
import uuid

# Create a simple app without the complex middleware for testing
from fastapi import FastAPI
from backend.routers import auth_router

test_app = FastAPI()
test_app.include_router(auth_router.router)

@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", 
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    test_app.dependency_overrides[get_session] = get_session_override
    client = TestClient(test_app)
    yield client
    test_app.dependency_overrides.clear()

@pytest.fixture
def admin_user(session: Session):
    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        first_name="Admin",
        last_name="User",
        role=UserRole.ADMIN,
        hashed_password=get_password_hash("AdminPassword123!"),
        is_active=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

class TestAuthenticationFlow:
    def test_successful_login(self, client: TestClient, admin_user: User):
        login_data = {
            "email": "admin@example.com",
            "password": "AdminPassword123!"
        }
        
        response = client.post("/auth/login", json=login_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert "token_type" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["email"] == "admin@example.com"

    def test_invalid_login_credentials(self, client: TestClient, admin_user: User):
        login_data = {
            "email": "admin@example.com",
            "password": "WrongPassword123!"
        }
        
        response = client.post("/auth/login", json=login_data)
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client: TestClient):
        login_data = {
            "email": "nonexistent@example.com",
            "password": "Password123!"
        }
        
        response = client.post("/auth/login", json=login_data)
        assert response.status_code == 401

    def test_protected_endpoint_without_token(self, client: TestClient):
        response = client.get("/auth/me")
        assert response.status_code in [401, 403]  # Either is acceptable for no token

    def test_protected_endpoint_with_token(self, client: TestClient, admin_user: User):
        login_data = {
            "email": "admin@example.com",
            "password": "AdminPassword123!"
        }
        
        login_response = client.post("/auth/login", json=login_data)
        token = login_response.json()["access_token"]
        
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/auth/me", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@example.com"
        assert data["role"] == "admin"