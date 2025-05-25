import aiofiles
from pathlib import Path
from uuid import UUID
from fastapi import UploadFile
import shutil

class StorageService:
    def __init__(self, base_path: str = "/data/batches"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def get_batch_directory(self, batch_id: UUID) -> Path:
        """Get the directory path for a specific batch"""
        return self.base_path / str(batch_id)
    
    def create_batch_directory(self, batch_id: UUID) -> Path:
        """Create directory for a batch and return the path"""
        batch_dir = self.get_batch_directory(batch_id)
        batch_dir.mkdir(parents=True, exist_ok=True)
        return batch_dir
    
    async def save_file(self, batch_id: UUID, file: UploadFile, filename: str) -> Path:
        """
        Save an uploaded file to the batch directory.
        
        Args:
            batch_id: Unique identifier for the batch
            file: FastAPI UploadFile object
            filename: Target filename (e.g., 'original.xls', 'tickets.pdf')
            
        Returns:
            Path to the saved file
        """
        batch_dir = self.create_batch_directory(batch_id)
        file_path = batch_dir / filename
        
        async with aiofiles.open(file_path, 'wb') as f:
            # Reset file pointer to beginning
            await file.seek(0)
            
            # Copy file content in chunks
            while chunk := await file.read(8192):  # 8KB chunks
                await f.write(chunk)
        
        return file_path
    
    async def save_file_content(self, batch_id: UUID, content: bytes, filename: str) -> Path:
        """
        Save file content directly to the batch directory.
        
        Args:
            batch_id: Unique identifier for the batch
            content: File content as bytes
            filename: Target filename
            
        Returns:
            Path to the saved file
        """
        batch_dir = self.create_batch_directory(batch_id)
        file_path = batch_dir / filename
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        return file_path
    
    def file_exists(self, batch_id: UUID, filename: str) -> bool:
        """Check if a file exists in the batch directory"""
        file_path = self.get_batch_directory(batch_id) / filename
        return file_path.exists()
    
    def get_file_path(self, batch_id: UUID, filename: str) -> Path:
        """Get the full path to a file in the batch directory"""
        return self.get_batch_directory(batch_id) / filename
    
    def get_file_size(self, batch_id: UUID, filename: str) -> int:
        """Get the size of a file in bytes"""
        file_path = self.get_file_path(batch_id, filename)
        return file_path.stat().st_size if file_path.exists() else 0
    
    def delete_batch_directory(self, batch_id: UUID) -> bool:
        """
        Delete the entire batch directory and all its contents.
        
        Args:
            batch_id: Unique identifier for the batch
            
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            batch_dir = self.get_batch_directory(batch_id)
            if batch_dir.exists():
                shutil.rmtree(batch_dir)
            return True
        except Exception:
            return False
    
    def delete_file(self, batch_id: UUID, filename: str) -> bool:
        """
        Delete a specific file from the batch directory.
        
        Args:
            batch_id: Unique identifier for the batch
            filename: Name of the file to delete
            
        Returns:
            True if deletion was successful, False otherwise
        """
        try:
            file_path = self.get_file_path(batch_id, filename)
            if file_path.exists():
                file_path.unlink()
            return True
        except Exception:
            return False
    
    def list_batch_files(self, batch_id: UUID) -> list[str]:
        """List all files in a batch directory"""
        batch_dir = self.get_batch_directory(batch_id)
        if not batch_dir.exists():
            return []
        
        return [f.name for f in batch_dir.iterdir() if f.is_file()]
    
    def get_batch_stats(self, batch_id: UUID) -> dict:
        """Get statistics about files in a batch directory"""
        batch_dir = self.get_batch_directory(batch_id)
        if not batch_dir.exists():
            return {"total_files": 0, "total_size": 0}
        
        files = list(batch_dir.iterdir())
        total_size = sum(f.stat().st_size for f in files if f.is_file())
        
        return {
            "total_files": len([f for f in files if f.is_file()]),
            "total_size": total_size,
            "files": [{"name": f.name, "size": f.stat().st_size} for f in files if f.is_file()]
        }
    
    def get_batch_files_info(self, batch_id: UUID) -> list[dict]:
        """Get detailed information about files in a batch"""
        batch_dir = self.get_batch_directory(batch_id)
        if not batch_dir.exists():
            return []
        
        files_info = []
        for file_path in batch_dir.iterdir():
            if file_path.is_file():
                stat = file_path.stat()
                files_info.append({
                    "name": file_path.name,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "type": "xls" if file_path.suffix.lower() in ['.xls', '.xlsx'] else "pdf" if file_path.suffix.lower() == '.pdf' else "other"
                })
        
        return files_info