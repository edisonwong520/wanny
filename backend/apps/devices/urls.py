from django.urls import path

from .views import (
    handle_device_control,
    handle_device_dashboard,
    handle_device_dashboard_refresh,
    handle_device_detail,
    handle_device_list,
)

app_name = "devices"

urlpatterns = [
    path("dashboard/", handle_device_dashboard, name="dashboard"),
    path("dashboard/refresh/", handle_device_dashboard_refresh, name="dashboard_refresh"),
    path("list/", handle_device_list, name="device_list"),
    path("<path:device_id>/controls/<path:control_id>/", handle_device_control, name="device_control"),
    path("<path:device_id>/", handle_device_detail, name="device_detail"),
]
