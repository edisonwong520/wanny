from django.urls import path
from .views import (
    handle_platform_auth,
    handle_platform_auth_authorize,
    handle_platform_auth_detail,
    handle_platform_auth_login,
)

app_name = "providers"

urlpatterns = [
    path('auth/', handle_platform_auth, name='platform_auth_upsert'),
    path('auth/<str:platform_name>/authorize/', handle_platform_auth_authorize, name='platform_auth_authorize'),
    path('auth/<str:platform_name>/login/', handle_platform_auth_login, name='platform_auth_login'),
    path('auth/<str:platform_name>/', handle_platform_auth_detail, name='platform_auth_detail'),
]
