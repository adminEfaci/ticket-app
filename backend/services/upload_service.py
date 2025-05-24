from typing import List, Dict, Any, Optional, Tuple
from fastapi import UploadFile
from uuid import UUID, uuid4
import asyncio

from .storage_service import StorageService
from .validation_service import ValidationService
from ..utils.hash_utils import calculate_combined_hash

class UploadService:
    def __init__(self, storage_service: StorageService, validation_service: ValidationService):
        self.storage = storage_service
        self.validation = validation_service
    
    async def process_file_pair(
        self, 
        xls_file: UploadFile, 
        pdf_file: UploadFile, 
        created_by: UUID,
        client_id: Optional[UUID] = None
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Process a single XLS+PDF file pair.
        
        Args:
            xls_file: XLS UploadFile
            pdf_file: PDF UploadFile
            created_by: User ID who uploaded the files
            client_id: Optional client ID for client users
            
        Returns:
            Tuple of (success, error_message, batch_data)
        """
        batch_id = uuid4()
        
        try:
            # Validate the file pair
            is_valid, error_message, validation_stats = await self.validation.validate_file_pair(
                xls_file, pdf_file
            )
            
            if not is_valid:
                return False, error_message, None
            
            # Save files to storage
            xls_path = await self.storage.save_file(batch_id, xls_file, "original.xls")
            pdf_path = await self.storage.save_file(batch_id, pdf_file, "tickets.pdf")
            
            # Calculate combined file hash
            file_hash = calculate_combined_hash(xls_path, pdf_path)
            
            # Prepare batch data
            batch_data = {
                "id": batch_id,
                "created_by": created_by,
                "client_id": client_id,
                "status": "pending",  # Will be converted to enum in the model
                "xls_filename": xls_file.filename,
                "pdf_filename": pdf_file.filename,
                "file_hash": file_hash,
                "error_reason": None,
                "stats": {
                    "validation": validation_stats,
                    "storage": self.storage.get_batch_stats(batch_id)
                }
            }
            
            return True, None, batch_data
            
        except Exception as e:
            # Clean up any partially saved files
            try:
                self.storage.delete_batch_directory(batch_id)
            except:
                pass
            
            return False, f"Upload processing failed: {str(e)}", None
    
    async def process_multiple_pairs(
        self,
        file_pairs: List[Tuple[UploadFile, UploadFile]],
        created_by: UUID,
        client_id: Optional[UUID] = None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Process multiple XLS+PDF file pairs concurrently.
        
        Args:
            file_pairs: List of (xls_file, pdf_file) tuples
            created_by: User ID who uploaded the files
            client_id: Optional client ID for client users
            
        Returns:
            Tuple of (successful_batches, failed_batches)
        """
        # Validate session limits
        if not self.validation.validate_session_pair_count(len(file_pairs)):
            error_msg = f"Too many file pairs. Maximum {self.validation.MAX_PAIRS_PER_SESSION} pairs allowed, got {len(file_pairs)}"
            failed_batches = [{
                "error": error_msg,
                "xls_filename": None,
                "pdf_filename": None
            }]
            return [], failed_batches
        
        # Process pairs concurrently
        tasks = []
        for xls_file, pdf_file in file_pairs:
            task = self.process_file_pair(xls_file, pdf_file, created_by, client_id)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successful_batches = []
        failed_batches = []
        
        for i, result in enumerate(results):
            xls_file, pdf_file = file_pairs[i]
            
            if isinstance(result, Exception):
                failed_batches.append({
                    "error": f"Processing exception: {str(result)}",
                    "xls_filename": xls_file.filename,
                    "pdf_filename": pdf_file.filename
                })
            else:
                success, error_message, batch_data = result
                
                if success:
                    successful_batches.append(batch_data)
                else:
                    failed_batches.append({
                        "error": error_message,
                        "xls_filename": xls_file.filename,
                        "pdf_filename": pdf_file.filename
                    })
        
        return successful_batches, failed_batches
    
    def extract_file_pairs_from_upload(self, files: List[UploadFile]) -> Tuple[List[Tuple[UploadFile, UploadFile]], List[str]]:
        """
        Extract XLS+PDF pairs from a list of uploaded files.
        
        Args:
            files: List of uploaded files
            
        Returns:
            Tuple of (valid_pairs, errors)
        """
        xls_files = []
        pdf_files = []
        errors = []
        
        # Separate files by type
        for file in files:
            if self.validation.validate_xls_extension(file.filename):
                xls_files.append(file)
            elif self.validation.validate_pdf_extension(file.filename):
                pdf_files.append(file)
            else:
                errors.append(f"Unsupported file type: {file.filename}")
        
        # Match XLS and PDF files by filename similarity
        pairs = []
        used_pdf_indices = set()
        
        for xls_file in xls_files:
            best_match_idx = None
            best_similarity = 0.0
            
            for i, pdf_file in enumerate(pdf_files):
                if i in used_pdf_indices:
                    continue
                
                similarity = self.validation.calculate_filename_similarity(
                    xls_file.filename, pdf_file.filename
                )
                
                if similarity > best_similarity and similarity >= 0.9:  # 90% similarity threshold
                    best_similarity = similarity
                    best_match_idx = i
            
            if best_match_idx is not None:
                pairs.append((xls_file, pdf_files[best_match_idx]))
                used_pdf_indices.add(best_match_idx)
            else:
                errors.append(f"No matching PDF found for XLS file: {xls_file.filename}")
        
        # Report unmatched PDF files
        for i, pdf_file in enumerate(pdf_files):
            if i not in used_pdf_indices:
                errors.append(f"No matching XLS found for PDF file: {pdf_file.filename}")
        
        return pairs, errors