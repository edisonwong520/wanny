import os
import django
import sys
import json
from django.test import Client

# Add backend to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wanny_server.settings')
django.setup()

def verify_registration_api():
    client = Client()
    test_email = f"test_user_pw_{int(django.utils.timezone.now().timestamp())}@example.com"
    test_name = "Test PW Walker"
    test_password = "secure_password_123"

    print(f"Step 1: Attempting to register user with email: {test_email}...")
    
    # 1. Successful registration
    response = client.post(
        '/api/accounts/register/', 
        data=json.dumps({"email": test_email, "name": test_name, "password": test_password}),
        content_type='application/json'
    )
    
    if response.status_code != 201:
        print(f"❌ Failed to register user: {response.status_code}")
        print(response.json())
        return False
    
    data = response.json()
    print(f"✅ User registered with hashed password. ID: {data['data']['id']}")

    # 2. Too short password
    print("Step 2: Testing short password rejection...")
    response = client.post(
        '/api/accounts/register/', 
        data=json.dumps({"email": "short@example.com", "name": "Short", "password": "123"}),
        content_type='application/json'
    )
    if response.status_code == 400 and "少于 6 位" in response.json().get("error", ""):
        print("✅ Short password correctly rejected.")
    else:
        print(f"❌ Short password logic failed. Status: {response.status_code}")
        return False

    # 3. Invalid email format
    print("Step 3: Testing invalid email format...")
    response = client.post(
        '/api/accounts/register/', 
        data=json.dumps({"email": "invalid-email", "name": "Name"}),
        content_type='application/json'
    )
    if response.status_code == 400 and "格式不合法" in response.json().get("error", ""):
        print("✅ Invalid email format correctly rejected.")
    else:
        print(f"❌ Invalid email format logic failed. Status: {response.status_code}")
        return False

    print("\n🎉 REGISTRATION API VERIFICATION PASSED!")
    return True

if __name__ == "__main__":
    success = verify_registration_api()
    if not success:
        sys.exit(1)
