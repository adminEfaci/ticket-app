from typing import List, Optional
from uuid import UUID
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status, File, UploadFile
from sqlmodel import Session

from backend.middleware.auth_middleware import get_current_user, admin_required
from backend.core.database import get_session
from backend.models.client import (
    ClientCreate, ClientRead, ClientUpdate,
    ClientReferenceCreate, ClientReferenceRead, ClientReferenceUpdate,
    ClientRateCreate, ClientRateRead, ClientRateUpdate,
    ClientHierarchy, ClientStatistics, ClientAssignmentResult
)
from backend.services.client_service import get_client_service
from backend.services.reference_matcher import get_reference_matcher_service
from backend.services.rate_service import RateService, RateAnalytics
from backend.services.ticket_service import TicketService
from backend.services.client_loader_service import ClientLoaderService


router = APIRouter(prefix="/api/clients", tags=["clients"])


# ========== CLIENT CRUD OPERATIONS ==========

@router.post("/", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
async def create_client(
    client_data: ClientCreate,
    current_user: dict = Depends(admin_required()),
    session: Session = Depends(get_session)
):
    """Create a new client (admin only)"""
    try:
        client_service = get_client_service(session)
        client = await client_service.create_client(client_data, current_user['user_id'])
        return client
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create client: {str(e)}")


@router.get("/", response_model=List[ClientRead])
async def list_clients(
    active_only: bool = Query(True, description="Only show active clients"),
    parent_id: Optional[UUID] = Query(None, description="Filter by parent client"),
    skip: int = Query(0, ge=0, description="Skip records"),
    limit: int = Query(100, ge=1, le=500, description="Limit records"),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """List all clients with optional filtering"""
    try:
        client_service = get_client_service(session)
        
        # For non-admin users, filter to their assigned client
        if current_user['role'] != 'admin' and current_user.get('client_id'):
            # Only show their own client
            client = await client_service.get_client(current_user.get('client_id'))
            return [client] if client else []
        
        # Admin users can see all clients
        clients = await client_service.get_clients(
            active_only=active_only,
            parent_id=parent_id,
            skip=skip,
            limit=limit
        )
        return clients
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list clients: {str(e)}")


@router.get("/hierarchy", response_model=List[ClientHierarchy])
async def get_client_hierarchy(
    root_client_id: Optional[UUID] = Query(None, description="Root client to start from"),
    current_user: dict = Depends(admin_required()),
    session: Session = Depends(get_session)
):
    """Get client hierarchy tree (admin only)"""
    try:
        client_service = get_client_service(session)
        hierarchy = await client_service.get_client_hierarchy(root_client_id)
        return hierarchy
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get client hierarchy: {str(e)}")


@router.get("/search", response_model=List[ClientRead])
async def search_clients(
    q: str = Query(..., min_length=1, description="Search term"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Search clients by name"""
    try:
        client_service = get_client_service(session)
        
        # For non-admin users, restrict search
        if current_user['role'] != 'admin' and current_user.get('client_id'):
            # Can only search their own client
            client = await client_service.get_client(current_user.get('client_id'))
            if client and q.lower() in client.name.lower():
                return [client]
            return []
        
        clients = await client_service.search_clients(q, limit)
        return clients
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/{client_id}", response_model=ClientRead)
async def get_client(
    client_id: UUID,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get a specific client by ID"""
    try:
        client_service = get_client_service(session)
        
        # Access control
        if current_user['role'] != 'admin' and current_user.get('client_id') != client_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        client = await client_service.get_client(client_id)
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")
        
        return client
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get client: {str(e)}")


@router.put("/{client_id}", response_model=ClientRead)
async def update_client(
    client_id: UUID,
    client_data: ClientUpdate,
    current_user: dict = Depends(admin_required()),
    session: Session = Depends(get_session)
):
    """Update client details (admin only)"""
    try:
        client_service = get_client_service(session)
        client = await client_service.update_client(client_id, client_data, current_user['user_id'])
        return client
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update client: {str(e)}")


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: UUID,
    current_user: dict = Depends(admin_required()),
    session: Session = Depends(get_session)
):
    """Delete a client (admin only, blocked if tickets exist)"""
    try:
        client_service = get_client_service(session)
        success = await client_service.delete_client(client_id, current_user['user_id'])
        if not success:
            raise HTTPException(status_code=404, detail="Client not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete client: {str(e)}")


# ========== CLIENT STATISTICS ==========

@router.get("/{client_id}/statistics", response_model=ClientStatistics)
async def get_client_statistics(
    client_id: UUID,
    date_from: Optional[date] = Query(None, description="Start date"),
    date_to: Optional[date] = Query(None, description="End date"),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get statistics for a client"""
    try:
        # Access control
        if current_user['role'] != 'admin' and current_user.get('client_id') != client_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        client_service = get_client_service(session)
        stats = await client_service.get_client_statistics(client_id, date_from, date_to)
        return stats
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


# ========== REFERENCE PATTERN MANAGEMENT ==========

@router.post("/{client_id}/references", response_model=ClientReferenceRead, status_code=status.HTTP_201_CREATED)
async def add_client_reference(
    client_id: UUID,
    reference_data: ClientReferenceCreate,
    current_user: dict = Depends(admin_required()),
    session: Session = Depends(get_session)
):
    """Add a reference pattern to a client (admin only)"""
    try:
        # Ensure client_id matches
        if reference_data.client_id != client_id:
            raise HTTPException(status_code=400, detail="Client ID mismatch")
        
        matcher_service = get_reference_matcher_service(session)
        
        # Validate pattern
        is_valid, error = matcher_service.validate_reference_pattern(
            reference_data.pattern,
            reference_data.is_regex,
            reference_data.is_fuzzy
        )
        if not is_valid:
            raise HTTPException(status_code=400, detail=error)
        
        # Check for conflicts
        conflicts = matcher_service.check_pattern_conflicts(
            reference_data.pattern,
            reference_data.is_regex,
            reference_data.is_fuzzy,
            exclude_client_id=client_id
        )
        if conflicts:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Pattern conflicts detected",
                    "conflicts": conflicts
                }
            )
        
        # Create reference
        from backend.models.client import ClientReference
        reference = ClientReference(**reference_data.model_dump(), created_by=current_user['user_id'])
        session.add(reference)
        session.commit()
        session.refresh(reference)
        
        return ClientReferenceRead.model_validate(reference)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add reference: {str(e)}")


@router.get("/{client_id}/references", response_model=List[ClientReferenceRead])
async def get_client_references(
    client_id: UUID,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get all reference patterns for a client"""
    try:
        # Access control
        if current_user['role'] != 'admin' and current_user.get('client_id') != client_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        matcher_service = get_reference_matcher_service(session)
        references = matcher_service.get_client_references(client_id)
        return [ClientReferenceRead.model_validate(ref) for ref in references]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get references: {str(e)}")


@router.put("/references/{reference_id}", response_model=ClientReferenceRead)
async def update_client_reference(
    reference_id: UUID,
    reference_data: ClientReferenceUpdate,
    current_user: dict = Depends(admin_required()),
    session: Session = Depends(get_session)
):
    """Update a reference pattern (admin only)"""
    try:
        from backend.models.client import ClientReference
        
        reference = session.get(ClientReference, reference_id)
        if not reference:
            raise HTTPException(status_code=404, detail="Reference not found")
        
        # Apply updates
        update_data = reference_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(reference, field, value)
        
        # Validate if pattern changed
        if 'pattern' in update_data or 'is_regex' in update_data or 'is_fuzzy' in update_data:
            matcher_service = get_reference_matcher_service(session)
            is_valid, error = matcher_service.validate_reference_pattern(
                reference.pattern,
                reference.is_regex,
                reference.is_fuzzy
            )
            if not is_valid:
                raise HTTPException(status_code=400, detail=error)
        
        session.commit()
        session.refresh(reference)
        
        return ClientReferenceRead.model_validate(reference)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update reference: {str(e)}")


@router.delete("/references/{reference_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client_reference(
    reference_id: UUID,
    current_user: dict = Depends(admin_required()),
    session: Session = Depends(get_session)
):
    """Delete a reference pattern (admin only)"""
    try:
        from backend.models.client import ClientReference
        
        reference = session.get(ClientReference, reference_id)
        if not reference:
            raise HTTPException(status_code=404, detail="Reference not found")
        
        session.delete(reference)
        session.commit()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete reference: {str(e)}")


# ========== RATE MANAGEMENT ==========

@router.post("/{client_id}/rates", response_model=ClientRateRead, status_code=status.HTTP_201_CREATED)
async def add_client_rate(
    client_id: UUID,
    rate_data: ClientRateCreate,
    auto_approve: bool = Query(False, description="Auto-approve rate (admin only)"),
    current_user: dict = Depends(admin_required()),
    session: Session = Depends(get_session)
):
    """Add a new rate for a client (admin only)"""
    try:
        # Ensure client_id matches
        if rate_data.client_id != client_id:
            raise HTTPException(status_code=400, detail="Client ID mismatch")
        
        rate_service = RateService(session)
        rate = await rate_service.create_rate(
            rate_data,
            approved_by=current_user['user_id'] if auto_approve else None,
            auto_approve=auto_approve
        )
        return rate
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add rate: {str(e)}")


@router.get("/{client_id}/rates", response_model=List[ClientRateRead])
async def get_client_rates(
    client_id: UUID,
    include_expired: bool = Query(False, description="Include expired rates"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Limit results"),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get rate history for a client"""
    try:
        # Access control
        if current_user['role'] != 'admin' and current_user.get('client_id') != client_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        rate_service = RateService(session)
        rates = await rate_service.get_client_rates(client_id, include_expired, limit)
        return rates
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get rates: {str(e)}")


@router.get("/{client_id}/rates/effective", response_model=ClientRateRead)
async def get_effective_rate(
    client_id: UUID,
    effective_date: Optional[date] = Query(None, description="Date to check (defaults to today)"),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get the effective rate for a client on a specific date"""
    try:
        # Access control
        if current_user['role'] != 'admin' and current_user.get('client_id') != client_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        rate_service = RateService(session)
        rate = await rate_service.get_effective_rate(client_id, effective_date)
        if not rate:
            raise HTTPException(status_code=404, detail="No effective rate found for this date")
        
        return rate
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get effective rate: {str(e)}")


@router.put("/rates/{rate_id}", response_model=ClientRateRead)
async def update_rate(
    rate_id: UUID,
    rate_data: ClientRateUpdate,
    current_user: dict = Depends(admin_required()),
    session: Session = Depends(get_session)
):
    """Update a rate (admin only, cannot update approved rates)"""
    try:
        rate_service = RateService(session)
        rate = await rate_service.update_rate(rate_id, rate_data, current_user['user_id'])
        if not rate:
            raise HTTPException(status_code=404, detail="Rate not found")
        
        return rate
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update rate: {str(e)}")


@router.post("/rates/{rate_id}/approve", response_model=ClientRateRead)
async def approve_rate(
    rate_id: UUID,
    current_user: dict = Depends(admin_required()),
    session: Session = Depends(get_session)
):
    """Approve a pending rate (admin only)"""
    try:
        rate_service = RateService(session)
        rate = await rate_service.approve_rate(rate_id, current_user['user_id'])
        if not rate:
            raise HTTPException(status_code=404, detail="Rate not found")
        
        return rate
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to approve rate: {str(e)}")


@router.delete("/rates/{rate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rate(
    rate_id: UUID,
    current_user: dict = Depends(admin_required()),
    session: Session = Depends(get_session)
):
    """Delete a rate (admin only, cannot delete approved rates)"""
    try:
        rate_service = RateService(session)
        success = await rate_service.delete_rate(rate_id, current_user['user_id'])
        if not success:
            raise HTTPException(status_code=404, detail="Rate not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete rate: {str(e)}")


# ========== RATE ANALYTICS ==========

@router.get("/rates/pending", response_model=List[ClientRateRead])
async def get_pending_rates(
    limit: Optional[int] = Query(None, ge=1, le=100, description="Limit results"),
    current_user: dict = Depends(admin_required()),
    session: Session = Depends(get_session)
):
    """Get all pending (unapproved) rates (admin only)"""
    try:
        rate_service = RateService(session)
        rates = await rate_service.get_pending_rates(limit)
        return rates
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get pending rates: {str(e)}")


@router.get("/{client_id}/rates/statistics")
async def get_rate_statistics(
    client_id: UUID,
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    current_user: dict = Depends(admin_required()),
    session: Session = Depends(get_session)
):
    """Get rate statistics for a client (admin only)"""
    try:
        analytics = RateAnalytics(session)
        stats = await analytics.get_rate_statistics(client_id, start_date, end_date)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get rate statistics: {str(e)}")


# ========== REFERENCE MATCHING TOOLS ==========

@router.post("/test-reference-matching")
async def test_reference_matching(
    test_references: List[str],
    current_user: dict = Depends(admin_required()),
    session: Session = Depends(get_session)
):
    """Test reference matching against configured patterns (admin only)"""
    try:
        matcher_service = get_reference_matcher_service(session)
        results = matcher_service.test_reference_matching(test_references)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reference matching test failed: {str(e)}")


@router.get("/find-by-reference/{reference}", response_model=Optional[ClientAssignmentResult])
async def find_client_by_reference(
    reference: str,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Find the best matching client for a reference"""
    try:
        matcher_service = get_reference_matcher_service(session)
        match_result = matcher_service.find_client_by_reference(reference)
        
        if not match_result:
            return None
        
        # Get effective rate
        rate_service = RateService(session)
        effective_rate = await rate_service.get_effective_rate(match_result.client_id)
        
        return ClientAssignmentResult(
            client_id=match_result.client_id,
            client_name=match_result.client_name,
            matched_pattern=match_result.matched_pattern,
            match_type=match_result.match_type,
            confidence=match_result.confidence,
            rate_per_tonne=effective_rate.rate_per_tonne if effective_rate else None,
            effective_rate_date=effective_rate.effective_from if effective_rate else None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reference lookup failed: {str(e)}")


# ========== CLIENT TICKETS ==========

@router.get("/{client_id}/tickets")
async def get_client_tickets(
    client_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Get tickets for a specific client"""
    try:
        # Access control
        if current_user['role'] != 'admin' and current_user.get('client_id') != client_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        ticket_service = TicketService(session)
        tickets = await ticket_service.get_tickets_by_client(
            client_id=client_id,
            skip=skip,
            limit=limit,
            date_from=date_from,
            date_to=date_to
        )
        return tickets
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get client tickets: {str(e)}")


# ========== BULK IMPORT ==========

@router.post("/import/csv", status_code=status.HTTP_201_CREATED)
async def import_clients_from_csv(
    file: UploadFile = File(..., description="CSV file with client data"),
    create_topps: bool = Query(True, description="Create TOPPS client for T-xxx references"),
    current_user: dict = Depends(admin_required()),
    session: Session = Depends(get_session)
):
    """Import clients from CSV file (admin only)"""
    try:
        # Validate file type
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="File must be a CSV")
        
        # Save uploaded file temporarily
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        try:
            loader_service = ClientLoaderService(session)
            
            # Create TOPPS client if requested
            if create_topps:
                await loader_service.create_topps_client(current_user['user_id'])
            
            # Load clients from CSV
            clients, errors = await loader_service.load_clients_from_csv(
                Path(tmp_path),
                current_user['user_id']
            )
            
            return {
                "success": True,
                "clients_created": len(clients),
                "errors": errors,
                "summary": f"Successfully imported {len(clients)} clients with {len(errors)} errors"
            }
            
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to import clients: {str(e)}")


@router.get("/export/csv")
async def export_clients_to_csv(
    include_references: bool = Query(True, description="Include reference patterns"),
    include_rates: bool = Query(True, description="Include current rates"),
    active_only: bool = Query(True, description="Only export active clients"),
    current_user: dict = Depends(admin_required()),
    session: Session = Depends(get_session)
):
    """Export clients to CSV format (admin only)"""
    try:
        from fastapi.responses import StreamingResponse
        import csv
        import io
        
        client_service = get_client_service(session)
        rate_service = RateService(session)
        matcher_service = get_reference_matcher_service(session)
        
        # Get all clients
        clients = await client_service.get_clients(active_only=active_only, limit=10000)
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        headers = [
            'Account Number', 'Account Name', 'Price', 'Contact Person', 
            'Email', 'Phone Number', 'Active', 'Invoice Format', 
            'Invoice Frequency', 'Credit Terms', 'Notes'
        ]
        
        if include_references:
            headers.append('Reference Patterns')
        
        writer.writerow(headers)
        
        # Write client data
        for client in clients:
            # Get current rate
            current_rate = None
            if include_rates:
                rate = await rate_service.get_effective_rate(client.id)
                current_rate = f"${rate.rate_per_tonne:.2f}" if rate else ""
            
            # Get reference patterns
            ref_patterns = ""
            if include_references:
                refs = matcher_service.get_client_references(client.id)
                ref_patterns = ";".join([ref.pattern for ref in refs if ref.active])
            
            row = [
                "",  # Account number (would need to extract from references)
                client.name,
                current_rate or "",
                client.billing_contact_name or "",
                client.billing_email,
                client.billing_phone or "",
                "Yes" if client.active else "No",
                client.invoice_format,
                client.invoice_frequency,
                f"{client.credit_terms_days} days",
                client.notes or ""
            ]
            
            if include_references:
                row.append(ref_patterns)
            
            writer.writerow(row)
        
        # Return as streaming response
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=clients_export.csv"}
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export clients: {str(e)}")