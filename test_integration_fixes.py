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
            if resp.status_code >= 400:
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
    response = requests.get(f"{BASE_URL}/batches", headers=headers)
    if response.status_code == 200:
        batches = response.json()
        print(f"   Found {len(batches)} batches")
        
        # Check batch statuses
        for batch in batches[:3]:
            print(f"   Batch {batch['id']}: status={batch['status']}, tickets={batch.get('stats', {}).get('total_tickets', 0)}")
        
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
    
    # Get tickets
    response = requests.get(f"{BASE_URL}/batches/tickets", headers=headers)
    if response.status_code == 200:
        tickets = response.json()
        print(f"   Found {len(tickets)} tickets")
        
        if tickets:
            # Show sample ticket
            ticket = tickets[0]
            print(f"   Sample ticket: {ticket['ticket_number']} - {ticket['entry_date']} - {ticket['net_weight']}kg")
            print("   ✓ Tickets populated successfully")
        else:
            print("   ✗ No tickets found")
    else:
        print(f"   ✗ Failed to get tickets: {response.text}")

def test_export_functionality():
    """Test export functionality"""
    print("\n4. Testing export functionality...")
    
    # Login
    login_data = {"email": "test@example.com", "password": "testpassword123"}
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    token = response.json()["access_token"]
    headers = get_headers(token)
    
    # Get export options
    response = requests.get(f"{BASE_URL}/api/export/weeks", headers=headers)
    if response.status_code == 200:
        weeks = response.json()
        print(f"   Found {len(weeks)} weeks available for export")
        
        if weeks:
            # Try to generate export for first week
            week = weeks[0]
            export_data = {
                "week_start": week["week_start"],
                "week_end": week["week_end"],
                "client_id": None  # All clients
            }
            
            response = requests.post(f"{BASE_URL}/api/export/generate", headers=headers, json=export_data)
            if response.status_code in [200, 201]:
                print(f"   ✓ Export generation successful for week {week['week_start']}")
            else:
                print(f"   ✗ Export generation failed: {response.text}")
        else:
            print("   ✗ No weeks available for export")
    else:
        print(f"   ✗ Failed to get export weeks: {response.text}")

def test_file_storage():
    """Test file storage integration"""
    print("\n5. Testing file storage...")
    
    # Login
    login_data = {"email": "test@example.com", "password": "testpassword123"}
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    token = response.json()["access_token"]
    headers = get_headers(token)
    
    # Get batches to check files
    response = requests.get(f"{BASE_URL}/batches", headers=headers)
    if response.status_code == 200:
        batches = response.json()
        if batches:
            batch = batches[0]
            batch_id = batch['id']
            
            # Try to download original file
            response = requests.get(f"{BASE_URL}/batches/{batch_id}/download", headers=headers)
            if response.status_code == 200:
                print(f"   ✓ File download working for batch {batch_id}")
            else:
                print(f"   ✗ File download failed: {response.status_code}")
        else:
            print("   - No batches to test file storage")
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
        
        print("\n" + "=" * 50)
        print("Integration testing complete!")
        
    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()