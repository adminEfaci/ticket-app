from pathlib import Path
from typing import List, Tuple, Optional, Union
from PIL import Image
from pdf2image import convert_from_path
import io
import logging

from ..utils.image_utils import ImageUtils

logger = logging.getLogger(__name__)


class PDFExtractionService:
    """
    Service for extracting images from PDF pages using pdf2image
    """
    
    def __init__(self):
        self.image_utils = ImageUtils()
        self.default_dpi = 300  # High quality for OCR
        self.min_page_width = 100
        self.min_page_height = 100
    
    def extract_pages_as_images(self, pdf_path: Union[str, Path]) -> List[Tuple[int, Image.Image]]:
        """
        Extract all pages from PDF as PIL Images
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            List of tuples (page_number, PIL_Image)
            
        Raises:
            ValueError: If PDF cannot be opened or is invalid
        """
        try:
            pdf_path = Path(pdf_path)
            if not pdf_path.exists():
                raise ValueError(f"PDF file not found: {pdf_path}")
            
            if not pdf_path.suffix.lower() == '.pdf':
                raise ValueError(f"File is not a PDF: {pdf_path}")
            
            # Convert PDF to images using pdf2image
            try:
                images = convert_from_path(
                    str(pdf_path),
                    dpi=self.default_dpi,
                    fmt='PNG'
                )
            except Exception as e:
                raise ValueError(f"Failed to open PDF: {e}")
            
            if not images:
                raise ValueError("PDF contains no pages")
            
            extracted_images = []
            
            for page_num, image in enumerate(images, 1):
                try:
                    # Check if page has reasonable dimensions
                    if image.width < self.min_page_width or image.height < self.min_page_height:
                        logger.warning(f"Page {page_num} has very small dimensions: {image.width}x{image.height}")
                        continue
                    
                    # Apply any image enhancements
                    enhanced_image = self.image_utils.enhance_image_for_ocr(image)
                    
                    if enhanced_image:
                        extracted_images.append((page_num, enhanced_image))
                        logger.info(f"Successfully extracted page {page_num}")
                    else:
                        logger.warning(f"Failed to enhance page {page_num}")
                        
                except Exception as e:
                    logger.error(f"Error processing page {page_num}: {e}")
                    continue
            
            if not extracted_images:
                raise ValueError("No pages could be extracted from PDF")
            
            logger.info(f"Extracted {len(extracted_images)} pages from PDF")
            return extracted_images
            
        except Exception as e:
            logger.error(f"Error extracting pages from PDF: {e}")
            raise ValueError(f"Failed to extract pages from PDF: {e}")
    
    def _convert_page_to_image(self, pdf_path: Union[str, Path], page_number: int) -> Optional[Image.Image]:
        """
        Convert a specific PDF page to PIL Image
        
        Args:
            pdf_path: Path to the PDF file
            page_number: Page number to convert (1-based)
            
        Returns:
            PIL Image or None if conversion fails
        """
        try:
            # Convert specific page using pdf2image
            images = convert_from_path(
                str(pdf_path),
                dpi=self.default_dpi,
                fmt='PNG',
                first_page=page_number,
                last_page=page_number
            )
            
            if images:
                pil_image = images[0]
                # Set DPI info for the image
                pil_image.info['dpi'] = (self.default_dpi, self.default_dpi)
                
                logger.debug(f"Page {page_number} converted to {pil_image.size} image at {self.default_dpi} DPI")
                return pil_image
            
            return None
            
        except Exception as e:
            logger.error(f"Error converting page {page_number} to image: {e}")
            return None
    
    def detect_and_crop_tickets(self, image: Image.Image, page_number: int) -> List[Tuple[Image.Image, dict]]:
        """
        Detect and crop individual tickets from a page image
        
        Args:
            image: PIL Image of the full page
            page_number: Page number for logging
            
        Returns:
            List of tuples (cropped_ticket_image, metadata_dict)
        """
        try:
            ticket_results = []
            
            # Detect multiple ticket boundaries on the page
            boundaries_list = self.image_utils.detect_multiple_tickets(image)
            
            logger.info(f"Page {page_number}: Detected {len(boundaries_list)} ticket(s)")
            
            for idx, boundaries in enumerate(boundaries_list):
                try:
                    # Crop to detected boundaries
                    cropped_image = self.image_utils.crop_image(image, boundaries)
                    
                    # Validate that cropped image has sufficient content
                    if self.image_utils.validate_image_completeness(cropped_image):
                        # Try to extract ticket number from the image
                        ticket_number = self.image_utils.extract_ticket_number_from_image(cropped_image)
                        
                        # Create metadata for this ticket
                        metadata = {
                            'page_number': page_number,
                            'ticket_index': idx,
                            'boundaries': boundaries,
                            'detected_ticket_number': ticket_number,
                            'image_size': cropped_image.size
                        }
                        
                        ticket_results.append((cropped_image, metadata))
                        logger.info(f"Page {page_number}, Ticket {idx}: Successfully extracted (Number: {ticket_number or 'Unknown'})")
                    else:
                        logger.warning(f"Page {page_number}, Ticket {idx}: Cropped area appears to be mostly empty")
                        
                except Exception as e:
                    logger.error(f"Error processing ticket {idx} on page {page_number}: {e}")
            
            # If no tickets were successfully extracted, try the full page
            if not ticket_results and self.image_utils.validate_image_completeness(image):
                metadata = {
                    'page_number': page_number,
                    'ticket_index': 0,
                    'boundaries': (0, 0, image.size[0], image.size[1]),
                    'detected_ticket_number': None,
                    'image_size': image.size
                }
                ticket_results.append((image, metadata))
                logger.warning(f"Page {page_number}: Using full page as single ticket")
            
            return ticket_results
            
        except Exception as e:
            logger.error(f"Error detecting tickets on page {page_number}: {e}")
            return []
    
    def enhance_image_for_processing(self, image: Image.Image) -> Image.Image:
        """
        Enhance image for better OCR and quality validation
        
        Args:
            image: Original PIL Image
            
        Returns:
            Enhanced PIL Image
        """
        try:
            # Apply enhancement for OCR
            enhanced = self.image_utils.enhance_image_for_ocr(image)
            
            logger.debug(f"Enhanced image for processing: {enhanced.size}")
            return enhanced
            
        except Exception as e:
            logger.error(f"Error enhancing image: {e}")
            return image
    
    def validate_pdf_file(self, pdf_path: Union[str, Path]) -> bool:
        """
        Validate that the file is a readable PDF
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            True if valid PDF, False otherwise
        """
        try:
            pdf_path = Path(pdf_path)
            
            if not pdf_path.exists():
                logger.error(f"PDF file does not exist: {pdf_path}")
                return False
            
            if not pdf_path.suffix.lower() == '.pdf':
                logger.error(f"File is not a PDF: {pdf_path}")
                return False
            
            # Try to convert first page to check if PDF is valid
            try:
                images = convert_from_path(
                    str(pdf_path),
                    dpi=72,  # Low DPI for quick validation
                    fmt='PNG',
                    first_page=1,
                    last_page=1
                )
                
                if not images:
                    logger.error(f"PDF contains no pages: {pdf_path}")
                    return False
                
                logger.info(f"Valid PDF: {pdf_path}")
                return True
                
            except Exception as e:
                logger.error(f"PDF is not readable: {e}")
                return False
            
        except Exception as e:
            logger.error(f"Error validating PDF: {e}")
            return False
    
    def get_pdf_info(self, pdf_path: Union[str, Path]) -> dict:
        """
        Get information about the PDF file
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Dictionary with PDF information
        """
        try:
            pdf_path = Path(pdf_path)
            
            # Get basic file info
            info = {
                'file_size': pdf_path.stat().st_size,
                'pages_info': []
            }
            
            # Convert first few pages to get page info
            try:
                # First, get page count by converting with low DPI
                test_images = convert_from_path(
                    str(pdf_path),
                    dpi=72,  # Low DPI for quick info gathering
                    fmt='PNG'
                )
                
                info['page_count'] = len(test_images)
                
                # Get detailed info for first 10 pages
                for i, image in enumerate(test_images[:10]):
                    page_info = {
                        'page_number': i + 1,
                        'width': image.width,
                        'height': image.height
                    }
                    info['pages_info'].append(page_info)
                
                # pdf2image doesn't provide metadata, so we'll leave it empty
                info['metadata'] = {}
                
            except Exception as e:
                logger.error(f"Error converting PDF for info: {e}")
                info['page_count'] = 0
                info['error'] = str(e)
            
            return info
            
        except Exception as e:
            logger.error(f"Error getting PDF info: {e}")
            return {
                'page_count': 0,
                'file_size': 0,
                'metadata': {},
                'pages_info': [],
                'error': str(e)
            }
    
    def extract_specific_pages(self, pdf_path: Union[str, Path], 
                             page_numbers: List[int]) -> List[Tuple[int, Image.Image]]:
        """
        Extract specific pages from PDF
        
        Args:
            pdf_path: Path to the PDF file
            page_numbers: List of page numbers to extract (1-based)
            
        Returns:
            List of tuples (page_number, PIL_Image)
        """
        try:
            pdf_path = Path(pdf_path)
            extracted_images = []
            
            # First get total page count to validate page numbers
            try:
                test_images = convert_from_path(
                    str(pdf_path),
                    dpi=72,  # Low DPI just to get page count
                    fmt='PNG'
                )
                total_pages = len(test_images)
            except Exception as e:
                logger.error(f"Error getting page count: {e}")
                return []
            
            for page_num in page_numbers:
                try:
                    if page_num < 1 or page_num > total_pages:
                        logger.warning(f"Page {page_num} does not exist in PDF (total pages: {total_pages})")
                        continue
                    
                    pil_image = self._convert_page_to_image(pdf_path, page_num)
                    
                    if pil_image:
                        # Apply enhancements
                        enhanced_image = self.image_utils.enhance_image_for_ocr(pil_image)
                        if enhanced_image:
                            extracted_images.append((page_num, enhanced_image))
                        else:
                            extracted_images.append((page_num, pil_image))
                        
                except Exception as e:
                    logger.error(f"Error extracting page {page_num}: {e}")
                    continue
            
            return extracted_images
            
        except Exception as e:
            logger.error(f"Error extracting specific pages: {e}")
            return []