#!/usr/bin/env python3
"""
Run image extraction via API
"""

import requests
import json

BASE_URL = "http://localhost:8000"

def extract_images_for_batches():
    """Extract images from PDFs via API"""
    
    # Login
    login_data = {"email": "test@example.com", "password": "testpassword123"}
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    
    if response.status_code != 200:
        print(f"Login failed: {response.text}")
        return
        
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Batch IDs that have PDFs
    batch_ids = [
        "8743c8ef-49af-400e-8668-9d7c596fe222",  # APRIL_14_2025
        "2d818905-3d6d-4f13-83a4-6b601aad5fda"   # APRIL_15_2025
    ]
    
    for batch_id in batch_ids:
        print(f"\nExtracting images for batch {batch_id}...")
        
        # Call image extraction endpoint
        response = requests.post(
            f"{BASE_URL}/batches/{batch_id}/extract-images",
            headers=headers
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"Success: {result}")
        else:
            print(f"Failed: {response.status_code} - {response.text}")
    
    print("\nImage extraction complete!")

if __name__ == "__main__":
    extract_images_for_batches()