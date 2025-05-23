import os
import xlrd
import PyPDF2
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from fastapi import UploadFile
from difflib import SequenceMatcher
import io

class ValidationService:
    
    # File size limits
    MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB
    MAX_PAIRS_PER_SESSION = 30
    
    # Supported file extensions
    ALLOWED_XLS_EXTENSIONS = {'.xls'}
    ALLOWED_PDF_EXTENSIONS = {'.pdf'}
    
    def __init__(self):
        pass
    
    def validate_file_extension(self, filename: str, allowed_extensions: set) -> bool:
        """Validate file extension"""
        extension = Path(filename).suffix.lower()
        return extension in allowed_extensions
    
    def validate_xls_extension(self, filename: str) -> bool:
        """Validate XLS file extension - only .xls allowed, not .xlsx"""
        return self.validate_file_extension(filename, self.ALLOWED_XLS_EXTENSIONS)
    
    def validate_pdf_extension(self, filename: str) -> bool:
        """Validate PDF file extension"""
        return self.validate_file_extension(filename, self.ALLOWED_PDF_EXTENSIONS)
    
    def validate_file_size(self, file_size: int) -> bool:
        """Validate file size is within limits"""
        return 0 < file_size <= self.MAX_FILE_SIZE
    
    def validate_session_pair_count(self, pair_count: int) -> bool:
        """Validate number of pairs in a session"""
        return 0 < pair_count <= self.MAX_PAIRS_PER_SESSION
    
    def calculate_filename_similarity(self, filename1: str, filename2: str) -> float:
        """
        Calculate similarity between two filenames.
        
        Args:
            filename1: First filename
            filename2: Second filename
            
        Returns:
            Similarity ratio (0.0 to 1.0)
        """
        # Remove extensions for comparison
        name1 = Path(filename1).stem.lower()
        name2 = Path(filename2).stem.lower()
        
        return SequenceMatcher(None, name1, name2).ratio()
    
    def validate_filename_pair_match(self, xls_filename: str, pdf_filename: str, min_similarity: float = 0.9) -> bool:
        """
        Validate that XLS and PDF filenames match with at least 90% similarity.
        
        Args:
            xls_filename: XLS filename
            pdf_filename: PDF filename
            min_similarity: Minimum similarity ratio (default 0.9 for 90%)
            
        Returns:
            True if filenames match criteria
        """
        similarity = self.calculate_filename_similarity(xls_filename, pdf_filename)
        return similarity >= min_similarity
    
    async def validate_xls_content(self, file: UploadFile) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Validate XLS file content and structure.
        
        Args:
            file: FastAPI UploadFile object
            
        Returns:
            Tuple of (is_valid, error_message, file_stats)
        """
        try:
            # Read file content
            await file.seek(0)
            content = await file.read()
            await file.seek(0)  # Reset for future use
            
            # Try to open with xlrd
            workbook = xlrd.open_workbook(file_contents=content)
            
            # Basic validation
            if workbook.nsheets == 0:
                return False, "XLS file contains no worksheets", None
            
            # Get stats about the workbook
            stats = {
                "sheet_count": workbook.nsheets,
                "sheet_names": workbook.sheet_names(),
                "total_rows": 0,
                "total_cols": 0
            }
            
            # Calculate total rows and columns across all sheets
            for sheet_idx in range(workbook.nsheets):
                sheet = workbook.sheet_by_index(sheet_idx)
                stats["total_rows"] += sheet.nrows
                stats["total_cols"] = max(stats["total_cols"], sheet.ncols)
            
            return True, None, stats
            
        except Exception as e:
            if "xlrd" in str(type(e).__module__):
                return False, f"Invalid XLS file format: {str(e)}", None
            else:
                return False, f"Error reading XLS file: {str(e)}", None
    
    async def validate_pdf_content(self, file: UploadFile) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Validate PDF file content and structure.
        
        Args:
            file: FastAPI UploadFile object
            
        Returns:
            Tuple of (is_valid, error_message, file_stats)
        """
        try:
            # Read file content
            await file.seek(0)
            content = await file.read()
            await file.seek(0)  # Reset for future use
            
            # Try to open with PyPDF2
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
            
            # Basic validation
            if len(pdf_reader.pages) == 0:
                return False, "PDF file contains no pages", None
            
            # Check if PDF is encrypted
            if pdf_reader.is_encrypted:
                return False, "Encrypted PDF files are not supported", None
            
            # Get stats about the PDF
            stats = {
                "page_count": len(pdf_reader.pages),
                "encrypted": pdf_reader.is_encrypted,
                "has_metadata": pdf_reader.metadata is not None
            }
            
            # Try to extract some text to verify readability
            try:
                first_page = pdf_reader.pages[0]
                text = first_page.extract_text()
                stats["has_extractable_text"] = len(text.strip()) > 0
                stats["first_page_text_length"] = len(text)
            except Exception:
                stats["has_extractable_text"] = False
                stats["first_page_text_length"] = 0
            
            return True, None, stats
            
        except Exception as e:
            if "PyPDF2" in str(type(e).__module__) or "pdf" in str(e).lower():
                return False, f"Invalid PDF file format: {str(e)}", None
            else:
                return False, f"Error reading PDF file: {str(e)}", None
    
    async def validate_file_pair(self, xls_file: UploadFile, pdf_file: UploadFile) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Validate a complete XLS+PDF file pair.
        
        Args:
            xls_file: XLS UploadFile
            pdf_file: PDF UploadFile
            
        Returns:
            Tuple of (is_valid, error_message, validation_stats)
        """
        validation_stats = {
            "xls_filename": xls_file.filename,
            "pdf_filename": pdf_file.filename,
            "xls_size": xls_file.size,
            "pdf_size": pdf_file.size,
        }
        
        # Validate file extensions
        if not self.validate_xls_extension(xls_file.filename):
            return False, f"Invalid XLS file extension. Only .xls files are supported, got {xls_file.filename}", validation_stats
        
        if not self.validate_pdf_extension(pdf_file.filename):
            return False, f"Invalid PDF file extension. Got {pdf_file.filename}", validation_stats
        
        # Validate file sizes
        if not self.validate_file_size(xls_file.size):
            return False, f"XLS file too large. Maximum size is {self.MAX_FILE_SIZE // (1024*1024)}MB, got {xls_file.size // (1024*1024)}MB", validation_stats
        
        if not self.validate_file_size(pdf_file.size):
            return False, f"PDF file too large. Maximum size is {self.MAX_FILE_SIZE // (1024*1024)}MB, got {pdf_file.size // (1024*1024)}MB", validation_stats
        
        # Validate filename matching
        similarity = self.calculate_filename_similarity(xls_file.filename, pdf_file.filename)
        validation_stats["filename_similarity"] = similarity
        
        if not self.validate_filename_pair_match(xls_file.filename, pdf_file.filename):
            return False, f"Filenames do not match sufficiently. Similarity: {similarity:.2%}, required: 90%", validation_stats
        
        # Validate XLS content
        xls_valid, xls_error, xls_stats = await self.validate_xls_content(xls_file)
        if not xls_valid:
            return False, f"XLS validation failed: {xls_error}", validation_stats
        
        validation_stats["xls_stats"] = xls_stats
        
        # Validate PDF content
        pdf_valid, pdf_error, pdf_stats = await self.validate_pdf_content(pdf_file)
        if not pdf_valid:
            return False, f"PDF validation failed: {pdf_error}", validation_stats
        
        validation_stats["pdf_stats"] = pdf_stats
        
        return True, None, validation_stats