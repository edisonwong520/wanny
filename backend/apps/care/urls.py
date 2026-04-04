from django.urls import path

from care.views import (
    handle_data_sources,
    handle_data_source_detail,
    handle_geocode,
    handle_rule_detail,
    handle_rules,
    handle_run_inspection,
    handle_suggestion_confirm_detail,
    handle_suggestion_execute,
    handle_suggestion_feedback,
    handle_suggestions,
    handle_weather_current,
    handle_weather_refresh,
)

app_name = "care"

urlpatterns = [
    path("suggestions/", handle_suggestions, name="suggestions"),
    path("suggestions/<int:pk>/feedback/", handle_suggestion_feedback, name="suggestion_feedback"),
    path("suggestions/<int:pk>/confirm-detail/", handle_suggestion_confirm_detail, name="suggestion_confirm_detail"),
    path("suggestions/<int:pk>/execute/", handle_suggestion_execute, name="suggestion_execute"),
    path("rules/", handle_rules, name="rules"),
    path("rules/<int:pk>/", handle_rule_detail, name="rule_detail"),
    path("data-sources/", handle_data_sources, name="data_sources"),
    path("data-sources/<int:pk>/", handle_data_source_detail, name="data_source_detail"),
    path("geocode/", handle_geocode, name="geocode"),
    path("weather/current/", handle_weather_current, name="weather_current"),
    path("weather/refresh/", handle_weather_refresh, name="weather_refresh"),
    path("run-inspection/", handle_run_inspection, name="run_inspection"),
]
