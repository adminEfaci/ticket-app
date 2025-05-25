#!/usr/bin/env python3
"""
Debug export issues
"""

import requests
import json
from datetime import date

BASE_URL = "http://localhost:8000"

def test_export():
    """Test export with various configurations"""
    
    # Login
    login_data = {"email": "test@example.com", "password": "testpassword123"}
    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    
    if response.status_code != 200:
        print(f"Login failed: {response.text}")
        return
        
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # First, check if we have tickets
    response = requests.get(f"{BASE_URL}/upload/batches", headers=headers)
    if response.status_code == 200:
        batches = response.json()
        total_tickets = 0
        for batch in batches:
            resp = requests.get(f"{BASE_URL}/batches/{batch['id']}/tickets", headers=headers)
            if resp.status_code == 200:
                tickets = resp.json()
                total_tickets += len(tickets)
                if tickets:
                    print(f"Batch {batch['xls_filename']}: {len(tickets)} tickets")
                    print(f"  Sample ticket: {tickets[0]['ticket_number']} - {tickets[0]['entry_date']}")
        
        print(f"\nTotal tickets in system: {total_tickets}")
    
    # Try different export configurations
    test_cases = [
        {
            "name": "Export without images, specific date range",
            "data": {
                "start_date": "2025-04-14",
                "end_date": "2025-04-15",
                "client_id": None,
                "include_images": False
            }
        },
        {
            "name": "Export with force flag",
            "data": {
                "start_date": "2025-04-01",
                "end_date": "2025-04-30",
                "client_id": None,
                "include_images": False,
                "force_export": True
            }
        }
    ]
    
    for test in test_cases:
        print(f"\n{test['name']}:")
        print(f"Request: {json.dumps(test['data'], indent=2)}")
        
        response = requests.post(
            f"{BASE_URL}/api/export/invoices-bundle",
            headers=headers,
            json=test['data']
        )
        
        print(f"Response status: {response.status_code}")
        if response.status_code in [200, 201]:
            result = response.json()
            print(f"Success: {json.dumps(result, indent=2)}")
        else:
            print(f"Failed: {response.text}")

if __name__ == "__main__":
    test_export()