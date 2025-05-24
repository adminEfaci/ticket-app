import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import io
from uuid import uuid4

from main import app
from backend.models.batch import ProcessingBatch, BatchStatus


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def temp_storage_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_session():
    session = AsyncMock()
    return session


@pytest.fixture
def sample_xls_content():
    # Minimal XLS file content (BOM + minimal structure)
    return b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' + b'\x00' * 500


@pytest.fixture
def sample_pdf_content():
    # Minimal PDF file content
    return b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000074 00000 n \n0000000120 00000 n \ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n178\n%%EOF'


@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer test_token"}


class TestUploadIntegration:
    
    @pytest.mark.asyncio
    async def test_complete_upload_flow_success(
        self, 
        client, 
        temp_storage_dir, 
        mock_session,
        sample_xls_content, 
        sample_pdf_content,
        auth_headers
    ):
        """Test complete upload flow from file submission to batch creation"""
        
        # Mock dependencies
        with patch('backend.routers.upload_router.get_session', return_value=mock_session), \
             patch('backend.routers.upload_router.get_storage_service'), \
             patch('backend.routers.upload_router.get_validation_service'), \
             patch('backend.routers.upload_router.get_batch_service'), \
             patch('backend.routers.upload_router.get_upload_service'), \
             patch('backend.middleware.auth_middleware.authenticated_required'):
            
            # Setup mocks
            mock_storage = mock_storage_cls.return_value
            mock_validation = mock_validation_cls.return_value
            mock_batch = mock_batch_cls.return_value
            mock_audit = mock_audit_cls.return_value
            mock_auth = mock_auth_cls.return_value
            
            # Mock auth service
            mock_auth.get_current_user.return_value = {
                "user_id": "test_user",
                "role": "admin"
            }
            
            # Mock validation service
            mock_validation.validate_file_type.return_value = True
            mock_validation.validate_file_size.return_value = True
            mock_validation.validate_xls_content.return_value = True
            mock_validation.validate_pdf_content.return_value = True
            mock_validation.validate_filename_pairing.return_value = True
            
            # Mock storage service
            batch_id = uuid4()
            mock_storage.save_file.return_value = temp_storage_dir / str(batch_id) / "test.xls"
            
            # Mock batch service
            test_batch = ProcessingBatch(
                id=batch_id,
                user_id="test_user",
                file_count=2,
                status=BatchStatus.READY,
                combined_hash="test_hash",
                created_at="2023-01-01T00:00:00",
                updated_at="2023-01-01T00:00:00"
            )
            mock_batch.create_batch.return_value = test_batch
            mock_batch.check_duplicate_hash.return_value = False
            
            # Create test files
            xls_file = io.BytesIO(sample_xls_content)
            pdf_file = io.BytesIO(sample_pdf_content)
            
            files = [
                ("files", ("document1.xls", xls_file, "application/vnd.ms-excel")),
                ("files", ("document1.pdf", pdf_file, "application/pdf"))
            ]
            
            # Make upload request
            response = client.post(
                "/upload/pairs",
                files=files,
                headers=auth_headers
            )
            
            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert "batch_id" in data
            assert data["message"] == "Files uploaded and batch created successfully"
            assert data["file_count"] == 2
            
            # Verify service calls
            mock_auth.get_current_user.assert_called_once()
            assert mock_validation.validate_file_type.call_count == 2
            assert mock_validation.validate_file_size.call_count == 2
            assert mock_storage.save_file.call_count == 2
            mock_batch.create_batch.assert_called_once()
            mock_audit.log_upload_success.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_flow_validation_failure(
        self, 
        client, 
        sample_xls_content, 
        sample_pdf_content,
        auth_headers
    ):
        """Test upload flow with validation failure"""
        
        with patch('backend.routers.upload_router.get_session') as mock_get_session, \
             patch('backend.routers.upload_router.ValidationService') as mock_validation_cls, \
             patch('backend.routers.upload_router.AuthService') as mock_auth_cls, \
             patch('backend.routers.upload_router.AuditService') as mock_audit_cls:
            
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session
            
            mock_validation = mock_validation_cls.return_value
            mock_auth = mock_auth_cls.return_value
            mock_audit = mock_audit_cls.return_value
            
            # Mock auth service
            mock_auth.get_current_user.return_value = {
                "user_id": "test_user",
                "role": "admin"
            }
            
            # Mock validation failure
            mock_validation.validate_file_type.return_value = False
            
            # Create test files
            xls_file = io.BytesIO(sample_xls_content)
            pdf_file = io.BytesIO(sample_pdf_content)
            
            files = [
                ("files", ("document1.txt", xls_file, "text/plain")),
                ("files", ("document1.pdf", pdf_file, "application/pdf"))
            ]
            
            # Make upload request
            response = client.post(
                "/upload/pairs",
                files=files,
                headers=auth_headers
            )
            
            # Verify error response
            assert response.status_code == 400
            data = response.json()
            assert "error" in data
            
            # Verify audit logging
            mock_audit.log_upload_failure.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_flow_duplicate_hash(
        self, 
        client, 
        temp_storage_dir,
        sample_xls_content, 
        sample_pdf_content,
        auth_headers
    ):
        """Test upload flow with duplicate hash detection"""
        
        with patch('backend.routers.upload_router.get_session') as mock_get_session, \
             patch('backend.routers.upload_router.StorageService') as mock_storage_cls, \
             patch('backend.routers.upload_router.ValidationService') as mock_validation_cls, \
             patch('backend.routers.upload_router.BatchService') as mock_batch_cls, \
             patch('backend.routers.upload_router.AuthService') as mock_auth_cls, \
             patch('backend.routers.upload_router.AuditService'):
            
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session
            
            mock_storage = mock_storage_cls.return_value
            mock_validation = mock_validation_cls.return_value
            mock_batch = mock_batch_cls.return_value
            mock_auth = mock_auth_cls.return_value
            
            # Mock auth service
            mock_auth.get_current_user.return_value = {
                "user_id": "test_user",
                "role": "admin"
            }
            
            # Mock validation success
            mock_validation.validate_file_type.return_value = True
            mock_validation.validate_file_size.return_value = True
            mock_validation.validate_xls_content.return_value = True
            mock_validation.validate_pdf_content.return_value = True
            mock_validation.validate_filename_pairing.return_value = True
            
            # Mock storage service
            batch_id = uuid4()
            mock_storage.save_file.return_value = temp_storage_dir / str(batch_id) / "test.xls"
            
            # Mock duplicate hash detection
            mock_batch.check_duplicate_hash.return_value = True
            
            # Create test files
            xls_file = io.BytesIO(sample_xls_content)
            pdf_file = io.BytesIO(sample_pdf_content)
            
            files = [
                ("files", ("document1.xls", xls_file, "application/vnd.ms-excel")),
                ("files", ("document1.pdf", pdf_file, "application/pdf"))
            ]
            
            # Make upload request
            response = client.post(
                "/upload/pairs",
                files=files,
                headers=auth_headers
            )
            
            # Verify duplicate error response
            assert response.status_code == 409
            data = response.json()
            assert "duplicate" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_upload_flow_file_count_limits(
        self, 
        client,
        sample_xls_content, 
        sample_pdf_content,
        auth_headers
    ):
        """Test upload flow with file count validation"""
        
        with patch('backend.routers.upload_router.AuthService') as mock_auth_cls:
            
            mock_auth = mock_auth_cls.return_value
            
            # Mock auth service
            mock_auth.get_current_user.return_value = {
                "user_id": "test_user",
                "role": "admin"
            }
            
            # Test with no files
            response = client.post(
                "/upload/pairs",
                files=[],
                headers=auth_headers
            )
            assert response.status_code == 400
            assert "at least 2 files" in response.json()["detail"].lower()
            
            # Test with too many files (62 files = 31 pairs, exceeds 30 pair limit)
            files = []
            for i in range(62):
                file_type = "xls" if i % 2 == 0 else "pdf"
                content = sample_xls_content if file_type == "xls" else sample_pdf_content
                mime_type = "application/vnd.ms-excel" if file_type == "xls" else "application/pdf"
                
                files.append(
                    ("files", (f"document{i//2}.{file_type}", io.BytesIO(content), mime_type))
                )
            
            response = client.post(
                "/upload/pairs",
                files=files,
                headers=auth_headers
            )
            assert response.status_code == 400
            assert "maximum of 60 files" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_batches_integration(
        self, 
        client,
        auth_headers
    ):
        """Test get batches endpoint integration"""
        
        with patch('backend.routers.upload_router.get_session') as mock_get_session, \
             patch('backend.routers.upload_router.BatchService') as mock_batch_cls, \
             patch('backend.routers.upload_router.AuthService') as mock_auth_cls:
            
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session
            
            mock_batch = mock_batch_cls.return_value
            mock_auth = mock_auth_cls.return_value
            
            # Mock auth service
            mock_auth.get_current_user.return_value = {
                "user_id": "test_user",
                "role": "admin"
            }
            
            # Mock batch data
            test_batches = [
                ProcessingBatch(
                    id=uuid4(),
                    user_id="test_user",
                    file_count=2,
                    status=BatchStatus.READY,
                    combined_hash="hash1",
                    created_at="2023-01-01T00:00:00",
                    updated_at="2023-01-01T00:00:00"
                ),
                ProcessingBatch(
                    id=uuid4(),
                    user_id="test_user",
                    file_count=4,
                    status=BatchStatus.PENDING,
                    combined_hash="hash2",
                    created_at="2023-01-02T00:00:00",
                    updated_at="2023-01-02T00:00:00"
                )
            ]
            mock_batch.get_user_batches.return_value = test_batches
            
            # Make request
            response = client.get("/batches/", headers=auth_headers)
            
            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["file_count"] == 2
            assert data[1]["file_count"] == 4

    @pytest.mark.asyncio
    async def test_get_upload_stats_integration(
        self, 
        client,
        auth_headers
    ):
        """Test get upload stats endpoint integration"""
        
        with patch('backend.routers.upload_router.get_session') as mock_get_session, \
             patch('backend.routers.upload_router.BatchService') as mock_batch_cls, \
             patch('backend.routers.upload_router.AuthService') as mock_auth_cls:
            
            mock_session = AsyncMock()
            mock_get_session.return_value = mock_session
            
            mock_batch = mock_batch_cls.return_value
            mock_auth = mock_auth_cls.return_value
            
            # Mock auth service
            mock_auth.get_current_user.return_value = {
                "user_id": "test_user",
                "role": "admin"
            }
            
            # Mock stats data
            mock_batch.get_upload_stats.return_value = {
                "total_batches": 10,
                "total_files": 45,
                "batches_by_status": {
                    "ready": 7,
                    "pending": 2,
                    "error": 1
                },
                "recent_uploads": 3
            }
            
            # Make request
            response = client.get("/upload/stats", headers=auth_headers)
            
            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert data["total_batches"] == 10
            assert data["total_files"] == 45
            assert data["batches_by_status"]["ready"] == 7

    @pytest.mark.asyncio
    async def test_unauthorized_access(self, client):
        """Test unauthorized access to upload endpoints"""
        
        # Test upload without auth
        response = client.post("/upload/pairs", files=[])
        assert response.status_code == 401
        
        # Test get batches without auth
        response = client.get("/batches/")
        assert response.status_code == 401
        
        # Test get stats without auth
        response = client.get("/upload/stats")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_role_based_access_control(
        self, 
        client,
        sample_xls_content, 
        sample_pdf_content
    ):
        """Test role-based access control for upload operations"""
        
        with patch('backend.routers.upload_router.AuthService') as mock_auth_cls:
            
            mock_auth = mock_auth_cls.return_value
            
            # Test with user role (should be allowed)
            mock_auth.get_current_user.return_value = {
                "user_id": "test_user",
                "role": "user"
            }
            
            headers = {"Authorization": "Bearer user_token"}
            
            # Create test files
            xls_file = io.BytesIO(sample_xls_content)
            pdf_file = io.BytesIO(sample_pdf_content)
            
            files = [
                ("files", ("document1.xls", xls_file, "application/vnd.ms-excel")),
                ("files", ("document1.pdf", pdf_file, "application/pdf"))
            ]
            
            # Mock other services for successful flow
            with patch('backend.routers.upload_router.get_session'), \
                 patch('backend.routers.upload_router.ValidationService'), \
                 patch('backend.routers.upload_router.StorageService'), \
                 patch('backend.routers.upload_router.BatchService'), \
                 patch('backend.routers.upload_router.AuditService'):
                
                response = client.post(
                    "/upload/pairs",
                    files=files,
                    headers=headers
                )
                
                # Should not be blocked by role (users can upload)
                assert response.status_code != 403