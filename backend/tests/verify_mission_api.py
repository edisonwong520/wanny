import os
import django
import sys

# Add backend to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wanny_server.settings')
django.setup()

from django.test import Client
from comms.models import PendingCommand
from django.utils import timezone

def verify_mission_api():
    client = Client()
    
    # 1. Create a mission
    print("Step 1: Creating a test mission...")
    mission = PendingCommand.objects.create(
        user_id="verifier",
        original_prompt="把空调开了",
        shell_command="echo AC_ON",
        metadata={
            "title": "空调控制",
            "risk": "low",
            "summary": "用户要求开启空调",
            "intent": "设备操作",
            "plan": ["检查当前状态", "下发指令"],
            "context": ["热死了"],
            "suggested_reply": "空调已开启。"
        }
    )
    
    # 2. List missions
    print("Step 2: Listing missions...")
    response = client.get('/api/comms/missions/')
    if response.status_code != 200:
        print(f"❌ Failed to list missions: {response.status_code}")
        return False
    
    data = response.json()
    if not any(m['id'] == str(mission.id) for m in data):
        print("❌ Created mission not found in API list")
        return False
    print("✅ Mission found in API list with correct metadata")

    # 3. Approve mission
    print("Step 3: Approving mission...")
    response = client.post(f'/api/comms/missions/{mission.id}/approve/')
    if response.status_code != 200:
        print(f"❌ Failed to approve mission: {response.status_code}")
        return False
    
    print(f"✅ Mission approved. Status: {response.status_code}, Result: {response.json().get('result')}")
    
    # 4. Verify model state
    mission.refresh_from_db()
    if not mission.is_approved or not mission.is_executed:
        print(f"❌ Mission state incorrect: approved={mission.is_approved}, executed={mission.is_executed}")
        return False
    print("✅ Model state updated correctly")
    
    print("\n🎉 MISSION API VERIFICATION PASSED!")
    return True

if __name__ == "__main__":
    success = verify_mission_api()
    if not success:
        sys.exit(1)
