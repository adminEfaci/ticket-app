import pytest
from uuid import uuid4
from unittest.mock import Mock, MagicMock, patch
from sqlmodel import Session, select
from backend.services.batch_service import BatchService
from backend.models.batch import ProcessingBatch, ProcessingBatchUpdate, BatchStatus
from backend.models.user import UserRole

class TestBatchService:
    
    def setup_method(self):
        self.mock_db = Mock(spec=Session)
        self.mock_storage = Mock()
        self.batch_service = BatchService(self.mock_db, self.mock_storage)
        
        self.test_user_id = uuid4()
        self.test_client_id = uuid4()
        self.test_batch_id = uuid4()
    
    def test_create_batch(self):
        """Test creating a new batch"""
        batch_data = {
            "created_by": self.test_user_id,
            "client_id": self.test_client_id,
            "status": BatchStatus.PENDING,
            "xls_filename": "test.xls",
            "pdf_filename": "test.pdf",
            "file_hash": "abc123"
        }
        
        # Mock the database operations
        mock_batch = Mock(spec=ProcessingBatch)
        self.mock_db.add.return_value = None
        self.mock_db.commit.return_value = None
        self.mock_db.refresh.return_value = None
        
        # Mock ProcessingBatch creation
        with patch('backend.services.batch_service.ProcessingBatch') as mock_batch_class:
            mock_batch_class.model_validate.return_value = mock_batch
            
            result = self.batch_service.create_batch(batch_data)
            
            assert result == mock_batch
            self.mock_db.add.assert_called_once_with(mock_batch)
            self.mock_db.commit.assert_called_once()
            self.mock_db.refresh.assert_called_once_with(mock_batch)
    
    def test_get_batch_by_id_admin(self):
        """Test getting batch by ID as admin (can see all)"""
        mock_batch = Mock(spec=ProcessingBatch)
        mock_result = Mock()
        mock_result.first.return_value = mock_batch
        self.mock_db.exec.return_value = mock_result
        
        result = self.batch_service.get_batch_by_id(
            self.test_batch_id, 
            self.test_user_id, 
            UserRole.ADMIN
        )
        
        assert result == mock_batch
        self.mock_db.exec.assert_called_once()
    
    def test_get_batch_by_id_client_own_batch(self):
        """Test client getting their own batch"""
        mock_batch = Mock(spec=ProcessingBatch)
        mock_batch.created_by = self.test_user_id
        mock_result = Mock()
        mock_result.first.return_value = mock_batch
        self.mock_db.exec.return_value = mock_result
        
        result = self.batch_service.get_batch_by_id(
            self.test_batch_id, 
            self.test_user_id, 
            UserRole.CLIENT
        )
        
        assert result == mock_batch
        self.mock_db.exec.assert_called_once()
    
    def test_get_batch_by_id_client_no_access(self):
        """Test client trying to access another user's batch"""
        mock_result = Mock()
        mock_result.first.return_value = None  # No access
        self.mock_db.exec.return_value = mock_result
        
        result = self.batch_service.get_batch_by_id(
            self.test_batch_id, 
            self.test_user_id, 
            UserRole.CLIENT
        )
        
        assert result is None
        self.mock_db.exec.assert_called_once()
    
    def test_get_batches_with_filters(self):
        """Test getting batches with filters"""
        mock_batches = [Mock(spec=ProcessingBatch) for _ in range(3)]
        mock_result = Mock()
        mock_result.all.return_value = mock_batches
        self.mock_db.exec.return_value = mock_result
        
        result = self.batch_service.get_batches(
            requester_id=self.test_user_id,
            requester_role=UserRole.MANAGER,
            skip=0,
            limit=10,
            status_filter="pending",
            client_filter=self.test_client_id
        )
        
        assert result == mock_batches
        self.mock_db.exec.assert_called_once()
    
    def test_update_batch(self):
        """Test updating a batch"""
        mock_batch = Mock(spec=ProcessingBatch)
        self.mock_db.get.return_value = mock_batch
        
        update_data = ProcessingBatchUpdate(status="ready", error_reason=None)
        
        result = self.batch_service.update_batch(self.test_batch_id, update_data)
        
        assert result == mock_batch
        self.mock_db.get.assert_called_once_with(ProcessingBatch, self.test_batch_id)
        self.mock_db.add.assert_called_once_with(mock_batch)
        self.mock_db.commit.assert_called_once()
        self.mock_db.refresh.assert_called_once_with(mock_batch)
    
    def test_update_batch_not_found(self):
        """Test updating non-existent batch"""
        self.mock_db.get.return_value = None
        
        update_data = ProcessingBatchUpdate(status="ready")
        result = self.batch_service.update_batch(self.test_batch_id, update_data)
        
        assert result is None
        self.mock_db.get.assert_called_once_with(ProcessingBatch, self.test_batch_id)
        self.mock_db.add.assert_not_called()
    
    def test_mark_batch_as_processed(self):
        """Test marking batch as processed"""
        mock_batch = Mock(spec=ProcessingBatch)
        self.mock_db.get.return_value = mock_batch
        
        with patch.object(self.batch_service, 'update_batch') as mock_update:
            mock_update.return_value = mock_batch
            
            result = self.batch_service.mark_batch_as_processed(self.test_batch_id)
            
            assert result == mock_batch
            mock_update.assert_called_once()
            # Check that the update data has the correct status
            update_call_args = mock_update.call_args[0][1]
            assert update_call_args.status == "ready"
            assert update_call_args.processed_at is not None
    
    def test_mark_batch_as_error(self):
        """Test marking batch as error"""
        mock_batch = Mock(spec=ProcessingBatch)
        error_reason = "File validation failed"
        
        with patch.object(self.batch_service, 'update_batch') as mock_update:
            mock_update.return_value = mock_batch
            
            result = self.batch_service.mark_batch_as_error(self.test_batch_id, error_reason)
            
            assert result == mock_batch
            mock_update.assert_called_once()
            # Check that the update data has the correct status and error
            update_call_args = mock_update.call_args[0][1]
            assert update_call_args.status == "error"
            assert update_call_args.error_reason == error_reason
    
    def test_delete_batch_admin_success(self):
        """Test admin deleting any batch successfully"""
        mock_batch = Mock(spec=ProcessingBatch)
        mock_batch.status = BatchStatus.PENDING
        
        with patch.object(self.batch_service, 'get_batch_by_id') as mock_get:
            mock_get.return_value = mock_batch
            self.mock_storage.delete_batch_directory.return_value = True
            
            result = self.batch_service.delete_batch(
                self.test_batch_id, 
                self.test_user_id, 
                UserRole.ADMIN
            )
            
            assert result is True
            mock_get.assert_called_once()
            self.mock_storage.delete_batch_directory.assert_called_once_with(self.test_batch_id)
            self.mock_db.delete.assert_called_once_with(mock_batch)
            self.mock_db.commit.assert_called_once()
    
    def test_delete_batch_client_own_pending(self):
        """Test client deleting their own pending batch"""
        mock_batch = Mock(spec=ProcessingBatch)
        mock_batch.created_by = self.test_user_id
        mock_batch.status = BatchStatus.PENDING
        
        with patch.object(self.batch_service, 'get_batch_by_id') as mock_get:
            mock_get.return_value = mock_batch
            self.mock_storage.delete_batch_directory.return_value = True
            
            result = self.batch_service.delete_batch(
                self.test_batch_id, 
                self.test_user_id, 
                UserRole.CLIENT
            )
            
            assert result is True
    
    def test_delete_batch_client_not_pending(self):
        """Test client cannot delete non-pending batch"""
        mock_batch = Mock(spec=ProcessingBatch)
        mock_batch.created_by = self.test_user_id
        mock_batch.status = BatchStatus.READY  # Not pending
        
        with patch.object(self.batch_service, 'get_batch_by_id') as mock_get:
            mock_get.return_value = mock_batch
            
            result = self.batch_service.delete_batch(
                self.test_batch_id, 
                self.test_user_id, 
                UserRole.CLIENT
            )
            
            assert result is False
            self.mock_storage.delete_batch_directory.assert_not_called()
    
    def test_delete_batch_not_found(self):
        """Test deleting non-existent batch"""
        with patch.object(self.batch_service, 'get_batch_by_id') as mock_get:
            mock_get.return_value = None
            
            result = self.batch_service.delete_batch(
                self.test_batch_id, 
                self.test_user_id, 
                UserRole.ADMIN
            )
            
            assert result is False
    
    def test_delete_batch_storage_error(self):
        """Test delete batch with storage error triggers rollback"""
        mock_batch = Mock(spec=ProcessingBatch)
        mock_batch.status = BatchStatus.PENDING
        
        with patch.object(self.batch_service, 'get_batch_by_id') as mock_get:
            mock_get.return_value = mock_batch
            self.mock_storage.delete_batch_directory.side_effect = Exception("Storage error")
            
            result = self.batch_service.delete_batch(
                self.test_batch_id, 
                self.test_user_id, 
                UserRole.ADMIN
            )
            
            assert result is False
            self.mock_db.rollback.assert_called_once()
    
    def test_check_duplicate_hash_exists(self):
        """Test checking for duplicate hash that exists"""
        mock_batch = Mock(spec=ProcessingBatch)
        mock_result = Mock()
        mock_result.first.return_value = mock_batch
        self.mock_db.exec.return_value = mock_result
        
        result = self.batch_service.check_duplicate_hash("abc123hash")
        
        assert result is True
        self.mock_db.exec.assert_called_once()
    
    def test_check_duplicate_hash_not_exists(self):
        """Test checking for duplicate hash that doesn't exist"""
        mock_result = Mock()
        mock_result.first.return_value = None
        self.mock_db.exec.return_value = mock_result
        
        result = self.batch_service.check_duplicate_hash("uniquehash")
        
        assert result is False
        self.mock_db.exec.assert_called_once()
    
    def test_check_duplicate_hash_exclude_batch(self):
        """Test checking for duplicate hash excluding specific batch"""
        mock_result = Mock()
        mock_result.first.return_value = None
        self.mock_db.exec.return_value = mock_result
        
        exclude_id = uuid4()
        result = self.batch_service.check_duplicate_hash("abc123hash", exclude_batch_id=exclude_id)
        
        assert result is False
        self.mock_db.exec.assert_called_once()
    
    def test_get_batch_stats(self):
        """Test getting batch statistics"""
        # Mock count queries - exec().first() returns the count directly
        self.mock_db.exec.return_value.first.side_effect = [
            100,  # total_batches
            20,   # pending_batches
            60,   # ready_batches
            10    # error_batches
        ]
        
        stats = self.batch_service.get_batch_stats()
        
        assert stats["total_batches"] == 100
        assert stats["pending_batches"] == 20
        assert stats["ready_batches"] == 60
        assert stats["error_batches"] == 10
        assert stats["processing_batches"] == 10  # 100 - 20 - 60 - 10
        
        # Verify all count queries were called
        assert self.mock_db.exec.call_count == 4