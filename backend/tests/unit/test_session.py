from datetime import timedelta
from backend.utils.datetime_utils import utcnow_naive
from uuid import uuid4
from backend.models.session import Session, SessionCreate

class TestSessionModel:
    def test_session_expiry_check(self):
        user_id = uuid4()
        
        active_session = Session(
            user_id=user_id,
            ip_address="127.0.0.1",
            user_agent="test-agent",
            token_hash="test-hash",
            expires_at=utcnow_naive() + timedelta(hours=1)
        )
        
        expired_session = Session(
            user_id=user_id,
            ip_address="127.0.0.1",
            user_agent="test-agent",
            token_hash="test-hash",
            expires_at=utcnow_naive() - timedelta(hours=1)
        )
        
        assert active_session.is_expired() is False
        assert expired_session.is_expired() is True

    def test_session_creation(self):
        user_id = uuid4()
        session_data = SessionCreate(
            user_id=user_id,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0 Test",
            token_hash="abcd1234"
        )
        
        assert session_data.user_id == user_id
        assert session_data.ip_address == "192.168.1.1"
        assert session_data.user_agent == "Mozilla/5.0 Test"
        assert session_data.token_hash == "abcd1234"

    def test_session_default_expiry(self):
        user_id = uuid4()
        session = Session(
            user_id=user_id,
            ip_address="127.0.0.1",
            user_agent="test-agent",
            token_hash="test-hash"
        )
        
        expected_expiry = utcnow_naive() + timedelta(hours=8)
        time_diff = abs((session.expires_at - expected_expiry).total_seconds())
        
        assert time_diff < 60