#!/usr/bin/env python3
"""
Test file download endpoints
"""

import requests

BASE_URL = "http://localhost:8000"

def test_downloads():
    """Test file download functionality"""
    
    # Login
    login_data = {"email": "test@example.com", "password": "testpassword123"}
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    
    if response.status_code != 200:
        print(f"Login failed: {response.text}")
        return
        
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get a specific batch that has files
    batch_ids_with_files = [
        "2d818905-3d6d-4f13-83a4-6b601aad5fda",  # APRIL_15_2025
        "8743c8ef-49af-400e-8668-9d7c596fe222"   # APRIL_14_2025
    ]
    
    for batch_id in batch_ids_with_files:
        response = requests.get(f"{BASE_URL}/upload/batches", headers=headers)
        if response.status_code == 200:
            batches = response.json()
            batch = next((b for b in batches if b['id'] == batch_id), None)
            if batch:
                print(f"\nTesting downloads for batch {batch_id} - {batch['xls_filename']}")
                break
        else:
            print(f"Failed to get batches: {response.text}")
            return
    
    if not batch:
        print("No batch found with files")
        return
    
    # Test XLS download
    print("\nTesting XLS download...")
    response = requests.get(
        f"{BASE_URL}/download/batch/{batch_id}/xls",
        headers=headers,
        stream=True
    )
    if response.status_code == 200:
        print(f"✅ XLS download successful")
        print(f"   Content-Type: {response.headers.get('content-type')}")
        print(f"   Size: {len(response.content)} bytes")
    else:
        print(f"❌ XLS download failed: {response.status_code} - {response.text}")
    
    # Test PDF download
    print("\nTesting PDF download...")
    response = requests.get(
        f"{BASE_URL}/download/batch/{batch_id}/pdf",
        headers=headers,
        stream=True
    )
    if response.status_code == 200:
        print(f"✅ PDF download successful")
        print(f"   Content-Type: {response.headers.get('content-type')}")
        print(f"   Size: {len(response.content)} bytes")
    else:
        print(f"❌ PDF download failed: {response.status_code} - {response.text}")

if __name__ == "__main__":
    test_downloads()