import os
import pytest
from django.conf import settings

@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """
    让所有测试默认具备数据库访问权限，遵循 TDD 快速试错原则。
    """
    pass

@pytest.fixture
def api_client():
    """
    标准的 Django REST framework 或 Django Test Client 封装。
    """
    from django.test import Client
    return Client()
