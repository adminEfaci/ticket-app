import pytest
import tempfile
import shutil
from pathlib import Path
from uuid import uuid4
from unittest.mock import Mock, AsyncMock
from fastapi import UploadFile
from backend.services.storage_service import StorageService

class TestStorageService:
    
    def setup_method(self):
        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.storage_service = StorageService(self.temp_dir)
        self.test_batch_id = uuid4()
    
    def teardown_method(self):
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_init_creates_base_directory(self):
        """Test that StorageService creates the base directory"""
        new_temp_dir = tempfile.mkdtemp()
        shutil.rmtree(new_temp_dir)  # Remove it first
        
        # Create service - should recreate directory
        StorageService(new_temp_dir)
        assert Path(new_temp_dir).exists()
        
        # Clean up
        shutil.rmtree(new_temp_dir, ignore_errors=True)
    
    def test_get_batch_directory(self):
        """Test getting batch directory path"""
        batch_dir = self.storage_service.get_batch_directory(self.test_batch_id)
        expected_path = Path(self.temp_dir) / str(self.test_batch_id)
        assert batch_dir == expected_path
    
    def test_create_batch_directory(self):
        """Test creating batch directory"""
        batch_dir = self.storage_service.create_batch_directory(self.test_batch_id)
        
        assert batch_dir.exists()
        assert batch_dir.is_dir()
        assert batch_dir.name == str(self.test_batch_id)
    
    @pytest.mark.asyncio
    async def test_save_file(self):
        """Test saving an uploaded file"""
        # Create mock upload file
        test_content = b"Test file content"
        mock_file = Mock(spec=UploadFile)
        mock_file.read = AsyncMock(side_effect=[test_content, b""])  # Second call returns empty
        mock_file.seek = AsyncMock()
        
        # Save file
        file_path = await self.storage_service.save_file(self.test_batch_id, mock_file, "test.txt")
        
        # Verify file was saved
        assert file_path.exists()
        assert file_path.read_bytes() == test_content
        assert file_path.name == "test.txt"
        
        # Verify seek was called to reset file pointer
        mock_file.seek.assert_called_with(0)
    
    @pytest.mark.asyncio
    async def test_save_file_content(self):
        """Test saving file content directly"""
        test_content = b"Direct content save"
        
        file_path = await self.storage_service.save_file_content(
            self.test_batch_id, 
            test_content, 
            "direct.txt"
        )
        
        assert file_path.exists()
        assert file_path.read_bytes() == test_content
        assert file_path.name == "direct.txt"
    
    def test_file_exists(self):
        """Test checking if file exists"""
        # File doesn't exist initially
        assert not self.storage_service.file_exists(self.test_batch_id, "nonexistent.txt")
        
        # Create file
        batch_dir = self.storage_service.create_batch_directory(self.test_batch_id)
        test_file = batch_dir / "exists.txt"
        test_file.write_text("test")
        
        # Now it should exist
        assert self.storage_service.file_exists(self.test_batch_id, "exists.txt")
    
    def test_get_file_path(self):
        """Test getting file path"""
        file_path = self.storage_service.get_file_path(self.test_batch_id, "test.txt")
        expected_path = Path(self.temp_dir) / str(self.test_batch_id) / "test.txt"
        assert file_path == expected_path
    
    def test_get_file_size(self):
        """Test getting file size"""
        # Non-existent file
        assert self.storage_service.get_file_size(self.test_batch_id, "nonexistent.txt") == 0
        
        # Create file with known content
        batch_dir = self.storage_service.create_batch_directory(self.test_batch_id)
        test_file = batch_dir / "sized.txt"
        test_content = "12345"
        test_file.write_text(test_content)
        
        assert self.storage_service.get_file_size(self.test_batch_id, "sized.txt") == len(test_content)
    
    def test_delete_file(self):
        """Test deleting a specific file"""
        # Create file
        batch_dir = self.storage_service.create_batch_directory(self.test_batch_id)
        test_file = batch_dir / "to_delete.txt"
        test_file.write_text("delete me")
        
        assert test_file.exists()
        
        # Delete file
        success = self.storage_service.delete_file(self.test_batch_id, "to_delete.txt")
        
        assert success
        assert not test_file.exists()
    
    def test_delete_file_nonexistent(self):
        """Test deleting non-existent file returns success"""
        success = self.storage_service.delete_file(self.test_batch_id, "nonexistent.txt")
        assert success  # Should return True even if file doesn't exist
    
    def test_delete_batch_directory(self):
        """Test deleting entire batch directory"""
        # Create batch with files
        batch_dir = self.storage_service.create_batch_directory(self.test_batch_id)
        (batch_dir / "file1.txt").write_text("content1")
        (batch_dir / "file2.txt").write_text("content2")
        
        assert batch_dir.exists()
        assert len(list(batch_dir.iterdir())) == 2
        
        # Delete batch directory
        success = self.storage_service.delete_batch_directory(self.test_batch_id)
        
        assert success
        assert not batch_dir.exists()
    
    def test_delete_batch_directory_nonexistent(self):
        """Test deleting non-existent batch directory returns success"""
        success = self.storage_service.delete_batch_directory(self.test_batch_id)
        assert success  # Should return True even if directory doesn't exist
    
    def test_list_batch_files(self):
        """Test listing files in batch directory"""
        # Empty directory
        files = self.storage_service.list_batch_files(self.test_batch_id)
        assert files == []
        
        # Create batch with files
        batch_dir = self.storage_service.create_batch_directory(self.test_batch_id)
        (batch_dir / "file1.txt").write_text("content1")
        (batch_dir / "file2.txt").write_text("content2")
        (batch_dir / "subdir").mkdir()  # Should be ignored
        
        files = self.storage_service.list_batch_files(self.test_batch_id)
        
        assert len(files) == 2
        assert "file1.txt" in files
        assert "file2.txt" in files
        assert "subdir" not in files  # Directories should be excluded
    
    def test_get_batch_stats(self):
        """Test getting batch statistics"""
        # Non-existent batch
        stats = self.storage_service.get_batch_stats(self.test_batch_id)
        assert stats["total_files"] == 0
        assert stats["total_size"] == 0
        
        # Create batch with files
        batch_dir = self.storage_service.create_batch_directory(self.test_batch_id)
        file1 = batch_dir / "file1.txt"
        file2 = batch_dir / "file2.txt"
        
        file1.write_text("12345")  # 5 bytes
        file2.write_text("1234567890")  # 10 bytes
        
        stats = self.storage_service.get_batch_stats(self.test_batch_id)
        
        assert stats["total_files"] == 2
        assert stats["total_size"] == 15  # 5 + 10 bytes
        assert len(stats["files"]) == 2
        
        # Check individual file stats
        file_stats = {f["name"]: f["size"] for f in stats["files"]}
        assert file_stats["file1.txt"] == 5
        assert file_stats["file2.txt"] == 10