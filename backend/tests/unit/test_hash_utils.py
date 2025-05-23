import pytest
import tempfile
import hashlib
from pathlib import Path
from backend.utils.hash_utils import (
    calculate_file_hash,
    calculate_file_hash_sync,
    calculate_combined_hash,
    calculate_content_hash
)

class TestHashUtils:
    
    def setup_method(self):
        self.temp_dir = Path(tempfile.mkdtemp())
    
    def teardown_method(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_calculate_file_hash_async(self):
        """Test async file hash calculation"""
        test_content = b"Test content for hashing"
        test_file = self.temp_dir / "test.txt"
        test_file.write_bytes(test_content)
        
        result_hash = await calculate_file_hash(test_file)
        expected_hash = hashlib.sha256(test_content).hexdigest()
        
        assert result_hash == expected_hash
        assert len(result_hash) == 64  # SHA256 is 64 hex characters
    
    def test_calculate_file_hash_sync(self):
        """Test synchronous file hash calculation"""
        test_content = b"Test content for sync hashing"
        test_file = self.temp_dir / "test_sync.txt"
        test_file.write_bytes(test_content)
        
        result_hash = calculate_file_hash_sync(test_file)
        expected_hash = hashlib.sha256(test_content).hexdigest()
        
        assert result_hash == expected_hash
        assert len(result_hash) == 64
    
    @pytest.mark.asyncio
    async def test_calculate_file_hash_large_file(self):
        """Test hash calculation with large file (tests chunking)"""
        # Create a file larger than 8KB chunk size
        test_content = b"A" * 10000  # 10KB
        test_file = self.temp_dir / "large.txt"
        test_file.write_bytes(test_content)
        
        result_hash = await calculate_file_hash(test_file)
        expected_hash = hashlib.sha256(test_content).hexdigest()
        
        assert result_hash == expected_hash
    
    def test_calculate_file_hash_sync_large_file(self):
        """Test sync hash calculation with large file"""
        test_content = b"B" * 20000  # 20KB
        test_file = self.temp_dir / "large_sync.txt"
        test_file.write_bytes(test_content)
        
        result_hash = calculate_file_hash_sync(test_file)
        expected_hash = hashlib.sha256(test_content).hexdigest()
        
        assert result_hash == expected_hash
    
    def test_calculate_combined_hash(self):
        """Test combined hash calculation of two files"""
        xls_content = b"XLS file content"
        pdf_content = b"PDF file content"
        
        xls_file = self.temp_dir / "test.xls"
        pdf_file = self.temp_dir / "test.pdf"
        
        xls_file.write_bytes(xls_content)
        pdf_file.write_bytes(pdf_content)
        
        result_hash = calculate_combined_hash(xls_file, pdf_file)
        
        # Calculate expected hash by combining content
        combined_content = xls_content + pdf_content
        expected_hash = hashlib.sha256(combined_content).hexdigest()
        
        assert result_hash == expected_hash
        assert len(result_hash) == 64
    
    def test_calculate_combined_hash_order_matters(self):
        """Test that file order matters in combined hash"""
        content1 = b"First file"
        content2 = b"Second file"
        
        file1 = self.temp_dir / "file1.txt"
        file2 = self.temp_dir / "file2.txt"
        
        file1.write_bytes(content1)
        file2.write_bytes(content2)
        
        hash1 = calculate_combined_hash(file1, file2)
        hash2 = calculate_combined_hash(file2, file1)
        
        # Should be different because order matters
        assert hash1 != hash2
    
    def test_calculate_content_hash(self):
        """Test hash calculation from byte content directly"""
        test_content = b"Direct byte content"
        
        result_hash = calculate_content_hash(test_content)
        expected_hash = hashlib.sha256(test_content).hexdigest()
        
        assert result_hash == expected_hash
        assert len(result_hash) == 64
    
    def test_calculate_content_hash_empty(self):
        """Test hash calculation with empty content"""
        empty_content = b""
        
        result_hash = calculate_content_hash(empty_content)
        expected_hash = hashlib.sha256(empty_content).hexdigest()
        
        assert result_hash == expected_hash
        # SHA256 of empty content is a specific known value
        assert result_hash == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    
    @pytest.mark.asyncio
    async def test_hash_consistency_async_vs_sync(self):
        """Test that async and sync methods produce same result"""
        test_content = b"Consistency test content"
        test_file = self.temp_dir / "consistency.txt"
        test_file.write_bytes(test_content)
        
        async_hash = await calculate_file_hash(test_file)
        sync_hash = calculate_file_hash_sync(test_file)
        
        assert async_hash == sync_hash
    
    def test_hash_different_for_different_content(self):
        """Test that different content produces different hashes"""
        content1 = b"Content one"
        content2 = b"Content two"
        
        hash1 = calculate_content_hash(content1)
        hash2 = calculate_content_hash(content2)
        
        assert hash1 != hash2
    
    def test_hash_same_for_same_content(self):
        """Test that same content always produces same hash"""
        content = b"Same content"
        
        hash1 = calculate_content_hash(content)
        hash2 = calculate_content_hash(content)
        
        assert hash1 == hash2
    
    @pytest.mark.asyncio
    async def test_calculate_file_hash_with_string_path(self):
        """Test file hash calculation with string path"""
        test_content = b"String path test"
        test_file = self.temp_dir / "string_path.txt"
        test_file.write_bytes(test_content)
        
        # Pass as string instead of Path object
        result_hash = await calculate_file_hash(str(test_file))
        expected_hash = hashlib.sha256(test_content).hexdigest()
        
        assert result_hash == expected_hash
    
    def test_calculate_file_hash_sync_with_string_path(self):
        """Test sync file hash calculation with string path"""
        test_content = b"String path sync test"
        test_file = self.temp_dir / "string_path_sync.txt"
        test_file.write_bytes(test_content)
        
        # Pass as string instead of Path object
        result_hash = calculate_file_hash_sync(str(test_file))
        expected_hash = hashlib.sha256(test_content).hexdigest()
        
        assert result_hash == expected_hash