#!/usr/bin/env python3
"""Test complete system integration - Frontend and Backend"""

import requests
import json
import sys

def test_system():
    print("=== COMPLETE SYSTEM TEST ===\n")
    
    # Test backend
    print("1. Testing Backend API...")
    try:
        # Login
        login_response = requests.post(
            "http://localhost:8000/auth/login",
            json={"email": "admin@example.com", "password": "admin123456"}
        )
        if login_response.status_code == 200:
            print("   ✓ Backend authentication works")
            token = login_response.json()["access_token"]
            
            # Test authenticated endpoint
            headers = {"Authorization": f"Bearer {token}"}
            
            # Get user info
            user_response = requests.get("http://localhost:8000/auth/me", headers=headers)
            if user_response.status_code == 200:
                print("   ✓ Can retrieve user information")
            
            # Get clients
            clients_response = requests.get("http://localhost:8000/api/clients/?limit=5", headers=headers)
            if clients_response.status_code == 200:
                clients = clients_response.json()
                client_count = len(clients)
                print(f"   ✓ Can retrieve clients (found {client_count} clients)")
                if client_count > 0:
                    print(f"   ✓ Sample client: {clients[0]['name']}")
        else:
            print(f"   ✗ Backend authentication failed: {login_response.status_code}")
            
    except Exception as e:
        print(f"   ✗ Backend test failed: {e}")
    
    # Test frontend
    print("\n2. Testing Frontend...")
    try:
        # Check main page
        main_response = requests.get("http://localhost:3000")
        if main_response.status_code == 200:
            print("   ✓ Frontend is accessible")
        
        # Check login page
        login_page = requests.get("http://localhost:3000/login")
        if login_page.status_code == 200 and "Email" in login_page.text:
            print("   ✓ Login page shows Email field (not Username)")
        
        # Check if it's our custom app (not default Next.js)
        if "Get started by editing" not in main_response.text:
            print("   ✓ Custom application is served (not default Next.js)")
        else:
            print("   ✗ Still showing default Next.js page!")
            
    except Exception as e:
        print(f"   ✗ Frontend test failed: {e}")
    
    print("\n3. System URLs:")
    print("   - Frontend: http://localhost:3000")
    print("   - Backend API: http://localhost:8000") 
    print("   - API Docs: http://localhost:8000/docs")
    print("\n4. Login Credentials:")
    print("   - Email: admin@example.com")
    print("   - Password: admin123456")
    
    print("\n=== TEST COMPLETE ===")

if __name__ == "__main__":
    test_system()