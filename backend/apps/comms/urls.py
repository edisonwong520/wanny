from django.urls import path
from comms.views import handle_missions, handle_mission_approve, handle_mission_reject

app_name = 'comms'

urlpatterns = [
    path('missions/', handle_missions, name='mission-list'),
    path('missions/<int:pk>/approve/', handle_mission_approve, name='mission-approve'),
    path('missions/<int:pk>/reject/', handle_mission_reject, name='mission-reject'),
]
