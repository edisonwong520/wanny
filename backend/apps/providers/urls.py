from django.urls import path
from .views import handle_platform_auth

app_name = "providers"

urlpatterns = [
    path('auth/', handle_platform_auth, name='platform_auth_upsert'),
]
