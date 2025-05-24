"""
Service for loading clients from CSV file
"""
import csv
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from uuid import UUID
import logging
import re

from sqlmodel import Session, select
from ..models.client import Client, ClientCreate, ClientReference, ClientReferenceCreate, ClientRate, ClientRateCreate
from datetime import date

logger = logging.getLogger(__name__)


class ClientLoaderService:
    """
    Service to load clients from CSV file and create reference patterns
    """
    
    def __init__(self, session: Session):
        self.session = session
    
    async def load_clients_from_csv(
        self,
        csv_path: Path,
        created_by: UUID
    ) -> Tuple[List[Client], List[Dict]]:
        """
        Load clients from CSV file
        
        Args:
            csv_path: Path to CSV file
            created_by: User ID creating the clients
            
        Returns:
            Tuple of (created_clients, errors)
        """
        created_clients = []
        errors = []
        
        try:
            with open(csv_path, 'r', encoding='utf-8-sig') as file:
                # Use DictReader to handle header row
                reader = csv.DictReader(file)
                
                for row_num, row in enumerate(reader, start=2):  # Start at 2 because header is row 1
                    try:
                        client = await self._process_client_row(row, created_by)
                        if client:
                            created_clients.append(client)
                    except Exception as e:
                        errors.append({
                            'row': row_num,
                            'account_number': row.get('Account Number', ''),
                            'name': row.get('Account Name', ''),
                            'error': str(e)
                        })
                        logger.error(f"Error processing row {row_num}: {e}")
            
            logger.info(f"Loaded {len(created_clients)} clients with {len(errors)} errors")
            return created_clients, errors
            
        except Exception as e:
            logger.error(f"Error reading CSV file: {e}")
            raise
    
    async def _process_client_row(self, row: Dict[str, str], created_by: UUID) -> Optional[Client]:
        """
        Process a single row from the CSV
        
        Args:
            row: Dictionary of column values
            created_by: User ID creating the client
            
        Returns:
            Created client or None if skipped
        """
        # Extract fields from CSV
        account_number = row.get('Account Number', '').strip()
        account_name = row.get('Account Name', '').strip()
        
        if not account_number or not account_name:
            logger.warning("Skipping row with missing account number or name")
            return None
        
        # Check if client already exists by name
        existing_client = self.session.exec(
            select(Client).where(Client.name == account_name)
        ).first()
        
        if existing_client:
            logger.info(f"Client already exists: {account_name}")
            # Update reference patterns if needed
            await self._create_reference_patterns(existing_client, account_number)
            return existing_client
        
        # Extract other fields
        price_str = row.get('Price', '').strip()
        rate_per_tonne = self._parse_price(price_str)
        
        # Create client
        client_data = ClientCreate(
            name=account_name,
            billing_email=row.get('Email', '').strip() or 'billing@example.com',  # Default if empty
            billing_contact_name=row.get('Contact Person', '').strip(),
            billing_phone=row.get('Phone Number', '').strip(),
            invoice_format='csv',  # Default
            invoice_frequency='weekly',  # Default
            credit_terms_days=30,  # Default
            active=True,
            notes=self._build_notes(row)
        )
        
        client = Client(**client_data.dict())
        client.created_by = created_by
        self.session.add(client)
        self.session.commit()
        self.session.refresh(client)
        
        # Create reference patterns
        await self._create_reference_patterns(client, account_number)
        
        # Create initial rate
        if rate_per_tonne:
            await self._create_client_rate(client, rate_per_tonne, created_by)
        
        logger.info(f"Created client: {client.name} with account number: {account_number}")
        return client
    
    async def _create_reference_patterns(self, client: Client, account_number: str) -> None:
        """
        Create reference patterns for a client based on account number
        
        Args:
            client: Client object
            account_number: Account number from CSV
        """
        # Check if patterns already exist
        existing_refs = self.session.exec(
            select(ClientReference).where(ClientReference.client_id == client.id)
        ).all()
        
        existing_patterns = {ref.pattern for ref in existing_refs}
        
        patterns_to_create = []
        
        # Pattern 1: Exact account number (e.g., "007")
        if account_number not in existing_patterns:
            patterns_to_create.append(
                ClientReferenceCreate(
                    client_id=client.id,
                    pattern=account_number,
                    is_regex=False,
                    is_fuzzy=False,
                    priority=1,
                    active=True,
                    description=f"Exact match for account {account_number}"
                )
            )
        
        # Pattern 2: With # prefix (e.g., "#007")
        hash_pattern = f"#{account_number}"
        if hash_pattern not in existing_patterns:
            patterns_to_create.append(
                ClientReferenceCreate(
                    client_id=client.id,
                    pattern=hash_pattern,
                    is_regex=False,
                    is_fuzzy=False,
                    priority=2,
                    active=True,
                    description=f"Hash prefix match for account {account_number}"
                )
            )
        
        # Pattern 3: For MM patterns (e.g., "MM1001" for account "1001")
        if account_number.isdigit() and len(account_number) >= 3:
            mm_pattern = f"MM{account_number}"
            if mm_pattern not in existing_patterns:
                patterns_to_create.append(
                    ClientReferenceCreate(
                        client_id=client.id,
                        pattern=mm_pattern,
                        is_regex=False,
                        is_fuzzy=False,
                        priority=3,
                        active=True,
                        description=f"MM prefix match for account {account_number}"
                    )
                )
        
        # Create all new patterns
        for pattern_data in patterns_to_create:
            pattern = ClientReference(**pattern_data.dict())
            self.session.add(pattern)
        
        if patterns_to_create:
            self.session.commit()
            logger.info(f"Created {len(patterns_to_create)} reference patterns for client {client.name}")
    
    async def _create_client_rate(
        self,
        client: Client,
        rate_per_tonne: float,
        created_by: UUID
    ) -> None:
        """
        Create initial rate for client
        
        Args:
            client: Client object
            rate_per_tonne: Rate per tonne
            created_by: User ID creating the rate
        """
        # Check if rate already exists
        existing_rate = self.session.exec(
            select(ClientRate).where(
                ClientRate.client_id == client.id,
                ClientRate.effective_to.is_(None)  # Current rate
            )
        ).first()
        
        if not existing_rate:
            rate_data = ClientRateCreate(
                client_id=client.id,
                rate_per_tonne=rate_per_tonne,
                effective_from=date.today(),
                effective_to=None,
                approved_by=created_by,
                notes="Initial rate from CSV import"
            )
            
            rate = ClientRate(**rate_data.dict())
            rate.approved_at = rate.created_at
            self.session.add(rate)
            self.session.commit()
            logger.info(f"Created rate ${rate_per_tonne}/tonne for client {client.name}")
    
    def _parse_price(self, price_str: str) -> Optional[float]:
        """
        Parse price from string (e.g., "$76.00" -> 76.0)
        
        Args:
            price_str: Price string from CSV
            
        Returns:
            Float price or None
        """
        if not price_str:
            return None
        
        # Remove currency symbols and whitespace
        cleaned = re.sub(r'[^\d.]', '', price_str)
        
        try:
            return float(cleaned)
        except ValueError:
            logger.warning(f"Could not parse price: {price_str}")
            return None
    
    def _build_notes(self, row: Dict[str, str]) -> str:
        """
        Build notes field from various CSV columns
        
        Args:
            row: CSV row dictionary
            
        Returns:
            Notes string
        """
        notes_parts = []
        
        # Add various note fields
        if row.get('NOTE1'):
            notes_parts.append(f"Note1: {row['NOTE1']}")
        if row.get('NOTE'):
            notes_parts.append(f"Note: {row['NOTE']}")
        if row.get('INFO'):
            notes_parts.append(f"Info: {row['INFO']}")
        if row.get('Payment Method'):
            notes_parts.append(f"Payment: {row['Payment Method']}")
        if row.get('Contact Person 2'):
            notes_parts.append(f"Contact 2: {row['Contact Person 2']}")
        
        # Add address info
        address_parts = []
        if row.get('Street 1'):
            address_parts.append(row['Street 1'])
        if row.get('Street 2'):
            address_parts.append(row['Street 2'])
        if row.get('City'):
            address_parts.append(row['City'])
        if row.get('Postal Code'):
            address_parts.append(row['Postal Code'])
        if row.get('Prov'):
            address_parts.append(row['Prov'])
        
        if address_parts:
            notes_parts.append(f"Address: {', '.join(address_parts)}")
        
        return ' | '.join(notes_parts) if notes_parts else ''
    
    async def create_topps_client(self, created_by: UUID) -> Client:
        """
        Create or get the TOPPS client for T-xxx references
        
        Args:
            created_by: User ID creating the client
            
        Returns:
            TOPPS client
        """
        # Check if TOPPS client exists
        topps_client = self.session.exec(
            select(Client).where(Client.name.ilike('%TOPPS%'))
        ).first()
        
        if topps_client:
            return topps_client
        
        # Create TOPPS client
        client_data = ClientCreate(
            name="TOPPS Environmental",
            billing_email="billing@toppsenvironmental.com",
            billing_contact_name="Billing Department",
            billing_phone="",
            invoice_format='csv',
            invoice_frequency='weekly',
            credit_terms_days=30,
            active=True,
            notes="Internal TOPPS account for T-xxx references"
        )
        
        client = Client(**client_data.dict())
        client.created_by = created_by
        self.session.add(client)
        self.session.commit()
        self.session.refresh(client)
        
        # Create T-* pattern for TOPPS
        pattern_data = ClientReferenceCreate(
            client_id=client.id,
            pattern='T-*',
            is_regex=False,
            is_fuzzy=False,
            priority=1,
            active=True,
            description="All T-xxx references belong to TOPPS"
        )
        
        pattern = ClientReference(**pattern_data.dict())
        self.session.add(pattern)
        self.session.commit()
        
        logger.info("Created TOPPS client for T-xxx references")
        return client