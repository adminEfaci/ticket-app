import re
from typing import Tuple, Optional, List
from PIL import Image
import logging

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    pytesseract = None

logger = logging.getLogger(__name__)


class OCRService:
    """
    Service for extracting text from images using OCR
    """
    
    def __init__(self):
        self.min_confidence = 80.0  # Minimum confidence threshold
        self.ticket_number_patterns = [
            r'[A-Z]\d{3,6}',           # T001, TKT12345
            r'[A-Z]{2,3}-?\d{3,6}',    # TKT-001, WB123456
            r'\d{4,8}',                # 12345678
            r'[A-Z]\d{2,4}[A-Z]\d{2,4}', # T12A34
        ]
        
        if not TESSERACT_AVAILABLE:
            logger.warning("Tesseract not available. OCR functionality will be limited.")
    
    def extract_ticket_number(self, image: Image.Image) -> Tuple[Optional[str], float]:
        """
        Extract ticket number from image using OCR
        
        Args:
            image: PIL Image to process
            
        Returns:
            Tuple of (ticket_number, confidence_score)
        """
        if not TESSERACT_AVAILABLE:
            logger.warning("Tesseract not available, using fallback method")
            return self._fallback_ticket_extraction(image)
        
        try:
            # Get OCR data with confidence scores
            ocr_data = pytesseract.image_to_data(
                image, 
                output_type=pytesseract.Output.DICT,
                config='--psm 6'  # Single uniform block of text
            )
            
            # Extract text with confidence scores
            texts = []
            confidences = []
            
            for i, text in enumerate(ocr_data['text']):
                if text.strip():
                    conf = float(ocr_data['conf'][i])
                    if conf > 0:  # Valid confidence score
                        texts.append(text.strip())
                        confidences.append(conf)
            
            if not texts:
                logger.warning("No text detected by OCR")
                return None, 0.0
            
            # Find the best ticket number candidate
            best_ticket_number, best_confidence = self._find_best_ticket_number(texts, confidences)
            
            logger.info(f"OCR extracted ticket number: {best_ticket_number} (confidence: {best_confidence:.1f}%)")
            
            return best_ticket_number, best_confidence
            
        except Exception as e:
            logger.error(f"Error in OCR processing: {e}")
            return None, 0.0
    
    def _find_best_ticket_number(self, texts: List[str], confidences: List[float]) -> Tuple[Optional[str], float]:
        """
        Find the best ticket number candidate from OCR results
        
        Args:
            texts: List of detected text strings
            confidences: Corresponding confidence scores
            
        Returns:
            Tuple of (best_ticket_number, confidence)
        """
        best_candidate = None
        best_confidence = 0.0
        
        # Combine all text into a single string for pattern matching
        combined_text = ' '.join(texts)
        
        # Try each pattern
        for pattern in self.ticket_number_patterns:
            matches = re.finditer(pattern, combined_text, re.IGNORECASE)
            
            for match in matches:
                candidate = match.group().upper()
                
                # Find confidence for this candidate
                candidate_confidence = self._calculate_candidate_confidence(
                    candidate, texts, confidences
                )
                
                # Check if this is the best candidate so far
                if candidate_confidence > best_confidence:
                    best_candidate = candidate
                    best_confidence = candidate_confidence
        
        # If no pattern matches found, try to find any alphanumeric sequence
        if not best_candidate:
            for i, text in enumerate(texts):
                if len(text) >= 3 and any(c.isalnum() for c in text):
                    candidate_confidence = confidences[i]
                    if candidate_confidence > best_confidence:
                        best_candidate = text.upper()
                        best_confidence = candidate_confidence
        
        return best_candidate, best_confidence
    
    def _calculate_candidate_confidence(self, candidate: str, texts: List[str], 
                                      confidences: List[float]) -> float:
        """
        Calculate confidence score for a ticket number candidate
        
        Args:
            candidate: Potential ticket number
            texts: List of detected text strings
            confidences: Corresponding confidence scores
            
        Returns:
            Calculated confidence score
        """
        try:
            # Find which text segments contribute to this candidate
            relevant_confidences = []
            
            for i, text in enumerate(texts):
                if candidate.lower() in text.lower() or text.lower() in candidate.lower():
                    relevant_confidences.append(confidences[i])
            
            if relevant_confidences:
                # Use average confidence of relevant segments
                avg_confidence = sum(relevant_confidences) / len(relevant_confidences)
                
                # Apply bonus for pattern match
                pattern_bonus = self._get_pattern_bonus(candidate)
                
                # Final confidence (capped at 100)
                final_confidence = min(avg_confidence + pattern_bonus, 100.0)
                
                return final_confidence
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating candidate confidence: {e}")
            return 0.0
    
    def _get_pattern_bonus(self, candidate: str) -> float:
        """
        Get bonus score based on how well candidate matches expected patterns
        
        Args:
            candidate: Ticket number candidate
            
        Returns:
            Bonus score (0-20)
        """
        bonuses = []
        
        # Length bonus
        if 3 <= len(candidate) <= 8:
            bonuses.append(5.0)
        
        # Pattern match bonus
        for pattern in self.ticket_number_patterns:
            if re.match(pattern + '$', candidate, re.IGNORECASE):
                bonuses.append(10.0)
                break
        
        # Character composition bonus
        if any(c.isalpha() for c in candidate) and any(c.isdigit() for c in candidate):
            bonuses.append(5.0)
        
        return sum(bonuses)
    
    def _fallback_ticket_extraction(self, image: Image.Image) -> Tuple[Optional[str], float]:
        """
        Fallback method when Tesseract is not available
        Uses basic image analysis to estimate if ticket number might be present
        
        Args:
            image: PIL Image to process
            
        Returns:
            Tuple of (None, estimated_confidence)
        """
        try:
            # Basic heuristics for ticket presence
            width, height = image.size
            
            # Estimate confidence based on image characteristics
            confidence = 0.0
            
            # Size check
            if width > 200 and height > 100:
                confidence += 20.0
            
            # Contrast check (simplified)
            try:
                from PIL import ImageStat
                if image.mode != 'L':
                    gray = image.convert('L')
                else:
                    gray = image
                
                stat = ImageStat.Stat(gray)
                contrast = stat.stddev[0]
                
                if contrast > 30:  # Good contrast
                    confidence += 30.0
                elif contrast > 15:  # Moderate contrast
                    confidence += 15.0
                    
            except Exception:
                confidence += 10.0  # Default if can't calculate
            
            # Content check (non-white pixels)
            try:
                import numpy as np
                img_array = np.array(image.convert('L'))
                non_white_ratio = np.sum(img_array < 240) / img_array.size
                
                if non_white_ratio > 0.1:  # At least 10% content
                    confidence += 20.0
                    
            except Exception:
                confidence += 10.0  # Default if can't calculate
            
            logger.info(f"Fallback OCR estimation: confidence {confidence:.1f}%")
            
            return None, confidence
            
        except Exception as e:
            logger.error(f"Error in fallback ticket extraction: {e}")
            return None, 0.0
    
    def validate_ticket_number(self, ticket_number: str) -> bool:
        """
        Validate that extracted ticket number meets basic criteria
        
        Args:
            ticket_number: Extracted ticket number
            
        Returns:
            True if valid, False otherwise
        """
        if not ticket_number or not ticket_number.strip():
            return False
        
        # Basic validation rules
        clean_number = ticket_number.strip().upper()
        
        # Length check
        if len(clean_number) < 3 or len(clean_number) > 20:
            return False
        
        # Must contain at least one alphanumeric character
        if not any(c.isalnum() for c in clean_number):
            return False
        
        # Check against known patterns
        for pattern in self.ticket_number_patterns:
            if re.match(pattern + '$', clean_number, re.IGNORECASE):
                return True
        
        # Allow any alphanumeric string that's reasonable length
        if re.match(r'^[A-Z0-9\-_]{3,15}$', clean_number):
            return True
        
        return False
    
    def extract_all_text(self, image: Image.Image) -> Tuple[str, float]:
        """
        Extract all text from image with average confidence
        
        Args:
            image: PIL Image to process
            
        Returns:
            Tuple of (extracted_text, average_confidence)
        """
        if not TESSERACT_AVAILABLE:
            logger.warning("Tesseract not available for full text extraction")
            return "", 0.0
        
        try:
            # Extract all text
            text = pytesseract.image_to_string(image, config='--psm 6')
            
            # Get confidence data
            ocr_data = pytesseract.image_to_data(
                image, 
                output_type=pytesseract.Output.DICT
            )
            
            # Calculate average confidence
            confidences = [float(conf) for conf in ocr_data['conf'] if float(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            return text.strip(), avg_confidence
            
        except Exception as e:
            logger.error(f"Error extracting all text: {e}")
            return "", 0.0
    
    def is_ocr_available(self) -> bool:
        """
        Check if OCR functionality is available
        
        Returns:
            True if Tesseract is available, False otherwise
        """
        return TESSERACT_AVAILABLE
    
    def get_ocr_config_for_tickets(self) -> str:
        """
        Get optimized Tesseract configuration for ticket number extraction
        
        Returns:
            Tesseract configuration string
        """
        # Configuration optimized for short alphanumeric strings
        return '--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'