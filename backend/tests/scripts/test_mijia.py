import time
from mijiaAPI import mijiaAPI

def test_mijia_connection():
    print("Initializing Mijia API...")
    # auth.json will be saved in ~/.config/mijia-api/auth.json by default
    api = mijiaAPI()
    
    print("Attempting to login. If you haven't logged in before, this will generate a QR code.")
    print("Please scan the QR code using the Mi Home (米家) APP.")
    try:
        api.login()
        print("\nLogin successful!")
    except Exception as e:
        print(f"\nLogin failed: {e}")
        return

    print("\nFetching home list...")
    try:
        homes = api.get_homes_list()
        print(f"Found {len(homes)} homes.")
        for i, home in enumerate(homes):
            print(f"  {i+1}. {home.get('name', 'Unknown')} (ID: {home.get('id')})")
    except Exception as e:
        print(f"Failed to get homes: {e}")

    print("\nFetching device list...")
    try:
        devices = api.get_devices_list()
        print(f"Found {len(devices)} devices (excluding shared).")
        for i, device in enumerate(devices[:10]):  # Show up to 10 devices
            print(f"  {i+1}. {device.get('name')} (Model: {device.get('model')}, DID: {device.get('did')})")
        if len(devices) > 10:
            print(f"  ... and {len(devices) - 10} more.")
            
    except Exception as e:
        print(f"Failed to get devices: {e}")

if __name__ == "__main__":
    test_mijia_connection()
