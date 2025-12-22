import requests
import json

def test_login_json():
    """Test login with JSON payload"""
    url = "http://127.0.0.1:8000/api/auth/login"
    
    # Test with valid credentials (using the user we created earlier)
    print("Testing login with JSON payload...")
    payload = {
        "username": "newuser123",
        "password": "securepassword123"
    }
    
    try:
        response = requests.post(url, json=payload)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"SUCCESS: Received access token")
            print(f"Token Type: {data.get('token_type')}")
            print(f"Access Token: {data.get('access_token')[:50]}...")
        else:
            print(f"FAILURE: {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    
    # Test with invalid credentials
    print("\nTesting with invalid credentials...")
    invalid_payload = {
        "username": "wronguser",
        "password": "wrongpassword"
    }
    
    try:
        response = requests.post(url, json=invalid_payload)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 401:
            print(f"SUCCESS: Correctly rejected invalid credentials")
        else:
            print(f"FAILURE: Expected 401, got {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_login_json()

