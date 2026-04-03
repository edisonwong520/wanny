import pytest
import json
from accounts.models import Account
from django.urls import reverse

@pytest.mark.django_db
def test_user_registration_success(client):
    """
    测试正常注册流程
    """
    url = reverse('register_user')
    data = {
        "email": "pytest_user@example.com",
        "name": "Pytest User",
        "password": "test_password_123"
    }
    response = client.post(
        url,
        data=json.dumps(data),
        content_type='application/json'
    )
    
    assert response.status_code == 201
    assert response.json()["status"] == "success"
    assert Account.objects.filter(email="pytest_user@example.com").exists()

@pytest.mark.django_db
def test_user_registration_duplicate_email(client):
    """
    测试重复邮箱注册应失败
    """
    # 先创建一个
    Account.objects.create(
        email="duplicate@example.com",
        name="Original",
        password="password"
    )
    
    url = reverse('register_user')
    data = {
        "email": "duplicate@example.com",
        "name": "Newbie",
        "password": "new_password"
    }
    response = client.post(
        url,
        data=json.dumps(data),
        content_type='application/json'
    )
    
    assert response.status_code == 400
    assert response.json()["error_code"] == "duplicate_email"
    assert "已被注册" in response.json()["error"]


@pytest.mark.django_db
def test_user_registration_duplicate_name(client):
    """
    测试重复昵称注册应失败
    """
    Account.objects.create(
        email="original@example.com",
        name="Jarvis",
        password="password"
    )

    url = reverse('register_user')
    data = {
        "email": "new@example.com",
        "name": "Jarvis",
        "password": "new_password"
    }
    response = client.post(
        url,
        data=json.dumps(data),
        content_type='application/json'
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "duplicate_name"
    assert "昵称" in response.json()["error"]

@pytest.mark.django_db
def test_user_registration_invalid_email(client):
    """
    测试非法邮箱格式
    """
    url = reverse('register_user')
    data = {
        "email": "not-an-email",
        "name": "Bad User",
        "password": "password"
    }
    response = client.post(
        url,
        data=json.dumps(data),
        content_type='application/json'
    )
    
    assert response.status_code == 400
    assert "不合法" in response.json()["error"]

@pytest.mark.django_db
def test_user_login_success(client):
    """
    测试登录成功逻辑
    """
    from django.contrib.auth.hashers import make_password
    Account.objects.create(
        email="login@example.com",
        name="Login User",
        password=make_password("secure_123")
    )
    
    url = reverse('login_user')
    response = client.post(
        url,
        data=json.dumps({"email": "login@example.com", "password": "secure_123"}),
        content_type='application/json'
    )
    
    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Login User"

@pytest.mark.django_db
def test_user_login_failure(client):
    """
    测试登录失败 (密码错误)
    """
    from django.contrib.auth.hashers import make_password
    Account.objects.create(
        email="failure@example.com",
        name="Fail User",
        password=make_password("right_password")
    )
    
    url = reverse('login_user')
    response = client.post(
        url,
        data=json.dumps({"email": "failure@example.com", "password": "wrong_password"}),
        content_type='application/json'
    )
    
    assert response.status_code == 401
    assert "错误" in response.json()["error"]

@pytest.mark.django_db
def test_user_login_by_nickname(client):
    """
    测试通过昵称（name 字段）登录
    """
    from django.contrib.auth.hashers import make_password
    Account.objects.create(
        email="nick@example.com",
        name="Jarvis",
        password=make_password("ironman")
    )
    
    url = reverse('login_user')
    response = client.post(
        url,
        # 使用 identifier 字段发送昵称
        data=json.dumps({"identifier": "Jarvis", "password": "ironman"}),
        content_type='application/json'
    )
    
    assert response.status_code == 200
    assert response.json()["data"]["email"] == "nick@example.com"
