import pytest
import json
import asyncio
from uuid import uuid4
from asgiref.sync import sync_to_async
from django.urls import reverse
from accounts.models import Account
from accounts.test_utils import auth_headers
from comms.models import Mission
from devices.models import DeviceSnapshot, DeviceRoom, DeviceDashboardState

@pytest.mark.django_db
def test_multi_tenancy_isolation(client):
    """
    测试多租户数据隔离：
    1. 创建用户 A 和 用户 B
    2. 用户 A 创建一条任务
    3. 用户 B 无法通过 API 看到用户 A 的任务
    4. 用户 B 无法通过 API 看到用户 A 的设备
    """
    # 1. 准备用户数据
    user_a = Account.objects.create(email="user_a@example.com", name="User A", password="pwd")
    user_b = Account.objects.create(email="user_b@example.com", name="User B", password="pwd")
    
    # 模拟 user_a 已经有过至少一次成功的刷新，否则 get_dashboard 会返回空演示状态
    from django.utils import timezone
    DeviceDashboardState.objects.create(account=user_a, key="default", refreshed_at=timezone.now())
    
    # 2. 用户 A 创建任务和设备
    Mission.objects.create(
        account=user_a,
        user_id="openid_a",
        original_prompt="User A's Task",
        status=Mission.StatusChoices.PENDING
    )
    
    room_a = DeviceRoom.objects.create(account=user_a, slug="living_a", name="Room A")
    DeviceSnapshot.objects.create(
        account=user_a,
        external_id="dev_a",
        room=room_a,
        name="Device A",
        category="light"
    )
    
    # 3. 验证用户 B 视角 (任务)
    url_missions = reverse('comms:mission-list')
    response_b_missions = client.get(
        url_missions,
        **auth_headers(user_b),
    )
    assert response_b_missions.status_code == 200
    assert len(response_b_missions.json()) == 0
    
    # 用户 A 应该能看到自己的
    response_a_missions = client.get(
        url_missions,
        **auth_headers(user_a),
    )
    assert response_a_missions.status_code == 200
    assert len(response_a_missions.json()) == 1
    assert response_a_missions.json()[0]["summary"] == "User A's Task"
    
    # 4. 验证用户 B 视角 (设备)
    url_dashboard = reverse('devices:dashboard')
    response_b_devices = client.get(
        url_dashboard,
        **auth_headers(user_b),
    )
    assert response_b_devices.status_code == 200
    snapshot_b = response_b_devices.json()["snapshot"]
    assert len(snapshot_b["devices"]) == 0
    assert len(snapshot_b["rooms"]) == 0
    
    # 用户 A 应该能看到自己的
    response_a_devices = client.get(
        url_dashboard,
        **auth_headers(user_a),
    )
    assert response_a_devices.status_code == 200
    snapshot_a = response_a_devices.json()["snapshot"]
    # 注意：DeviceDashboardService 在没有快照时可能会返回演示数据，但我们在测试中手动创建了记录
    # 且代码逻辑中如果是 filter(account=account) 应该只返回 A 的
    assert len(snapshot_a["devices"]) == 1
    assert snapshot_a["devices"][0]["name"] == "Device A"

@pytest.mark.django_db
@pytest.mark.asyncio
async def test_memory_and_profile_isolation():
    """
    测试 AI 记忆和画像在服务层的隔离性。
    1. 为用户 A 和 用户 B 记录记忆
    2. 验证用户 A 搜不到用户 B 的记忆
    3. 验证画像列表过滤
    """
    import shutil
    import tempfile
    import os
    from memory.services import MemoryService
    from memory.models import UserProfile
    from memory.vector_store import VectorStore

    # 创建临时 ChromaDB 目录
    test_chroma_path = tempfile.mkdtemp()
    os.environ["CHROMA_PERSIST_DIR"] = test_chroma_path
    VectorStore._instance = None # 强制重新初始化

    try:
        unique_suffix = uuid4().hex

        # 1. 准备账户
        user_a = await sync_to_async(Account.objects.create)(
            email=f"mem_a_{unique_suffix}@example.com",
            name=f"Mem A {unique_suffix}",
        )
        user_b = await sync_to_async(Account.objects.create)(
            email=f"mem_b_{unique_suffix}@example.com",
            name=f"Mem B {unique_suffix}",
        )

        # 2. 注入记忆 (VectorStore)
        await MemoryService.record_conversation(user_a, "user", "My secret code is 1234")
        await MemoryService.record_conversation(user_b, "user", "My secret code is 5678")
        
        # 3. 检索 A 的记忆，不应包含 B 的内容
        context_a = await MemoryService.get_context_for_chat(user_a, "code")
        assert "1234" in context_a
        assert "5678" not in context_a

        # 4. 检索 B 的记忆，不应包含 A 的内容
        context_b = await MemoryService.get_context_for_chat(user_b, "code")
        assert "5678" in context_b
        assert "1234" not in context_b

        # 5. 画像隔离 (Database)
        await sync_to_async(UserProfile.objects.create)(
            account=user_a, key="test_key", value="Value A", category="Other"
        )
        await sync_to_async(UserProfile.objects.create)(
            account=user_b, key="test_key", value="Value B", category="Other"
        )

        profiles_a = await MemoryService.list_profiles(user_a)
        assert len(profiles_a) == 1
        assert profiles_a[0]["value"] == "Value A"

        profiles_b = await MemoryService.list_profiles(user_b)
        assert len(profiles_b) == 1
        assert profiles_b[0]["value"] == "Value B"
    finally:
        # 清理临时目录
        if os.path.exists(test_chroma_path):
            shutil.rmtree(test_chroma_path)
        VectorStore._instance = None

@pytest.mark.django_db
def test_unauthorized_access(client):
    """
    测试未提供身份头时的访问限制
    """
    url = reverse('comms:mission-list')
    response = client.get(url)
    # 中间件对于未提供 email 的请求目前返回 None，由视图处理 401
    assert response.status_code == 401
    assert "Unauthorized" in response.json()["error"]
