import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
import io
from uuid import UUID, uuid4

from main import app
from backend.models.batch import ProcessingBatch, BatchStatus
from backend.models.user import UserRole


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def temp_storage_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_xls_content():
    # Minimal XLS file content (BOM + minimal structure)
    return b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' + b'\x00' * 500


@pytest.fixture
def sample_pdf_content():
    # Minimal PDF file content
    return b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000074 00000 n \n0000000120 00000 n \ntrailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n178\n%%EOF'


@pytest.fixture
def mock_user():
    return {
        "user_id": "test_user_123",
        "role": "user",
        "email": "test@example.com"
    }


class TestUploadIntegrationSimple:
    
    @pytest.mark.asyncio
    async def test_upload_endpoint_unauthorized(self, client):
        """Test upload endpoint returns 403 for unauthorized requests"""
        
        response = client.post("/upload/pairs", files=[])
        
        # Should return 403 (Forbidden) for missing auth
        assert response.status_code == 403
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_upload_endpoint_authentication_required(
        self, 
        client
    ):
        """Test upload endpoint requires authentication"""
        
        # Test without any authorization - should get 403 immediately
        response = client.post("/upload/pairs", files=[])
        assert response.status_code == 403
        
        # This confirms authentication is properly enforced
        # More detailed auth testing requires full Docker environment

    @pytest.mark.asyncio 
    async def test_batches_endpoint_unauthorized(self, client):
        """Test batches endpoint returns 403 for unauthorized requests"""
        
        response = client.get("/upload/batches")
        
        # Should return 403 (Forbidden) for missing auth
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_stats_endpoint_unauthorized(self, client):
        """Test stats endpoint returns 403 for unauthorized requests"""
        
        response = client.get("/upload/stats")
        
        # Should return 403 (Forbidden) for missing auth
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_file_validation_flow(
        self, 
        sample_xls_content, 
        sample_pdf_content
    ):
        """Test file validation logic separately"""
        
        from backend.services.validation_service import ValidationService
        
        validation_service = ValidationService()
        
        # Test XLS validation
        with tempfile.NamedTemporaryFile(suffix='.xls', delete=False) as xls_file:
            xls_file.write(sample_xls_content)
            xls_file.flush()
            
            # Test file extension validation
            assert validation_service.validate_xls_extension("test.xls") == True
            assert validation_service.validate_xls_extension("test.xlsx") == False
            assert validation_service.validate_xls_extension("test.txt") == False
            
            # Test file size validation (should pass for small test file)
            file_size = os.path.getsize(xls_file.name)
            assert validation_service.validate_file_size(file_size) == True
            
            # Clean up
            os.unlink(xls_file.name)
        
        # Test PDF validation
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as pdf_file:
            pdf_file.write(sample_pdf_content)
            pdf_file.flush()
            
            # Test file extension validation
            assert validation_service.validate_pdf_extension("test.pdf") == True
            assert validation_service.validate_pdf_extension("test.txt") == False
            
            # Test file size validation (should pass for small test file)
            file_size = os.path.getsize(pdf_file.name)
            assert validation_service.validate_file_size(file_size) == True
            
            # Clean up
            os.unlink(pdf_file.name)

    @pytest.mark.asyncio
    async def test_storage_service_integration(self, temp_storage_dir):
        """Test storage service operations"""
        
        from backend.services.storage_service import StorageService
        
        storage_service = StorageService(str(temp_storage_dir))
        
        # Test batch directory creation
        batch_id = uuid4()
        batch_dir = storage_service.create_batch_directory(batch_id)
        
        assert batch_dir.exists()
        assert batch_dir.name == str(batch_id)
        
        # Test file operations
        test_content = b"test file content"
        test_file = batch_dir / "test.txt"
        
        # Write file
        with open(test_file, 'wb') as f:
            f.write(test_content)
        
        # Verify file exists
        assert test_file.exists()
        
        # Test directory cleanup
        storage_service.delete_batch_directory(batch_id)
        assert not batch_dir.exists()

    @pytest.mark.asyncio
    async def test_hash_utils_integration(self, temp_storage_dir):
        """Test hash utility functions"""
        
        from backend.utils.hash_utils import calculate_file_hash, calculate_combined_hash
        
        # Create test files
        xls_file = temp_storage_dir / "test.xls"
        pdf_file = temp_storage_dir / "test.pdf"
        
        xls_content = b"test xls content"
        pdf_content = b"test pdf content"
        
        with open(xls_file, 'wb') as f:
            f.write(xls_content)
        
        with open(pdf_file, 'wb') as f:
            f.write(pdf_content)
        
        # Test individual file hashing (async)
        xls_hash = await calculate_file_hash(xls_file)
        pdf_hash = await calculate_file_hash(pdf_file)
        
        assert len(xls_hash) == 64  # SHA256 hex string length
        assert len(pdf_hash) == 64
        assert xls_hash != pdf_hash
        
        # Test combined hashing (sync)
        combined_hash = calculate_combined_hash(xls_file, pdf_file)
        assert len(combined_hash) == 64
        
        # Hash should be deterministic
        combined_hash2 = calculate_combined_hash(xls_file, pdf_file)
        assert combined_hash == combined_hash2

    @pytest.mark.asyncio
    async def test_batch_model_validation(self):
        """Test batch model creation and validation"""
        
        from backend.models.batch import ProcessingBatch, BatchStatus
        
        # Test valid batch creation
        batch = ProcessingBatch(
            created_by=uuid4(),
            status=BatchStatus.PENDING,
            xls_filename="test.xls",
            pdf_filename="test.pdf",
            file_hash="test_hash_123"
        )
        
        assert batch.status == BatchStatus.PENDING
        assert batch.xls_filename == "test.xls"
        assert batch.pdf_filename == "test.pdf"
        
        # Test status transitions
        batch.status = BatchStatus.VALIDATING
        assert batch.status == BatchStatus.VALIDATING
        
        batch.status = BatchStatus.READY
        assert batch.status == BatchStatus.READY

    @pytest.mark.asyncio
    async def test_filename_pairing_logic(self):
        """Test filename pairing validation"""
        
        from backend.services.validation_service import ValidationService
        
        validation_service = ValidationService()
        
        # Test matching filenames
        assert validation_service.validate_filename_pair_match("document1.xls", "document1.pdf") == True
        assert validation_service.validate_filename_pair_match("Document1.XLS", "document1.PDF") == True
        
        # Test non-matching filenames
        assert validation_service.validate_filename_pair_match("document1.xls", "document2.pdf") == False
        
        # Test similarity threshold
        similarity = validation_service.calculate_filename_similarity("document1.xls", "document1.pdf")
        assert similarity >= 0.9  # Should be very similar
        
        similarity = validation_service.calculate_filename_similarity("document1.xls", "different.pdf")
        assert similarity < 0.9  # Should be dissimilar

    @pytest.mark.asyncio
    async def test_user_role_validation(self):
        """Test user role enum validation"""
        
        from backend.models.user import UserRole
        
        # Test valid roles
        assert UserRole.CLIENT == "client"
        assert UserRole.PROCESSOR == "processor"
        assert UserRole.MANAGER == "manager"
        assert UserRole.ADMIN == "admin"
        
        # Test role creation from string
        role = UserRole("client")
        assert role == UserRole.CLIENT