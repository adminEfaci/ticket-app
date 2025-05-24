import hashlib
import aiofiles
from typing import Union
from pathlib import Path

async def calculate_file_hash(file_path: Union[str, Path]) -> str:
    """
    Calculate SHA256 hash of a file asynchronously.
    
    Args:
        file_path: Path to the file
        
    Returns:
        SHA256 hash as hexadecimal string
    """
    hash_sha256 = hashlib.sha256()
    
    async with aiofiles.open(file_path, 'rb') as f:
        while chunk := await f.read(8192):  # 8KB chunks
            hash_sha256.update(chunk)
    
    return hash_sha256.hexdigest()

def calculate_file_hash_sync(file_path: Union[str, Path]) -> str:
    """
    Calculate SHA256 hash of a file synchronously.
    
    Args:
        file_path: Path to the file
        
    Returns:
        SHA256 hash as hexadecimal string
    """
    hash_sha256 = hashlib.sha256()
    
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):  # 8KB chunks
            hash_sha256.update(chunk)
    
    return hash_sha256.hexdigest()

def calculate_combined_hash(xls_path: Union[str, Path], pdf_path: Union[str, Path]) -> str:
    """
    Calculate combined SHA256 hash of XLS and PDF files.
    
    Args:
        xls_path: Path to XLS file
        pdf_path: Path to PDF file
        
    Returns:
        Combined SHA256 hash as hexadecimal string
    """
    hash_sha256 = hashlib.sha256()
    
    # Add XLS file content
    with open(xls_path, 'rb') as f:
        while chunk := f.read(8192):
            hash_sha256.update(chunk)
    
    # Add PDF file content
    with open(pdf_path, 'rb') as f:
        while chunk := f.read(8192):
            hash_sha256.update(chunk)
    
    return hash_sha256.hexdigest()

def calculate_content_hash(content: bytes) -> str:
    """
    Calculate SHA256 hash of byte content.
    
    Args:
        content: Byte content to hash
        
    Returns:
        SHA256 hash as hexadecimal string
    """
    return hashlib.sha256(content).hexdigest()