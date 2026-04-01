from django.urls import path

from .views import handle_device_control, handle_device_dashboard, handle_device_dashboard_refresh

app_name = "devices"

urlpatterns = [
    path("dashboard/", handle_device_dashboard, name="dashboard"),
    path("dashboard/refresh/", handle_device_dashboard_refresh, name="dashboard_refresh"),
    path("<path:device_id>/controls/<path:control_id>/", handle_device_control, name="device_control"),
]
