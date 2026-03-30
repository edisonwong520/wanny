from django.urls import path
from .views import handle_platform_auth, handle_platform_auth_detail

app_name = "providers"

urlpatterns = [
    path('auth/', handle_platform_auth, name='platform_auth_upsert'),
    path('auth/<str:platform_name>/', handle_platform_auth_detail, name='platform_auth_detail'),
]
