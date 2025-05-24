import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4
from PIL import Image, ImageDraw

from backend.services.pdf_extraction_service import PDFExtractionService
from backend.services.ocr_service import OCRService
from backend.services.image_validator import ImageValidator
from backend.services.image_export_service import ImageExportService
from backend.services.ticket_image_service import TicketImageService
from backend.models.ticket_image import TicketImageCreate


class TestPDFImageExtractionFlow:
    """Integration tests for the complete PDF to ticket image extraction flow"""
    
    @pytest.fixture
    def temp_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def mock_db(self):
        return Mock()
    
    @pytest.fixture
    def batch_id(self):
        return str(uuid4())
    
    @pytest.fixture
    def services(self, temp_dir, mock_db):
        """Create all services needed for integration testing"""
        return {
            'pdf_service': PDFExtractionService(),
            'ocr_service': OCRService(),
            'validator': ImageValidator(),
            'export_service': ImageExportService(base_path=temp_dir),
            'ticket_service': TicketImageService(db=mock_db)
        }
    
    @pytest.fixture
    def sample_ticket_image(self):
        """Create a sample ticket image with text"""
        img = Image.new('RGB', (800, 600), color='white')
        draw = ImageDraw.Draw(img)
        
        # Add ticket-like content
        draw.rectangle([50, 50, 750, 550], outline='black', width=3)
        draw.text((100, 100), "TICKET", fill='black')
        draw.text((100, 150), "TK-2024-001", fill='black')
        draw.text((100, 200), "Event: Concert", fill='black')
        draw.text((100, 250), "Date: 2024-12-31", fill='black')
        draw.text((100, 300), "Seat: A-15", fill='black')
        
        return img
    
    def create_mock_pdf(self, temp_dir, images):
        """Create a mock PDF file with the given images"""
        pdf_path = Path(temp_dir) / "test_tickets.pdf"
        
        # For testing, we'll create a simple PDF-like file
        # In a real scenario, this would be a proper PDF with PyMuPDF
        with open(pdf_path, 'wb') as f:
            f.write(b'%PDF-1.4 mock content')
        
        return pdf_path
    
    def test_complete_extraction_flow_success(self, services, temp_dir, batch_id, sample_ticket_image):
        """Test the complete extraction flow from PDF to database"""
        
        # Create mock PDF
        pdf_path = self.create_mock_pdf(temp_dir, [sample_ticket_image])
        
        # Mock PDF extraction to return our sample image
        with patch.object(services['pdf_service'], 'extract_pages_as_images') as mock_extract:
            mock_extract.return_value = [(1, sample_ticket_image)]
            
            # Mock ticket detection to return the full image
            with patch.object(services['pdf_service'], 'detect_and_crop_tickets') as mock_detect:
                mock_detect.return_value = [sample_ticket_image]
                
                # Mock OCR to return a ticket number
                with patch.object(services['ocr_service'], 'extract_ticket_number') as mock_ocr:
                    mock_ocr.return_value = ("TK-2024-001", 95.0)
                    
                    # Mock image validation to pass
                    with patch.object(services['validator'], 'validate_image') as mock_validate:
                        mock_validate.return_value = {
                            'valid': True,
                            'errors': [],
                            'warnings': [],
                            'metrics': {'dpi': 300, 'contrast': 85.0, 'size_mb': 2.5}
                        }
                        
                        # Mock database operations
                        services['ticket_service'].db.add.return_value = None
                        services['ticket_service'].db.commit.return_value = None
                        services['ticket_service'].db.refresh.return_value = None
                        
                        # Execute the complete flow
                        result = self.execute_complete_flow(
                            services, pdf_path, batch_id
                        )
                        
                        # Verify the flow executed successfully
                        assert result['success'] is True
                        assert result['pages_processed'] == 1
                        assert result['images_extracted'] == 1
                        assert result['images_failed'] == 0
                        
                        # Verify all services were called
                        mock_extract.assert_called_once()
                        mock_detect.assert_called_once()
                        mock_ocr.assert_called_once()
                        mock_validate.assert_called_once()
    
    def test_extraction_flow_with_validation_failure(self, services, temp_dir, batch_id, sample_ticket_image):
        """Test extraction flow when image validation fails"""
        
        pdf_path = self.create_mock_pdf(temp_dir, [sample_ticket_image])
        
        with patch.object(services['pdf_service'], 'extract_pages_as_images') as mock_extract:
            mock_extract.return_value = [(1, sample_ticket_image)]
            
            with patch.object(services['pdf_service'], 'detect_and_crop_tickets') as mock_detect:
                mock_detect.return_value = [sample_ticket_image]
                
                with patch.object(services['ocr_service'], 'extract_ticket_number') as mock_ocr:
                    mock_ocr.return_value = ("TK-2024-001", 95.0)
                    
                    # Mock validation to fail
                    with patch.object(services['validator'], 'validate_image') as mock_validate:
                        mock_validate.return_value = {
                            'valid': False,
                            'errors': ['DPI too low: 100. Minimum required: 150'],
                            'warnings': [],
                            'metrics': {'dpi': 100, 'contrast': 85.0, 'size_mb': 2.5}
                        }
                        
                        result = self.execute_complete_flow(
                            services, pdf_path, batch_id
                        )
                        
                        # Should still process but mark as failed
                        assert result['success'] is True  # Flow completes
                        assert result['pages_processed'] == 1
                        assert result['images_extracted'] == 0  # But no valid images
                        assert result['images_failed'] == 1
    
    def test_extraction_flow_with_ocr_failure(self, services, temp_dir, batch_id, sample_ticket_image):
        """Test extraction flow when OCR fails to find ticket number"""
        
        pdf_path = self.create_mock_pdf(temp_dir, [sample_ticket_image])
        
        with patch.object(services['pdf_service'], 'extract_pages_as_images') as mock_extract:
            mock_extract.return_value = [(1, sample_ticket_image)]
            
            with patch.object(services['pdf_service'], 'detect_and_crop_tickets') as mock_detect:
                mock_detect.return_value = [sample_ticket_image]
                
                # Mock OCR to fail
                with patch.object(services['ocr_service'], 'extract_ticket_number') as mock_ocr:
                    mock_ocr.return_value = (None, 0.0)
                    
                    with patch.object(services['validator'], 'validate_image') as mock_validate:
                        mock_validate.return_value = {
                            'valid': True,
                            'errors': [],
                            'warnings': [],
                            'metrics': {'dpi': 300, 'contrast': 85.0, 'size_mb': 2.5}
                        }
                        
                        # Mock database operations
                        services['ticket_service'].db.add.return_value = None
                        services['ticket_service'].db.commit.return_value = None
                        services['ticket_service'].db.refresh.return_value = None
                        
                        result = self.execute_complete_flow(
                            services, pdf_path, batch_id
                        )
                        
                        # Should still save image but without ticket number
                        assert result['success'] is True
                        assert result['pages_processed'] == 1
                        assert result['images_extracted'] == 1
                        assert result['ocr_low_confidence'] == 1
    
    def test_extraction_flow_multiple_pages(self, services, temp_dir, batch_id):
        """Test extraction flow with multiple PDF pages"""
        
        # Create multiple sample images
        images = []
        for i in range(3):
            img = Image.new('RGB', (800, 600), color='white')
            draw = ImageDraw.Draw(img)
            draw.rectangle([50, 50, 750, 550], outline='black', width=3)
            draw.text((100, 100), f"TICKET {i+1}", fill='black')
            draw.text((100, 150), f"TK-2024-{i+1:03d}", fill='black')
            images.append(img)
        
        pdf_path = self.create_mock_pdf(temp_dir, images)
        
        with patch.object(services['pdf_service'], 'extract_pages_as_images') as mock_extract:
            # Return all pages
            mock_extract.return_value = [(i+1, img) for i, img in enumerate(images)]
            
            with patch.object(services['pdf_service'], 'detect_and_crop_tickets') as mock_detect:
                # Each page has one ticket
                mock_detect.side_effect = [[img] for img in images]
                
                with patch.object(services['ocr_service'], 'extract_ticket_number') as mock_ocr:
                    # Return different ticket numbers for each
                    mock_ocr.side_effect = [
                        (f"TK-2024-{i+1:03d}", 90.0 + i) for i in range(3)
                    ]
                    
                    with patch.object(services['validator'], 'validate_image') as mock_validate:
                        mock_validate.return_value = {
                            'valid': True,
                            'errors': [],
                            'warnings': [],
                            'metrics': {'dpi': 300, 'contrast': 85.0, 'size_mb': 2.5}
                        }
                        
                        # Mock database operations
                        services['ticket_service'].db.add.return_value = None
                        services['ticket_service'].db.commit.return_value = None
                        services['ticket_service'].db.refresh.return_value = None
                        
                        result = self.execute_complete_flow(
                            services, pdf_path, batch_id
                        )
                        
                        # Should process all pages and extract all tickets
                        assert result['success'] is True
                        assert result['pages_processed'] == 3
                        assert result['images_extracted'] == 3
                        assert result['images_failed'] == 0
    
    def test_extraction_flow_pdf_error(self, services, temp_dir, batch_id):
        """Test extraction flow when PDF processing fails"""
        
        pdf_path = Path(temp_dir) / "invalid.pdf"
        pdf_path.write_text("not a pdf")
        
        with patch.object(services['pdf_service'], 'extract_pages_as_images') as mock_extract:
            mock_extract.side_effect = ValueError("Invalid PDF file")
            
            result = self.execute_complete_flow(
                services, pdf_path, batch_id
            )
            
            # Should handle error gracefully
            assert result['success'] is False
            assert 'error' in result
            assert 'Invalid PDF file' in result['error']
    
    def test_extraction_flow_with_image_export(self, services, temp_dir, batch_id, sample_ticket_image):
        """Test that images are properly exported to the file system"""
        
        pdf_path = self.create_mock_pdf(temp_dir, [sample_ticket_image])
        
        with patch.object(services['pdf_service'], 'extract_pages_as_images') as mock_extract:
            mock_extract.return_value = [(1, sample_ticket_image)]
            
            with patch.object(services['pdf_service'], 'detect_and_crop_tickets') as mock_detect:
                mock_detect.return_value = [sample_ticket_image]
                
                with patch.object(services['ocr_service'], 'extract_ticket_number') as mock_ocr:
                    mock_ocr.return_value = ("TK-2024-001", 95.0)
                    
                    with patch.object(services['validator'], 'validate_image') as mock_validate:
                        mock_validate.return_value = {
                            'valid': True,
                            'errors': [],
                            'warnings': [],
                            'metrics': {'dpi': 300, 'contrast': 85.0, 'size_mb': 2.5}
                        }
                        
                        # Mock database operations
                        services['ticket_service'].db.add.return_value = None
                        services['ticket_service'].db.commit.return_value = None
                        services['ticket_service'].db.refresh.return_value = None
                        
                        result = self.execute_complete_flow(
                            services, pdf_path, batch_id
                        )
                        
                        # Verify image was exported
                        assert result['success'] is True
                        
                        # Check that batch directory was created
                        batch_dir = Path(temp_dir) / batch_id / "images"
                        assert batch_dir.exists()
    
    def test_extraction_flow_service_integration(self, services, temp_dir, batch_id, sample_ticket_image):
        """Test that all services work together correctly"""
        
        pdf_path = self.create_mock_pdf(temp_dir, [sample_ticket_image])
        
        with patch.object(services['pdf_service'], 'extract_pages_as_images') as mock_extract:
            mock_extract.return_value = [(1, sample_ticket_image)]
            
            with patch.object(services['pdf_service'], 'detect_and_crop_tickets') as mock_detect:
                mock_detect.return_value = [sample_ticket_image]
                
                # Test actual OCR service integration
                with patch('backend.services.ocr_service.pytesseract.image_to_data') as mock_tesseract:
                    mock_tesseract.return_value = {
                        'text': ['', 'TICKET', 'TK-2024-001', 'Event', ''],
                        'conf': [0, 85, 95, 80, 0]
                    }
                    
                    # Test actual validation service integration
                    with patch.object(services['validator'].image_utils, 'calculate_dpi') as mock_dpi, \
                         patch.object(services['validator'].image_utils, 'calculate_contrast_ratio') as mock_contrast, \
                         patch.object(services['validator'].image_utils, 'get_image_size_mb') as mock_size, \
                         patch.object(services['validator'].image_utils, 'validate_image_completeness') as mock_complete:
                        
                        mock_dpi.return_value = (300, 300)
                        mock_contrast.return_value = 85.0
                        mock_size.return_value = 2.5
                        mock_complete.return_value = True
                        
                        # Mock database operations
                        services['ticket_service'].db.add.return_value = None
                        services['ticket_service'].db.commit.return_value = None
                        services['ticket_service'].db.refresh.return_value = None
                        
                        result = self.execute_complete_flow(
                            services, pdf_path, batch_id
                        )
                        
                        # Verify integration worked
                        assert result['success'] is True
                        assert result['images_extracted'] == 1
                        
                        # Verify services were called with expected data
                        mock_tesseract.assert_called_once()
                        mock_dpi.assert_called_once()
                        mock_contrast.assert_called_once()
    
    def execute_complete_flow(self, services, pdf_path, batch_id):
        """Execute the complete PDF to ticket image extraction flow"""
        try:
            # Step 1: Extract pages from PDF
            page_images = services['pdf_service'].extract_pages_as_images(pdf_path)
            
            if not page_images:
                return {
                    'success': False,
                    'error': 'No pages could be extracted from PDF'
                }
            
            # Initialize extraction results
            extraction_result = {
                'success': True,
                'pages_processed': len(page_images),
                'images_extracted': 0,
                'images_failed': 0,
                'ocr_low_confidence': 0,
                'quality_failed': 0,
                'extraction_errors': []
            }
            
            # Step 2: Process each page
            for page_number, page_image in page_images:
                try:
                    # Step 3: Detect and crop tickets on the page
                    cropped_tickets = services['pdf_service'].detect_and_crop_tickets(page_image, page_number)
                    
                    if not cropped_tickets:
                        cropped_tickets = [page_image]  # Use full page if no tickets detected
                    
                    # Step 4: Process each detected ticket
                    for ticket_index, ticket_image in enumerate(cropped_tickets):
                        try:
                            # Step 5: Extract ticket number using OCR
                            ticket_number, ocr_confidence = services['ocr_service'].extract_ticket_number(ticket_image)
                            
                            if ocr_confidence < 80.0:
                                extraction_result['ocr_low_confidence'] += 1
                            
                            # Step 6: Validate image quality
                            validation_result = services['validator'].validate_image(ticket_image)
                            
                            if not validation_result['valid']:
                                extraction_result['quality_failed'] += 1
                                extraction_result['images_failed'] += 1
                                continue
                            
                            # Step 7: Save image to file system
                            export_result = services['export_service'].save_ticket_image(
                                ticket_image, batch_id, ticket_number, page_number
                            )
                            
                            if not export_result['success']:
                                extraction_result['images_failed'] += 1
                                extraction_result['extraction_errors'].append(
                                    f"Failed to save image: {export_result.get('error', 'Unknown error')}"
                                )
                                continue
                            
                            # Step 8: Save ticket image record to database
                            ticket_image_data = TicketImageCreate(
                                batch_id=batch_id,
                                page_number=page_number,
                                image_path=export_result['image_path'],
                                ticket_number=ticket_number,
                                ocr_confidence=ocr_confidence / 100.0 if ocr_confidence > 0 else None,
                                valid=validation_result['valid']
                            )
                            
                            services['ticket_service'].create_ticket_image(ticket_image_data)
                            extraction_result['images_extracted'] += 1
                            
                        except Exception as e:
                            extraction_result['images_failed'] += 1
                            extraction_result['extraction_errors'].append(
                                f"Error processing ticket {ticket_index} on page {page_number}: {str(e)}"
                            )
                
                except Exception as e:
                    extraction_result['images_failed'] += 1
                    extraction_result['extraction_errors'].append(
                        f"Error processing page {page_number}: {str(e)}"
                    )
            
            return extraction_result
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def test_error_recovery_and_logging(self, services, temp_dir, batch_id, sample_ticket_image):
        """Test that the flow handles errors gracefully and logs appropriately"""
        
        pdf_path = self.create_mock_pdf(temp_dir, [sample_ticket_image])
        
        with patch.object(services['pdf_service'], 'extract_pages_as_images') as mock_extract:
            mock_extract.return_value = [(1, sample_ticket_image), (2, sample_ticket_image)]
            
            with patch.object(services['pdf_service'], 'detect_and_crop_tickets') as mock_detect:
                # First page succeeds, second page fails
                mock_detect.side_effect = [
                    [sample_ticket_image],  # Page 1 success
                    Exception("Ticket detection failed")  # Page 2 error
                ]
                
                with patch.object(services['ocr_service'], 'extract_ticket_number') as mock_ocr:
                    mock_ocr.return_value = ("TK-2024-001", 95.0)
                    
                    with patch.object(services['validator'], 'validate_image') as mock_validate:
                        mock_validate.return_value = {
                            'valid': True,
                            'errors': [],
                            'warnings': [],
                            'metrics': {'dpi': 300, 'contrast': 85.0, 'size_mb': 2.5}
                        }
                        
                        # Mock database operations
                        services['ticket_service'].db.add.return_value = None
                        services['ticket_service'].db.commit.return_value = None
                        services['ticket_service'].db.refresh.return_value = None
                        
                        result = self.execute_complete_flow(
                            services, pdf_path, batch_id
                        )
                        
                        # Should process what it can and log errors
                        assert result['success'] is True
                        assert result['pages_processed'] == 2
                        assert result['images_extracted'] == 1  # Only page 1 succeeded
                        assert result['images_failed'] == 1   # Page 2 failed
                        assert len(result['extraction_errors']) == 1
                        assert 'Ticket detection failed' in result['extraction_errors'][0]