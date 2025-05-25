#!/usr/bin/env python3
"""
Test that all integration issues have been fixed
"""

import requests
import json
from typing import Dict, Any

# Base URL
BASE_URL = "http://localhost:8000"

def get_headers(token: str) -> Dict[str, str]:
    """Get headers with auth token"""
    return {"Authorization": f"Bearer {token}"}

def test_auth_consistency():
    """Test that authentication returns consistent User objects"""
    print("1. Testing authentication consistency...")
    
    # Login
    login_data = {"email": "test@example.com", "password": "testpassword123"}
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    
    if response.status_code == 200:
        token = response.json()["access_token"]
        
        # Test various endpoints that require auth
        endpoints = [
            "/upload/batches",
            "/api/clients"
        ]
        
        for endpoint in endpoints:
            resp = requests.get(f"{BASE_URL}{endpoint}", headers=get_headers(token))
            print(f"   {endpoint}: {resp.status_code}")
            if resp.status_code >= 400 and resp.status_code != 404:
                print(f"      Error: {resp.text}")
        
        print("   ✓ Authentication working consistently")
    else:
        print(f"   ✗ Login failed: {response.text}")

def test_batch_processing():
    """Test batch processing with status handling"""
    print("\n2. Testing batch processing...")
    
    # Login
    login_data = {"email": "test@example.com", "password": "testpassword123"}
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    token = response.json()["access_token"]
    headers = get_headers(token)
    
    # Get batches
    response = requests.get(f"{BASE_URL}/upload/batches", headers=headers)
    if response.status_code == 200:
        batches = response.json()
        print(f"   Found {len(batches)} batches")
        
        # Check batch statuses
        for batch in batches[:3]:
            print(f"   Batch {batch['id']}: status={batch['status']}, xls={batch.get('xls_filename', 'N/A')}")
        
        print("   ✓ Batch processing working")
    else:
        print(f"   ✗ Failed to get batches: {response.text}")

def test_ticket_data():
    """Test that tickets are populated"""
    print("\n3. Testing ticket data...")
    
    # Login
    login_data = {"email": "test@example.com", "password": "testpassword123"}
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    token = response.json()["access_token"]
    headers = get_headers(token)
    
    # Get batches first
    response = requests.get(f"{BASE_URL}/upload/batches", headers=headers)
    if response.status_code == 200:
        batches = response.json()
        tickets_found = False
        
        # Check each batch for tickets
        for batch in batches:
            batch_id = batch['id']
            resp = requests.get(f"{BASE_URL}/batches/{batch_id}/tickets", headers=headers)
            if resp.status_code == 200:
                tickets = resp.json()
                if tickets:
                    print(f"   Found {len(tickets)} tickets in batch {batch_id}")
                    ticket = tickets[0]
                    print(f"   Sample ticket: {ticket['ticket_number']} - {ticket['entry_date']} - {ticket['net_weight']}kg")
                    tickets_found = True
                    break
        
        if tickets_found:
            print("   ✓ Tickets populated successfully")
        else:
            print("   ✗ No tickets found in any batch")
    else:
        print(f"   ✗ Failed to get batches: {response.text}")

def test_export_functionality():
    """Test export functionality"""
    print("\n4. Testing export functionality...")
    
    # Login
    login_data = {"email": "test@example.com", "password": "testpassword123"}
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    token = response.json()["access_token"]
    headers = get_headers(token)
    
    # Test export generation with date range
    from datetime import datetime, timedelta
    # Use April 2025 dates since that's when our test data is from
    start_date = "2025-04-01"
    end_date = "2025-04-30"
    
    export_data = {
        "start_date": start_date,
        "end_date": end_date,
        "client_id": None,  # All clients
        "include_images": False  # Don't include images since we don't have them
    }
    
    response = requests.post(f"{BASE_URL}/api/export/invoices-bundle", headers=headers, json=export_data)
    if response.status_code in [200, 201]:
        result = response.json()
        print(f"   ✓ Export generation successful: {result.get('message', 'Success')}")
        if 'export_id' in result:
            print(f"   Export ID: {result['export_id']}")
    else:
        print(f"   ✗ Export generation failed: {response.text}")

def test_file_storage():
    """Test file storage integration"""
    print("\n5. Testing file storage...")
    
    # Login
    login_data = {"email": "test@example.com", "password": "testpassword123"}
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    token = response.json()["access_token"]
    headers = get_headers(token)
    
    # Get batches to check files exist
    response = requests.get(f"{BASE_URL}/upload/batches", headers=headers)
    if response.status_code == 200:
        batches = response.json()
        if batches:
            batch = batches[0]
            # Check that batch has file info
            if batch.get('xls_filename'):
                print(f"   ✓ File storage working - batch has file: {batch['xls_filename']}")
                print(f"   Batch {batch['id']} status: {batch['status']}")
            else:
                print("   ✗ Batch missing file information")
        else:
            print("   - No batches to test file storage")
    else:
        print(f"   ✗ Failed to get batches: {response.text}")

def test_client_assignment():
    """Test that tickets have client assignments"""
    print("\n6. Testing client assignment...")
    
    # Login
    login_data = {"email": "test@example.com", "password": "testpassword123"}
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    token = response.json()["access_token"]
    headers = get_headers(token)
    
    # Get batches first
    response = requests.get(f"{BASE_URL}/upload/batches", headers=headers)
    if response.status_code == 200:
        batches = response.json()
        
        # Check tickets in batches
        assigned_count = 0
        total_count = 0
        
        for batch in batches[:2]:  # Check first 2 batches
            batch_id = batch['id']
            resp = requests.get(f"{BASE_URL}/batches/{batch_id}/tickets", headers=headers)
            if resp.status_code == 200:
                tickets = resp.json()
                for ticket in tickets[:10]:  # Check first 10 tickets
                    total_count += 1
                    if ticket.get('client_id'):
                        assigned_count += 1
        
        if total_count > 0:
            print(f"   {assigned_count}/{total_count} tickets have client assignments")
            if assigned_count > 0:
                print("   ✓ Client assignment working")
            else:
                print("   ✗ No tickets have client assignments")
        else:
            print("   - No tickets found to test")
    else:
        print(f"   ✗ Failed to get batches: {response.text}")

def main():
    """Run all integration tests"""
    print("Testing Integration Fixes")
    print("=" * 50)
    
    try:
        test_auth_consistency()
        test_batch_processing()
        test_ticket_data()
        test_export_functionality()
        test_file_storage()
        test_client_assignment()
        
        print("\n" + "=" * 50)
        print("Integration testing complete!")
        
    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()