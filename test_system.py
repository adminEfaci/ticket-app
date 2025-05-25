#!/usr/bin/env python
"""Test script to verify the system is working correctly"""
import requests
import json
import sys

BASE_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"

def test_frontend():
    """Test frontend is accessible"""
    print("1. Testing Frontend...")
    try:
        response = requests.get(FRONTEND_URL, timeout=5)
        if response.status_code == 200:
            print("✅ Frontend is accessible at http://localhost:3000")
            return True
        else:
            print(f"❌ Frontend returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Frontend error: {e}")
        return False

def test_backend():
    """Test backend API is accessible"""
    print("\n2. Testing Backend API...")
    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=5)
        if response.status_code == 200:
            print("✅ Backend API is accessible at http://localhost:8000")
            print("✅ API Documentation available at http://localhost:8000/docs")
            return True
        else:
            print(f"❌ Backend returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Backend error: {e}")
        return False

def test_login():
    """Test admin login"""
    print("\n3. Testing Admin Login...")
    try:
        # Use JSON data for login
        data = {
            "email": "admin@example.com",
            "password": "admin123456"
        }
        response = requests.post(
            f"{BASE_URL}/auth/login", 
            json=data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            if "access_token" in result:
                print("✅ Admin login successful!")
                print(f"   Email: admin@example.com")
                print(f"   Password: admin123456")
                return result["access_token"]
            else:
                print("❌ Login response missing access token")
                return None
        else:
            print(f"❌ Login failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Login error: {e}")
        return None

def test_authenticated_request(token):
    """Test authenticated API request"""
    print("\n4. Testing Authenticated API Access...")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
        
        if response.status_code == 200:
            user = response.json()
            print("✅ Authenticated API access working!")
            print(f"   User: {user.get('first_name', '')} {user.get('last_name', '')}")
            print(f"   Role: {user.get('role', 'N/A')}")
            return True
        else:
            print(f"❌ API request failed with status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API error: {e}")
        return False

def test_clients(token):
    """Test client data"""
    print("\n5. Testing Client Data...")
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/api/clients/", headers=headers)
        
        if response.status_code == 200:
            clients = response.json()
            print(f"✅ Found {len(clients)} clients in the system")
            if len(clients) > 0:
                print("   Sample clients:")
                for client in clients[:5]:
                    print(f"   - {client.get('name', 'Unknown')}")
            return True
        else:
            print(f"❌ Failed to fetch clients: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Client fetch error: {e}")
        return False

def main():
    print("=" * 60)
    print("TICKET MANAGEMENT SYSTEM - VERIFICATION TEST")
    print("=" * 60)
    
    all_tests_passed = True
    
    # Test frontend
    if not test_frontend():
        all_tests_passed = False
    
    # Test backend
    if not test_backend():
        all_tests_passed = False
        print("\n❌ Backend not accessible. Cannot continue tests.")
        return False
    
    # Test login
    token = test_login()
    if not token:
        all_tests_passed = False
        print("\n❌ Login failed. Cannot continue authenticated tests.")
    else:
        # Test authenticated requests
        if not test_authenticated_request(token):
            all_tests_passed = False
        
        # Test client data
        if not test_clients(token):
            all_tests_passed = False
    
    print("\n" + "=" * 60)
    if all_tests_passed:
        print("✅ ALL TESTS PASSED! System is ready for use.")
        print("\nYou can now:")
        print("1. Access the frontend at: http://localhost:3000")
        print("2. Login with: admin@example.com / admin123456")
        print("3. Upload XLS files from the samples folder")
        print("4. Manage clients and users in the admin panel")
    else:
        print("❌ Some tests failed. Please check the errors above.")
    print("=" * 60)
    
    return all_tests_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)