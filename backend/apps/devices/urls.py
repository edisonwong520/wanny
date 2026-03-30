from django.urls import path

from .views import handle_device_dashboard, handle_device_dashboard_refresh

app_name = "devices"

urlpatterns = [
    path("dashboard/", handle_device_dashboard, name="dashboard"),
    path("dashboard/refresh/", handle_device_dashboard_refresh, name="dashboard_refresh"),
]
