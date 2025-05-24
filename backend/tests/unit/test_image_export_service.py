import pytest
import tempfile
import shutil
from unittest.mock import patch
from pathlib import Path
from PIL import Image

from backend.services.image_export_service import ImageExportService


class TestImageExportService:
    
    @pytest.fixture
    def temp_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def export_service(self, temp_dir):
        return ImageExportService(base_path=temp_dir)
    
    @pytest.fixture
    def sample_image(self):
        return Image.new('RGB', (400, 300), color='white')
    
    @pytest.fixture
    def batch_id(self):
        return "batch-2024-001"
    
    def test_init_default_values(self, export_service, temp_dir):
        assert export_service.base_path == Path(temp_dir)
        assert export_service.default_format == "PNG"
        assert export_service.default_quality == 95
        assert export_service.optimize_images is True
        assert hasattr(export_service, 'image_utils')
    
    def test_init_with_custom_base_path(self, temp_dir):
        custom_base = temp_dir
        service = ImageExportService(base_path=custom_base)
        assert service.base_path == Path(custom_base)
    
    def test_init_creates_base_directory(self, temp_dir):
        new_path = Path(temp_dir) / "new_base"
        ImageExportService(base_path=str(new_path))
        assert new_path.exists()
        assert new_path.is_dir()
    
    def test_get_batch_images_directory_creates_path(self, export_service, batch_id):
        result = export_service._get_batch_images_directory(batch_id)
        
        expected_path = export_service.base_path / batch_id / "images"
        assert result == expected_path
        assert result.exists()
        assert result.is_dir()
    
    def test_save_ticket_image_success_with_ticket_number(self, export_service, sample_image, batch_id):
        ticket_number = "TK-2024-001"
        page_number = 1
        
        def mock_save_image(image, path, **kwargs):
            # Create the file so it exists when checked
            Path(path).touch()
            return True
        
        with patch.object(export_service.image_utils, 'generate_image_filename') as mock_gen, \
             patch.object(export_service.image_utils, 'save_image_as_png', side_effect=mock_save_image) as mock_save:
            
            expected_filename = f"{ticket_number}_page_{page_number}.png"
            mock_gen.return_value = expected_filename
            
            result = export_service.save_ticket_image(sample_image, batch_id, ticket_number, page_number)
            
            assert result['success'] is True
            assert result['filename'] == expected_filename
            assert 'image_path' in result
            assert result['file_size_bytes'] >= 0
            
            mock_gen.assert_called_once_with(ticket_number, page_number)
            mock_save.assert_called_once()
    
    def test_save_ticket_image_success_without_ticket_number(self, export_service, sample_image, batch_id):
        page_number = 2
        
        def mock_save_image(image, path, **kwargs):
            # Create the file so it exists when checked
            Path(path).touch()
            return True
        
        with patch.object(export_service.image_utils, 'generate_image_filename') as mock_gen, \
             patch.object(export_service.image_utils, 'save_image_as_png', side_effect=mock_save_image):
            
            expected_filename = f"unknown_ticket_page_{page_number}.png"
            mock_gen.return_value = expected_filename
            
            result = export_service.save_ticket_image(sample_image, batch_id, None, page_number)
            
            assert result['success'] is True
            assert result['filename'] == expected_filename
            mock_gen.assert_called_once_with(None, page_number)
    
    def test_save_ticket_image_save_failure(self, export_service, sample_image, batch_id):
        with patch.object(export_service.image_utils, 'generate_image_filename') as mock_gen, \
             patch.object(export_service.image_utils, 'save_image_as_png') as mock_save:
            
            mock_gen.return_value = "test.png"
            mock_save.return_value = False
            
            result = export_service.save_ticket_image(sample_image, batch_id, "TK-001", 1)
            
            assert result['success'] is False
            assert 'error' in result
    
    def test_save_ticket_image_exception_handling(self, export_service, sample_image, batch_id):
        with patch.object(export_service.image_utils, 'generate_image_filename') as mock_gen:
            mock_gen.side_effect = Exception("Filename generation error")
            
            result = export_service.save_ticket_image(sample_image, batch_id, "TK-001", 1)
            
            assert result['success'] is False
            assert 'error' in result
            assert "Filename generation error" in result['error']
    
    def test_ensure_unique_filename_no_conflict(self, export_service, temp_dir):
        test_path = Path(temp_dir) / "test.png"
        
        result = export_service._ensure_unique_filename(test_path)
        
        assert result == test_path
    
    def test_ensure_unique_filename_with_conflict(self, export_service, temp_dir):
        test_path = Path(temp_dir) / "test.png"
        test_path.touch()  # Create the file
        
        result = export_service._ensure_unique_filename(test_path)
        
        assert result != test_path
        assert result.name == "test_1.png"
    
    def test_get_image_path_existing_file(self, export_service, batch_id):
        filename = "test.png"
        
        # Create the expected directory structure and file
        images_dir = export_service._get_batch_images_directory(batch_id)
        test_file = images_dir / filename
        test_file.touch()
        
        result = export_service.get_image_path(batch_id, filename)
        
        assert result == test_file
        assert result.exists()
    
    def test_get_image_path_nonexistent_file(self, export_service, batch_id):
        result = export_service.get_image_path(batch_id, "nonexistent.png")
        assert result is None
    
    def test_delete_image_success(self, export_service, batch_id):
        filename = "test.png"
        
        # Create the file
        images_dir = export_service._get_batch_images_directory(batch_id)
        test_file = images_dir / filename
        test_file.touch()
        
        result = export_service.delete_image(batch_id, filename)
        
        assert result is True
        assert not test_file.exists()
    
    def test_delete_image_not_found(self, export_service, batch_id):
        result = export_service.delete_image(batch_id, "nonexistent.png")
        assert result is False
    
    def test_list_batch_images_empty(self, export_service, batch_id):
        result = export_service.list_batch_images(batch_id)
        assert result == []
    
    def test_list_batch_images_with_files(self, export_service, batch_id):
        # Create some test files
        images_dir = export_service._get_batch_images_directory(batch_id)
        
        test_files = ["image1.png", "image2.png", "image3.png"]
        for filename in test_files:
            (images_dir / filename).touch()
        
        result = export_service.list_batch_images(batch_id)
        
        assert len(result) == 3
        filenames = [img['filename'] for img in result]
        for filename in test_files:
            assert filename in filenames
    
    def test_get_batch_images_info_empty(self, export_service, batch_id):
        result = export_service.get_batch_images_info(batch_id)
        
        assert result['batch_id'] == batch_id
        assert result['image_count'] == 0
        assert result['total_size_bytes'] == 0
        assert result['total_size_mb'] == 0.0
        assert result['images'] == []
    
    def test_get_batch_images_info_with_files(self, export_service, batch_id):
        # Create some test files with content
        images_dir = export_service._get_batch_images_directory(batch_id)
        
        test_content = b"fake image data"
        for i in range(3):
            test_file = images_dir / f"image{i}.png"
            test_file.write_bytes(test_content)
        
        result = export_service.get_batch_images_info(batch_id)
        
        assert result['batch_id'] == batch_id
        assert result['image_count'] == 3
        assert result['total_size_bytes'] == len(test_content) * 3
        assert result['total_size_mb'] > 0
    
    def test_cleanup_batch_images_success(self, export_service, batch_id):
        # Create some test files
        images_dir = export_service._get_batch_images_directory(batch_id)
        
        test_files = []
        for i in range(3):
            test_file = images_dir / f"image{i}.png"
            test_file.touch()
            test_files.append(test_file)
        
        result = export_service.cleanup_batch_images(batch_id)
        
        assert result['success'] is True
        assert result['deleted_count'] == 3
        assert len(result['errors']) == 0
        
        for test_file in test_files:
            assert not test_file.exists()
    
    def test_cleanup_batch_images_empty(self, export_service, batch_id):
        result = export_service.cleanup_batch_images(batch_id)
        
        assert result['success'] is True
        assert result['deleted_count'] == 0
        assert len(result['errors']) == 0
    
    def test_verify_image_integrity_valid(self, export_service, batch_id, sample_image):
        filename = "test.png"
        
        # Save a real image
        images_dir = export_service._get_batch_images_directory(batch_id)
        image_path = images_dir / filename
        sample_image.save(image_path, format='PNG')
        
        result = export_service.verify_image_integrity(batch_id, filename)
        
        assert result is True
    
    def test_verify_image_integrity_invalid(self, export_service, batch_id):
        filename = "invalid.png"
        
        # Create a file with invalid image data
        images_dir = export_service._get_batch_images_directory(batch_id)
        image_path = images_dir / filename
        image_path.write_bytes(b"not an image")
        
        result = export_service.verify_image_integrity(batch_id, filename)
        
        assert result is False
    
    def test_verify_image_integrity_not_found(self, export_service, batch_id):
        result = export_service.verify_image_integrity(batch_id, "nonexistent.png")
        assert result is False
    
    def test_get_export_statistics_empty(self, export_service):
        result = export_service.get_export_statistics()
        
        assert result['total_batches'] == 0
        assert result['total_images'] == 0
        assert result['total_size_bytes'] == 0
        assert result['total_size_mb'] == 0.0
        assert result['batch_details'] == []
    
    def test_get_export_statistics_with_data(self, export_service):
        # Create multiple batches with images
        batch_ids = ["batch1", "batch2"]
        test_content = b"fake image data"
        
        for batch_id in batch_ids:
            images_dir = export_service._get_batch_images_directory(batch_id)
            for i in range(2):
                test_file = images_dir / f"image{i}.png"
                test_file.write_bytes(test_content)
        
        result = export_service.get_export_statistics()
        
        assert result['total_batches'] == 2
        assert result['total_images'] == 4
        assert result['total_size_bytes'] == len(test_content) * 4
        assert result['total_size_mb'] > 0
        assert len(result['batch_details']) == 2
    
    def test_save_multiple_images_same_batch(self, export_service, batch_id):
        images_data = [
            (Image.new('RGB', (400, 300), color='red'), "TK-001", 1),
            (Image.new('RGB', (400, 300), color='green'), "TK-002", 1),
            (Image.new('RGB', (400, 300), color='blue'), None, 2)
        ]
        
        def mock_save_image(image, path, **kwargs):
            # Create the file so it exists when checked
            Path(path).touch()
            return True
        
        with patch.object(export_service.image_utils, 'generate_image_filename') as mock_gen, \
             patch.object(export_service.image_utils, 'save_image_as_png', side_effect=mock_save_image):
            
            mock_gen.side_effect = [
                "TK-001_page_1.png",
                "TK-002_page_1.png", 
                "unknown_ticket_page_2.png"
            ]
            
            results = []
            for image, ticket_number, page_number in images_data:
                result = export_service.save_ticket_image(image, batch_id, ticket_number, page_number)
                results.append(result)
            
            assert all(result['success'] for result in results)
            filenames = [result['filename'] for result in results]
            assert len(set(filenames)) == 3  # All unique filenames
    
    def test_result_structure_completeness(self, export_service, sample_image, batch_id):
        def mock_save_image(image, path, **kwargs):
            # Create the file so it exists when checked
            Path(path).touch()
            return True
        
        with patch.object(export_service.image_utils, 'generate_image_filename') as mock_gen, \
             patch.object(export_service.image_utils, 'save_image_as_png', side_effect=mock_save_image):
            
            mock_gen.return_value = "test.png"
            
            result = export_service.save_ticket_image(sample_image, batch_id, "TK-001", 1)
            
            required_keys = ['success', 'filename', 'image_path', 'file_size_bytes']
            for key in required_keys:
                assert key in result
            
            assert isinstance(result['success'], bool)
            assert isinstance(result['filename'], str)
            assert isinstance(result['image_path'], str)
            assert isinstance(result['file_size_bytes'], int)
    
    def test_result_structure_on_failure(self, export_service, sample_image, batch_id):
        with patch.object(export_service.image_utils, 'generate_image_filename') as mock_gen:
            mock_gen.side_effect = Exception("Test error")
            
            result = export_service.save_ticket_image(sample_image, batch_id, "TK-001", 1)
            
            required_keys = ['success', 'error']
            for key in required_keys:
                assert key in result
            
            assert result['success'] is False
            assert isinstance(result['error'], str)
            assert len(result['error']) > 0
    
    def test_base_path_creation_error_handling(self):
        # Test with invalid path (should not raise exception)
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            mock_mkdir.side_effect = PermissionError("Permission denied")
            
            # Should not raise exception, just log error
            service = ImageExportService(base_path="/invalid/path")
            assert isinstance(service, ImageExportService)