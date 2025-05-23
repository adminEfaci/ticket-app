import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from backend.core.database import get_session
from backend.models.user import User
from backend.core.auth import get_password_hash
from main import app
import uuid

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

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

@pytest.fixture
def admin_user(session: Session):
    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        first_name="Admin",
        last_name="User",
        role="admin",
        hashed_password=get_password_hash("AdminPassword123!"),
        is_active=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

@pytest.fixture
def client_user(session: Session):
    user = User(
        id=uuid.uuid4(),
        email="client@example.com",
        first_name="Client",
        last_name="User",
        role="client",
        hashed_password=get_password_hash("ClientPassword123!"),
        is_active=True
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

class TestAuthenticationFlow:
    def test_root_endpoint(self, client: TestClient):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data

    def test_health_check(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

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
        assert response.status_code == 403  # FastAPI returns 403 when no auth header provided

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

    def test_logout_flow(self, client: TestClient, admin_user: User):
        login_data = {
            "email": "admin@example.com",
            "password": "AdminPassword123!"
        }
        
        login_response = client.post("/auth/login", json=login_data)
        token = login_response.json()["access_token"]
        
        headers = {"Authorization": f"Bearer {token}"}
        logout_response = client.post("/auth/logout", headers=headers)
        
        assert logout_response.status_code == 200
        assert logout_response.json()["message"] == "Successfully logged out"
        
        response = client.get("/auth/me", headers=headers)
        assert response.status_code == 401

class TestUserManagement:
    def test_admin_can_create_user(self, client: TestClient, admin_user: User):
        login_data = {
            "email": "admin@example.com",
            "password": "AdminPassword123!"
        }
        
        login_response = client.post("/auth/login", json=login_data)
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        new_user_data = {
            "email": "newuser@example.com",
            "first_name": "New",
            "last_name": "User",
            "password": "NewPassword123!",
            "role": "client"
        }
        
        response = client.post("/users/", json=new_user_data, headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["role"] == "client"

    def test_client_cannot_access_users_list(self, client: TestClient, client_user: User):
        login_data = {
            "email": "client@example.com",
            "password": "ClientPassword123!"
        }
        
        login_response = client.post("/auth/login", json=login_data)
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.get("/users/", headers=headers)
        assert response.status_code == 403

    def test_client_can_access_own_data(self, client: TestClient, client_user: User):
        login_data = {
            "email": "client@example.com",
            "password": "ClientPassword123!"
        }
        
        login_response = client.post("/auth/login", json=login_data)
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        response = client.get(f"/users/{client_user.id}", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["email"] == "client@example.com"

class TestBusinessRules:
    def test_password_lockout_after_failed_attempts(self, client: TestClient, admin_user: User):
        login_data = {
            "email": "admin@example.com",
            "password": "WrongPassword123!"
        }
        
        for _ in range(5):
            response = client.post("/auth/login", json=login_data)
            assert response.status_code == 401
        
        correct_login_data = {
            "email": "admin@example.com",
            "password": "AdminPassword123!"
        }
        
        response = client.post("/auth/login", json=correct_login_data)
        assert response.status_code == 401

    def test_session_expiry_validation(self, client: TestClient, admin_user: User):
        login_data = {
            "email": "admin@example.com",
            "password": "AdminPassword123!"
        }
        
        login_response = client.post("/auth/login", json=login_data)
        token = login_response.json()["access_token"]
        
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post("/auth/validate-token", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True