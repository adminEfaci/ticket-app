import pytest
from uuid import uuid4
from unittest.mock import Mock
from backend.utils.datetime_utils import utcnow_naive
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from backend.services.ticket_image_service import TicketImageService
from backend.models.ticket_image import TicketImage, TicketImageCreate, TicketImageUpdate


class TestTicketImageService:
    
    @pytest.fixture
    def mock_db(self):
        return Mock(spec=Session)
    
    @pytest.fixture
    def ticket_image_service(self, mock_db):
        return TicketImageService(db=mock_db)
    
    @pytest.fixture
    def batch_id(self):
        return uuid4()
    
    @pytest.fixture
    def ticket_image_id(self):
        return uuid4()
    
    @pytest.fixture
    def sample_ticket_image_create(self, batch_id):
        return TicketImageCreate(
            batch_id=batch_id,
            page_number=1,
            image_path="/data/batches/batch-001/images/TK-2024-001_page_1.png",
            ticket_number="TK-2024-001",
            ocr_confidence=0.92,
            valid=True
        )
    
    @pytest.fixture
    def sample_ticket_image(self, ticket_image_id, batch_id):
        return TicketImage(
            id=ticket_image_id,
            batch_id=batch_id,
            page_number=1,
            image_path="/data/batches/batch-001/images/TK-2024-001_page_1.png",
            ticket_number="TK-2024-001",
            ocr_confidence=0.92,
            valid=True,
            created_at=utcnow_naive()
        )
    
    def test_create_ticket_image_success(self, ticket_image_service, mock_db, sample_ticket_image_create):
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        
        result = ticket_image_service.create_ticket_image(sample_ticket_image_create)
        
        assert isinstance(result, TicketImage)
        assert result.batch_id == sample_ticket_image_create.batch_id
        assert result.ticket_number == sample_ticket_image_create.ticket_number
        assert result.page_number == sample_ticket_image_create.page_number
        
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
    
    def test_create_ticket_image_database_error(self, ticket_image_service, mock_db, sample_ticket_image_create):
        mock_db.commit.side_effect = SQLAlchemyError("Database error")
        
        with pytest.raises(SQLAlchemyError):
            ticket_image_service.create_ticket_image(sample_ticket_image_create)
        
        mock_db.rollback.assert_called_once()
    
    def test_get_ticket_image_by_id_success(self, ticket_image_service, mock_db, sample_ticket_image, ticket_image_id):
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket_image
        
        result = ticket_image_service.get_ticket_image_by_id(ticket_image_id)
        
        assert result == sample_ticket_image
        mock_db.query.assert_called_once_with(TicketImage)
    
    def test_get_ticket_image_by_id_not_found(self, ticket_image_service, mock_db, ticket_image_id):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = ticket_image_service.get_ticket_image_by_id(ticket_image_id)
        
        assert result is None
    
    def test_get_ticket_images_by_batch_id_success(self, ticket_image_service, mock_db, sample_ticket_image, batch_id):
        mock_images = [sample_ticket_image]
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = mock_images
        mock_db.query.return_value = mock_query
        
        result = ticket_image_service.get_ticket_images_by_batch_id(batch_id)
        
        assert result == mock_images
        assert len(result) == 1
        mock_db.query.assert_called_once_with(TicketImage)
    
    def test_get_ticket_images_by_batch_id_empty(self, ticket_image_service, mock_db, batch_id):
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        result = ticket_image_service.get_ticket_images_by_batch_id(batch_id)
        
        assert result == []
    
    def test_update_ticket_image_success(self, ticket_image_service, mock_db, sample_ticket_image, ticket_image_id):
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket_image
        
        update_data = TicketImageUpdate(
            ticket_number="TK-2024-002",
            ocr_confidence=0.95
        )
        
        result = ticket_image_service.update_ticket_image(ticket_image_id, update_data)
        
        assert result == sample_ticket_image
        mock_db.commit.assert_called_once()
    
    def test_update_ticket_image_not_found(self, ticket_image_service, mock_db, ticket_image_id):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        update_data = TicketImageUpdate(ticket_number="TK-2024-002")
        
        result = ticket_image_service.update_ticket_image(ticket_image_id, update_data)
        
        assert result is None
        mock_db.commit.assert_not_called()
    
    def test_delete_ticket_image_success(self, ticket_image_service, mock_db, sample_ticket_image, ticket_image_id):
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket_image
        
        result = ticket_image_service.delete_ticket_image(ticket_image_id)
        
        assert result is True
        mock_db.delete.assert_called_once_with(sample_ticket_image)
        mock_db.commit.assert_called_once()
    
    def test_delete_ticket_image_not_found(self, ticket_image_service, mock_db, ticket_image_id):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = ticket_image_service.delete_ticket_image(ticket_image_id)
        
        assert result is False
        mock_db.delete.assert_not_called()
        mock_db.commit.assert_not_called()
    
    def test_get_batch_image_statistics_success(self, ticket_image_service, mock_db, batch_id):
        # Create mock images with different properties
        mock_images = []
        for i in range(5):
            img = Mock()
            img.valid = i < 4  # 4 valid, 1 invalid
            img.ocr_confidence = 0.8 + (i * 0.05) if i < 3 else None  # 3 with OCR
            img.ticket_number = f"TK-{i}" if i < 3 else None  # 3 with ticket numbers
            mock_images.append(img)
        
        mock_db.query.return_value.filter.return_value.all.return_value = mock_images
        
        result = ticket_image_service.get_batch_image_statistics(batch_id)
        
        assert result['total_images'] == 5
        assert result['valid_images'] == 4
        assert result['invalid_images'] == 1
        assert result['images_with_ocr'] == 3
        assert result['detected_tickets'] == 3
        assert result['unique_ticket_numbers'] == 3
        assert result['success_rate'] == 80.0
    
    def test_get_batch_image_statistics_no_images(self, ticket_image_service, mock_db, batch_id):
        mock_db.query.return_value.filter.return_value.all.return_value = []
        
        result = ticket_image_service.get_batch_image_statistics(batch_id)
        
        assert result['total_images'] == 0
        assert result['valid_images'] == 0
        assert result['invalid_images'] == 0
        assert result['success_rate'] == 0.0
    
    def test_mark_image_as_invalid_success(self, ticket_image_service, mock_db, sample_ticket_image, ticket_image_id):
        mock_db.query.return_value.filter.return_value.first.return_value = sample_ticket_image
        
        result = ticket_image_service.mark_image_as_invalid(ticket_image_id, "Poor quality")
        
        assert result is True
        assert sample_ticket_image.valid is False
        assert sample_ticket_image.error_reason == "Poor quality"
        mock_db.commit.assert_called_once()
    
    def test_mark_image_as_invalid_not_found(self, ticket_image_service, mock_db, ticket_image_id):
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        result = ticket_image_service.mark_image_as_invalid(ticket_image_id, "Poor quality")
        
        assert result is False
    
    def test_get_images_by_ticket_number_success(self, ticket_image_service, mock_db, sample_ticket_image):
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [sample_ticket_image]
        mock_db.query.return_value = mock_query
        
        result = ticket_image_service.get_images_by_ticket_number("TK-2024-001")
        
        assert len(result) == 1
        assert result[0] == sample_ticket_image
    
    def test_get_images_by_ticket_number_no_results(self, ticket_image_service, mock_db):
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = []
        mock_db.query.return_value = mock_query
        
        result = ticket_image_service.get_images_by_ticket_number("NONEXISTENT")
        
        assert result == []
    
    def test_bulk_update_image_status_success(self, ticket_image_service, mock_db):
        image_ids = [uuid4(), uuid4(), uuid4()]
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = 3
        mock_db.query.return_value = mock_query
        
        result = ticket_image_service.bulk_update_image_status(image_ids, False, "Bulk invalid")
        
        assert result == 3
        mock_db.commit.assert_called_once()
    
    def test_create_ticket_images_batch_success(self, ticket_image_service, mock_db, batch_id):
        image_data_list = []
        for i in range(3):
            image_data_list.append(TicketImageCreate(
                batch_id=batch_id,
                page_number=i+1,
                image_path=f"/data/batches/batch-001/images/image_{i+1}.png",
                ticket_number=f"TK-2024-{i+1:03d}",
                ocr_confidence=0.8 + (i * 0.05),
                valid=True
            ))
        
        mock_db.add_all.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None
        
        results = ticket_image_service.create_ticket_images_batch(image_data_list)
        
        assert len(results) == 3
        assert all(isinstance(result, TicketImage) for result in results)
        mock_db.add_all.assert_called_once()
        mock_db.commit.assert_called_once()
    
    def test_create_ticket_images_batch_empty(self, ticket_image_service, mock_db):
        results = ticket_image_service.create_ticket_images_batch([])
        
        assert results == []
        mock_db.add_all.assert_not_called()
        mock_db.commit.assert_not_called()
    
    def test_check_user_access_admin(self, ticket_image_service, batch_id):
        user = {'id': uuid4(), 'role': 'admin'}
        
        result = ticket_image_service.check_user_access(user, batch_id)
        
        assert result is True
    
    def test_check_user_access_manager(self, ticket_image_service, batch_id):
        user = {'id': uuid4(), 'role': 'manager'}
        
        result = ticket_image_service.check_user_access(user, batch_id)
        
        assert result is True
    
    def test_error_handling_during_commit(self, ticket_image_service, mock_db, sample_ticket_image_create):
        mock_db.commit.side_effect = SQLAlchemyError("Database connection error")
        
        with pytest.raises(SQLAlchemyError):
            ticket_image_service.create_ticket_image(sample_ticket_image_create)
        
        mock_db.rollback.assert_called_once()