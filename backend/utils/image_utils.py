import os
from pathlib import Path
from typing import Tuple, Optional, Union
from PIL import Image, ImageStat
import numpy as np
import logging

logger = logging.getLogger(__name__)


class ImageUtils:
    """Utility functions for image processing and validation"""
    
    @staticmethod
    def calculate_dpi(image: Image.Image) -> Tuple[float, float]:
        """
        Calculate DPI of an image
        
        Args:
            image: PIL Image object
            
        Returns:
            Tuple of (x_dpi, y_dpi)
        """
        try:
            # Get DPI from image info, default to 72 if not available
            dpi = image.info.get('dpi', (72, 72))
            if isinstance(dpi, (list, tuple)) and len(dpi) >= 2:
                return float(dpi[0]), float(dpi[1])
            elif isinstance(dpi, (int, float)):
                return float(dpi), float(dpi)
            else:
                return 72.0, 72.0
        except Exception as e:
            logger.warning(f"Could not determine DPI: {e}")
            return 72.0, 72.0
    
    @staticmethod
    def calculate_contrast_ratio(image: Image.Image) -> float:
        """
        Calculate contrast ratio of an image
        
        Args:
            image: PIL Image object
            
        Returns:
            Contrast ratio as percentage (0-100)
        """
        try:
            # Convert to grayscale for contrast calculation
            if image.mode != 'L':
                gray_image = image.convert('L')
            else:
                gray_image = image
            
            # Calculate standard deviation as measure of contrast
            stat = ImageStat.Stat(gray_image)
            contrast = stat.stddev[0]
            
            # Normalize to percentage (typical range 0-128 for 8-bit images)
            contrast_percentage = (contrast / 128.0) * 100.0
            
            return min(contrast_percentage, 100.0)
            
        except Exception as e:
            logger.error(f"Error calculating contrast: {e}")
            return 0.0
    
    @staticmethod
    def get_image_size_mb(image: Image.Image) -> float:
        """
        Estimate image size in MB when saved as PNG
        
        Args:
            image: PIL Image object
            
        Returns:
            Estimated size in MB
        """
        try:
            # Estimate based on dimensions and color depth
            width, height = image.size
            
            # Estimate bytes per pixel based on mode
            if image.mode == 'RGB':
                bytes_per_pixel = 3
            elif image.mode == 'RGBA':
                bytes_per_pixel = 4
            elif image.mode == 'L':
                bytes_per_pixel = 1
            else:
                bytes_per_pixel = 4  # Conservative estimate
            
            # Raw size estimate
            raw_size = width * height * bytes_per_pixel
            
            # PNG compression typically achieves 30-70% compression
            # Use 50% as middle estimate
            estimated_size = raw_size * 0.5
            
            # Convert to MB
            size_mb = estimated_size / (1024 * 1024)
            
            return size_mb
            
        except Exception as e:
            logger.error(f"Error estimating image size: {e}")
            return 0.0
    
    @staticmethod
    def crop_image(image: Image.Image, bbox: Tuple[int, int, int, int]) -> Image.Image:
        """
        Crop image to specified bounding box
        
        Args:
            image: PIL Image object
            bbox: (left, top, right, bottom) coordinates
            
        Returns:
            Cropped PIL Image
        """
        try:
            # Ensure bbox is within image bounds
            width, height = image.size
            left, top, right, bottom = bbox
            
            left = max(0, min(left, width))
            top = max(0, min(top, height))
            right = max(left, min(right, width))
            bottom = max(top, min(bottom, height))
            
            return image.crop((left, top, right, bottom))
            
        except Exception as e:
            logger.error(f"Error cropping image: {e}")
            return image
    
    @staticmethod
    def enhance_image_for_ocr(image: Image.Image) -> Image.Image:
        """
        Enhance image for better OCR results
        
        Args:
            image: PIL Image object
            
        Returns:
            Enhanced PIL Image
        """
        try:
            # Convert to grayscale
            if image.mode != 'L':
                image = image.convert('L')
            
            # Convert to numpy array for processing
            img_array = np.array(image)
            
            # Apply histogram equalization to improve contrast
            from PIL import ImageOps
            enhanced = ImageOps.equalize(image)
            
            return enhanced
            
        except Exception as e:
            logger.error(f"Error enhancing image: {e}")
            return image
    
    @staticmethod
    def save_image_as_png(image: Image.Image, output_path: Union[str, Path], 
                         optimize: bool = True, quality: int = 95) -> bool:
        """
        Save image as PNG file
        
        Args:
            image: PIL Image object
            output_path: Path where to save the image
            optimize: Whether to optimize the PNG
            quality: Quality setting (0-100)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            output_path = Path(output_path)
            
            # Ensure directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save as PNG
            save_kwargs = {
                'format': 'PNG',
                'optimize': optimize
            }
            
            # Add quality for formats that support it
            if image.mode in ('RGB', 'RGBA'):
                save_kwargs['quality'] = quality
            
            image.save(output_path, **save_kwargs)
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving image: {e}")
            return False
    
    @staticmethod
    def detect_ticket_boundaries(image: Image.Image) -> Optional[Tuple[int, int, int, int]]:
        """
        Detect ticket boundaries in an image using edge detection
        
        Args:
            image: PIL Image object
            
        Returns:
            Bounding box (left, top, right, bottom) or None if not detected
        """
        try:
            # Convert to grayscale
            if image.mode != 'L':
                gray = image.convert('L')
            else:
                gray = image
            
            # Convert to numpy array
            img_array = np.array(gray)
            
            # Simple edge detection - find significant changes in brightness
            # This is a basic implementation - could be enhanced with OpenCV
            
            # Calculate gradients
            grad_x = np.abs(np.diff(img_array, axis=1))
            grad_y = np.abs(np.diff(img_array, axis=0))
            
            # Find areas with high gradient (edges)
            threshold = np.mean(grad_x) + 2 * np.std(grad_x)
            
            # Find bounding box of high-gradient areas
            edge_pixels_x = np.where(grad_x > threshold)
            edge_pixels_y = np.where(grad_y > threshold)
            
            if len(edge_pixels_x[0]) > 0 and len(edge_pixels_x[1]) > 0:
                top = max(0, np.min(edge_pixels_x[0]) - 10)
                bottom = min(img_array.shape[0], np.max(edge_pixels_x[0]) + 10)
                left = max(0, np.min(edge_pixels_x[1]) - 10)
                right = min(img_array.shape[1], np.max(edge_pixels_x[1]) + 10)
                
                return (left, top, right, bottom)
            
            # If no clear boundaries detected, return full image
            return None
            
        except Exception as e:
            logger.error(f"Error detecting ticket boundaries: {e}")
            return None
    
    @staticmethod
    def detect_multiple_tickets(image: Image.Image) -> list[Tuple[int, int, int, int]]:
        """
        Detect multiple ticket boundaries in a single page
        Based on the sample PDFs, there are typically 2 tickets per page
        
        Args:
            image: PIL Image object of the full page
            
        Returns:
            List of bounding boxes [(left, top, right, bottom), ...]
        """
        try:
            width, height = image.size
            
            # Convert to grayscale for analysis
            if image.mode != 'L':
                gray = image.convert('L')
            else:
                gray = image
            
            img_array = np.array(gray)
            
            # Find horizontal dividing lines (strong horizontal edges)
            # Calculate horizontal gradients
            grad_y = np.abs(np.diff(img_array, axis=0))
            
            # Sum gradients across width to find strong horizontal lines
            horizontal_profile = np.sum(grad_y, axis=1)
            
            # Find peaks in horizontal profile (potential dividing lines)
            threshold = np.mean(horizontal_profile) + 2 * np.std(horizontal_profile)
            dividing_lines = np.where(horizontal_profile > threshold)[0]
            
            # Group nearby lines (within 20 pixels)
            if len(dividing_lines) > 0:
                grouped_lines = []
                current_group = [dividing_lines[0]]
                
                for i in range(1, len(dividing_lines)):
                    if dividing_lines[i] - dividing_lines[i-1] <= 20:
                        current_group.append(dividing_lines[i])
                    else:
                        grouped_lines.append(int(np.mean(current_group)))
                        current_group = [dividing_lines[i]]
                
                if current_group:
                    grouped_lines.append(int(np.mean(current_group)))
                
                # Find the most prominent dividing line near the middle
                mid_height = height // 2
                closest_to_mid = None
                min_distance = height
                
                for line in grouped_lines:
                    distance = abs(line - mid_height)
                    if distance < min_distance:
                        min_distance = distance
                        closest_to_mid = line
                
                # If we found a good dividing line, split the image
                if closest_to_mid and min_distance < height * 0.3:  # Within 30% of middle
                    # Add some margin
                    margin = 50
                    
                    # Top ticket
                    top_box = (0, 0, width, closest_to_mid + margin)
                    
                    # Bottom ticket
                    bottom_box = (0, closest_to_mid - margin, width, height)
                    
                    return [top_box, bottom_box]
            
            # Fallback: If no clear dividing line, try to split evenly
            # But first check if page seems to have multiple tickets
            if height > width * 1.5:  # Page is tall enough for multiple tickets
                mid_point = height // 2
                overlap = 50  # Some overlap to ensure we don't cut tickets
                
                top_box = (0, 0, width, mid_point + overlap)
                bottom_box = (0, mid_point - overlap, width, height)
                
                return [top_box, bottom_box]
            
            # Single ticket on page
            return [(0, 0, width, height)]
            
        except Exception as e:
            logger.error(f"Error detecting multiple tickets: {e}")
            # Return full page as single ticket on error
            return [(0, 0, image.size[0], image.size[1])]
    
    @staticmethod
    def validate_image_completeness(image: Image.Image, min_filled_percentage: float = 10.0) -> bool:
        """
        Check if image has sufficient content (not mostly blank)
        
        Args:
            image: PIL Image object
            min_filled_percentage: Minimum percentage of non-white pixels
            
        Returns:
            True if image has sufficient content
        """
        try:
            # Convert to grayscale
            if image.mode != 'L':
                gray = image.convert('L')
            else:
                gray = image
            
            # Convert to numpy array
            img_array = np.array(gray)
            
            # Count non-white pixels (assuming white is > 240)
            non_white_pixels = np.sum(img_array < 240)
            total_pixels = img_array.size
            
            filled_percentage = (non_white_pixels / total_pixels) * 100.0
            
            return filled_percentage >= min_filled_percentage
            
        except Exception as e:
            logger.error(f"Error validating image completeness: {e}")
            return False
    
    @staticmethod
    def create_batch_image_directory(batch_id: str, base_path: str = "/data/batches") -> Path:
        """
        Create directory structure for batch images
        
        Args:
            batch_id: Batch identifier
            base_path: Base path for batch storage
            
        Returns:
            Path to the images directory
        """
        try:
            images_dir = Path(base_path) / str(batch_id) / "images"
            images_dir.mkdir(parents=True, exist_ok=True)
            return images_dir
            
        except Exception as e:
            logger.error(f"Error creating batch image directory: {e}")
            raise
    
    @staticmethod
    def extract_ticket_number_from_image(image: Image.Image) -> Optional[str]:
        """
        Extract ticket number from a ticket image using OCR
        
        Args:
            image: PIL Image of the ticket
            
        Returns:
            Ticket number if found, None otherwise
        """
        try:
            import pytesseract
            import re
            
            # Enhance image for OCR
            enhanced = ImageUtils.enhance_for_ocr(image)
            
            # Extract text
            text = pytesseract.image_to_string(enhanced)
            
            # Look for ticket number pattern
            # Pattern: "TICKET #" followed by numbers
            ticket_pattern = r'TICKET\s*#\s*(\d+)'
            match = re.search(ticket_pattern, text, re.IGNORECASE)
            
            if match:
                return match.group(1)
            
            # Alternative pattern: just numbers that look like ticket numbers
            # (6 digits, starting with 17)
            alt_pattern = r'\b(17\d{4})\b'
            matches = re.findall(alt_pattern, text)
            if matches:
                return matches[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting ticket number: {e}")
            return None
    
    @staticmethod
    def generate_image_filename(ticket_number: str, page_number: int, ticket_index: int = 0) -> str:
        """
        Generate standardized filename for ticket image
        
        Args:
            ticket_number: Ticket number (if detected)
            page_number: PDF page number
            ticket_index: Index of ticket on page (for multi-ticket pages)
            
        Returns:
            Standardized filename
        """
        if ticket_number and ticket_number.strip():
            # Use ticket number if available
            safe_ticket_number = "".join(c for c in ticket_number if c.isalnum() or c in "-_")
            return f"{safe_ticket_number}_page{page_number}.png"
        else:
            # Use page number and index
            return f"ticket_page{page_number}_{ticket_index}.png"