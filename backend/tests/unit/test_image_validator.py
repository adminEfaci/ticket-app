import pytest
from PIL import Image, ImageDraw
from unittest.mock import Mock, patch

from backend.services.image_validator import ImageValidator


class TestImageValidator:
    
    @pytest.fixture
    def validator(self):
        return ImageValidator()
    
    @pytest.fixture
    def valid_image(self):
        """Create a valid test image"""
        image = Image.new('RGB', (300, 200), color='white')
        # Add some content to make it non-blank
        draw = ImageDraw.Draw(image)
        draw.rectangle([50, 50, 250, 150], fill='black')
        draw.text((100, 100), "TEST TICKET", fill='white')
        
        # Set DPI info
        image.info['dpi'] = (300, 300)
        return image
    
    @pytest.fixture
    def small_image(self):
        """Create an image that's too small"""
        return Image.new('RGB', (50, 30), color='white')
    
    @pytest.fixture
    def large_image(self):
        """Create an image that's too large"""
        return Image.new('RGB', (15000, 10000), color='white')
    
    @pytest.fixture
    def low_dpi_image(self):
        """Create an image with low DPI"""
        image = Image.new('RGB', (300, 200), color='white')
        draw = ImageDraw.Draw(image)
        draw.rectangle([50, 50, 250, 150], fill='black')
        image.info['dpi'] = (72, 72)  # Low DPI
        return image
    
    @pytest.fixture
    def blank_image(self):
        """Create a mostly blank image"""
        return Image.new('RGB', (300, 200), color='white')
    
    def test_validate_valid_image(self, validator, valid_image):
        """Test validation of a valid image"""
        result = validator.validate_image(valid_image)
        
        assert result['valid'] is True
        assert len(result['errors']) == 0
        assert 'metrics' in result
        assert 'dpi' in result['metrics']
        assert 'contrast_ratio' in result['metrics']
        assert 'estimated_size_mb' in result['metrics']
        assert 'dimensions' in result['metrics']
    
    def test_validate_small_image(self, validator, small_image):
        """Test validation fails for small image"""
        result = validator.validate_image(small_image)
        
        assert result['valid'] is False
        assert any('dimensions too small' in error for error in result['errors'])
        assert result['metrics']['dimensions'] == (50, 30)
    
    def test_validate_large_image(self, validator, large_image):
        """Test validation fails for oversized image"""
        result = validator.validate_image(large_image)
        
        assert result['valid'] is False
        assert any('dimensions too large' in error for error in result['errors'])
        assert result['metrics']['dimensions'] == (15000, 10000)
    
    def test_validate_low_dpi_image(self, validator, low_dpi_image):
        """Test validation fails for low DPI image"""
        result = validator.validate_image(low_dpi_image)
        
        assert result['valid'] is False
        assert any('DPI too low' in error for error in result['errors'])
        assert result['metrics']['dpi'] == (72.0, 72.0)
    
    def test_validate_blank_image(self, validator, blank_image):
        """Test validation fails for mostly blank image"""
        result = validator.validate_image(blank_image)
        
        assert result['valid'] is False
        assert any('mostly blank' in error for error in result['errors'])
    
    def test_quick_validation_valid(self, validator, valid_image):
        """Test quick validation for valid image"""
        result = validator.validate_quick(valid_image)
        assert result is True
    
    def test_quick_validation_invalid(self, validator, small_image):
        """Test quick validation for invalid image"""
        result = validator.validate_quick(small_image)
        assert result is False
    
    def test_validation_summary_valid(self, validator, valid_image):
        """Test validation summary for valid image"""
        result = validator.validate_image(valid_image)
        summary = validator.get_validation_summary(result)
        
        assert "✓ Valid image" in summary
        assert "300x200 pixels" in summary
    
    def test_validation_summary_invalid(self, validator, small_image):
        """Test validation summary for invalid image"""
        result = validator.validate_image(small_image)
        summary = validator.get_validation_summary(result)
        
        assert "✗ Invalid image" in summary
        assert "errors" in summary
    
    def test_set_validation_thresholds(self, validator):
        """Test updating validation thresholds"""
        original_min_dpi = validator.min_dpi
        
        validator.set_validation_thresholds(min_dpi=200.0, min_contrast_ratio=40.0)
        
        assert validator.min_dpi == 200.0
        assert validator.min_contrast_ratio == 40.0
        
        # Reset for other tests
        validator.min_dpi = original_min_dpi
    
    def test_validate_batch_images(self, validator, valid_image, small_image):
        """Test batch validation of multiple images"""
        images = [valid_image, small_image, valid_image]
        
        result = validator.validate_batch_images(images)
        
        assert result['total_images'] == 3
        assert result['valid_images'] == 2
        assert result['invalid_images'] == 1
        assert result['success_rate'] == (2/3 * 100.0)
        assert len(result['individual_results']) == 3
    
    def test_contrast_calculation(self, validator):
        """Test contrast calculation with known values"""
        # Create high contrast image
        high_contrast = Image.new('RGB', (100, 100), color='white')
        draw = ImageDraw.Draw(high_contrast)
        draw.rectangle([0, 0, 50, 100], fill='black')
        
        # Create low contrast image (all gray)
        low_contrast = Image.new('RGB', (100, 100), color='gray')
        
        high_result = validator.validate_image(high_contrast)
        low_result = validator.validate_image(low_contrast)
        
        # High contrast should have higher contrast ratio
        assert high_result['metrics']['contrast_ratio'] > low_result['metrics']['contrast_ratio']
    
    def test_dpi_validation_with_different_values(self, validator):
        """Test DPI validation with different x and y values"""
        image = Image.new('RGB', (300, 200), color='white')
        draw = ImageDraw.Draw(image)
        draw.rectangle([50, 50, 250, 150], fill='black')
        
        # Set mismatched DPI values
        image.info['dpi'] = (300, 150)
        
        result = validator.validate_image(image)
        
        # Should use the lower DPI value for validation
        assert result['metrics']['dpi'] == (300.0, 150.0)
        
        # Should fail because min DPI is 150 and lower value is 150
        # Actually this should pass since min(300, 150) = 150 which equals threshold
        
        # Test with values below threshold
        image.info['dpi'] = (300, 100)
        result = validator.validate_image(image)
        assert result['valid'] is False  # Should fail because min(300, 100) = 100 < 150
    
    def test_file_size_estimation(self, validator):
        """Test file size estimation"""
        # Create images of different sizes
        small = Image.new('RGB', (100, 100), color='white')
        large = Image.new('RGB', (1000, 1000), color='white')
        
        small_result = validator.validate_image(small)
        large_result = validator.validate_image(large)
        
        # Large image should have larger estimated size
        assert large_result['metrics']['estimated_size_mb'] > small_result['metrics']['estimated_size_mb']
    
    def test_aspect_ratio_warning(self, validator):
        """Test aspect ratio warning for unusual dimensions"""
        # Create very wide image
        wide_image = Image.new('RGB', (1000, 50), color='white')
        draw = ImageDraw.Draw(wide_image)
        draw.rectangle([100, 10, 900, 40], fill='black')
        wide_image.info['dpi'] = (300, 300)
        
        result = validator.validate_image(wide_image)
        
        # Should have warning about unusual aspect ratio
        assert any('aspect ratio' in warning for warning in result['warnings'])
    
    def test_validation_error_handling(self, validator):
        """Test validation with corrupted image data"""
        # Test with None image - should return invalid result, not raise exception
        result = validator.validate_image(None)
        assert result['valid'] is False
        assert len(result['errors']) > 0
    
    @patch('backend.services.image_validator.ImageUtils')
    def test_validation_with_utils_error(self, mock_utils, validator):
        """Test validation when utils methods fail"""
        # Mock utils to raise exceptions
        mock_utils_instance = Mock()
        mock_utils_instance.calculate_dpi.side_effect = Exception("DPI calculation failed")
        mock_utils_instance.calculate_contrast_ratio.side_effect = Exception("Contrast calculation failed")
        mock_utils_instance.get_image_size_mb.side_effect = Exception("Size calculation failed")
        mock_utils_instance.validate_image_completeness.side_effect = Exception("Completeness check failed")
        
        validator.image_utils = mock_utils_instance
        
        # Create simple test image
        test_image = Image.new('RGB', (300, 200), color='white')
        
        result = validator.validate_image(test_image)
        
        # Should have errors for failed calculations
        assert result['valid'] is False
        assert len(result['errors']) > 0
    
    def test_custom_thresholds_validation(self, validator):
        """Test validation with custom thresholds"""
        # Set very strict thresholds
        validator.set_validation_thresholds(
            min_dpi=400.0,
            min_contrast_ratio=60.0,
            max_file_size_mb=1.0,
            min_completeness_percentage=50.0
        )
        
        # Create image that would normally pass
        image = Image.new('RGB', (300, 200), color='white')
        draw = ImageDraw.Draw(image)
        draw.rectangle([50, 50, 250, 150], fill='black')
        image.info['dpi'] = (300, 300)  # Below new threshold
        
        result = validator.validate_image(image)
        
        # Should fail with strict thresholds
        assert result['valid'] is False
        
        # Reset thresholds
        validator.set_validation_thresholds(
            min_dpi=150.0,
            min_contrast_ratio=30.0,
            max_file_size_mb=5.0
        )