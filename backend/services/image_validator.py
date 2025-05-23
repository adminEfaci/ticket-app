from typing import Optional, List, Dict, Any
from PIL import Image
import logging

from ..utils.image_utils import ImageUtils

logger = logging.getLogger(__name__)


class ImageValidator:
    """
    Service for validating image quality according to business rules
    """
    
    def __init__(self):
        self.image_utils = ImageUtils()
        
        # Business rule thresholds
        self.min_dpi = 150.0
        self.min_contrast_ratio = 30.0
        self.max_file_size_mb = 5.0
        self.min_completeness_percentage = 10.0
        
        # Minimum image dimensions
        self.min_width = 100
        self.min_height = 100
        
        # Maximum image dimensions (reasonable limits)
        self.max_width = 10000
        self.max_height = 10000
    
    def validate_image(self, image: Image.Image) -> Dict[str, Any]:
        """
        Comprehensive image validation against all business rules
        
        Args:
            image: PIL Image to validate
            
        Returns:
            Dictionary with validation results:
            {
                'valid': bool,
                'errors': List[str],
                'warnings': List[str],
                'metrics': {
                    'dpi': Tuple[float, float],
                    'contrast_ratio': float,
                    'estimated_size_mb': float,
                    'completeness_percentage': float,
                    'dimensions': Tuple[int, int]
                }
            }
        """
        result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'metrics': {}
        }
        
        try:
            # Validate dimensions
            self._validate_dimensions(image, result)
            
            # Validate DPI
            self._validate_dpi(image, result)
            
            # Validate contrast
            self._validate_contrast(image, result)
            
            # Validate file size
            self._validate_file_size(image, result)
            
            # Validate completeness
            self._validate_completeness(image, result)
            
            # Overall validation result
            result['valid'] = len(result['errors']) == 0
            
            if result['valid']:
                logger.info("Image passed all validation checks")
            else:
                logger.warning(f"Image validation failed: {result['errors']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error during image validation: {e}")
            return {
                'valid': False,
                'errors': [f"Validation error: {str(e)}"],
                'warnings': [],
                'metrics': {}
            }
    
    def _validate_dimensions(self, image: Image.Image, result: Dict[str, Any]) -> None:
        """Validate image dimensions"""
        try:
            width, height = image.size
            result['metrics']['dimensions'] = (width, height)
            
            # Check minimum dimensions
            if width < self.min_width or height < self.min_height:
                result['errors'].append(
                    f"Image dimensions too small: {width}x{height}. "
                    f"Minimum: {self.min_width}x{self.min_height}"
                )
            
            # Check maximum dimensions
            if width > self.max_width or height > self.max_height:
                result['errors'].append(
                    f"Image dimensions too large: {width}x{height}. "
                    f"Maximum: {self.max_width}x{self.max_height}"
                )
            
            # Check aspect ratio (warn if unusual)
            aspect_ratio = width / height if height > 0 else 0
            if aspect_ratio < 0.1 or aspect_ratio > 10.0:
                result['warnings'].append(
                    f"Unusual aspect ratio: {aspect_ratio:.2f}. "
                    "This might indicate incorrect cropping."
                )
                
        except Exception as e:
            result['errors'].append(f"Error validating dimensions: {e}")
    
    def _validate_dpi(self, image: Image.Image, result: Dict[str, Any]) -> None:
        """Validate image DPI"""
        try:
            dpi_x, dpi_y = self.image_utils.calculate_dpi(image)
            result['metrics']['dpi'] = (dpi_x, dpi_y)
            
            # Use the lower of the two DPI values
            effective_dpi = min(dpi_x, dpi_y)
            
            if effective_dpi < self.min_dpi:
                result['errors'].append(
                    f"Image DPI too low: {effective_dpi:.1f}. "
                    f"Minimum required: {self.min_dpi}"
                )
            
            # Warn if DPI values are very different
            if abs(dpi_x - dpi_y) > 20:
                result['warnings'].append(
                    f"DPI mismatch: X={dpi_x:.1f}, Y={dpi_y:.1f}. "
                    "This might indicate scaling issues."
                )
                
        except Exception as e:
            result['errors'].append(f"Error validating DPI: {e}")
    
    def _validate_contrast(self, image: Image.Image, result: Dict[str, Any]) -> None:
        """Validate image contrast ratio"""
        try:
            contrast_ratio = self.image_utils.calculate_contrast_ratio(image)
            result['metrics']['contrast_ratio'] = contrast_ratio
            
            if contrast_ratio < self.min_contrast_ratio:
                result['errors'].append(
                    f"Image contrast too low: {contrast_ratio:.1f}%. "
                    f"Minimum required: {self.min_contrast_ratio}%"
                )
            
            # Warn if contrast is very high (might indicate issues)
            if contrast_ratio > 90.0:
                result['warnings'].append(
                    f"Very high contrast detected: {contrast_ratio:.1f}%. "
                    "This might indicate over-processing or artifacts."
                )
                
        except Exception as e:
            result['errors'].append(f"Error validating contrast: {e}")
    
    def _validate_file_size(self, image: Image.Image, result: Dict[str, Any]) -> None:
        """Validate estimated file size"""
        try:
            estimated_size_mb = self.image_utils.get_image_size_mb(image)
            result['metrics']['estimated_size_mb'] = estimated_size_mb
            
            if estimated_size_mb > self.max_file_size_mb:
                result['errors'].append(
                    f"Estimated file size too large: {estimated_size_mb:.2f}MB. "
                    f"Maximum allowed: {self.max_file_size_mb}MB"
                )
            
            # Warn if file size is very small
            if estimated_size_mb < 0.01:  # 10KB
                result['warnings'].append(
                    f"Very small estimated file size: {estimated_size_mb:.3f}MB. "
                    "This might indicate a mostly empty image."
                )
                
        except Exception as e:
            result['errors'].append(f"Error validating file size: {e}")
    
    def _validate_completeness(self, image: Image.Image, result: Dict[str, Any]) -> None:
        """Validate image completeness (not mostly blank)"""
        try:
            is_complete = self.image_utils.validate_image_completeness(
                image, self.min_completeness_percentage
            )
            
            if not is_complete:
                result['errors'].append(
                    f"Image appears to be mostly blank. "
                    f"Minimum content required: {self.min_completeness_percentage}%"
                )
            
            # Calculate actual completeness percentage for metrics
            try:
                import numpy as np
                if image.mode != 'L':
                    gray = image.convert('L')
                else:
                    gray = image
                
                img_array = np.array(gray)
                non_white_pixels = np.sum(img_array < 240)
                total_pixels = img_array.size
                completeness_percentage = (non_white_pixels / total_pixels) * 100.0
                
                result['metrics']['completeness_percentage'] = completeness_percentage
                
            except Exception:
                result['metrics']['completeness_percentage'] = 0.0
                
        except Exception as e:
            result['errors'].append(f"Error validating completeness: {e}")
    
    def validate_quick(self, image: Image.Image) -> bool:
        """
        Quick validation check (basic requirements only)
        
        Args:
            image: PIL Image to validate
            
        Returns:
            True if image passes basic validation
        """
        try:
            # Check dimensions
            width, height = image.size
            if width < self.min_width or height < self.min_height:
                return False
            
            # Check DPI
            dpi_x, dpi_y = self.image_utils.calculate_dpi(image)
            if min(dpi_x, dpi_y) < self.min_dpi:
                return False
            
            # Check if not mostly blank
            if not self.image_utils.validate_image_completeness(image):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error in quick validation: {e}")
            return False
    
    def get_validation_summary(self, validation_result: Dict[str, Any]) -> str:
        """
        Get a human-readable summary of validation results
        
        Args:
            validation_result: Result from validate_image()
            
        Returns:
            Summary string
        """
        if validation_result['valid']:
            metrics = validation_result['metrics']
            dpi = metrics.get('dpi', (0, 0))
            contrast = metrics.get('contrast_ratio', 0)
            size = metrics.get('estimated_size_mb', 0)
            dims = metrics.get('dimensions', (0, 0))
            
            summary = (
                f"✓ Valid image: {dims[0]}x{dims[1]} pixels, "
                f"{min(dpi):.1f} DPI, {contrast:.1f}% contrast, "
                f"{size:.2f}MB estimated"
            )
            
            if validation_result['warnings']:
                summary += f" ({len(validation_result['warnings'])} warnings)"
            
            return summary
        else:
            error_count = len(validation_result['errors'])
            summary = f"✗ Invalid image: {error_count} errors"
            
            if validation_result['errors']:
                # Include first error for context
                summary += f" - {validation_result['errors'][0]}"
            
            return summary
    
    def set_validation_thresholds(self, **kwargs) -> None:
        """
        Update validation thresholds
        
        Args:
            **kwargs: Threshold values to update
                min_dpi: Minimum DPI
                min_contrast_ratio: Minimum contrast percentage
                max_file_size_mb: Maximum file size in MB
                min_completeness_percentage: Minimum content percentage
        """
        if 'min_dpi' in kwargs:
            self.min_dpi = float(kwargs['min_dpi'])
            
        if 'min_contrast_ratio' in kwargs:
            self.min_contrast_ratio = float(kwargs['min_contrast_ratio'])
            
        if 'max_file_size_mb' in kwargs:
            self.max_file_size_mb = float(kwargs['max_file_size_mb'])
            
        if 'min_completeness_percentage' in kwargs:
            self.min_completeness_percentage = float(kwargs['min_completeness_percentage'])
        
        logger.info(f"Updated validation thresholds: DPI≥{self.min_dpi}, "
                   f"Contrast≥{self.min_contrast_ratio}%, "
                   f"Size≤{self.max_file_size_mb}MB, "
                   f"Content≥{self.min_completeness_percentage}%")
    
    def validate_batch_images(self, images: List[Image.Image]) -> Dict[str, Any]:
        """
        Validate a batch of images and provide summary statistics
        
        Args:
            images: List of PIL Images to validate
            
        Returns:
            Dictionary with batch validation results
        """
        results = {
            'total_images': len(images),
            'valid_images': 0,
            'invalid_images': 0,
            'total_errors': 0,
            'total_warnings': 0,
            'individual_results': []
        }
        
        for i, image in enumerate(images):
            validation_result = self.validate_image(image)
            results['individual_results'].append(validation_result)
            
            if validation_result['valid']:
                results['valid_images'] += 1
            else:
                results['invalid_images'] += 1
            
            results['total_errors'] += len(validation_result['errors'])
            results['total_warnings'] += len(validation_result['warnings'])
        
        results['success_rate'] = (results['valid_images'] / results['total_images'] * 100.0 
                                 if results['total_images'] > 0 else 0.0)
        
        return results