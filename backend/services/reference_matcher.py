import re
from typing import List, Optional, Tuple, Dict, Any
from uuid import UUID

from sqlmodel import Session, select, and_

from backend.models.client import (
    Client, ClientReference
)
from backend.utils.fuzzy_utils import FuzzyMatchUtils


class ReferenceMatchResult:
    """Result of a reference matching operation"""
    
    def __init__(
        self,
        client_id: UUID,
        client_name: str,
        matched_pattern: str,
        match_type: str,
        confidence: float,
        reference_id: UUID
    ):
        self.client_id = client_id
        self.client_name = client_name
        self.matched_pattern = matched_pattern
        self.match_type = match_type
        self.confidence = confidence
        self.reference_id = reference_id


class ReferenceMatcherService:
    """Service for matching ticket references to clients using various strategies"""
    
    def __init__(self, session: Session):
        self.session = session
        
        # Match type priorities (lower = higher priority)
        self.match_priorities = {
            "exact": 1,
            "prefix": 2,
            "regex": 3,
            "fuzzy": 4
        }
    
    def find_client_by_reference(self, reference: str) -> Optional[ReferenceMatchResult]:
        """
        Find the best matching client for a given reference
        
        Priority order: exact > prefix > regex > fuzzy
        Within each type, uses priority field and confidence
        
        Special handling:
        - References starting with T- are mapped to TOPPS client
        - References like #007 match patterns 007
        """
        if not reference or not reference.strip():
            return None
        
        reference = reference.strip()
        
        # Special handling for T-xxx patterns -> TOPPS client
        if reference.upper().startswith('T-'):
            topps_client = self.session.exec(
                select(Client).where(
                    and_(
                        Client.name.ilike('%TOPPS%'),
                        Client.active
                    )
                )
            ).first()
            
            if topps_client:
                return ReferenceMatchResult(
                    client_id=topps_client.id,
                    client_name=topps_client.name,
                    matched_pattern='T-*',
                    match_type='exact',
                    confidence=1.0,
                    reference_id=UUID('00000000-0000-0000-0000-000000000000')  # Special case
                )
        
        # Get all active client references
        client_refs = self.session.exec(
            select(ClientReference)
            .join(Client, ClientReference.client_id == Client.id)
            .where(
                and_(
                    ClientReference.active,
                    Client.active
                )
            )
            .order_by(ClientReference.priority.asc())
        ).all()
        
        if not client_refs:
            return None
        
        # Try matching in priority order
        all_matches = []
        
        # 1. Exact matches
        exact_matches = self._find_exact_matches(reference, client_refs)
        all_matches.extend(exact_matches)
        
        # 2. Prefix matches  
        prefix_matches = self._find_prefix_matches(reference, client_refs)
        all_matches.extend(prefix_matches)
        
        # 3. Regex matches
        regex_matches = self._find_regex_matches(reference, client_refs)
        all_matches.extend(regex_matches)
        
        # 4. Fuzzy matches
        fuzzy_matches = self._find_fuzzy_matches(reference, client_refs)
        all_matches.extend(fuzzy_matches)
        
        if not all_matches:
            return None
        
        # Sort by priority and confidence
        all_matches.sort(key=lambda m: (
            self.match_priorities[m.match_type],
            -m.confidence,  # Higher confidence first
            self._get_reference_priority(m.reference_id, client_refs)
        ))
        
        return all_matches[0]
    
    def _find_exact_matches(
        self, 
        reference: str, 
        client_refs: List[ClientReference]
    ) -> List[ReferenceMatchResult]:
        """Find exact string matches"""
        matches = []
        
        # Normalize reference - remove # prefix for matching
        normalized_ref = reference
        if reference.startswith('#') and len(reference) > 1:
            normalized_ref = reference[1:]  # Remove # prefix
        
        for ref in client_refs:
            if not ref.is_regex and not ref.is_fuzzy:
                # Try exact match
                if reference == ref.pattern or normalized_ref == ref.pattern:
                    client = self._get_client_for_reference(ref)
                    if client:
                        matches.append(ReferenceMatchResult(
                            client_id=client.id,
                            client_name=client.name,
                            matched_pattern=ref.pattern,
                            match_type="exact",
                            confidence=1.0,
                            reference_id=ref.id
                        ))
                # Also try if pattern has # prefix
                elif ref.pattern.startswith('#') and ref.pattern[1:] == normalized_ref:
                    client = self._get_client_for_reference(ref)
                    if client:
                        matches.append(ReferenceMatchResult(
                            client_id=client.id,
                            client_name=client.name,
                            matched_pattern=ref.pattern,
                            match_type="exact",
                            confidence=1.0,
                            reference_id=ref.id
                        ))
        
        return matches
    
    def _find_prefix_matches(
        self, 
        reference: str, 
        client_refs: List[ClientReference]
    ) -> List[ReferenceMatchResult]:
        """Find prefix matches (pattern ends with *)"""
        matches = []
        
        for ref in client_refs:
            if not ref.is_regex and not ref.is_fuzzy and ref.pattern.endswith('*'):
                prefix = ref.pattern[:-1]  # Remove the *
                if prefix and reference.startswith(prefix):
                    # Calculate confidence based on how much of the reference is matched
                    confidence = len(prefix) / len(reference) if reference else 0.0
                    confidence = min(confidence, 0.95)  # Cap at 95% for prefix matches
                    
                    client = self._get_client_for_reference(ref)
                    if client:
                        matches.append(ReferenceMatchResult(
                            client_id=client.id,
                            client_name=client.name,
                            matched_pattern=ref.pattern,
                            match_type="prefix",
                            confidence=confidence,
                            reference_id=ref.id
                        ))
        
        return matches
    
    def _find_regex_matches(
        self, 
        reference: str, 
        client_refs: List[ClientReference]
    ) -> List[ReferenceMatchResult]:
        """Find regex pattern matches"""
        matches = []
        
        for ref in client_refs:
            if ref.is_regex and not ref.is_fuzzy:
                try:
                    pattern = re.compile(ref.pattern, re.IGNORECASE)
                    match = pattern.match(reference)
                    
                    if match:
                        # Calculate confidence based on how much of the reference is matched
                        matched_length = len(match.group(0))
                        confidence = matched_length / len(reference) if reference else 0.0
                        confidence = min(confidence, 0.9)  # Cap at 90% for regex matches
                        
                        client = self._get_client_for_reference(ref)
                        if client:
                            matches.append(ReferenceMatchResult(
                                client_id=client.id,
                                client_name=client.name,
                                matched_pattern=ref.pattern,
                                match_type="regex",
                                confidence=confidence,
                                reference_id=ref.id
                            ))
                
                except re.error:
                    # Skip invalid regex patterns
                    continue
        
        return matches
    
    def _find_fuzzy_matches(
        self, 
        reference: str, 
        client_refs: List[ClientReference]
    ) -> List[ReferenceMatchResult]:
        """Find fuzzy string matches"""
        matches = []
        
        for ref in client_refs:
            if ref.is_fuzzy and not ref.is_regex:
                # Use fuzzy matching from Phase 5
                is_match, similarity = FuzzyMatchUtils.fuzzy_reference_match(
                    reference, 
                    ref.pattern,
                    threshold=0.6  # Lower threshold for client assignment
                )
                
                if is_match:
                    # Scale confidence for fuzzy matches (max 85%)
                    confidence = similarity * 0.85
                    
                    client = self._get_client_for_reference(ref)
                    if client:
                        matches.append(ReferenceMatchResult(
                            client_id=client.id,
                            client_name=client.name,
                            matched_pattern=ref.pattern,
                            match_type="fuzzy",
                            confidence=confidence,
                            reference_id=ref.id
                        ))
        
        return matches
    
    def _get_client_for_reference(self, ref: ClientReference) -> Optional[Client]:
        """Get the client associated with a reference"""
        return self.session.get(Client, ref.client_id)
    
    def _get_reference_priority(
        self, 
        reference_id: UUID, 
        client_refs: List[ClientReference]
    ) -> int:
        """Get the priority value for a reference"""
        for ref in client_refs:
            if ref.id == reference_id:
                return ref.priority
        return 999  # Default high priority number (low priority)
    
    def find_all_matches(self, reference: str) -> List[ReferenceMatchResult]:
        """
        Find all possible matches for a reference (for debugging/analysis)
        """
        if not reference or not reference.strip():
            return []
        
        reference = reference.strip()
        
        # Get all active client references
        client_refs = self.session.exec(
            select(ClientReference)
            .join(Client, ClientReference.client_id == Client.id)
            .where(
                and_(
                    ClientReference.active,
                    Client.active
                )
            )
            .order_by(ClientReference.priority.asc())
        ).all()
        
        if not client_refs:
            return []
        
        # Find all types of matches
        all_matches = []
        all_matches.extend(self._find_exact_matches(reference, client_refs))
        all_matches.extend(self._find_prefix_matches(reference, client_refs))
        all_matches.extend(self._find_regex_matches(reference, client_refs))
        all_matches.extend(self._find_fuzzy_matches(reference, client_refs))
        
        # Sort by match type priority and confidence
        all_matches.sort(key=lambda m: (
            self.match_priorities[m.match_type],
            -m.confidence,
            self._get_reference_priority(m.reference_id, client_refs)
        ))
        
        return all_matches
    
    def validate_reference_pattern(
        self, 
        pattern: str, 
        is_regex: bool = False,
        is_fuzzy: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a reference pattern
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not pattern or not pattern.strip():
            return False, "Pattern cannot be empty"
        
        pattern = pattern.strip()
        
        # Validate regex patterns
        if is_regex:
            try:
                re.compile(pattern)
            except re.error as e:
                return False, f"Invalid regex pattern: {e}"
        
        # Check for conflicting flags
        if is_regex and is_fuzzy:
            return False, "Pattern cannot be both regex and fuzzy"
        
        # Pattern length limits
        if len(pattern) > 200:
            return False, "Pattern too long (max 200 characters)"
        
        if len(pattern) < 1:
            return False, "Pattern too short (min 1 character)"
        
        return True, None
    
    def check_pattern_conflicts(
        self, 
        pattern: str, 
        is_regex: bool = False,
        is_fuzzy: bool = False,
        exclude_client_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """
        Check if a pattern would conflict with existing patterns
        
        Returns list of conflicts with details
        """
        conflicts = []
        
        # Get existing patterns
        query = select(ClientReference).join(Client, ClientReference.client_id == Client.id).where(
            and_(
                ClientReference.active,
                Client.active
            )
        )
        
        if exclude_client_id:
            query = query.where(Client.id != exclude_client_id)
        
        existing_refs = self.session.exec(query).all()
        
        for existing_ref in existing_refs:
            conflict_type = self._detect_conflict(
                pattern, is_regex, is_fuzzy,
                existing_ref.pattern, existing_ref.is_regex, existing_ref.is_fuzzy
            )
            
            if conflict_type:
                client = self._get_client_for_reference(existing_ref)
                conflicts.append({
                    "conflict_type": conflict_type,
                    "existing_pattern": existing_ref.pattern,
                    "existing_client_id": existing_ref.client_id,
                    "existing_client_name": client.name if client else "Unknown",
                    "existing_is_regex": existing_ref.is_regex,
                    "existing_is_fuzzy": existing_ref.is_fuzzy
                })
        
        return conflicts
    
    def _detect_conflict(
        self,
        new_pattern: str, new_is_regex: bool, new_is_fuzzy: bool,
        existing_pattern: str, existing_is_regex: bool, existing_is_fuzzy: bool
    ) -> Optional[str]:
        """
        Detect if two patterns would conflict
        
        Returns conflict type or None if no conflict
        """
        # Exact duplicate
        if (new_pattern == existing_pattern and 
            new_is_regex == existing_is_regex and 
            new_is_fuzzy == existing_is_fuzzy):
            return "duplicate"
        
        # Both exact patterns that are the same
        if (not new_is_regex and not new_is_fuzzy and 
            not existing_is_regex and not existing_is_fuzzy):
            if new_pattern == existing_pattern:
                return "exact_duplicate"
        
        # Prefix conflicts
        if not new_is_regex and not new_is_fuzzy and new_pattern.endswith('*'):
            prefix = new_pattern[:-1]
            if (not existing_is_regex and not existing_is_fuzzy and 
                existing_pattern.startswith(prefix)):
                return "prefix_conflict"
        
        if (not existing_is_regex and not existing_is_fuzzy and 
            existing_pattern.endswith('*')):
            existing_prefix = existing_pattern[:-1]
            if (not new_is_regex and not new_is_fuzzy and 
                new_pattern.startswith(existing_prefix)):
                return "prefix_conflict"
        
        # For other complex conflicts (regex vs fuzzy, etc.), we could add more logic
        # For now, we'll be conservative and allow them
        
        return None
    
    def get_client_references(self, client_id: UUID) -> List[ClientReference]:
        """Get all references for a client"""
        return list(self.session.exec(
            select(ClientReference).where(
                ClientReference.client_id == client_id
            ).order_by(ClientReference.priority.asc())
        ).all())
    
    def test_reference_matching(self, test_references: List[str]) -> Dict[str, Any]:
        """
        Test reference matching against a list of test references
        
        Useful for validating client reference patterns
        """
        results = {}
        
        for ref in test_references:
            match_result = self.find_client_by_reference(ref)
            all_matches = self.find_all_matches(ref)
            
            results[ref] = {
                "best_match": {
                    "client_id": str(match_result.client_id) if match_result else None,
                    "client_name": match_result.client_name if match_result else None,
                    "matched_pattern": match_result.matched_pattern if match_result else None,
                    "match_type": match_result.match_type if match_result else None,
                    "confidence": match_result.confidence if match_result else 0.0
                },
                "all_matches": [
                    {
                        "client_id": str(m.client_id),
                        "client_name": m.client_name,
                        "matched_pattern": m.matched_pattern,
                        "match_type": m.match_type,
                        "confidence": m.confidence
                    } for m in all_matches
                ],
                "total_matches": len(all_matches)
            }
        
        return results


def get_reference_matcher_service(session: Session) -> ReferenceMatcherService:
    """Dependency injection for ReferenceMatcherService"""
    return ReferenceMatcherService(session)