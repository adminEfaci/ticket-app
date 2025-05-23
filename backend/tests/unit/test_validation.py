import pytest
import io
from unittest.mock import Mock, AsyncMock, patch
from fastapi import UploadFile
from backend.services.validation_service import ValidationService

class TestValidationService:
    
    def setup_method(self):
        self.validation_service = ValidationService()
    
    def test_validate_xls_extension(self):
        """Test XLS extension validation - only .xls allowed"""
        assert self.validation_service.validate_xls_extension("test.xls")
        assert not self.validation_service.validate_xls_extension("test.xlsx")
        assert self.validation_service.validate_xls_extension("test.XLS")  # Case insensitive
        assert not self.validation_service.validate_xls_extension("test.pdf")
        assert not self.validation_service.validate_xls_extension("test.txt")
    
    def test_validate_pdf_extension(self):
        """Test PDF extension validation"""
        assert self.validation_service.validate_pdf_extension("test.pdf")
        assert self.validation_service.validate_pdf_extension("test.PDF")  # Case insensitive
        assert not self.validation_service.validate_pdf_extension("test.xls")
        assert not self.validation_service.validate_pdf_extension("test.txt")
    
    def test_validate_file_size(self):
        """Test file size validation"""
        # Valid sizes
        assert self.validation_service.validate_file_size(1024)  # 1KB
        assert self.validation_service.validate_file_size(100 * 1024 * 1024)  # 100MB
        assert self.validation_service.validate_file_size(200 * 1024 * 1024)  # 200MB (max)
        
        # Invalid sizes
        assert not self.validation_service.validate_file_size(0)  # Empty file
        assert not self.validation_service.validate_file_size(-1)  # Negative size
        assert not self.validation_service.validate_file_size(201 * 1024 * 1024)  # Over 200MB
    
    def test_validate_session_pair_count(self):
        """Test session pair count validation"""
        # Valid counts
        assert self.validation_service.validate_session_pair_count(1)
        assert self.validation_service.validate_session_pair_count(15)
        assert self.validation_service.validate_session_pair_count(30)  # Max
        
        # Invalid counts
        assert not self.validation_service.validate_session_pair_count(0)
        assert not self.validation_service.validate_session_pair_count(-1)
        assert not self.validation_service.validate_session_pair_count(31)  # Over max
    
    def test_calculate_filename_similarity(self):
        """Test filename similarity calculation"""
        # Identical stems
        similarity = self.validation_service.calculate_filename_similarity("test.xls", "test.pdf")
        assert similarity == 1.0
        
        # Very similar
        similarity = self.validation_service.calculate_filename_similarity("client_A_apr12.xls", "client_A_apr12.pdf")
        assert similarity == 1.0
        
        # Somewhat similar
        similarity = self.validation_service.calculate_filename_similarity("client_A.xls", "client_B.pdf")
        assert 0.5 < similarity < 1.0
        
        # Not similar
        similarity = self.validation_service.calculate_filename_similarity("report.xls", "invoice.pdf")
        assert similarity < 0.5
        
        # Case insensitive
        similarity = self.validation_service.calculate_filename_similarity("TEST.xls", "test.pdf")
        assert similarity == 1.0
    
    def test_validate_filename_pair_match(self):
        """Test filename pair matching with 90% threshold"""
        # Perfect match
        assert self.validation_service.validate_filename_pair_match("test.xls", "test.pdf")
        
        # Good match above threshold
        assert self.validation_service.validate_filename_pair_match("client_report_2023.xls", "client_report_2023.pdf")
        
        # Below threshold
        assert not self.validation_service.validate_filename_pair_match("report.xls", "invoice.pdf")
        
        # Custom threshold
        assert self.validation_service.validate_filename_pair_match("similar.xls", "similr.pdf", min_similarity=0.7)
        assert not self.validation_service.validate_filename_pair_match("similar.xls", "different.pdf", min_similarity=0.9)

