import re
from typing import Tuple
from difflib import SequenceMatcher


class FuzzyMatchUtils:
    """Utilities for fuzzy string matching and OCR error tolerance"""
    
    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings"""
        if not s1:
            return len(s2)
        if not s2:
            return len(s1)
        
        # Create matrix
        matrix = [[0] * (len(s2) + 1) for _ in range(len(s1) + 1)]
        
        # Initialize first row and column
        for i in range(len(s1) + 1):
            matrix[i][0] = i
        for j in range(len(s2) + 1):
            matrix[0][j] = j
        
        # Fill matrix
        for i in range(1, len(s1) + 1):
            for j in range(1, len(s2) + 1):
                if s1[i-1] == s2[j-1]:
                    cost = 0
                else:
                    cost = 1
                
                matrix[i][j] = min(
                    matrix[i-1][j] + 1,      # deletion
                    matrix[i][j-1] + 1,      # insertion
                    matrix[i-1][j-1] + cost  # substitution
                )
        
        return matrix[len(s1)][len(s2)]
    
    @staticmethod
    def similarity_ratio(s1: str, s2: str) -> float:
        """Calculate similarity ratio between two strings (0.0 to 1.0)"""
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
        
        # Normalize strings
        s1_norm = s1.strip().upper()
        s2_norm = s2.strip().upper()
        
        # Use SequenceMatcher for better performance on longer strings
        return SequenceMatcher(None, s1_norm, s2_norm).ratio()
    
    @staticmethod
    def fuzzy_ticket_match(ticket1: str, ticket2: str, threshold: float = 0.8) -> Tuple[bool, float]:
        """
        Check if two ticket numbers match with fuzzy logic for OCR errors
        
        Args:
            ticket1: First ticket number
            ticket2: Second ticket number  
            threshold: Minimum similarity ratio to consider a match
            
        Returns:
            Tuple of (is_match, similarity_score)
        """
        if not ticket1 or not ticket2:
            return False, 0.0
        
        # Normalize tickets (remove spaces, standardize case)
        t1_norm = FuzzyMatchUtils.normalize_ticket_number(ticket1)
        t2_norm = FuzzyMatchUtils.normalize_ticket_number(ticket2)
        
        # Exact match gets perfect score
        if t1_norm == t2_norm:
            return True, 1.0
        
        # Calculate similarity
        similarity = FuzzyMatchUtils.similarity_ratio(t1_norm, t2_norm)
        
        # Check for common OCR errors
        ocr_adjusted_similarity = FuzzyMatchUtils._adjust_for_ocr_errors(t1_norm, t2_norm, similarity)
        
        final_similarity = max(similarity, ocr_adjusted_similarity)
        is_match = final_similarity >= threshold
        
        return is_match, final_similarity
    
    @staticmethod
    def normalize_ticket_number(ticket: str) -> str:
        """Normalize ticket number for comparison"""
        if not ticket:
            return ""
        
        # Remove whitespace and convert to uppercase
        normalized = re.sub(r'\s+', '', ticket.upper())
        
        # Remove common separators that might be inconsistent
        normalized = re.sub(r'[-_/]', '', normalized)
        
        return normalized
    
    @staticmethod
    def _adjust_for_ocr_errors(s1: str, s2: str, base_similarity: float) -> float:
        """Adjust similarity score accounting for common OCR errors"""
        if not s1 or not s2:
            return base_similarity
        
        # Common OCR character substitutions
        ocr_substitutions = {
            '0': ['O', 'D', 'Q'],
            'O': ['0', 'D', 'Q'],
            '1': ['I', 'L', '|'],
            'I': ['1', 'L', '|'],
            'L': ['1', 'I', '|'],
            '8': ['B', '3'],
            'B': ['8', '3'],
            '5': ['S'],
            'S': ['5'],
            '6': ['G'],
            'G': ['6'],
            '2': ['Z'],
            'Z': ['2']
        }
        
        # Try substituting common OCR errors
        s1_variants = [s1]
        s2_variants = [s2]
        
        # Generate variants for s1
        for i, char in enumerate(s1):
            if char in ocr_substitutions:
                for replacement in ocr_substitutions[char]:
                    variant = s1[:i] + replacement + s1[i+1:]
                    s1_variants.append(variant)
        
        # Generate variants for s2
        for i, char in enumerate(s2):
            if char in ocr_substitutions:
                for replacement in ocr_substitutions[char]:
                    variant = s2[:i] + replacement + s2[i+1:]
                    s2_variants.append(variant)
        
        # Find best match among variants
        best_similarity = base_similarity
        for v1 in s1_variants:
            for v2 in s2_variants:
                if v1 == v2:
                    return 1.0  # Perfect match after OCR correction
                similarity = FuzzyMatchUtils.similarity_ratio(v1, v2)
                best_similarity = max(best_similarity, similarity)
        
        return best_similarity
    
    @staticmethod
    def fuzzy_reference_match(ref1: str, ref2: str, threshold: float = 0.7) -> Tuple[bool, float]:
        """
        Match reference fields with more lenient fuzzy logic
        
        Args:
            ref1: First reference string
            ref2: Second reference string
            threshold: Minimum similarity ratio to consider a match
            
        Returns:
            Tuple of (is_match, similarity_score)
        """
        if not ref1 or not ref2:
            return False, 0.0
        
        # Normalize references
        r1_norm = FuzzyMatchUtils.normalize_reference(ref1)
        r2_norm = FuzzyMatchUtils.normalize_reference(ref2)
        
        # Exact match
        if r1_norm == r2_norm:
            return True, 1.0
        
        # Check if one is contained in the other (partial match)
        if r1_norm in r2_norm or r2_norm in r1_norm:
            # Give high score for containment
            similarity = 0.9
        else:
            # Calculate regular similarity
            similarity = FuzzyMatchUtils.similarity_ratio(r1_norm, r2_norm)
        
        is_match = similarity >= threshold
        return is_match, similarity
    
    @staticmethod
    def normalize_reference(reference: str) -> str:
        """Normalize reference string for comparison"""
        if not reference:
            return ""
        
        # Convert to uppercase and remove extra whitespace
        normalized = re.sub(r'\s+', ' ', reference.upper().strip())
        
        # Remove common punctuation that might be inconsistent
        normalized = re.sub(r'[.,;:!?]', '', normalized)
        
        return normalized
    
    @staticmethod
    def weight_within_tolerance(weight1: float, weight2: float, tolerance: float = 0.5) -> Tuple[bool, float]:
        """
        Check if two weights are within tolerance
        
        Args:
            weight1: First weight value
            weight2: Second weight value
            tolerance: Maximum allowed difference
            
        Returns:
            Tuple of (is_within_tolerance, similarity_score)
        """
        if weight1 is None or weight2 is None:
            return False, 0.0
        
        difference = abs(weight1 - weight2)
        
        if difference <= tolerance:
            # Calculate similarity based on how close they are
            # Perfect match (0 difference) = 1.0, at tolerance = 0.5
            similarity = max(0.5, 1.0 - (difference / tolerance) * 0.5)
            return True, similarity
        else:
            # Still calculate a similarity even if outside tolerance
            # This helps with partial credit in scoring
            max_reasonable_diff = tolerance * 3  # 1.5 tonnes
            similarity = max(0.0, 1.0 - (difference / max_reasonable_diff))
            return False, similarity
    
    @staticmethod
    def date_within_tolerance(date1, date2, tolerance_days: int = 1) -> Tuple[bool, float]:
        """
        Check if two dates are within tolerance
        
        Args:
            date1: First date
            date2: Second date
            tolerance_days: Maximum allowed difference in days
            
        Returns:
            Tuple of (is_within_tolerance, similarity_score)
        """
        if not date1 or not date2:
            return False, 0.0
        
        # Convert to dates if they're datetime objects
        from datetime import datetime
        
        if isinstance(date1, datetime):
            date1 = date1.date()
        if isinstance(date2, datetime):
            date2 = date2.date()
        
        difference = abs((date1 - date2).days)
        
        if difference <= tolerance_days:
            # Perfect match (same day) = 1.0, at tolerance = 0.8
            similarity = max(0.8, 1.0 - (difference / tolerance_days) * 0.2)
            return True, similarity
        else:
            # Still calculate similarity for partial credit
            max_reasonable_diff = tolerance_days * 7  # One week
            similarity = max(0.0, 1.0 - (difference / max_reasonable_diff))
            return False, similarity