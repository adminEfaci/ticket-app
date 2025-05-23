from datetime import timedelta
from backend.core.auth import (
    verify_password, 
    get_password_hash, 
    create_access_token, 
    verify_token, 
    validate_password_strength
)

class TestPasswordHashing:
    def test_password_hashing(self):
        password = "TestPassword123!"
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert verify_password(password, hashed) is True
        assert verify_password("wrong_password", hashed) is False

    def test_password_strength_validation(self):
        assert validate_password_strength("short") is False
        assert validate_password_strength("alllowercase123!") is False
        assert validate_password_strength("ALLUPPERCASE123!") is False
        assert validate_password_strength("NoNumbers!") is False
        assert validate_password_strength("NoSpecialChars123") is False
        assert validate_password_strength("ValidPassword123!") is True
        assert validate_password_strength("AnotherValid1@") is True

class TestTokenGeneration:
    def test_token_generation(self):
        data = {"sub": "test_user", "role": "admin"}
        token = create_access_token(data)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_verification(self):
        data = {"sub": "test_user", "role": "admin"}
        token = create_access_token(data)
        
        payload = verify_token(token)
        
        assert payload is not None
        assert payload["sub"] == "test_user"
        assert payload["role"] == "admin"
        assert "exp" in payload

    def test_invalid_token_verification(self):
        invalid_token = "invalid.token.here"
        payload = verify_token(invalid_token)
        
        assert payload is None

    def test_token_expiry(self):
        data = {"sub": "test_user"}
        expires_delta = timedelta(seconds=-1)
        expired_token = create_access_token(data, expires_delta)
        
        payload = verify_token(expired_token)
        assert payload is None