class TestValidationServiceAsync:
    
    def setup_method(self):
        self.validation_service = ValidationService()
    
    @pytest.mark.asyncio
    async def test_validate_xls_content_valid(self):
        """Test XLS content validation with valid file"""
        # Create a mock XLS file content (simplified)
        mock_content = b'\x09\x08\x08\x00\x00\x00\x00\x00'  # Simplified XLS header
        
        mock_file = Mock(spec=UploadFile)
        mock_file.read = AsyncMock(return_value=mock_content)
        mock_file.seek = AsyncMock()
        
        # Mock xlrd module
        with patch('backend.services.validation_service.xlrd') as mock_xlrd:
            mock_workbook = Mock()
            mock_workbook.nsheets = 2
            mock_workbook.sheet_names.return_value = ["Sheet1", "Sheet2"]
            
            mock_sheet = Mock()
            mock_sheet.nrows = 10
            mock_sheet.ncols = 5
            mock_workbook.sheet_by_index.return_value = mock_sheet
            
            mock_xlrd.open_workbook.return_value = mock_workbook
            
            is_valid, error, stats = await self.validation_service.validate_xls_content(mock_file)
            
            assert is_valid
            assert error is None
            assert stats["sheet_count"] == 2
            assert stats["total_rows"] == 20  # 2 sheets * 10 rows
            assert stats["total_cols"] == 5
    
    @pytest.mark.asyncio
    async def test_validate_xls_content_invalid(self):
        """Test XLS content validation with invalid file"""
        mock_content = b'invalid content'
        
        mock_file = Mock(spec=UploadFile)
        mock_file.read = AsyncMock(return_value=mock_content)
        mock_file.seek = AsyncMock()
        
        # Mock xlrd to raise error
        with patch('backend.services.validation_service.xlrd') as mock_xlrd:
            mock_xlrd.open_workbook.side_effect = Exception("Invalid XLS format")
            
            is_valid, error, stats = await self.validation_service.validate_xls_content(mock_file)
            
            assert not is_valid
            assert "Error reading XLS file" in error
            assert stats is None
    
    @pytest.mark.asyncio
    async def test_validate_pdf_content_valid(self):
        """Test PDF content validation with valid file"""
        mock_content = b'%PDF-1.4 mock content'
        
        mock_file = Mock(spec=UploadFile)
        mock_file.read = AsyncMock(return_value=mock_content)
        mock_file.seek = AsyncMock()
        
        # Mock PyPDF2
        with patch('backend.services.validation_service.PyPDF2') as mock_pypdf:
            mock_reader = Mock()
            mock_reader.pages = [Mock(), Mock()]  # 2 pages
            mock_reader.is_encrypted = False
            mock_reader.metadata = {"title": "Test PDF"}
            
            # Mock text extraction
            mock_page = Mock()
            mock_page.extract_text.return_value = "Sample text content"
            mock_reader.pages = [mock_page]
            
            mock_pypdf.PdfReader.return_value = mock_reader
            
            is_valid, error, stats = await self.validation_service.validate_pdf_content(mock_file)
            
            assert is_valid
            assert error is None
            assert stats["page_count"] == 1
            assert not stats["encrypted"]
            assert stats["has_extractable_text"]
    
    @pytest.mark.asyncio
    async def test_validate_pdf_content_encrypted(self):
        """Test PDF content validation with encrypted file"""
        mock_content = b'%PDF-1.4 encrypted'
        
        mock_file = Mock(spec=UploadFile)
        mock_file.read = AsyncMock(return_value=mock_content)
        mock_file.seek = AsyncMock()
        
        # Mock PyPDF2 with encrypted PDF
        with patch('backend.services.validation_service.PyPDF2') as mock_pypdf:
            mock_reader = Mock()
            mock_reader.pages = [Mock()]
            mock_reader.is_encrypted = True
            
            mock_pypdf.PdfReader.return_value = mock_reader
            
            is_valid, error, stats = await self.validation_service.validate_pdf_content(mock_file)
            
            assert not is_valid
            assert "Encrypted PDF files are not supported" in error
            assert stats is None
    
    @pytest.mark.asyncio
    async def test_validate_file_pair_success(self):
        """Test complete file pair validation - success case"""
        mock_xls_file = Mock(spec=UploadFile)
        mock_xls_file.filename = "client_report.xls"
        mock_xls_file.size = 1024 * 1024  # 1MB
        
        mock_pdf_file = Mock(spec=UploadFile)
        mock_pdf_file.filename = "client_report.pdf"
        mock_pdf_file.size = 2 * 1024 * 1024  # 2MB
        
        # Mock the content validation methods
        with patch.object(self.validation_service, 'validate_xls_content') as mock_xls_valid, \
             patch.object(self.validation_service, 'validate_pdf_content') as mock_pdf_valid:
            
            mock_xls_valid.return_value = (True, None, {"sheet_count": 1})
            mock_pdf_valid.return_value = (True, None, {"page_count": 5})
            
            is_valid, error, stats = await self.validation_service.validate_file_pair(mock_xls_file, mock_pdf_file)
            
            assert is_valid
            assert error is None
            assert stats["filename_similarity"] == 1.0
            assert stats["xls_stats"]["sheet_count"] == 1
            assert stats["pdf_stats"]["page_count"] == 5
    
    @pytest.mark.asyncio
    async def test_validate_file_pair_wrong_extension(self):
        """Test file pair validation with wrong extension"""
        mock_xls_file = Mock(spec=UploadFile)
        mock_xls_file.filename = "client_report.xlsx"  # Wrong extension
        mock_xls_file.size = 1024 * 1024
        
        mock_pdf_file = Mock(spec=UploadFile)
        mock_pdf_file.filename = "client_report.pdf"
        mock_pdf_file.size = 2 * 1024 * 1024
        
        is_valid, error, stats = await self.validation_service.validate_file_pair(mock_xls_file, mock_pdf_file)
        
        assert not is_valid
        assert "Invalid XLS file extension" in error
        assert "Only .xls files are supported" in error
    
    @pytest.mark.asyncio
    async def test_validate_file_pair_size_too_large(self):
        """Test file pair validation with oversized file"""
        mock_xls_file = Mock(spec=UploadFile)
        mock_xls_file.filename = "client_report.xls"
        mock_xls_file.size = 250 * 1024 * 1024  # 250MB - too large
        
        mock_pdf_file = Mock(spec=UploadFile)
        mock_pdf_file.filename = "client_report.pdf"
        mock_pdf_file.size = 2 * 1024 * 1024
        
        is_valid, error, stats = await self.validation_service.validate_file_pair(mock_xls_file, mock_pdf_file)
        
        assert not is_valid
        assert "XLS file too large" in error
        assert "Maximum size is 200MB" in error
    
    @pytest.mark.asyncio
    async def test_validate_file_pair_filenames_dont_match(self):
        """Test file pair validation with mismatched filenames"""
        mock_xls_file = Mock(spec=UploadFile)
        mock_xls_file.filename = "report_a.xls"
        mock_xls_file.size = 1024 * 1024
        
        mock_pdf_file = Mock(spec=UploadFile)
        mock_pdf_file.filename = "completely_different.pdf"
        mock_pdf_file.size = 2 * 1024 * 1024
        
        is_valid, error, stats = await self.validation_service.validate_file_pair(mock_xls_file, mock_pdf_file)
        
        assert not is_valid
        assert "Filenames do not match sufficiently" in error
        assert "required: 90%" in error