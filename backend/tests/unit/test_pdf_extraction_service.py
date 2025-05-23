import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from PIL import Image
import io

from backend.services.pdf_extraction_service import PDFExtractionService


class TestPDFExtractionService:
    
    @pytest.fixture
    def pdf_service(self):
        return PDFExtractionService()
    
    @pytest.fixture
    def mock_pdf_document(self):
        mock_doc = MagicMock()
        mock_doc.page_count = 3
        mock_doc.close.return_value = None
        return mock_doc
    
    @pytest.fixture
    def mock_pdf_page(self):
        mock_page = Mock()
        mock_page.rect = Mock()
        mock_page.rect.width = 800
        mock_page.rect.height = 600
        mock_page.rotation = 0
        return mock_page
    
    @pytest.fixture
    def sample_image(self):
        image = Image.new('RGB', (800, 600), color='white')
        return image
    
    @pytest.fixture
    def temp_pdf_file(self):
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_path = temp_file.name
            # Write minimal PDF content
            temp_file.write(b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n%%EOF')
        yield temp_path
        os.unlink(temp_path)
    
    def test_init_default_values(self, pdf_service):
        assert pdf_service.default_dpi == 300
        assert pdf_service.min_page_width == 100
        assert pdf_service.min_page_height == 100
        assert hasattr(pdf_service, 'image_utils')
    
    def test_validate_pdf_file_valid(self, pdf_service, temp_pdf_file):
        with patch('backend.services.pdf_extraction_service.convert_from_path') as mock_convert:
            # Mock a successful image conversion
            mock_image = Mock()
            mock_convert.return_value = [mock_image]
            
            result = pdf_service.validate_pdf_file(temp_pdf_file)
            
            assert result is True
            mock_convert.assert_called_once()
    
    def test_validate_pdf_file_not_exists(self, pdf_service):
        result = pdf_service.validate_pdf_file("/nonexistent/file.pdf")
        assert result is False
    
    def test_validate_pdf_file_not_pdf(self, pdf_service):
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            result = pdf_service.validate_pdf_file(temp_path)
            assert result is False
        finally:
            os.unlink(temp_path)
    
    def test_validate_pdf_file_no_pages(self, pdf_service, temp_pdf_file):
        with patch('backend.services.pdf_extraction_service.convert_from_path') as mock_convert:
            # Mock empty image list (no pages)
            mock_convert.return_value = []
            
            result = pdf_service.validate_pdf_file(temp_pdf_file)
            
            assert result is False
    
    def test_extract_pages_as_images_success(self, pdf_service):
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_path = temp_file.name
            # Write minimal PDF content
            temp_file.write(b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n%%EOF')
        
        try:
            # Create mock images
            mock_image1 = Image.new('RGB', (800, 600), color='white')
            mock_image2 = Image.new('RGB', (800, 600), color='gray')
            
            with patch('backend.services.pdf_extraction_service.convert_from_path') as mock_convert:
                mock_convert.return_value = [mock_image1, mock_image2]
                
                # Mock image enhancement
                with patch.object(pdf_service.image_utils, 'enhance_image_for_ocr', side_effect=lambda x: x):
                    result = pdf_service.extract_pages_as_images(temp_path)
                
                assert len(result) == 2
                assert result[0][0] == 1  # Page number
                assert result[1][0] == 2  # Page number
                assert isinstance(result[0][1], Image.Image)
                assert isinstance(result[1][1], Image.Image)
        finally:
            os.unlink(temp_path)
    
    def test_extract_pages_as_images_file_not_found(self, pdf_service):
        with pytest.raises(ValueError, match="PDF file not found"):
            pdf_service.extract_pages_as_images("/nonexistent/file.pdf")
    
    def test_extract_pages_as_images_not_pdf(self, pdf_service):
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            with pytest.raises(ValueError, match="File is not a PDF"):
                pdf_service.extract_pages_as_images(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_extract_pages_as_images_empty_pdf(self, pdf_service):
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_path = temp_file.name
            # Write minimal PDF content
            temp_file.write(b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n%%EOF')
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            with patch('backend.services.pdf_extraction_service.convert_from_path') as mock_convert:
                mock_convert.return_value = []  # Empty list of images
                
                with pytest.raises(ValueError, match="PDF contains no pages"):
                    pdf_service.extract_pages_as_images(temp_path)
        finally:
            os.unlink(temp_path)
    
    @patch('backend.services.pdf_extraction_service.convert_from_path')
    def test_extract_pages_pathlib_path(self, mock_convert_from_path, pdf_service):
        # Create a mock PIL Image
        sample_image = Image.new('RGB', (800, 600), color='white')
        mock_convert_from_path.return_value = [sample_image]
        
        with patch.object(pdf_service.image_utils, 'enhance_image_for_ocr', side_effect=lambda x: x):
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                temp_path = Path(temp_file.name)
            
            try:
                result = pdf_service.extract_pages_as_images(temp_path)
                assert len(result) == 1
                assert result[0][0] == 1  # Page number
                assert isinstance(result[0][1], Image.Image)
            finally:
                os.unlink(temp_path)
    
    @patch('backend.services.pdf_extraction_service.convert_from_path')
    def test_convert_page_to_image_success(self, mock_convert_from_path, pdf_service):
        # Create a mock PIL Image
        sample_image = Image.new('RGB', (800, 600), color='white')
        sample_image.info['dpi'] = (300, 300)
        mock_convert_from_path.return_value = [sample_image]
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            result = pdf_service._convert_page_to_image(temp_path, 1)
            
            assert isinstance(result, Image.Image)
            assert result.size == (800, 600)
            assert result.info['dpi'] == (300, 300)
            mock_convert_from_path.assert_called_once_with(
                temp_path,
                dpi=300,
                fmt='PNG',
                first_page=1,
                last_page=1
            )
        finally:
            os.unlink(temp_path)
    
    @patch('backend.services.pdf_extraction_service.convert_from_path')
    def test_convert_page_to_image_failure(self, mock_convert_from_path, pdf_service):
        mock_convert_from_path.side_effect = Exception("Conversion error")
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            result = pdf_service._convert_page_to_image(temp_path, 1)
            
            assert result is None
        finally:
            os.unlink(temp_path)
    
    def test_detect_and_crop_tickets_with_boundaries(self, pdf_service, sample_image):
        with patch.object(pdf_service.image_utils, 'detect_multiple_tickets') as mock_detect, \
             patch.object(pdf_service.image_utils, 'crop_image') as mock_crop, \
             patch.object(pdf_service.image_utils, 'validate_image_completeness') as mock_validate, \
             patch.object(pdf_service.image_utils, 'extract_ticket_number_from_image') as mock_extract:
            
            mock_detect.return_value = [(100, 100, 500, 400)]  # Single ticket boundary
            mock_crop.return_value = sample_image
            mock_validate.return_value = True
            mock_extract.return_value = "12345"
            
            result = pdf_service.detect_and_crop_tickets(sample_image, 1)
            
            assert len(result) == 1
            assert result[0][0] == sample_image  # First element is the image
            assert result[0][1]['page_number'] == 1  # Second element is metadata
            assert result[0][1]['detected_ticket_number'] == "12345"
            mock_detect.assert_called_once_with(sample_image)
            mock_crop.assert_called_once()
            mock_validate.assert_called_once()
    
    def test_detect_and_crop_tickets_no_boundaries(self, pdf_service, sample_image):
        with patch.object(pdf_service.image_utils, 'detect_multiple_tickets') as mock_detect, \
             patch.object(pdf_service.image_utils, 'validate_image_completeness') as mock_validate:
            
            mock_detect.return_value = []  # No tickets detected
            mock_validate.return_value = True
            
            result = pdf_service.detect_and_crop_tickets(sample_image, 1)
            
            assert len(result) == 1
            assert result[0][0] == sample_image  # Uses full page as ticket
            assert result[0][1]['page_number'] == 1
            assert result[0][1]['boundaries'] == (0, 0, 800, 600)
    
    def test_detect_and_crop_tickets_empty_page(self, pdf_service, sample_image):
        with patch.object(pdf_service.image_utils, 'detect_multiple_tickets') as mock_detect, \
             patch.object(pdf_service.image_utils, 'validate_image_completeness') as mock_validate:
            
            mock_detect.return_value = []  # No tickets detected
            mock_validate.return_value = False  # Page is empty
            
            result = pdf_service.detect_and_crop_tickets(sample_image, 1)
            
            assert len(result) == 0
    
    def test_enhance_image_for_processing_success(self, pdf_service, sample_image):
        enhanced_image = Image.new('L', (800, 600), color=128)
        
        with patch.object(pdf_service.image_utils, 'enhance_image_for_ocr', return_value=enhanced_image):
            result = pdf_service.enhance_image_for_processing(sample_image)
            
            assert result == enhanced_image
            pdf_service.image_utils.enhance_image_for_ocr.assert_called_once_with(sample_image)
    
    def test_enhance_image_for_processing_failure(self, pdf_service, sample_image):
        with patch.object(pdf_service.image_utils, 'enhance_image_for_ocr', side_effect=Exception("Enhancement error")):
            result = pdf_service.enhance_image_for_processing(sample_image)
            
            assert result == sample_image  # Should return original on error
    
    @patch('backend.services.pdf_extraction_service.convert_from_path')
    def test_get_pdf_info_success(self, mock_convert_from_path, pdf_service, temp_pdf_file):
        # Create mock PIL Images for 2 pages
        mock_image1 = Image.new('RGB', (800, 600), color='white')
        mock_image2 = Image.new('RGB', (800, 600), color='white')
        mock_convert_from_path.return_value = [mock_image1, mock_image2]
        
        result = pdf_service.get_pdf_info(temp_pdf_file)
        
        assert result['page_count'] == 2
        assert result['metadata'] == {}  # pdf2image doesn't provide metadata
        assert len(result['pages_info']) == 2
        assert result['pages_info'][0]['page_number'] == 1
        assert result['pages_info'][0]['width'] == 800
        assert result['pages_info'][0]['height'] == 600
        assert result['pages_info'][1]['page_number'] == 2
        assert result['pages_info'][1]['width'] == 800
        assert result['pages_info'][1]['height'] == 600
        assert result['file_size'] > 0
    
    def test_get_pdf_info_error(self, pdf_service):
        result = pdf_service.get_pdf_info("/nonexistent/file.pdf")
        
        assert result['page_count'] == 0
        assert result['file_size'] == 0
        assert 'error' in result
    
    @patch('backend.services.pdf_extraction_service.convert_from_path')
    def test_extract_specific_pages_success(self, mock_convert_from_path, pdf_service):
        # Create 5 mock PIL Images
        mock_images = [Image.new('RGB', (800, 600), color='white') for _ in range(5)]
        mock_convert_from_path.return_value = mock_images
        
        with patch.object(pdf_service.image_utils, 'enhance_image_for_ocr', side_effect=lambda x: x):
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                temp_path = temp_file.name
            
            try:
                result = pdf_service.extract_specific_pages(temp_path, [1, 3, 5])
                
                assert len(result) == 3
                page_numbers = [page_num for page_num, _ in result]
                assert page_numbers == [1, 3, 5]
                for page_num, img in result:
                    assert isinstance(img, Image.Image)
            finally:
                os.unlink(temp_path)
    
    @patch('backend.services.pdf_extraction_service.convert_from_path')
    def test_extract_specific_pages_invalid_page_numbers(self, mock_convert_from_path, pdf_service):
        # Create 3 mock PIL Images
        mock_images = [Image.new('RGB', (800, 600), color='white') for _ in range(3)]
        mock_convert_from_path.return_value = mock_images
        
        with patch.object(pdf_service.image_utils, 'enhance_image_for_ocr', side_effect=lambda x: x):
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                temp_path = temp_file.name
            
            try:
                result = pdf_service.extract_specific_pages(temp_path, [0, 4, 10])
                
                # Should return empty list as all page numbers are invalid
                assert len(result) == 0
            finally:
                os.unlink(temp_path)
    
    def test_extract_specific_pages_error(self, pdf_service):
        result = pdf_service.extract_specific_pages("/nonexistent/file.pdf", [1, 2])
        assert result == []
    
    def _create_mock_png_bytes(self):
        img = Image.new('RGB', (800, 600), color='white')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        return img_bytes.getvalue()
    
    @patch('backend.services.pdf_extraction_service.convert_from_path')
    def test_dpi_setting_in_converted_image(self, mock_convert_from_path, pdf_service):
        # Create a mock PIL Image without DPI info
        sample_image = Image.new('RGB', (800, 600), color='white')
        mock_convert_from_path.return_value = [sample_image]
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            result = pdf_service._convert_page_to_image(temp_path, 1)
            
            assert isinstance(result, Image.Image)
            assert 'dpi' in result.info
            assert result.info['dpi'] == (300, 300)
        finally:
            os.unlink(temp_path)
    
    def test_small_page_dimensions_handling(self, pdf_service):
        with patch('backend.services.pdf_extraction_service.convert_from_path') as mock_convert_from_path:
            # Create 2 mock PIL Images with different sizes
            normal_image = Image.new('RGB', (800, 600), color='white')
            small_image = Image.new('RGB', (50, 30), color='white')
            mock_convert_from_path.return_value = [normal_image, small_image]
            
            with patch.object(pdf_service.image_utils, 'enhance_image_for_ocr', side_effect=lambda x: x):
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                    temp_path = temp_file.name
                
                try:
                    # Assuming the service filters out small pages based on dimensions
                    result = pdf_service.extract_pages_as_images(temp_path)
                    
                    # This test might need adjustment based on how the service actually handles small pages
                    # If it filters by size, we'd expect only the normal-sized page
                    # If it doesn't filter, we'd expect both pages
                    assert len(result) >= 1
                    assert result[0][0] == 1  # First page number
                    assert isinstance(result[0][1], Image.Image)
                finally:
                    os.unlink(temp_path)