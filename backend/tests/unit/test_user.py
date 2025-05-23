import pytest
from unittest.mock import Mock
from uuid import uuid4
from backend.models.user import User, UserCreate, UserRole
from backend.services.user_service import UserService

class TestUserService:
    @pytest.fixture
    def mock_db(self):
        return Mock()
    
    @pytest.fixture
    def user_service(self, mock_db):
        return UserService(mock_db)
    
    @pytest.fixture
    def sample_user(self):
        return User(
            id=uuid4(),
            email="test@example.com",
            first_name="Test",
            last_name="User",
            role=UserRole.CLIENT,
            hashed_password="hashed_password",
            is_active=True
        )

    def test_get_user_by_id_as_admin(self, user_service, mock_db, sample_user):
        mock_db.exec.return_value.first.return_value = sample_user
        
        result = user_service.get_user_by_id(
            user_id=sample_user.id,
            requester_role="admin",
            requester_id=uuid4()
        )
        
        assert result == sample_user

    def test_get_user_by_id_as_client_own_data(self, user_service, mock_db, sample_user):
        mock_db.exec.return_value.first.return_value = sample_user
        
        result = user_service.get_user_by_id(
            user_id=sample_user.id,
            requester_role="client",
            requester_id=sample_user.id
        )
        
        assert result == sample_user

    def test_get_user_by_id_as_client_others_data(self, user_service, mock_db, sample_user):
        result = user_service.get_user_by_id(
            user_id=sample_user.id,
            requester_role="client",
            requester_id=uuid4()
        )
        
        assert result is None

    def test_get_users_as_client(self, user_service, mock_db):
        result = user_service.get_users(requester_role="client")
        
        assert result == []

    def test_get_users_as_processor(self, user_service, mock_db):
        mock_db.exec.return_value.all.return_value = []
        
        result = user_service.get_users(requester_role="processor")
        
        mock_db.exec.assert_called_once()
        assert result == []

class TestUserModel:
    def test_user_create_validation(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            UserCreate(
                email="test@example.com",
                first_name="Test",
                last_name="User",
                password="short"
            )

    def test_user_create_password_complexity(self):
        with pytest.raises(ValueError, match="Password must contain uppercase, lowercase, digit, and special character"):
            UserCreate(
                email="test@example.com",
                first_name="Test",
                last_name="User",
                password="alllowercase"
            )

    def test_valid_user_create(self):
        user_data = UserCreate(
            email="test@example.com",
            first_name="Test",
            last_name="User",
            password="ValidPassword123!"
        )
        
        assert user_data.email == "test@example.com"
        assert user_data.first_name == "Test"
        assert user_data.last_name == "User"
        assert user_data.role == UserRole.CLIENT