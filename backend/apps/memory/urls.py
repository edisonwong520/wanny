from django.urls import path

from . import views

app_name = "memory"

urlpatterns = [
    path("profiles/", views.handle_profiles, name="profiles"),
]
