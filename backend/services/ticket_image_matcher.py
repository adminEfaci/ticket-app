"""
Service for matching tickets from XLS/CSV with their images from PDF
"""
from typing import List, Dict, Tuple, Optional
from uuid import UUID
import logging
from pathlib import Path

from ..models.ticket import TicketDTO, TicketUpdate
from ..services.pdf_extraction_service import PDFExtractionService
from ..services.storage_service import StorageService
from ..utils.image_utils import ImageUtils
from ..utils.fuzzy_utils import FuzzyMatcher

logger = logging.getLogger(__name__)


class TicketImageMatcher:
    """
    Service to match tickets from XLS/CSV data with their corresponding images from PDF
    """
    
    def __init__(
        self,
        pdf_service: PDFExtractionService,
        storage_service: StorageService,
        fuzzy_matcher: FuzzyMatcher
    ):
        self.pdf_service = pdf_service
        self.storage_service = storage_service
        self.fuzzy_matcher = fuzzy_matcher
        self.image_utils = ImageUtils()
    
    async def match_tickets_with_images(
        self,
        tickets: List[TicketDTO],
        pdf_path: Path,
        batch_id: UUID
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Match tickets from XLS with images from PDF
        
        Args:
            tickets: List of tickets from XLS
            pdf_path: Path to PDF file
            batch_id: Batch ID for storage
            
        Returns:
            Tuple of (matched_tickets, unmatched_items)
        """
        try:
            # Extract images from PDF
            logger.info(f"Extracting images from PDF: {pdf_path}")
            pdf_images = await self._extract_pdf_images(pdf_path, batch_id)
            
            # Create ticket lookup by number
            {t.ticket_number: t for t in tickets if t.ticket_number}
            
            # Create image lookup by detected ticket number
            image_lookup = {}
            unmatched_images = []
            
            for img_data in pdf_images:
                detected_number = img_data['metadata'].get('detected_ticket_number')
                if detected_number:
                    image_lookup[detected_number] = img_data
                else:
                    unmatched_images.append(img_data)
            
            # Match tickets with images
            matched_tickets = []
            unmatched_tickets = []
            
            for ticket in tickets:
                if not ticket.ticket_number:
                    unmatched_tickets.append({
                        'ticket': ticket,
                        'reason': 'No ticket number'
                    })
                    continue
                
                # Try exact match first
                if ticket.ticket_number in image_lookup:
                    img_data = image_lookup[ticket.ticket_number]
                    matched_tickets.append({
                        'ticket': ticket,
                        'image_path': img_data['image_path'],
                        'pdf_page_number': img_data['metadata']['page_number'],
                        'match_quality': 1.0,
                        'ocr_confidence': img_data['metadata'].get('ocr_confidence', 0.9)
                    })
                    # Remove from lookup to avoid duplicate matches
                    del image_lookup[ticket.ticket_number]
                else:
                    # Try fuzzy matching with unmatched images
                    best_match = await self._find_best_image_match(ticket, unmatched_images)
                    if best_match:
                        matched_tickets.append({
                            'ticket': ticket,
                            'image_path': best_match['image_path'],
                            'pdf_page_number': best_match['metadata']['page_number'],
                            'match_quality': best_match['match_score'],
                            'ocr_confidence': best_match['metadata'].get('ocr_confidence', 0.5)
                        })
                        unmatched_images.remove(best_match['image_data'])
                    else:
                        unmatched_tickets.append({
                            'ticket': ticket,
                            'reason': 'No matching image found'
                        })
            
            # Add remaining unmatched images to the unmatched list
            for img_data in unmatched_images:
                unmatched_tickets.append({
                    'image': img_data,
                    'reason': 'No matching ticket in XLS'
                })
            
            # Add remaining images in lookup (not matched to any ticket)
            for ticket_num, img_data in image_lookup.items():
                unmatched_tickets.append({
                    'image': img_data,
                    'detected_number': ticket_num,
                    'reason': 'Ticket number not found in XLS'
                })
            
            logger.info(f"Matching complete: {len(matched_tickets)} matched, {len(unmatched_tickets)} unmatched")
            
            return matched_tickets, unmatched_tickets
            
        except Exception as e:
            logger.error(f"Error matching tickets with images: {e}")
            raise
    
    async def _extract_pdf_images(self, pdf_path: Path, batch_id: UUID) -> List[Dict]:
        """
        Extract all ticket images from PDF
        
        Args:
            pdf_path: Path to PDF file
            batch_id: Batch ID for storage
            
        Returns:
            List of image data dictionaries
        """
        pdf_images = []
        
        # Extract pages from PDF
        page_images = self.pdf_service.extract_pages_as_images(pdf_path)
        
        for page_num, page_image in page_images:
            # Detect and crop individual tickets on this page
            ticket_results = self.pdf_service.detect_and_crop_tickets(page_image, page_num)
            
            for ticket_image, metadata in ticket_results:
                try:
                    # Generate filename
                    ticket_number = metadata.get('detected_ticket_number')
                    filename = self.image_utils.generate_image_filename(
                        ticket_number,
                        page_num,
                        metadata['ticket_index']
                    )
                    
                    # Save image
                    image_path = await self.storage_service.save_ticket_image(
                        batch_id,
                        ticket_image,
                        filename
                    )
                    
                    pdf_images.append({
                        'image_path': image_path,
                        'metadata': metadata,
                        'image': ticket_image  # Keep for fuzzy matching if needed
                    })
                    
                except Exception as e:
                    logger.error(f"Error saving ticket image from page {page_num}: {e}")
        
        return pdf_images
    
    async def _find_best_image_match(
        self,
        ticket: TicketDTO,
        unmatched_images: List[Dict]
    ) -> Optional[Dict]:
        """
        Find best matching image for a ticket using fuzzy matching
        
        Args:
            ticket: Ticket to match
            unmatched_images: List of unmatched images
            
        Returns:
            Best matching image data or None
        """
        if not unmatched_images:
            return None
        
        best_match = None
        best_score = 0.0
        
        for img_data in unmatched_images:
            # Try OCR on the image to extract text
            try:
                import pytesseract
                text = pytesseract.image_to_string(img_data['image'])
                
                # Check if ticket number appears in the text
                if ticket.ticket_number in text:
                    score = 0.9
                else:
                    # Use fuzzy matching
                    score = self.fuzzy_matcher.calculate_similarity(
                        ticket.ticket_number,
                        text[:100]  # Check first 100 chars
                    )
                
                if score > best_score and score > 0.7:  # Minimum threshold
                    best_score = score
                    best_match = {
                        'image_data': img_data,
                        'image_path': img_data['image_path'],
                        'metadata': img_data['metadata'],
                        'match_score': score
                    }
                    
            except Exception as e:
                logger.error(f"Error during fuzzy matching: {e}")
        
        return best_match
    
    def create_ticket_updates(self, matched_tickets: List[Dict]) -> List[Tuple[str, TicketUpdate]]:
        """
        Create ticket update objects with image information
        
        Args:
            matched_tickets: List of matched ticket-image pairs
            
        Returns:
            List of (ticket_number, TicketUpdate) tuples
        """
        updates = []
        
        for match in matched_tickets:
            ticket = match['ticket']
            update = TicketUpdate(
                image_path=match['image_path'],
                pdf_page_number=match['pdf_page_number'],
                pdf_source_file=match.get('pdf_source_file'),
                image_extracted=True,
                match_quality=match.get('match_quality', 1.0),
                ocr_confidence=match.get('ocr_confidence', 0.9)
            )
            updates.append((ticket.ticket_number, update))
        
        return updates
    
    def generate_matching_report(
        self,
        matched_tickets: List[Dict],
        unmatched_items: List[Dict]
    ) -> Dict:
        """
        Generate a report of the matching results
        
        Args:
            matched_tickets: List of matched tickets
            unmatched_items: List of unmatched items
            
        Returns:
            Report dictionary
        """
        report = {
            'total_matched': len(matched_tickets),
            'total_unmatched': len(unmatched_items),
            'match_rate': len(matched_tickets) / (len(matched_tickets) + len(unmatched_items)) * 100 if (len(matched_tickets) + len(unmatched_items)) > 0 else 0,
            'unmatched_tickets': [],
            'unmatched_images': [],
            'low_confidence_matches': []
        }
        
        # Categorize unmatched items
        for item in unmatched_items:
            if 'ticket' in item:
                report['unmatched_tickets'].append({
                    'ticket_number': item['ticket'].ticket_number,
                    'reason': item['reason']
                })
            elif 'image' in item:
                report['unmatched_images'].append({
                    'page_number': item['image']['metadata']['page_number'],
                    'detected_number': item.get('detected_number'),
                    'reason': item['reason']
                })
        
        # Find low confidence matches
        for match in matched_tickets:
            if match.get('match_quality', 1.0) < 0.9:
                report['low_confidence_matches'].append({
                    'ticket_number': match['ticket'].ticket_number,
                    'match_quality': match['match_quality'],
                    'ocr_confidence': match.get('ocr_confidence')
                })
        
        return report